import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from hermes_cli import kanban_db as kb
from hermes_cli import kanban_objectives as obj
from hermes_cli.kanban_db_connect import connect


class ObjectivesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"HERMES_HOME": str(self.path), "HERMES_KANBAN_DB": str(self.path / "kanban.db")})
        self.env.start()
        self.conn = connect(self.path / "kanban.db")
        self.root = kb.create_task(self.conn, title="Make Nora faster, with measured quality", assignee="default", workspace_kind="dir", workspace_path=str(self.path), triage=True)
        self.evidence = self.path / "capture.json"
        self.outcome = self.path / "comparison.json"
        self.stage = {"id": "capture", "title": "Capture exact routing input", "body": "Instrument the constructed authorized workflow list and input, verify exact-byte replay. Missing logs require implementation, then capture.", "workspace_path": str(self.path), "checks": [{"path": str(self.evidence), "kind": "json", "assertions": [{"key": "workflows", "op": "count_ge", "value": 1}, {"key": "input", "op": "nonempty"}]}]}
        self.spec = {"schema": 1, "objective": "Compare routing on identical inputs with measured quality and latency", "owner": "default", "stale_seconds": 60, "max_repairs": 2, "stages": [self.stage], "checks": [{"path": str(self.outcome), "kind": "json", "assertions": [{"key": "paired_requests", "op": "ge", "value": 2}, {"key": "quality_delta", "op": "ge", "value": 0}, {"key": "latency_delta_ms", "op": "lt", "value": 0}]}]}
        obj.enroll(self.conn, self.root, self.spec)

    def tearDown(self):
        self.conn.close()
        self.env.stop()
        self.tmp.cleanup()

    def tasks(self):
        return self.conn.execute("SELECT task FROM objective_members WHERE stage='capture'").fetchall()

    def capture(self):
        self.evidence.write_text(json.dumps({"workflows": ["kb-search"], "input": {"message": "question"}}))

    def outcome_passes(self):
        self.outcome.write_text(json.dumps({"paired_requests": 3, "quality_delta": 0, "latency_delta_ms": -10}))

    def test_missing_capture_creates_assigned_implementation_without_root_dependency(self):
        actions = obj.tick(self.conn)
        tid = actions[0]["created_stage"]
        task = kb.get_task(self.conn, tid)
        self.assertEqual(task.assignee, "default")
        self.assertEqual(task.status, "ready")
        self.assertEqual(kb.parent_ids(self.conn, tid), [])
        self.assertIn(tid, kb.parent_ids(self.conn, self.root))
        self.assertIn("Current objective contract", kb.build_worker_context(self.conn, tid))
        self.assertEqual(obj.tick(self.conn), [])
        self.assertEqual(len(self.tasks()), 1)

    def test_rejects_infrastructure_only_completion_then_accepts_outcome_and_wakes_root(self):
        obj.tick(self.conn)
        tid = self.tasks()[0]["task"]
        self.assertFalse(kb.complete_task(self.conn, tid, result="714 transport calls passed"))
        self.capture()
        self.assertTrue(kb.complete_task(self.conn, tid, result="Captured exact input"))
        obj.tick(self.conn)
        self.assertEqual(kb.get_task(self.conn, self.root).status, "ready")
        self.assertFalse(kb.complete_task(self.conn, self.root, result="All helper tests passed"))
        self.outcome_passes()
        self.assertTrue(kb.complete_task(self.conn, self.root, result="Measured paired outcome"))
        receipt = self.conn.execute("SELECT evidence FROM objective_receipts WHERE task=?", (self.root,)).fetchone()
        self.assertIn("sha256", receipt["evidence"])

    def test_contract_revision_invalidates_old_tasks_and_receipts(self):
        obj.tick(self.conn)
        old = self.tasks()[0]["task"]
        self.capture()
        self.assertTrue(kb.complete_task(self.conn, old))
        new_spec = copy.deepcopy(self.spec)
        new_spec["objective"] += " and calibration"
        self.assertEqual(obj.enroll(self.conn, self.root, new_spec), 2)
        obj.tick(self.conn)
        self.assertEqual(len(self.tasks()), 2)
        self.outcome_passes()
        self.assertFalse(kb.complete_task(self.conn, self.root))

    def test_dynamic_child_inherits_current_contract_and_cross_objective_rejected(self):
        child = kb.create_task(self.conn, title="Child", creator_task_id=self.root)
        self.assertEqual(obj.contract(self.conn, child)["root"], self.root)
        another = kb.create_task(self.conn, title="Other", triage=True)
        obj.enroll(self.conn, another, self.spec)
        with self.assertRaises(ValueError):
            kb.create_task(self.conn, title="Ambiguous", parents=[self.root, another])
        self.assertFalse(self.conn.execute("SELECT 1 FROM tasks WHERE title='Ambiguous'").fetchone())

    def test_internal_blocker_creates_idempotent_repair_and_resumes_after_evidence(self):
        obj.tick(self.conn)
        tid = self.tasks()[0]["task"]
        fix = self.path / "fixed.json"
        repair = {"body": "Repair the recorder", "checks": [{"path": str(fix), "kind": "json", "assertions": [{"key": "replay", "op": "eq", "value": True}]}]}
        obj.report_blocker(self.conn, tid, "internal_repair", "Recorder does not exist", repair)
        actions = obj.tick(self.conn)
        rid = actions[0]["repair"]
        self.assertEqual(obj.tick(self.conn), [])
        self.assertEqual(kb.get_task(self.conn, rid).status, "ready")
        self.assertFalse(kb.complete_task(self.conn, rid))
        fix.write_text('{"replay":true}')
        self.assertTrue(kb.complete_task(self.conn, rid))
        obj.tick(self.conn)
        self.assertEqual(kb.get_task(self.conn, tid).status, "ready")

    def test_external_input_and_pause_are_preserved(self):
        obj.tick(self.conn, now=100)
        tid = self.tasks()[0]["task"]
        obj.report_blocker(self.conn, tid, "permission", "Owner approval required")
        obj.tick(self.conn, now=300)
        self.assertEqual(kb.get_task(self.conn, tid).status, "blocked")
        with kb.write_txn(self.conn):
            self.conn.execute("UPDATE objective_contracts SET paused=1 WHERE root=?", (self.root,))
        self.capture()
        self.assertFalse(kb.complete_task(self.conn, tid))
        self.assertEqual(obj.tick(self.conn, now=1000), [])

    def test_stagnation_bounded_and_card_activity_does_not_reset_progress(self):
        obj.tick(self.conn, now=100)
        tid = self.tasks()[0]["task"]
        kb.block_task(self.conn, tid, kind="capability", reason="No recorder")
        kb.add_comment(self.conn, tid, "default", "An audit report")
        actions = obj.tick(self.conn, now=200)
        self.assertEqual(actions[0]["resumed_stalled"], tid)
        kb.block_task(self.conn, tid, kind="capability", reason="No recorder")
        obj.tick(self.conn, now=300)
        kb.block_task(self.conn, tid, kind="capability", reason="No recorder")
        obj.tick(self.conn, now=400)
        self.assertEqual(kb.get_task(self.conn, tid).status, "triage")
        self.assertEqual(obj.tick(self.conn, now=500), [])

    def test_evidence_rechecks_completed_stages_and_rejects_bad_numbers(self):
        obj.tick(self.conn)
        tid = self.tasks()[0]["task"]
        self.capture()
        self.assertTrue(kb.complete_task(self.conn, tid))
        obj.tick(self.conn)
        self.outcome_passes()
        self.evidence.unlink()
        self.assertFalse(kb.complete_task(self.conn, self.root))
        self.capture()
        self.outcome.write_text('{"paired_requests":true,"quality_delta":0,"latency_delta_ms":-10}')
        self.assertFalse(kb.complete_task(self.conn, self.root))
        self.outcome.write_text('{"paired_requests":3,"quality_delta":NaN,"latency_delta_ms":-10}')
        self.assertFalse(kb.complete_task(self.conn, self.root))

    def test_manual_review_completion_uses_same_gate(self):
        obj.tick(self.conn)
        tid = self.tasks()[0]["task"]
        with kb.write_txn(self.conn):
            self.conn.execute("UPDATE tasks SET status='review' WHERE id=?", (tid,))
        self.assertFalse(kb.complete_task(self.conn, tid, summary="Human review approved"))
        self.assertEqual(kb.get_task(self.conn, tid).status, "review")
        self.capture()
        self.assertTrue(kb.complete_task(self.conn, tid))

    def test_wrong_run_cannot_record_receipt(self):
        obj.tick(self.conn)
        tid = self.tasks()[0]["task"]
        self.capture()
        self.assertFalse(kb.complete_task(self.conn, tid, expected_run_id=999))
        self.assertFalse(self.conn.execute("SELECT 1 FROM objective_receipts WHERE task=?", (tid,)).fetchone())

    def test_cli_completion_is_gated(self):
        obj.tick(self.conn)
        tid = self.tasks()[0]["task"]
        args = [sys.executable, "-m", "hermes_cli.main", "kanban", "complete", tid, "--result", "Tests passed"]
        denied = subprocess.run(args, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(denied.returncode, 0, denied.stdout + denied.stderr)
        self.assertEqual(kb.get_task(self.conn, tid).status, "ready")
        self.capture()
        allowed = subprocess.run(args, capture_output=True, text=True, timeout=30)
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)

    def test_unenrolled_legacy_tasks_keep_native_behavior(self):
        tid = kb.create_task(self.conn, title="Unrelated work", workspace_kind="dir", workspace_path=str(self.path))
        self.assertTrue(kb.complete_task(self.conn, tid))

    def test_invalid_contract_fails_before_board_changes(self):
        bad = copy.deepcopy(self.spec)
        bad["stages"][0]["after"] = ["capture"]
        with self.assertRaises(ValueError):
            obj.enroll(self.conn, self.root, bad)
        self.assertEqual(obj.contract(self.conn, self.root)["revision"], 1)

    def test_new_goal_requires_contract_and_acquisition_cannot_claim_completion_without_it(self):
        with kb.write_txn(self.conn):
            self.conn.execute("INSERT INTO objective_policy VALUES(1,0)")
        goal = kb.create_task(self.conn, title="Another real goal", goal_mode=True, workspace_kind="dir", workspace_path=str(self.path))
        self.assertFalse(kb.complete_task(self.conn, goal))
        actions = obj.tick(self.conn)
        acquisition = next(a["contract_acquisition"] for a in actions if "contract_acquisition" in a)
        self.assertFalse(kb.complete_task(self.conn, acquisition, result="Plan written"))
        self.assertNotIn(goal, kb.parent_ids(self.conn, acquisition))
        obj.enroll(self.conn, goal, self.spec)
        self.assertTrue(kb.complete_task(self.conn, acquisition, result="Contract enrolled"))

    def test_trusted_verifier_is_executed_and_failure_preserves_incomplete_state(self):
        spec = copy.deepcopy(self.spec)
        spec["stages"][0]["checks"].append({"kind": "command", "argv": [sys.executable, "-c", "raise SystemExit(1)"], "cwd": str(self.path)})
        obj.enroll(self.conn, self.root, spec)
        obj.tick(self.conn)
        tid = self.tasks()[0]["task"]
        self.capture()
        self.assertFalse(kb.complete_task(self.conn, tid))
        self.assertEqual(kb.get_task(self.conn, tid).status, "ready")

    def test_rejected_done_implementation_is_reopened_on_same_card(self):
        existing = kb.create_task(self.conn, title="Implement recorder", workspace_kind="dir", workspace_path=str(self.path))
        self.assertTrue(kb.complete_task(self.conn, existing, result="Partial handoff"))
        child = kb.create_task(self.conn, title="Independent readiness", parents=[existing], workspace_kind="dir", workspace_path=str(self.path))
        self.assertTrue(kb.complete_task(self.conn, child))
        spec = copy.deepcopy(self.spec)
        spec["stages"][0]["task_id"] = existing
        obj.enroll(self.conn, self.root, spec)
        actions = obj.tick(self.conn)
        self.assertIn({"reopened_implementation": existing}, actions)
        self.assertEqual(kb.get_task(self.conn, existing).status, "ready")
        self.assertEqual(kb.get_task(self.conn, child).status, "todo")
        self.assertEqual(kb.get_task(self.conn, existing).result, "Partial handoff")
        self.assertEqual(len(self.tasks()), 1)

    def test_known_dependency_resumes_review_after_repaired_implementation(self):
        obj.tick(self.conn)
        implementation = self.tasks()[0]["task"]
        reviewer = kb.create_task(self.conn, title="Review", creator_task_id=self.root, workspace_kind="dir", workspace_path=str(self.path))
        obj.report_blocker(self.conn, reviewer, "dependency", "Implementation needs repair", {"task_id": implementation})
        obj.tick(self.conn)
        self.assertEqual(kb.get_task(self.conn, reviewer).status, "blocked")
        self.capture()
        self.assertTrue(kb.complete_task(self.conn, implementation))
        obj.tick(self.conn)
        self.assertEqual(kb.get_task(self.conn, reviewer).status, "ready")

    def test_owner_reopen_is_an_explicit_requeue_for_the_native_respawn_guard(self):
        from hermes_cli import kanban_db_dispatch as dispatch
        obj.tick(self.conn)
        task = self.tasks()[0]["task"]
        self.capture()
        self.assertTrue(kb.complete_task(self.conn, task, result="Independent review found a concrete defect"))
        with kb.write_txn(self.conn):
            self.conn.execute("UPDATE tasks SET consecutive_failures=1,block_recurrences=3 WHERE id=?", (task,))
        self.assertTrue(obj.reopen_for_repair(self.conn, task, "Owner implemented the finding; re-review current sources"))
        self.assertIsNone(dispatch.check_respawn_guard(self.conn, task))
        current = kb.get_task(self.conn, task)
        self.assertEqual(current.consecutive_failures, 1)
        self.assertEqual(current.block_recurrences, 3)
        self.assertEqual(current.status, "ready")
        self.assertIsNone(self.conn.execute("SELECT task FROM objective_receipts WHERE task=?", (task,)).fetchone())

    def test_agent_tool_uses_same_gate_even_if_model_judge_is_unavailable(self):
        from tools import kanban_tools
        obj.tick(self.conn)
        tid = self.tasks()[0]["task"]
        with patch.object(kanban_tools, "_goal_judge_available", return_value=False):
            denied = json.loads(kanban_tools._handle_complete({"task_id": tid, "summary": "Helper tests passed"}))
            self.assertIn("error", denied)
            self.assertIn("implement/repair", denied["error"])
            self.assertEqual(kb.get_task(self.conn, tid).status, "ready")
            self.capture()
            allowed = json.loads(kanban_tools._handle_complete({"task_id": tid, "summary": "Capture verified"}))
            self.assertNotIn("error", allowed)

    def test_dashboard_http_done_uses_same_gate(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        plugin_path = os.environ.get("HERMES_TEST_KANBAN_API", "/nix/store/7m15iqha9bkcn7ckw9ryr7nvl7xxnqbn-source/plugins/kanban/dashboard/plugin_api.py")
        module_spec = importlib.util.spec_from_file_location("objective_test_api", plugin_path)
        module = importlib.util.module_from_spec(module_spec)
        sys.modules[module_spec.name] = module
        module_spec.loader.exec_module(module)
        app = FastAPI()
        app.include_router(module.router)
        obj.tick(self.conn)
        tid = self.tasks()[0]["task"]
        with TestClient(app) as client:
            denied = client.patch(f"/tasks/{tid}", json={"status": "done", "summary": "Helper tests passed"})
            self.assertEqual(denied.status_code, 409, denied.text)
            self.capture()
            allowed = client.patch(f"/tasks/{tid}", json={"status": "done", "summary": "Capture verified"})
            self.assertEqual(allowed.status_code, 200, allowed.text)

    def test_dispatch_tick_runs_supervisor_without_plugin_observers_and_dry_run_is_safe(self):
        from hermes_cli.kanban_db_dispatch import DispatchResult
        with patch.object(kb, "_kanban_observer_consumed", return_value=False):
            kb._fire_dispatch_tick_hook(DispatchResult(), dry_run=True)
            self.assertEqual(len(self.tasks()), 0)
            kb._fire_dispatch_tick_hook(DispatchResult())
            self.assertEqual(len(self.tasks()), 1)

    def test_capacity_death_between_reap_and_classification_retains_exit_code(self):
        from hermes_cli import kanban_db_dispatch as dispatch
        child = subprocess.Popen([sys.executable, "-c", "raise SystemExit(75)"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 10
            while dispatch._pid_alive(child.pid) and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(dispatch._pid_alive(child.pid))
            self.assertNotIn(child.pid, dispatch._recent_worker_exits)
            dead = dispatch._classify_dead_worker(child.pid, "isolated-test")
            self.assertEqual((dead.kind, dead.code, dead.rate_limited), ("rate_limited", 75, True))
        finally:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=5)

    def test_capacity_classification_waits_for_concurrent_reaper_publication(self):
        from hermes_cli import kanban_db_dispatch as dispatch
        child = subprocess.Popen([sys.executable, "-c", "raise SystemExit(75)"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        consumed = threading.Event()
        publish = threading.Event()
        classification_boundary = threading.Event()
        results, errors = [], []
        record_exit = dispatch._record_worker_exit
        exit_lock = getattr(dispatch, "_worker_exit_lock", threading.RLock())

        def delayed_publication(pid, status):
            if pid == child.pid:
                consumed.set()
                if not publish.wait(5):
                    raise RuntimeError("Test did not release exit publication")
            record_exit(pid, status)

        class ObservedLock:
            def __enter__(self):
                if not exit_lock.acquire(blocking=False):
                    if threading.current_thread() is classifier:
                        classification_boundary.set()
                    exit_lock.acquire()
                return self

            def __exit__(self, *exc):
                exit_lock.release()

        def reap():
            try:
                dispatch.reap_worker_zombies()
            except BaseException as exc:
                errors.append(exc)

        def classify():
            try:
                results.append(dispatch._classify_dead_worker(child.pid, "isolated-second-board"))
            except BaseException as exc:
                errors.append(exc)
            finally:
                classification_boundary.set()

        reaper = threading.Thread(target=reap)
        classifier = threading.Thread(target=classify)
        try:
            deadline = time.monotonic() + 10
            while dispatch._pid_alive(child.pid) and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(dispatch._pid_alive(child.pid))
            self.assertNotIn(child.pid, dispatch._recent_worker_exits)
            # The old runtime has no lock. It reaches the boundary by returning
            # unknown; the fixed runtime reaches it by contending on the lock.
            with patch.object(dispatch, "_worker_exit_lock", ObservedLock(), create=True), \
                    patch.object(dispatch, "_record_worker_exit", side_effect=delayed_publication):
                try:
                    reaper.start()
                    self.assertTrue(consumed.wait(5), "Reaper must own the actual wait status")
                    classifier.start()
                    self.assertTrue(classification_boundary.wait(5), "Second thread must attempt classification")
                finally:
                    publish.set()
                    for thread in (reaper, classifier):
                        if thread.ident is not None:
                            thread.join(timeout=5)
                self.assertFalse(reaper.is_alive())
                self.assertFalse(classifier.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(len(results), 1)
            dead = results[0]
            self.assertEqual((dead.kind, dead.code, dead.rate_limited), ("rate_limited", 75, True))
        finally:
            publish.set()
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=5)

    def test_pause_prevents_dispatch_and_resume_preserves_external_blocks(self):
        obj.tick(self.conn)
        tid = self.tasks()[0]["task"]
        obj.set_paused(self.conn, self.root, True)
        self.assertIsNone(kb.claim_task(self.conn, tid))
        obj.set_paused(self.conn, self.root, False)
        self.assertIsNotNone(kb.claim_task(self.conn, tid))
        with patch.object(kb, "_terminate_reclaimed_worker") as terminate:
            obj.set_paused(self.conn, self.root, True)
            self.assertEqual(kb.get_task(self.conn, tid).status, "blocked")
            terminate.assert_called_once()
        obj.set_paused(self.conn, self.root, False)
        self.assertEqual(kb.get_task(self.conn, tid).status, "ready")

    def test_new_goal_waits_for_contract_before_claim(self):
        with kb.write_txn(self.conn):
            self.conn.execute("INSERT INTO objective_policy VALUES(1,0)")
        tid = kb.create_task(self.conn, title="Goal", goal_mode=True)
        self.assertIsNone(kb.claim_task(self.conn, tid))

    def test_stale_evidence_cannot_finish_stage(self):
        obj.tick(self.conn)
        tid = self.tasks()[0]["task"]
        self.capture()
        os.utime(self.evidence, (1, 1))
        self.assertFalse(kb.complete_task(self.conn, tid))

    def test_changed_verifier_outcome_reopens_done_stage_without_duplicate_receipts(self):
        flag = self.path / "flag"
        flag.write_text("valid")
        spec = copy.deepcopy(self.spec)
        spec["stages"][0]["checks"].append({"kind": "command", "argv": [sys.executable, "-c", "from pathlib import Path; import sys; sys.exit(0 if Path(sys.argv[1]).read_text()=='valid' else 1)", str(flag)], "cwd": str(self.path)})
        obj.enroll(self.conn, self.root, spec)
        obj.tick(self.conn)
        tid = self.tasks()[0]["task"]
        self.capture()
        self.assertTrue(kb.complete_task(self.conn, tid))
        obj.tick(self.conn)
        accepted = self.conn.execute("SELECT count(*) FROM task_events WHERE task_id=? AND kind='objective_acceptance_passed'", (tid,)).fetchone()[0]
        self.assertEqual(accepted, 1)
        flag.write_text("invalid")
        actions = obj.tick(self.conn)
        self.assertIn({"reopened_implementation": tid}, actions)
        self.assertEqual(kb.get_task(self.conn, tid).status, "ready")

    def continuation(self, limit=2, kind="transient"):
        obj.tick(self.conn, now=100)
        tid = self.tasks()[0]["task"]
        checkpoint = self.path / "continuation.json"
        spec = copy.deepcopy(self.spec)
        spec["stages"][0]["task_id"] = tid
        spec["continuations"] = [{"task_id": tid, "checkpoint": str(checkpoint), "max_runs": limit}]
        obj.enroll(self.conn, self.root, spec)
        obj.tick(self.conn, now=100)
        kb.block_task(self.conn, tid, kind=kind, reason="Verified slice finished; internal work remains")
        source = self.path / "source.py"
        source.write_text("changed implementation")
        report = self.path / "tests.xml"
        report.write_text('<testsuite><testcase name="actual_regression"/></testsuite>')
        def reference(path):
            return {"path": str(path), "sha256": obj.hashlib.sha256(path.read_bytes()).hexdigest()}
        data = {"schema": 1, "task_id": tid, "run_id": kb.list_runs(self.conn, tid)[-1].id,
                "revision": obj.contract(self.conn, tid)["revision"], "provider_calls": 0,
                "internal_work_remaining": True, "completed": ["parity-fixed"],
                "next_action": "Implement corrective read and verify supported final answer",
                "sources": [reference(source)], "artifacts": [reference(report)], "test_reports": [reference(report)]}
        checkpoint.write_text(json.dumps(data))
        return tid, checkpoint, data

    def test_verified_internal_checkpoint_resumes_without_completion_or_root_retry_reset(self):
        tid, checkpoint, data = self.continuation()
        with kb.write_txn(self.conn):
            self.conn.execute("UPDATE objective_progress SET attempts=3 WHERE root=?", (self.root,))
        actions = obj.tick(self.conn, now=100)
        self.assertIn({"continued_internal_work": tid, "used": 1}, actions)
        self.assertEqual(kb.get_task(self.conn, tid).status, "ready")
        self.assertFalse(self.conn.execute("SELECT 1 FROM objective_receipts WHERE task=?", (tid,)).fetchone())
        self.assertEqual(self.conn.execute("SELECT attempts FROM objective_progress WHERE root=?", (self.root,)).fetchone()[0], 3)
        self.assertIn(data["next_action"], obj.worker_context(self.conn, tid))
        self.assertEqual(obj.tick(self.conn, now=100), [])

    def test_continuation_needs_new_milestone_and_current_run(self):
        tid, checkpoint, data = self.continuation()
        obj.tick(self.conn, now=100)
        kb.block_task(self.conn, tid, kind="transient", reason="Another incomplete slice")
        self.assertEqual(obj.tick(self.conn, now=100), [])
        data["run_id"] = kb.list_runs(self.conn, tid)[-1].id
        checkpoint.write_text(json.dumps(data))
        self.assertEqual(obj.tick(self.conn, now=100), [])
        data["completed"].append("corrective-read-fixed")
        checkpoint.write_text(json.dumps(data))
        self.assertIn({"continued_internal_work": tid, "used": 2}, obj.tick(self.conn, now=100))

    def test_continuation_rejects_failed_or_tampered_test_reports(self):
        tid, checkpoint, data = self.continuation()
        report = Path(data["test_reports"][0]["path"])
        report.write_text('<testsuite><testcase name="regression"><failure/></testcase></testsuite>')
        self.assertEqual(obj.tick(self.conn, now=100), [])
        data["test_reports"][0]["sha256"] = obj.hashlib.sha256(report.read_bytes()).hexdigest()
        data["artifacts"][0]["sha256"] = data["test_reports"][0]["sha256"]
        checkpoint.write_text(json.dumps(data))
        self.assertEqual(obj.tick(self.conn, now=100), [])

    def test_continuation_preserves_pause_and_explicit_permission(self):
        tid, checkpoint, data = self.continuation()
        obj.set_paused(self.conn, self.root, True)
        self.assertEqual(obj.tick(self.conn, now=100), [])
        obj.set_paused(self.conn, self.root, False)
        obj.report_blocker(self.conn, tid, "permission", "Await explicit approval")
        self.assertEqual(obj.tick(self.conn, now=100), [])
        self.assertEqual(kb.get_task(self.conn, tid).status, "blocked")

    def test_continuation_cannot_bypass_unfinished_prerequisite(self):
        tid, checkpoint, data = self.continuation()
        prerequisite = kb.create_task(self.conn, title="Actual prerequisite", creator_task_id=self.root)
        kb.link_tasks(self.conn, prerequisite, tid)
        self.assertEqual(obj.tick(self.conn, now=100), [])
        self.assertNotEqual(kb.get_task(self.conn, tid).status, "ready")

    def test_continuation_limit_is_durable_and_escalates_once(self):
        tid, checkpoint, data = self.continuation(limit=1)
        obj.tick(self.conn, now=100)
        kb.block_task(self.conn, tid, kind="transient", reason="More work")
        data["run_id"] = kb.list_runs(self.conn, tid)[-1].id
        data["completed"].append("new-progress")
        checkpoint.write_text(json.dumps(data))
        self.assertEqual(obj.tick(self.conn, now=100), [])
        self.assertEqual(obj.tick(self.conn, now=100), [])
        self.assertEqual(self.conn.execute("SELECT count(*) FROM task_events WHERE task_id=? AND kind='objective_continuation_exhausted'", (tid,)).fetchone()[0], 1)
        obj.tick(self.conn, now=1000)
        self.assertNotEqual(kb.get_task(self.conn, tid).status, "ready")

    def test_continuation_cannot_resume_after_inference_or_wrong_revision(self):
        tid, checkpoint, data = self.continuation()
        data["provider_calls"] = 1
        checkpoint.write_text(json.dumps(data))
        self.assertEqual(obj.tick(self.conn, now=100), [])
        data["provider_calls"] = 0
        data["revision"] += 1
        checkpoint.write_text(json.dumps(data))
        self.assertEqual(obj.tick(self.conn, now=100), [])

    def test_verified_progress_can_continue_native_internal_triage_without_erasing_history(self):
        tid, checkpoint, data = self.continuation(limit=4)
        for i in range(3):
            if i:
                kb.block_task(self.conn, tid, kind="transient", reason="Next verified slice")
                data["run_id"] = kb.list_runs(self.conn, tid)[-1].id
                data["completed"].append(f"slice-{i}")
                checkpoint.write_text(json.dumps(data))
            self.assertIn({"continued_internal_work": tid, "used": i + 1}, obj.tick(self.conn, now=100))
        self.assertEqual(kb.get_task(self.conn, tid).block_recurrences, 3)

    def test_missing_checkpoint_escalates_once_instead_of_silently_parking(self):
        tid, checkpoint, data = self.continuation()
        checkpoint.unlink()
        self.assertEqual(obj.tick(self.conn, now=100), [])
        self.assertEqual(obj.tick(self.conn, now=100), [])
        self.assertEqual(self.conn.execute("SELECT count(*) FROM task_events WHERE task_id=? AND kind='objective_continuation_rejected'", (tid,)).fetchone()[0], 1)
        checkpoint.write_text(json.dumps(data))
        self.assertIn({"continued_internal_work": tid, "used": 1}, obj.tick(self.conn, now=100))

    def test_owner_can_enroll_continuation_without_resetting_scientific_contract_or_retries(self):
        obj.tick(self.conn, now=100)
        tid = self.tasks()[0]["task"]
        before = dict(obj.contract(self.conn, tid))
        with kb.write_txn(self.conn):
            self.conn.execute("UPDATE objective_progress SET attempts=3 WHERE root=?", (self.root,))
        obj.configure_continuation(self.conn, tid, self.path / "outbox.json", 6)
        self.assertEqual(dict(obj.contract(self.conn, tid)), before)
        self.assertEqual(self.conn.execute("SELECT attempts FROM objective_progress WHERE root=?", (self.root,)).fetchone()[0], 3)
        self.assertIn(str(self.path / "outbox.json"), obj.worker_context(self.conn, tid))
        with self.assertRaises(ValueError):
            obj.configure_continuation(self.conn, self.root, self.path / "root.json", 6)
        with self.assertRaises(ValueError):
            obj.configure_continuation(self.conn, tid, self.path / "outbox.json", 100)

    def test_existing_prerequisite_can_be_adopted_but_unrelated_tasks_cannot(self):
        legacy = kb.create_task(self.conn, title="Existing implementation")
        unrelated = kb.create_task(self.conn, title="Unrelated task")
        obj.tick(self.conn, now=100)
        tid = self.tasks()[0]["task"]
        kb.link_tasks(self.conn, legacy, tid)
        self.assertIsNone(obj.contract(self.conn, legacy))
        checks = [{"kind": "file", "path": str(self.path / "implementation-proof.json")}]
        obj.configure_continuation(self.conn, legacy, self.path / "legacy.json", 2, member_of=tid, completion_checks=checks)
        self.assertEqual(obj.contract(self.conn, legacy)["root"], self.root)
        self.assertFalse(kb.complete_task(self.conn, legacy))
        (self.path / "implementation-proof.json").write_text("verified implementation scope")
        self.assertTrue(kb.complete_task(self.conn, legacy))
        self.assertFalse(kb.complete_task(self.conn, self.root))
        with self.assertRaises(ValueError):
            obj.configure_continuation(self.conn, unrelated, self.path / "unrelated.json", 2, member_of=tid)
        self.assertIsNone(obj.contract(self.conn, unrelated))

    def test_native_uncategorized_stop_requires_verified_explicit_internal_checkpoint(self):
        tid, checkpoint, data = self.continuation(kind=None)
        data["internal_work_remaining"] = False
        checkpoint.write_text(json.dumps(data))
        self.assertEqual(obj.tick(self.conn, now=100), [])
        data["internal_work_remaining"] = True
        checkpoint.write_text(json.dumps(data))
        self.assertIn({"continued_internal_work": tid, "used": 1}, obj.tick(self.conn, now=100))

    def test_native_uncategorized_triage_after_retries_continues_verified_work(self):
        tid, checkpoint, data = self.continuation(kind=None)
        with kb.write_txn(self.conn):
            self.conn.execute("UPDATE tasks SET status='triage' WHERE id=?", (tid,))
        self.assertFalse(obj.claim_allowed(self.conn, tid))
        self.assertIn({"continued_internal_work": tid, "used": 1}, obj.tick(self.conn, now=100))
        self.assertTrue(obj.claim_allowed(self.conn, tid))

    def test_native_iteration_exhaustion_uses_verified_finite_continuation(self):
        tid, checkpoint, data = self.continuation(kind=None)
        self.conn.execute("UPDATE task_runs SET status='gave_up', outcome='gave_up', error=?, metadata=? WHERE id=?",
                          ('Iteration budget exhausted (90/90) — task could not complete within the allowed iterations',
                           json.dumps({'trigger_outcome': 'timed_out', 'effective_limit': 1}), data['run_id']))
        self.assertFalse(obj.claim_allowed(self.conn, tid))
        self.assertIn({'continued_internal_work': tid, 'used': 1}, obj.tick(self.conn, now=100))
        self.assertTrue(obj.claim_allowed(self.conn, tid))
        self.assertEqual(kb.list_runs(self.conn, tid)[-1].status, 'gave_up')
        self.assertEqual(obj.tick(self.conn, now=100), [])
        self.assertFalse(self.conn.execute('SELECT 1 FROM objective_receipts WHERE task=?', (tid,)).fetchone())

    def test_arbitrary_gave_up_cannot_unblock_around_checkpoint_gate(self):
        tid, checkpoint, data = self.continuation(kind=None)
        self.conn.execute("UPDATE task_runs SET status='gave_up', outcome='gave_up', error=?, metadata=? WHERE id=?",
                          ('Provider rejected credentials', json.dumps({'trigger_outcome': 'timed_out'}), data['run_id']))
        self.assertEqual(obj.tick(self.conn, now=100), [])
        self.assertTrue(kb.unblock_task(self.conn, tid))
        self.assertFalse(obj.claim_allowed(self.conn, tid))

    def test_native_unblock_cannot_bypass_continuation_checkpoint_or_allowance(self):
        tid, checkpoint, data = self.continuation(limit=1, kind=None)
        self.assertTrue(kb.unblock_task(self.conn, tid))
        self.assertIsNone(kb.claim_task(self.conn, tid))
        self.assertIn({"continued_internal_work": tid, "used": 1}, obj.tick(self.conn, now=100))
        claim = kb.claim_task(self.conn, tid)
        self.assertIsNotNone(claim)
        kb.block_task(self.conn, tid, reason="Further coding remains", expected_run_id=claim.current_run_id)
        if kb.get_task(self.conn, tid).status == "blocked":
            kb.unblock_task(self.conn, tid)
        data["run_id"] = kb.list_runs(self.conn, tid)[-1].id
        data["completed"].append("another-verified-slice")
        checkpoint.write_text(json.dumps(data))
        self.assertEqual(obj.tick(self.conn, now=100), [])
        self.assertIsNone(kb.claim_task(self.conn, tid))

    def test_checkpoint_owned_triage_cannot_spawn_a_new_graph_or_call_decomposer(self):
        from hermes_cli import kanban_decompose
        from hermes_cli.kanban_db_graph import decompose_triage_task
        tid, checkpoint, data = self.continuation(kind=None)
        with kb.write_txn(self.conn):
            self.conn.execute("UPDATE tasks SET status='triage' WHERE id=?", (tid,))
        before = self.conn.execute("SELECT count(*) FROM tasks").fetchone()[0]
        self.assertIsNone(decompose_triage_task(self.conn, tid, root_assignee="default", children=[{"title": "Unwanted replan", "assignee": "default"}]))
        with patch.object(kanban_decompose, "_call_aux") as aux:
            result = kanban_decompose.decompose_task(tid)
            self.assertFalse(result.ok)
            aux.assert_not_called()
        self.assertEqual(self.conn.execute("SELECT count(*) FROM tasks").fetchone()[0], before)

    def test_unrelated_triage_keeps_native_decomposition(self):
        from hermes_cli.kanban_db_graph import decompose_triage_task
        tid = kb.create_task(self.conn, title="Unrelated work", triage=True)
        children = decompose_triage_task(self.conn, tid, root_assignee="default", children=[{"title": "Legitimate subtask", "assignee": "default"}])
        self.assertEqual(len(children), 1)

    def test_empty_raw_logs_are_retained_with_exact_hash_but_cannot_replace_evidence(self):
        tid, checkpoint, data = self.continuation(kind=None)
        empty = self.path / "stdout.log"
        empty.write_bytes(b"")
        entry = {"path": str(empty), "sha256": obj.hashlib.sha256(b"").hexdigest()}
        data["artifacts"].append(entry)
        checkpoint.write_text(json.dumps(data))
        self.assertIn({"continued_internal_work": tid, "used": 1}, obj.tick(self.conn, now=100))
        event = self.conn.execute("SELECT payload FROM task_events WHERE task_id=? AND kind='objective_continued'", (tid,)).fetchone()
        self.assertIn({**entry, "bytes": 0}, json.loads(event[0])["evidence"])
        with self.assertRaises(ValueError):
            data["artifacts"] = [entry]
            checkpoint.write_text(json.dumps(data))
            obj._continuation_checkpoint(checkpoint, tid, data["run_id"], data["revision"], [])

    def test_empty_sources_or_test_reports_are_still_rejected(self):
        tid, checkpoint, data = self.continuation(kind=None)
        source = Path(data["sources"][0]["path"])
        source.write_bytes(b"")
        data["sources"][0]["sha256"] = obj.hashlib.sha256(b"").hexdigest()
        checkpoint.write_text(json.dumps(data))
        self.assertEqual(obj.tick(self.conn, now=100), [])
        source.write_text("changed implementation")
        data["sources"][0]["sha256"] = obj.hashlib.sha256(source.read_bytes()).hexdigest()
        report = Path(data["test_reports"][0]["path"])
        report.write_bytes(b"")
        data["test_reports"][0]["sha256"] = obj.hashlib.sha256(b"").hexdigest()
        data["artifacts"][0]["sha256"] = data["test_reports"][0]["sha256"]
        checkpoint.write_text(json.dumps(data))
        self.assertEqual(obj.tick(self.conn, now=100), [])


if __name__ == "__main__":
    unittest.main()
