from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


HOOK_DIR = Path(__file__).resolve().parents[1] / "hooks"
HOOK = HOOK_DIR / "session_checkpoint.py"
ANALYZER = HOOK_DIR / "analyze_session.py"


def transcript_line(timestamp: str, record_type: str, payload: dict) -> bytes:
    return (
        json.dumps(
            {"timestamp": timestamp, "type": record_type, "payload": payload},
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


class SessionCheckpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive = self.root / "archives"
        self.transcript = self.root / "rollout.jsonl"
        self.session_id = "test-session"
        self.env = os.environ.copy()
        self.env["CODEX_COMPACTION_ARCHIVE_ROOT"] = str(self.archive)
        self.transcript.write_bytes(
            transcript_line(
                "2026-07-27T10:00:00Z",
                "session_meta",
                {"id": self.session_id, "cwd": "/workspace", "cli_version": "test"},
            )
            + transcript_line(
                "2026-07-27T10:00:01Z",
                "response_item",
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "keep this evidence"}],
                },
            )
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def event(self, name: str, **overrides) -> dict:
        event = {
            "session_id": self.session_id,
            "transcript_path": str(self.transcript),
            "cwd": "/workspace",
            "hook_event_name": name,
            "model": "test-model",
            "turn_id": "turn-1",
        }
        event.update(overrides)
        return event

    def run_hook(self, event: dict, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(event),
            text=True,
            capture_output=True,
            env=env or self.env,
            check=False,
        )

    def manifest(self) -> dict:
        return json.loads(
            (self.archive / self.session_id / "manifest.json").read_text("utf-8")
        )

    def reconstructed(self, generation: dict | None = None) -> bytes:
        generation = generation or self.manifest()["generations"][-1]
        return b"".join(
            (self.archive / self.session_id / chunk["path"]).read_bytes()
            for chunk in generation["chunks"]
        )

    def test_precompact_captures_exact_bytes_and_manifest_metadata(self) -> None:
        result = self.run_hook(self.event("PreCompact", trigger="auto"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        manifest = self.manifest()
        self.assertEqual(self.reconstructed(), self.transcript.read_bytes())
        self.assertEqual(manifest["checkpoints"][0]["trigger"], "auto")
        self.assertEqual(manifest["checkpoints"][0]["turn_id"], "turn-1")
        self.assertEqual(manifest["generations"][0]["archived_through"], self.transcript.stat().st_size)
        self.assertEqual(oct((self.archive / self.session_id).stat().st_mode & 0o777), "0o700")
        chunk_path = self.archive / self.session_id / manifest["generations"][0]["chunks"][0]["path"]
        self.assertEqual(oct(chunk_path.stat().st_mode & 0o777), "0o600")

    def test_incremental_and_idempotent_capture(self) -> None:
        self.assertEqual(self.run_hook(self.event("PreCompact", trigger="manual")).returncode, 0)
        first = self.manifest()
        self.assertEqual(self.run_hook(self.event("PreCompact", trigger="manual")).returncode, 0)
        second = self.manifest()
        self.assertEqual(len(second["generations"][0]["chunks"]), 1)
        self.assertEqual(len(second["checkpoints"]), 2)
        with self.transcript.open("ab") as handle:
            handle.write(
                transcript_line(
                    "2026-07-27T10:00:02Z",
                    "event_msg",
                    {"type": "task_complete"},
                )
            )
        self.assertEqual(self.run_hook(self.event("PreCompact", trigger="auto")).returncode, 0)
        third = self.manifest()
        self.assertEqual(len(third["generations"]), 1)
        self.assertEqual(len(third["generations"][0]["chunks"]), 2)
        self.assertEqual(self.reconstructed(), self.transcript.read_bytes())
        self.assertNotEqual(
            first["generations"][0]["chain_sha256"],
            third["generations"][0]["chain_sha256"],
        )

    def test_truncation_starts_a_new_generation(self) -> None:
        self.assertEqual(self.run_hook(self.event("PreCompact", trigger="manual")).returncode, 0)
        self.transcript.write_bytes(b'{"type":"replacement"}\n')
        self.assertEqual(self.run_hook(self.event("PreCompact", trigger="manual")).returncode, 0)
        manifest = self.manifest()
        self.assertEqual(len(manifest["generations"]), 2)
        self.assertEqual(self.reconstructed(), self.transcript.read_bytes())

    def test_replaced_source_starts_a_new_generation(self) -> None:
        self.assertEqual(self.run_hook(self.event("PreCompact", trigger="manual")).returncode, 0)
        replacement = self.root / "replacement.jsonl"
        replacement.write_bytes(self.transcript.read_bytes())
        os.replace(replacement, self.transcript)
        self.assertEqual(self.run_hook(self.event("PreCompact", trigger="manual")).returncode, 0)
        self.assertEqual(len(self.manifest()["generations"]), 2)

    def test_in_place_prefix_change_starts_a_new_generation(self) -> None:
        self.assertEqual(self.run_hook(self.event("PreCompact", trigger="manual")).returncode, 0)
        content = bytearray(self.transcript.read_bytes())
        content[2] = ord("X")
        self.transcript.write_bytes(content)
        self.assertEqual(self.run_hook(self.event("PreCompact", trigger="manual")).returncode, 0)
        self.assertEqual(len(self.manifest()["generations"]), 2)

    def test_missing_transcript_fails_closed(self) -> None:
        self.transcript.unlink()
        result = self.run_hook(self.event("PreCompact", trigger="auto"))
        self.assertEqual(result.returncode, 0)
        response = json.loads(result.stdout)
        self.assertFalse(response["continue"])
        self.assertIn("cannot open transcript", response["stopReason"])

    def test_unusable_archive_root_fails_closed(self) -> None:
        bad_root = self.root / "not-a-directory"
        bad_root.write_text("occupied", encoding="utf-8")
        env = dict(self.env)
        env["CODEX_COMPACTION_ARCHIVE_ROOT"] = str(bad_root)
        result = self.run_hook(self.event("PreCompact", trigger="auto"), env=env)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)["continue"])

    def test_corrupt_manifest_fails_closed(self) -> None:
        session_dir = self.archive / self.session_id
        session_dir.mkdir(parents=True)
        (session_dir / "manifest.json").write_text("not-json", encoding="utf-8")
        result = self.run_hook(self.event("PreCompact", trigger="manual"))
        self.assertEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)["continue"])

    def test_concurrent_runs_do_not_duplicate_raw_chunks(self) -> None:
        event = self.event("PreCompact", trigger="auto")
        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(lambda _: self.run_hook(event), range(12)))
        self.assertTrue(all(result.returncode == 0 for result in results))
        manifest = self.manifest()
        self.assertEqual(len(manifest["generations"][0]["chunks"]), 1)
        self.assertEqual(len(manifest["checkpoints"]), 12)
        self.assertEqual(self.reconstructed(), self.transcript.read_bytes())

    def test_postcompact_and_compact_session_start_are_recorded(self) -> None:
        self.assertEqual(self.run_hook(self.event("PreCompact", trigger="manual")).returncode, 0)
        post = self.run_hook(self.event("PostCompact", trigger="manual"))
        self.assertEqual(post.returncode, 0, post.stderr)
        post_context = json.loads(post.stdout)["systemMessage"]
        self.assertIn("analyze_session.py", post_context)
        self.assertIn(str(self.archive / self.session_id / "manifest.json"), post_context)
        start = self.run_hook(self.event("SessionStart", source="compact"))
        self.assertEqual(start.returncode, 0, start.stderr)
        response = json.loads(start.stdout)
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn("losslessly checkpointed", context)
        self.assertIn("manifest.json", context)
        names = [item["hook_event_name"] for item in self.manifest()["lifecycle"]]
        self.assertEqual(names, ["PreCompact", "PostCompact", "SessionStart"])

    def test_session_end_captures_final_tail(self) -> None:
        self.assertEqual(self.run_hook(self.event("PreCompact", trigger="auto")).returncode, 0)
        with self.transcript.open("ab") as handle:
            handle.write(b'{"timestamp":"later","type":"event_msg","payload":{"type":"task_complete"}}\n')
        end = self.run_hook(self.event("SessionEnd"))
        self.assertEqual(end.returncode, 0, end.stderr)
        self.assertEqual(self.reconstructed(), self.transcript.read_bytes())
        self.assertEqual(self.manifest()["lifecycle"][-1]["hook_event_name"], "SessionEnd")

    def test_analyzer_verifies_and_renders_source_offsets(self) -> None:
        self.assertEqual(self.run_hook(self.event("PreCompact", trigger="auto")).returncode, 0)
        result = subprocess.run(
            [sys.executable, str(ANALYZER), self.session_id],
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Verification: passed", result.stdout)
        self.assertIn("keep this evidence", result.stdout)
        self.assertIn("Byte range", result.stdout)

    def test_analyzer_reports_chunk_corruption(self) -> None:
        self.assertEqual(self.run_hook(self.event("PreCompact", trigger="auto")).returncode, 0)
        manifest = self.manifest()
        chunk = self.archive / self.session_id / manifest["generations"][0]["chunks"][0]["path"]
        chunk.write_bytes(chunk.read_bytes() + b"corruption")
        result = subprocess.run(
            [sys.executable, str(ANALYZER), self.session_id, "--verify-only"],
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("SHA-256 does not match", result.stderr)

    def test_analyzer_preserves_malformed_json_as_evidence(self) -> None:
        with self.transcript.open("ab") as handle:
            handle.write(b"malformed-json\n")
        self.assertEqual(self.run_hook(self.event("PreCompact", trigger="manual")).returncode, 0)
        result = subprocess.run(
            [sys.executable, str(ANALYZER), self.session_id],
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("invalid-json", result.stdout)
        self.assertIn("Unparseable record preserved", result.stdout)


if __name__ == "__main__":
    unittest.main()
