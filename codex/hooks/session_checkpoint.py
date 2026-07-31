#!/usr/bin/env python3
"""Losslessly checkpoint local Codex transcripts at lifecycle boundaries.

The hook stores exact transcript bytes as immutable incremental chunks. The
manifest is an index over those chunks, not a second transcript. No transcript
content is written to stdout or stderr.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterator


SCHEMA_VERSION = 1
BLOCK_SIZE = 1024 * 1024
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
DEFAULT_ARCHIVE_ROOT = Path.home() / ".codex" / "compaction-checkpoints"
SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9._-]{1,200}$")


class CheckpointError(RuntimeError):
    """Raised when a checkpoint cannot be proven durable and complete."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def archive_root() -> Path:
    configured = os.environ.get("CODEX_COMPACTION_ARCHIVE_ROOT")
    return Path(configured).expanduser() if configured else DEFAULT_ARCHIVE_ROOT


def safe_session_component(session_id: str) -> str:
    if SAFE_SESSION_ID.fullmatch(session_id):
        return session_id
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]
    return f"session-{digest}"


def ensure_private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def fsync_dir(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def atomic_write_json(path: Path, value: Any) -> None:
    ensure_private_dir(path.parent)
    temp = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True).encode("utf-8"))
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
        os.chmod(path, 0o600)
        fsync_dir(path.parent)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temp.unlink()


def load_manifest(path: Path, session_id: str) -> dict[str, Any]:
    if not path.exists():
        now = utc_now()
        return {
            "schema_version": SCHEMA_VERSION,
            "session_id": session_id,
            "created_at": now,
            "updated_at": now,
            "generations": [],
            "checkpoints": [],
            "lifecycle": [],
        }
    try:
        with path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckpointError(f"cannot read existing manifest: {exc}") from exc
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise CheckpointError(
            f"unsupported manifest schema {manifest.get('schema_version')!r}"
        )
    if manifest.get("session_id") != session_id:
        raise CheckpointError("manifest session id does not match hook session id")
    for required in ("generations", "checkpoints", "lifecycle"):
        if not isinstance(manifest.get(required), list):
            raise CheckpointError(f"manifest field {required!r} is not a list")
    return manifest


