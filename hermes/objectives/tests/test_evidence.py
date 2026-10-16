import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

path = os.environ.get("HERMES_TEST_EVIDENCE_VERIFIER", str(Path(__file__).resolve().parent.parent / "verify_evidence.py"))
spec = importlib.util.spec_from_file_location("objective_evidence", path)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class EvidenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value))
        return {"path": str(path), "sha256": verifier.sha(path)}

    def capture(self):
        source = self.write("source.java", {"current": True})
        payload = {"userMessage": "Question", "playbookOptions": [{"key": "allowed-workflow"}]}
        raw = self.write("request.json", payload)
        replay = self.write("replay.json", payload)
        return {"schema": 1, "kind": "capture", "sources": [source], "artifacts": [raw], "snapshots": [{**raw, "round_trip": replay, "origin": "native-router-input"}], "provider_calls": 0}

    def comparison(self):
        source = self.write("source.java", {"current": True})
        pairs = []
        for i in range(2):
            inp = self.write(f"input{i}.json", {"message": str(i)})
            pair = {"id": f"pair{i}", "input": inp}
            for arm in ("baseline", "treatment"):
                latency = 100 if arm == "baseline" else 200
                trace = self.write(f"trace{i}-{arm}.json", {"input_sha256": inp["sha256"], "latency_ms": latency})
                quality = self.write(f"quality{i}-{arm}.json", {"input_sha256": inp["sha256"], "score": 0.9, "judge_model": "gpt-6-astra", "blind": True, "citations": ["raw input evidence"]})
                pair[arm] = {"input_sha256": inp["sha256"], "trace": trace, "latency_ms": latency, "cost_status": "unknown", "measurement_scope": "frozen-response-continuation", "quality": quality}
            pairs.append(pair)
        plan = self.write("plan.json", {"pair_ids": [pair["id"] for pair in pairs]})
        source_digest = hashlib.sha256(json.dumps({source["path"]: source["sha256"]}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        review = self.write("execution-review.json", {"verdict": "APPROVE", "plan_sha256": plan["sha256"], "source_digest": source_digest})
        return {"schema": 1, "kind": "comparison", "sources": [source], "artifacts": [source], "pairs": pairs, "execution_plan": plan, "execution_review": review, "failures_and_fallbacks": [], "limitations": ["Frozen responses; unknown costs"], "supports_live_network_speedup": False}

    def check(self, data):
        report = self.write("manifest.json", data)
        return verifier.verify(report["path"], data["kind"])

    def test_exact_native_capture_round_trip_passes(self):
        self.assertEqual(self.check(self.capture())["kind"], "capture")

    def test_capture_missing_workflow_or_separate_replay_fails(self):
        data = self.capture()
        data["snapshots"][0]["round_trip"] = {k: v for k, v in data["snapshots"][0].items() if k in {"path", "sha256"}}
        with self.assertRaises(ValueError):
            self.check(data)

    def test_capture_only_alias_cannot_be_presented_as_exact_native_input(self):
        data = self.capture()
        payload = {"userMessage": "Question", "message": "Question", "playbookOptions": [{"key": "allowed-workflow"}]}
        raw = self.write("request.json", payload)
        replay = self.write("replay.json", payload)
        data["artifacts"] = [raw]
        data["snapshots"] = [{**raw, "round_trip": replay, "origin": "native-router-input"}]
        with self.assertRaises(ValueError):
            self.check(data)

    def test_negative_comparison_and_unknown_cost_are_valid_evidence(self):
        self.assertEqual(self.check(self.comparison())["kind"], "comparison")

    def test_reconstructed_comparison_cannot_claim_live_speedup(self):
        data = self.comparison()
        data["supports_live_network_speedup"] = True
        with self.assertRaises(ValueError):
            self.check(data)

    def test_latency_must_match_raw_trace(self):
        data = self.comparison()
        data["pairs"][0]["treatment"]["latency_ms"] = 1
        with self.assertRaises(ValueError):
            self.check(data)

    def test_mutated_sources_and_failed_executed_tests_fail(self):
        data = self.capture()
        Path(data["sources"][0]["path"]).write_text("changed")
        with self.assertRaises(ValueError):
            self.check(data)
        source = self.write("source.java", {"current": True})
        path = self.root / "tests.xml"
        path.write_text('<testsuite><testcase name="regression"><failure>bad</failure></testcase></testsuite>')
        report = {"path": str(path), "sha256": verifier.sha(path)}
        with self.assertRaises(ValueError):
            self.check({"schema": 1, "kind": "implementation", "sources": [source], "artifacts": [report], "test_reports": [report]})

    def test_native_same_card_review_requires_distinct_implementation_and_review_runs(self):
        source = self.write("source.java", {"current": True})
        sources = {source["path"]: source["sha256"]}
        source_digest = hashlib.sha256(json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        review = self.write("review.json", {"verdict": "APPROVE", "source_digest": source_digest, "reviewer_task": "t_same", "implementation_task": "t_same", "reviewer_run": 2, "implementation_run": 1})
        artifact = self.write("protocol.json", {"frozen": "exact bytes"})
        data = {"schema": 1, "kind": "readiness", "sources": [source], "artifacts": [artifact], "review": review, "protocol": artifact, "budget_record": artifact}
        self.assertEqual(self.check(data)["kind"], "readiness")
        data["review"] = self.write("review.json", {"verdict": "APPROVE", "source_digest": source_digest, "reviewer_task": "t_same", "implementation_task": "t_same", "reviewer_run": 1, "implementation_run": 1})
        with self.assertRaises(ValueError):
            self.check(data)

    def test_partial_pairs_and_unapproved_plan_cannot_complete_comparison(self):
        data = self.comparison()
        data["pairs"].pop()
        with self.assertRaises(ValueError):
            self.check(data)
        data = self.comparison()
        data["execution_review"] = self.write("execution-review.json", {"verdict": "CHANGES_REQUIRED"})
        with self.assertRaises(ValueError):
            self.check(data)
