#!/usr/bin/env python3
"""Verify and render a deterministic timeline from a local Codex archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterator

from session_checkpoint import (
    SCHEMA_VERSION,
    archive_root,
    canonical_json_bytes,
    generation_seed,
    next_chain_hash,
    safe_session_component,
)


MAX_SUMMARY = 600


class AnalysisError(RuntimeError):
    pass


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while data := handle.read(1024 * 1024):
            digest.update(data)
    return digest.hexdigest()


def load_and_verify(session_dir: Path) -> tuple[dict[str, Any], list[str]]:
    manifest_path = session_dir / "manifest.json"
    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise AnalysisError(f"cannot read manifest: {exc}") from exc
    errors: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"unsupported manifest schema {manifest.get('schema_version')!r}")
    generations = manifest.get("generations")
    if not isinstance(generations, list) or not generations:
        errors.append("manifest has no transcript generations")
        return manifest, errors
    for generation in generations:
        chunks = generation.get("chunks", [])
        if not isinstance(chunks, list):
            errors.append(f"generation {generation.get('id')} chunks are not a list")
            continue
        expected_start = 0
        expected_chain = generation_seed(
            str(manifest.get("session_id")),
            generation.get("id"),
            generation.get("transcript_path"),
            generation.get("source"),
        )
        if chunks and chunks[0].get("previous_chain_sha256") != expected_chain:
            errors.append(
                f"generation {generation.get('id')}: initial chain seed does not match"
            )
        if not chunks and generation.get("archived_through") != 0:
            errors.append(f"generation {generation.get('id')} has no chunks")
        for chunk in chunks:
            label = chunk.get("path", "<missing>")
            chunk_path = session_dir / label
            if chunk.get("start") != expected_start:
                errors.append(f"{label}: expected byte start {expected_start}")
            if not chunk_path.is_file():
                errors.append(f"{label}: chunk is missing")
                expected_start = chunk.get("end", expected_start)
                continue
            actual_size = chunk_path.stat().st_size
            if actual_size != chunk.get("size") or actual_size != chunk.get("end") - chunk.get("start"):
                errors.append(f"{label}: size does not match manifest")
            actual_sha = file_sha256(chunk_path)
            if actual_sha != chunk.get("sha256"):
                errors.append(f"{label}: SHA-256 does not match manifest")
            previous = chunk.get("previous_chain_sha256")
            if expected_chain is None:
                expected_chain = previous
            if previous != expected_chain:
                errors.append(f"{label}: previous chain hash does not match")
            basis = {key: chunk.get(key) for key in ("path", "start", "end", "size", "sha256")}
            try:
                calculated_chain = next_chain_hash(previous, basis)
            except Exception as exc:
                errors.append(f"{label}: cannot calculate chain hash: {exc}")
                calculated_chain = None
            if calculated_chain != chunk.get("chain_sha256"):
                errors.append(f"{label}: chain hash does not match")
            expected_chain = chunk.get("chain_sha256")
            expected_start = chunk.get("end", expected_start)
        if expected_start != generation.get("archived_through"):
            errors.append(
                f"generation {generation.get('id')}: chunks end at {expected_start}, "
                f"manifest says {generation.get('archived_through')}"
            )
        if chunks and expected_chain != generation.get("chain_sha256"):
            errors.append(f"generation {generation.get('id')}: final chain hash differs")
    return manifest, errors


def iter_generation_lines(
    session_dir: Path, generation: dict[str, Any]
) -> Iterator[tuple[int, int, bytes]]:
    carry = b""
    carry_start = 0
    absolute = 0
    for chunk in generation.get("chunks", []):
        path = session_dir / chunk["path"]
        with path.open("rb") as handle:
            while data := handle.read(1024 * 1024):
                combined = carry + data
                base = carry_start if carry else absolute
                parts = combined.splitlines(keepends=True)
                carry = b""
                for index, part in enumerate(parts):
                    if not part.endswith((b"\n", b"\r")) and index == len(parts) - 1:
                        carry = part
                        carry_start = base
                    else:
                        end = base + len(part)
                        yield base, end, part
                        base = end
                absolute += len(data)
                if not carry:
                    carry_start = absolute
    if carry:
        yield carry_start, carry_start + len(carry), carry


def collect_text(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str):
        texts.append(value)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                for key in ("text", "input_text", "output_text", "content"):
                    if key in item:
                        texts.extend(collect_text(item[key]))
            elif isinstance(item, str):
                texts.append(item)
    elif isinstance(value, dict):
        for key in ("text", "message", "content", "summary", "output"):
            if key in value:
                texts.extend(collect_text(value[key]))
    return [text for text in texts if text]


def compact_text(text: str) -> str:
    text = " ".join(text.split())
    if len(text) > MAX_SUMMARY:
        return text[: MAX_SUMMARY - 20] + " … [see raw bytes]"
    return text


def describe_record(record: dict[str, Any]) -> tuple[str, str]:
    record_type = str(record.get("type", "unknown"))
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    payload_type = str(payload.get("type", ""))
    if record_type == "session_meta":
        return "session", compact_text(
            f"Session metadata: cwd={payload.get('cwd')}; source={payload.get('source')}; "
            f"CLI={payload.get('cli_version')}"
        )
    if record_type == "compacted":
        history = payload.get("replacement_history")
        count = len(history) if isinstance(history, list) else "unknown"
        return "compaction", f"Compacted record; replacement history items={count}"
    if record_type == "event_msg":
        texts = collect_text(payload.get("message"))
        if not texts:
            texts = collect_text(payload.get("content"))
        summary = " | ".join(texts) if texts else payload_type or "event"
        return f"event:{payload_type or 'unknown'}", compact_text(summary)
    if record_type == "response_item":
        role = payload.get("role")
        texts = collect_text(payload.get("content"))
        if payload_type in {"function_call", "custom_tool_call"}:
            name = payload.get("name") or payload.get("tool_name") or "tool"
            arguments = payload.get("arguments") or payload.get("input") or ""
            return "tool-call", compact_text(f"{name}: {arguments}")
        if payload_type in {"function_call_output", "custom_tool_call_output"}:
            output = payload.get("output") or payload.get("content") or ""
            return "tool-output", compact_text(" | ".join(collect_text(output)) or str(output))
        if payload_type == "reasoning":
            summary = " | ".join(collect_text(payload.get("summary")))
            return "reasoning-summary", compact_text(summary or "Opaque/encrypted reasoning item preserved")
        return f"message:{role or payload_type or 'unknown'}", compact_text(
            " | ".join(texts) or payload_type or "response item"
        )
    if record_type in {"turn_context", "world_state"}:
        return record_type, f"{record_type} metadata preserved"
    return record_type, compact_text(payload_type or "record preserved")


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def render_timeline(
    session_dir: Path,
    manifest: dict[str, Any],
    generation: dict[str, Any],
    verification_errors: list[str],
) -> str:
    lines = [
        f"# Codex session {manifest.get('session_id')}",
        f"Archive: `{session_dir}`",
        f"Generation: {generation.get('id')}",
        f"Archived bytes: {generation.get('archived_through')}",
        f"Source prefix SHA-256: `{generation.get('source_prefix_sha256')}`",
        f"Chunk-chain SHA-256: `{generation.get('chain_sha256')}`",
        f"Verification: {'FAILED' if verification_errors else 'passed'}",
    ]
    if verification_errors:
        lines.extend(["## Verification errors", *[f"- {error}" for error in verification_errors]])
    lines.extend(
        [
            "## Compaction checkpoints",
            "| ID | Time | Trigger | Turn | Generation | Byte boundary | Chain SHA-256 |",
            "|---:|---|---|---|---:|---:|---|",
        ]
    )
    for checkpoint in manifest.get("checkpoints", []):
        lines.append(
            "| {checkpoint_id} | {timestamp} | {trigger} | {turn_id} | {generation_id} | "
            "{archived_through} | `{chain_sha256}` |".format(
                **{
                    key: markdown_cell(checkpoint.get(key, ""))
                    for key in (
                        "checkpoint_id",
                        "timestamp",
                        "trigger",
                        "turn_id",
                        "generation_id",
                        "archived_through",
                        "chain_sha256",
                    )
                }
            )
        )
    lines.extend(
        [
            "## Evidence timeline",
            "Derived summaries may be truncated. The byte range points to the lossless raw archive.",
            "| Time | Byte range | Category | Summary |",
            "|---|---:|---|---|",
        ]
    )
    for start, end, raw in iter_generation_lines(session_dir, generation):
        try:
            record = json.loads(raw)
            if not isinstance(record, dict):
                raise ValueError("record is not an object")
            timestamp = record.get("timestamp", "")
            category, summary = describe_record(record)
        except (json.JSONDecodeError, ValueError) as exc:
            timestamp = ""
            category = "invalid-json"
            summary = f"Unparseable record preserved: {exc}"
        lines.append(
            f"| {markdown_cell(timestamp)} | {start}-{end} | {markdown_cell(category)} | "
            f"{markdown_cell(summary)} |"
        )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify and render a Codex compaction-checkpoint archive"
    )
    parser.add_argument("session_id", help="Codex session id")
    parser.add_argument("--generation", type=int, help="Generation id; defaults to latest")
    parser.add_argument("--output", type=Path, help="Write Markdown here instead of stdout")
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    session_dir = archive_root() / safe_session_component(args.session_id)
    try:
        manifest, errors = load_and_verify(session_dir)
        generations = manifest.get("generations", [])
        generation = next(
            (
                item
                for item in generations
                if args.generation is not None and item.get("id") == args.generation
            ),
            generations[-1] if args.generation is None and generations else None,
        )
        if generation is None:
            raise AnalysisError("requested generation does not exist")
        if args.verify_only:
            if errors:
                for error in errors:
                    print(error, file=sys.stderr)
            else:
                print(
                    f"verified session {args.session_id} generation {generation.get('id')}"
                )
            return 1 if errors else 0
        rendered = render_timeline(session_dir, manifest, generation, errors)
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
            os.chmod(args.output, 0o600)
        else:
            sys.stdout.write(rendered)
        return 1 if errors else 0
    except (AnalysisError, OSError, json.JSONDecodeError) as exc:
        print(f"session analysis failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