@contextlib.contextmanager
def session_lock(session_dir: Path) -> Iterator[None]:
    ensure_private_dir(session_dir)
    lock_path = session_dir / ".lock"
    with lock_path.open("a+b") as handle:
        os.chmod(lock_path, 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def open_regular_file(path: Path) -> Iterator[tuple[BinaryIO, os.stat_result]]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise CheckpointError(f"cannot open transcript: {exc}") from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise CheckpointError("transcript path is not a regular file")
        with os.fdopen(fd, "rb", closefd=True) as handle:
            fd = -1
            yield handle, before
    finally:
        if fd >= 0:
            os.close(fd)


def scan_prefixes(
    handle: BinaryIO, snapshot_size: int, prior_end: int
) -> tuple[str, str]:
    if prior_end < 0 or prior_end > snapshot_size:
        raise CheckpointError("invalid prior transcript boundary")
    handle.seek(0)
    full_digest = hashlib.sha256()
    prior_digest = hashlib.sha256()
    position = 0
    while position < snapshot_size:
        data = handle.read(min(BLOCK_SIZE, snapshot_size - position))
        if not data:
            raise CheckpointError("transcript became shorter while hashing")
        if position < prior_end:
            prior_count = min(len(data), prior_end - position)
            prior_digest.update(data[:prior_count])
        full_digest.update(data)
        position += len(data)
    return prior_digest.hexdigest(), full_digest.hexdigest()


def generation_seed(
    session_id: str, generation_id: int, path: str, source: dict[str, int]
) -> str:
    return hashlib.sha256(
        canonical_json_bytes(
            {
                "domain": "codex-compaction-generation-v1",
                "session_id": session_id,
                "generation_id": generation_id,
                "transcript_path": path,
                "source": source,
            }
        )
    ).hexdigest()


def next_chain_hash(previous: str, chunk: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    try:
        digest.update(bytes.fromhex(previous))
    except ValueError as exc:
        raise CheckpointError("manifest contains an invalid chain hash") from exc
    digest.update(canonical_json_bytes(chunk))
    return digest.hexdigest()


def publish_chunk(
    handle: BinaryIO,
    chunks_dir: Path,
    generation_id: int,
    start: int,
    end: int,
) -> dict[str, Any] | None:
    if start == end:
        return None
    ensure_private_dir(chunks_dir)
    temp = chunks_dir / f".chunk.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    digest = hashlib.sha256()
    written = 0
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            handle.seek(start)
            remaining = end - start
            while remaining:
                data = handle.read(min(BLOCK_SIZE, remaining))
                if not data:
                    raise CheckpointError("transcript became shorter while copying")
                output.write(data)
                digest.update(data)
                written += len(data)
                remaining -= len(data)
            output.flush()
            os.fsync(output.fileno())
        if written != end - start:
            raise CheckpointError("checkpoint chunk length mismatch")
        chunk_sha = digest.hexdigest()
        name = (
            f"g{generation_id:04d}-{start:020d}-{end:020d}-{chunk_sha}.jsonl"
        )
        destination = chunks_dir / name
        os.chmod(temp, 0o600)
        os.replace(temp, destination)
        os.chmod(destination, 0o600)
        fsync_dir(chunks_dir)
        return {
            "path": f"chunks/{name}",
            "start": start,
            "end": end,
            "size": written,
            "sha256": chunk_sha,
        }
    finally:
        with contextlib.suppress(FileNotFoundError):
            temp.unlink()


def source_identity(path: Path, metadata: os.stat_result) -> dict[str, int]:
    return {
        "device": int(metadata.st_dev),
        "inode": int(metadata.st_ino),
    }


def metadata_stable(before: os.stat_result, after: os.stat_result) -> bool:
    return (
        before.st_dev == after.st_dev
        and before.st_ino == after.st_ino
        and before.st_size == after.st_size
        and before.st_mtime_ns == after.st_mtime_ns
    )


def capture_transcript(
    manifest: dict[str, Any], session_dir: Path, event: dict[str, Any]
) -> dict[str, Any]:
    transcript_value = event.get("transcript_path")
    if not isinstance(transcript_value, str) or not transcript_value:
        raise CheckpointError("hook did not provide a transcript path")
    transcript_path = Path(transcript_value).expanduser().absolute()
    chunks_dir = session_dir / "chunks"

    for attempt in range(2):
        with open_regular_file(transcript_path) as (handle, before):
            snapshot_size = int(before.st_size)
            identity = source_identity(transcript_path, before)
            resolved_path = str(transcript_path)
            current = (
                manifest["generations"][-1]
                if manifest["generations"]
                else None
            )
            same_generation = bool(
                current
                and current.get("transcript_path") == resolved_path
                and current.get("source") == identity
                and isinstance(current.get("archived_through"), int)
                and current["archived_through"] <= snapshot_size
            )
            prior_end = current["archived_through"] if same_generation else 0
            prior_sha, full_sha = scan_prefixes(handle, snapshot_size, prior_end)
            if same_generation and prior_sha != current.get("source_prefix_sha256"):
                same_generation = False
                prior_end = 0
            if not same_generation:
                generation_id = len(manifest["generations"]) + 1
                current = {
                    "id": generation_id,
                    "created_at": utc_now(),
                    "transcript_path": resolved_path,
                    "source": identity,
                    "archived_through": 0,
                    "source_prefix_sha256": EMPTY_SHA256,
                    "chain_sha256": generation_seed(
                        manifest["session_id"], generation_id, resolved_path, identity
                    ),
                    "chunks": [],
                    "replacement_reason": (
                        "initial"
                        if not manifest["generations"]
                        else "source-replaced-truncated-or-prefix-changed"
                    ),
                }
                prior_end = 0
            chunk = publish_chunk(
                handle, chunks_dir, current["id"], prior_end, snapshot_size
            )
            after = os.fstat(handle.fileno())
            if not metadata_stable(before, after):
                if attempt == 0:
                    continue
                raise CheckpointError("transcript changed repeatedly during checkpoint")

        if current not in manifest["generations"]:
            manifest["generations"].append(current)
        if chunk is not None:
            chunk["previous_chain_sha256"] = current["chain_sha256"]
            chunk["chain_sha256"] = next_chain_hash(
                current["chain_sha256"],
                {key: chunk[key] for key in ("path", "start", "end", "size", "sha256")},
            )
            current["chunks"].append(chunk)
            current["chain_sha256"] = chunk["chain_sha256"]
        current["archived_through"] = snapshot_size
        current["source_prefix_sha256"] = full_sha
        current["updated_at"] = utc_now()
        return {
            "generation_id": current["id"],
            "archived_through": snapshot_size,
            "source_prefix_sha256": full_sha,
            "chain_sha256": current["chain_sha256"],
            "chunk_path": chunk["path"] if chunk else None,
        }
    raise CheckpointError("unable to capture a stable transcript snapshot")


def lifecycle_record(event: dict[str, Any], capture: dict[str, Any] | None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "sequence": None,
        "timestamp": utc_now(),
        "hook_event_name": event.get("hook_event_name"),
        "turn_id": event.get("turn_id"),
        "trigger": event.get("trigger"),
        "source": event.get("source"),
        "cwd": event.get("cwd"),
        "model": event.get("model"),
    }
    if capture:
        record.update(capture)
    return {key: value for key, value in record.items() if value is not None}


def checkpoint_event(event: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    session_id = event.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise CheckpointError("hook did not provide a session id")
    root = archive_root()
    ensure_private_dir(root)
    session_dir = root / safe_session_component(session_id)
    manifest_path = session_dir / "manifest.json"
    event_name = event.get("hook_event_name")
    with session_lock(session_dir):
        manifest = load_manifest(manifest_path, session_id)
        capture = None
        if event_name in {"PreCompact", "SessionEnd"}:
            capture = capture_transcript(manifest, session_dir, event)
        record = lifecycle_record(event, capture)
        record["sequence"] = len(manifest["lifecycle"]) + 1
        manifest["lifecycle"].append(record)
        if event_name == "PreCompact":
            checkpoint = dict(record)
            checkpoint["checkpoint_id"] = len(manifest["checkpoints"]) + 1
            manifest["checkpoints"].append(checkpoint)
        manifest["updated_at"] = utc_now()
        atomic_write_json(manifest_path, manifest)
    return session_dir, record


def compact_context(session_dir: Path, record: dict[str, Any]) -> str:
    manifest_path = session_dir / "manifest.json"
    checkpoint = record.get("sequence")
    return (
        "The pre-compaction transcript was losslessly checkpointed. "
        f"Manifest: {manifest_path}. Lifecycle record: {checkpoint}. "
        "If compacted context is insufficient or a claim needs auditing, use "
        "the manifest and immutable chunks as the evidence source; generate a "
        "readable timeline with ~/.codex/hooks/analyze_session.py."
    )


def emit_precompact_failure(message: str) -> int:
    response = {
        "continue": False,
        "stopReason": f"Pre-compaction transcript checkpoint failed: {message}",
        "systemMessage": (
            "Codex did not compact because the lossless transcript checkpoint "
            f"could not be verified: {message}"
        ),
    }
    json.dump(response, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


def run_hook(event: dict[str, Any]) -> int:
    event_name = event.get("hook_event_name")
    supported = {"PreCompact", "PostCompact", "SessionStart", "SessionEnd"}
    if event_name not in supported:
        raise CheckpointError(f"unsupported hook event {event_name!r}")
    if event_name == "SessionStart" and event.get("source") != "compact":
        return 0
    try:
        session_dir, record = checkpoint_event(event)
    except (CheckpointError, OSError, json.JSONDecodeError) as exc:
        if event_name == "PreCompact":
            return emit_precompact_failure(str(exc))
        raise
    if event_name == "SessionStart":
        response = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": compact_context(session_dir, record),
            }
        }
        json.dump(response, sys.stdout, separators=(",", ":"))
        sys.stdout.write("\n")
    elif event_name == "PostCompact":
        response = {"systemMessage": compact_context(session_dir, record)}
        json.dump(response, sys.stdout, separators=(",", ":"))
        sys.stdout.write("\n")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Codex lifecycle hook for lossless transcript checkpoints"
    )
    parser.add_argument(
        "--event-json",
        help="Read a hook event from this file instead of stdin (test/debug only)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    os.umask(0o077)
    args = parse_args(argv if argv is not None else sys.argv[1:])
    try:
        if args.event_json:
            with Path(args.event_json).open("r", encoding="utf-8") as handle:
                event = json.load(handle)
        else:
            event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise CheckpointError("hook input is not a JSON object")
        return run_hook(event)
    except (CheckpointError, OSError, json.JSONDecodeError) as exc:
        print(f"session checkpoint hook failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
