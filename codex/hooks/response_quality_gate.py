#!/usr/bin/env python3
"""Stop hook that catches over-expanded answers to narrow lookup questions.

The model still performs the semantic comprehension pass. This hook provides
an output-level backstop for the recurring, measurable failure mode: a short
question receiving a long, heavily sectioned answer with a second recap.
"""

from __future__ import annotations

import json
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MAX_EVENT_BYTES = 2 * 1024 * 1024
MAX_TRANSCRIPT_TAIL_BYTES = 4 * 1024 * 1024
MAX_PROMPT_WORDS = 80
MAX_RESPONSE_WORDS = 320
MAX_RESPONSE_HEADINGS = 5

SKIP_PROMPT_PREFIXES = (
    "<codex_internal_context",
    "<environment_context>",
    "<recommended_plugins>",
    "<skill",
    "<subagent_notification",
    "<turn_aborted",
    "<user_instructions>",
    "<turn_context>",
    "# AGENTS.md instructions for ",
)

LOOKUP_START = re.compile(r"^\s*(?:where|what|why|how|which)\b", re.IGNORECASE)
LOOKUP_INSIDE = re.compile(
    r"\b(?:where|how)\s+(?:is|are|was|were|does|do)\b", re.IGNORECASE
)
EXPLICIT_DEPTH = re.compile(
    r"\b(?:in detail|detailed|thorough|comprehensive|exhaustive|deep[- ]dive|"
    r"all (?:the )?(?:details|references|cases)|step[- ]by[- ]step|"
    r"(?:long|lengthy) answer|\d+ words?)\b",
    re.IGNORECASE,
)
BROAD_SCOPE = re.compile(
    r"\b(?:entire|whole|overall)\s+(?:system|architecture|flow|feature|module)\b",
    re.IGNORECASE,
)
FENCED_BLOCK = re.compile(r"```.*?```", re.DOTALL)
WORD = re.compile(r"\b[\w'-]+\b", re.UNICODE)
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
RECAP_HEADING = re.compile(
    r"^(?:complete flow|recap|summary|in short|bottom line|conclusion)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Review:
    block: bool
    reason: str = ""


def extract_message_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for block in payload.get("content", []):
        if not isinstance(block, dict):
            continue
        if block.get("type") not in ("input_text", "output_text"):
            continue
        value = block.get("text")
        if isinstance(value, str) and value:
            parts.append(value)
    return "\n".join(parts)


def prompt_from_record(record: dict[str, Any]) -> str | None:
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return None
    if (
        record.get("type") == "response_item"
        and payload.get("type") == "message"
        and payload.get("role") == "user"
    ):
        return extract_message_text(payload)
    if record.get("type") == "event_msg" and payload.get("type") == "user_message":
        value = payload.get("message")
        return value if isinstance(value, str) else None
    return None


def latest_user_prompt(transcript_value: Any) -> str | None:
    if not isinstance(transcript_value, str) or not transcript_value:
        return None
    path = Path(transcript_value).expanduser()
    try:
        metadata = path.stat()
        if not stat.S_ISREG(metadata.st_mode):
            return None
        with path.open("rb") as handle:
            start = max(0, metadata.st_size - MAX_TRANSCRIPT_TAIL_BYTES)
            handle.seek(start)
            data = handle.read(MAX_TRANSCRIPT_TAIL_BYTES)
    except OSError:
        return None

    lines = data.splitlines()
    if start and lines:
        lines = lines[1:]
    for raw in reversed(lines):
        try:
            record = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(record, dict):
            continue
        prompt = prompt_from_record(record)
        if not prompt or prompt.lstrip().startswith(SKIP_PROMPT_PREFIXES):
            continue
        return prompt
    return None


def word_count(text: str) -> int:
    return len(WORD.findall(text))


def is_narrow_lookup(prompt: str) -> bool:
    prose = FENCED_BLOCK.sub(" ", prompt).strip()
    if not prose or word_count(prose) > MAX_PROMPT_WORDS:
        return False
    if prose.count("?") > 2 or EXPLICIT_DEPTH.search(prose) or BROAD_SCOPE.search(prose):
        return False
    return bool(LOOKUP_START.search(prose) or LOOKUP_INSIDE.search(prose))


def review_response(prompt: str, response: str) -> Review:
    if not is_narrow_lookup(prompt):
        return Review(False)

    words = word_count(response)
    headings = [value.strip(" `*_#") for value in HEADING.findall(response)]
    recap = any(RECAP_HEADING.fullmatch(value) for value in headings)
    failures: list[str] = []
    if words > MAX_RESPONSE_WORDS:
        failures.append(f"{words} words (limit {MAX_RESPONSE_WORDS})")
    if len(headings) > MAX_RESPONSE_HEADINGS:
        failures.append(
            f"{len(headings)} headings (limit {MAX_RESPONSE_HEADINGS})"
        )
    if recap and len(headings) > 1 and words > 120:
        failures.append("a recap section after the explanation")
    if not failures:
        return Review(False)

    observed = ", ".join(failures)
    reason = (
        "Revise the final answer before sending it. The user asked a narrow "
        f"lookup/explanation question, and the draft has {observed}. Put the "
        "direct answer first. Keep only the location, definition, and evidence "
        "needed for this question. Remove repeated flow/summary material and "
        f"unrelated issue background. Stay within {MAX_RESPONSE_WORDS} words "
        f"and {MAX_RESPONSE_HEADINGS} headings. Preserve material uncertainty "
        "and the required verification note. Return only the revised answer."
    )
    return Review(True, reason)


def evaluate_event(event: dict[str, Any]) -> Review:
    if event.get("stop_hook_active") is True:
        return Review(False)
    response = event.get("last_assistant_message")
    if not isinstance(response, str) or not response.strip():
        return Review(False)
    prompt = latest_user_prompt(event.get("transcript_path"))
    if prompt is None:
        return Review(False)
    return review_response(prompt, response)


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(MAX_EVENT_BYTES + 1)
        if len(raw) > MAX_EVENT_BYTES:
            return 0
        event = json.loads(raw)
        if not isinstance(event, dict):
            return 0
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return 0

    review = evaluate_event(event)
    if review.block:
        print(json.dumps({"decision": "block", "reason": review.reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
