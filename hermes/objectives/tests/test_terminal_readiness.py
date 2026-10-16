import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import verify_terminal_readiness as terminal
import verify_evidence as execution
import verify_readiness_disposition as disposition


class TerminalReadinessTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data))
        return {"path": str(path), "sha256": execution.sha(path)}

    def fixture(self):
        source = self.write("source.java", {"real": True})
        digest = hashlib.sha256(json.dumps({source["path"]: source["sha256"]},
                                          sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        replay = self.write("replay.json", {"status": "OPEN", "unsupported": True, "generatorCalls": 0,
                                           "newExternalAttempts": 1, "gateFailures": ["JEV_INVALID_REQUIRES_NEW_FREEZE"]})
        proof = self.write("verification.json", {"source_digest": digest, "new_provider_calls": 0,
                                                "credentials_accessed": False,
                                                "hashes": {replay["path"]: replay["sha256"]}})
        snapshot = self.write("snapshot.json", {"sourceDigest": digest,
                                                "artifactHashes": {replay["path"]: replay["sha256"]}})
        review = self.write("review.json", {"verdict": "DO_NOT_RUN_TECHNICAL_INCOMPATIBILITY",
                                           "source_digest": digest, "reviewer_task": "review",
                                           "implementation_task": "implementation", "reviewer_run": 2,
                                           "implementation_run": 1, "execution_approved": False,
                                           "comparison_enabled": False, "verification": proof, "snapshot": snapshot})
        budget = self.write("budget.json", {"remaining": 333, "diagnostics": "CLOSED"})
        protocol = self.write("negative.json", {"source_digest": digest, "review": review,
                                               "budget_record": budget, "executable": False,
                                               "comparison_complete": False, "execution_allowlist": [],
                                               "new_provider_calls": 0})
        return {"schema": 1, "kind": "terminal-readiness", "sources": [source], "artifacts": [replay],
                "readiness": "DO_NOT_RUN_TECHNICAL_INCOMPATIBILITY", "source_digest": digest,
                "review": review, "protocol": protocol, "budget_record": budget, "reproduction": replay,
                "comparison_enabled": False, "execution_approved": False, "comparison_complete": False,
                "supports_live_network_speedup": False, "provider_calls": 0, "diagnostics_remaining": 0,
                "limitations": ["Transport incompatibility does not establish model efficacy."]}

    def verify(self, data):
        return terminal.verify(self.write("terminal.json", data)["path"])

    def test_terminal_decision_passes_without_granting_execution(self):
        data = self.fixture()
        self.assertIs(self.verify(data)["execution_approved"], False)
        data["kind"] = "readiness"
        with self.assertRaises(ValueError):
            execution.verify(self.write("execute.json", data)["path"], "readiness")

    def test_enabled_execution_extra_calls_and_speed_claims_are_rejected(self):
        for key, value in [("comparison_enabled", True), ("execution_approved", True),
                           ("comparison_complete", True), ("supports_live_network_speedup", True),
                           ("provider_calls", 1), ("provider_calls", False), ("diagnostics_remaining", 1)]:
            with self.subTest(key=key, value=value):
                data = self.fixture()
                data[key] = value
                with self.assertRaises(ValueError):
                    self.verify(data)

    def test_stale_source_or_tampered_review_is_rejected(self):
        for key in ["sources", "review"]:
            data = self.fixture()
            item = data[key][0] if key == "sources" else data[key]
            Path(item["path"]).write_text("changed")
            with self.assertRaises(ValueError):
                self.verify(data)

    def test_unreviewed_or_generator_producing_replay_is_rejected(self):
        for change in ["unbound", "generated"]:
            data = self.fixture()
            replay = {"unsupported": True, "generatorCalls": 1 if change == "generated" else 0,
                      "gateFailures": ["JEV_INVALID_REQUIRES_NEW_FREEZE"]}
            data["reproduction"] = self.write("different-replay.json", replay)
            if change == "generated":
                review = json.loads(Path(data["review"]["path"]).read_text())
                proof = json.loads(Path(review["verification"]["path"]).read_text())
                proof["hashes"][data["reproduction"]["path"]] = data["reproduction"]["sha256"]
                review["verification"] = self.write("verification.json", proof)
                snapshot = json.loads(Path(review["snapshot"]["path"]).read_text())
                snapshot["artifactHashes"][data["reproduction"]["path"]] = data["reproduction"]["sha256"]
                review["snapshot"] = self.write("snapshot.json", snapshot)
                data["review"] = self.write("review.json", review)
                protocol = json.loads(Path(data["protocol"]["path"]).read_text())
                protocol["review"] = data["review"]
                data["protocol"] = self.write("negative.json", protocol)
            with self.assertRaises(ValueError):
                self.verify(data)

    def test_self_review_and_changed_budget_binding_are_rejected(self):
        data = self.fixture()
        review = json.loads(Path(data["review"]["path"]).read_text())
        review.update(reviewer_task="implementation", reviewer_run=1)
        data["review"] = self.write("review.json", review)
        with self.assertRaises(ValueError):
            self.verify(data)
        data = self.fixture()
        data["budget_record"] = self.write("other-budget.json", {"remaining": 900})
        with self.assertRaises(ValueError):
            self.verify(data)

    def test_stage_disposition_accepts_terminal_but_still_requires_current_source(self):
        data = self.fixture()
        report = self.write("stage.json", data)
        self.assertFalse(disposition.verify(report["path"], self.root, ["source.java"])["execution_approved"])
        with self.assertRaises(ValueError):
            disposition.verify(report["path"], self.root, ["unbound.java"])
        data["kind"] = "other"
        with self.assertRaises(ValueError):
            disposition.verify(self.write("stage.json", data)["path"])

    def test_stage_disposition_preserves_execution_APPROVE_requirement(self):
        data = self.fixture()
        data["kind"] = "readiness"
        with self.assertRaises(ValueError):
            disposition.verify(self.write("stage.json", data)["path"])


if __name__ == "__main__":
    unittest.main()
