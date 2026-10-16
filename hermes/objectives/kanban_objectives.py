"""Evidence-driven project supervision at Hermes' shared Kanban boundary.

Contracts and receipts live in the board DB. This is a cooperative workflow
guard, not a sandbox against a process with direct SQLite/filesystem access.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import subprocess
import time
import xml.etree.ElementTree as ET

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS objective_contracts (root TEXT PRIMARY KEY, revision INTEGER NOT NULL, digest TEXT NOT NULL, spec TEXT NOT NULL, paused INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS objective_members (task TEXT PRIMARY KEY, root TEXT NOT NULL, stage TEXT)",
    "CREATE TABLE IF NOT EXISTS objective_receipts (task TEXT PRIMARY KEY, revision INTEGER NOT NULL, digest TEXT NOT NULL, evidence TEXT NOT NULL, accepted_at INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS objective_blockers (task TEXT PRIMARY KEY, kind TEXT NOT NULL, reason TEXT NOT NULL, repair TEXT, resolved INTEGER NOT NULL DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS objective_progress (root TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, changed_at INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS objective_work_specs (task TEXT PRIMARY KEY, revision INTEGER NOT NULL, spec TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS objective_policy (id INTEGER PRIMARY KEY CHECK(id=1), require_contract_since INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS objective_contract_requests (task TEXT PRIMARY KEY, root TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS objective_paused_runs (task TEXT PRIMARY KEY, root TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS objective_continuations (task TEXT PRIMARY KEY, used INTEGER NOT NULL, run_id INTEGER NOT NULL, checkpoint_sha TEXT NOT NULL, completed TEXT NOT NULL, next_action TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS objective_continuation_policies (task TEXT PRIMARY KEY, root TEXT NOT NULL, checkpoint TEXT NOT NULL, max_runs INTEGER NOT NULL)",
)
KINDS = {"missing_artifact", "internal_repair", "transient", "dependency", "external_input", "permission"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def ensure(conn):
    # Never executescript: it would commit the caller's transition transaction.
    for statement in SCHEMA:
        conn.execute(statement)


def contract(conn, task_id):
    ensure(conn)
    return conn.execute(
        "SELECT c.*, m.stage FROM objective_members m JOIN objective_contracts c ON c.root=m.root WHERE m.task=?",
        (task_id,),
    ).fetchone()


def validate_check(check):
    if isinstance(check, dict) and check.get("kind") == "command":
        argv = check.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv) or not Path(argv[0]).is_absolute():
            raise ValueError("verifier argv requires an absolute executable and string arguments")
        if not Path(check.get("cwd", "")).is_absolute() or not 1 <= check.get("timeout", 10) <= 10:
            raise ValueError("verifier cwd must be absolute and timeout between 1 and 10 seconds")
        for arg in argv[1:]:
            if Path(arg).is_absolute() and Path(arg).suffix in {".py", ".sh"} and arg not in check.get("source_hashes", {}):
                raise ValueError("verifier script must be pinned in source_hashes")
        return
    if not isinstance(check, dict) or not Path(check.get("path", "")).is_absolute():
        raise ValueError("evidence paths must be absolute")
    if check.get("kind") not in {"file", "json"}:
        raise ValueError("check kind must be file or json")
    if check["kind"] == "json" and not check.get("assertions"):
        raise ValueError("JSON checks require assertions")
    for assertion in check.get("assertions", []):
        if assertion.get("op") not in {"eq", "ge", "gt", "le", "lt", "count_ge", "nonempty"}:
            raise ValueError("unsupported assertion operator")
        if not isinstance(assertion.get("key"), str):
            raise ValueError("assertion key must be a dotted JSON path")


def validate(spec):
    if spec.get("schema") != 1 or not spec.get("objective") or not spec.get("owner"):
        raise ValueError("schema=1, objective and owner are required")
    if not spec.get("stages") or not spec.get("checks"):
        raise ValueError("contracts need executable stages and final outcome checks")
    ids = [s.get("id") for s in spec["stages"]]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("stage IDs must be unique nonempty strings")
    for stage in spec["stages"]:
        if not stage.get("title") or not stage.get("body") or not stage.get("checks"):
            raise ValueError("every stage needs title, body and evidence checks")
        if stage.get("workspace_kind", "dir") != "scratch" and not Path(stage.get("workspace_path", "")).is_absolute():
            raise ValueError("persistent stage workspaces must be absolute")
        if any(p not in ids for p in stage.get("after", [])):
            raise ValueError("unknown stage prerequisite")
        for check in stage["checks"]:
            validate_check(check)
    for check in spec["checks"]:
        validate_check(check)
    if sum(c.get("timeout", 10) for s in spec["stages"] for c in s["checks"] if c["kind"] == "command") + sum(c.get("timeout", 10) for c in spec["checks"] if c["kind"] == "command") > 10:
        raise ValueError("total verifier timeout budget must not exceed 10 seconds")
    # Topological validation before changing a real board.
    seen = set()
    while len(seen) < len(ids):
        ready = {s["id"] for s in spec["stages"] if set(s.get("after", [])) <= seen}
        if ready <= seen:
            raise ValueError("stage dependency cycle")
        seen |= ready
    if not 60 <= spec.get("stale_seconds", 1800) <= 86400:
        raise ValueError("stale_seconds must be between 60 and 86400")
    if not 0 <= spec.get("max_repairs", 2) <= 5:
        raise ValueError("max_repairs must be between 0 and 5")
    continuations = spec.get("continuations", [])
    tasks = [c.get("task_id") for c in continuations]
    if len(tasks) != len(set(tasks)):
        raise ValueError("continuation tasks must be unique")
    for policy in continuations:
        if not policy.get("task_id") or not Path(policy.get("checkpoint", "")).is_absolute():
            raise ValueError("continuation task and absolute checkpoint required")
        if type(policy.get("max_runs")) is not int or not 1 <= policy["max_runs"] <= 8:
            raise ValueError("continuation allowance must be between one and eight runs")


def enroll(conn, root, spec):
    from hermes_cli import kanban_db as kb
    validate(spec)
    if not kb.get_task(conn, root):
        raise ValueError("unknown root task")
    with kb.write_txn(conn):
        ensure(conn)
        old = conn.execute("SELECT * FROM objective_contracts WHERE root=?", (root,)).fetchone()
        revision = (old["revision"] if old else 0) + 1
        fingerprint = digest(spec)
        if old and old["digest"] == fingerprint:
            return old["revision"]
        conn.execute(
            "INSERT INTO objective_contracts(root,revision,digest,spec,created_at) VALUES(?,?,?,?,?) ON CONFLICT(root) DO UPDATE SET revision=excluded.revision,digest=excluded.digest,spec=excluded.spec,created_at=excluded.created_at",
            (root, revision, fingerprint, canonical(spec), int(time.time())),
        )
        conn.execute("INSERT OR REPLACE INTO objective_members VALUES(?,?,NULL)", (root, root))
        conn.execute("DELETE FROM objective_progress WHERE root=?", (root,))
        kb._append_event(conn, root, "objective_enrolled", {"revision": revision, "digest": fingerprint})
    return revision


def inherit(conn, task_id, parents=(), creator=None):
    """Creator/dependency links propagate the contract, independently of prompts."""
    ensure(conn)
    roots = {r["root"] for p in (*parents, creator) if p for r in
             conn.execute("SELECT root FROM objective_members WHERE task=?", (p,))}
    if len(roots) > 1:
        raise ValueError("cross-objective task requires explicit contract ownership")
    if roots:
        conn.execute("INSERT OR IGNORE INTO objective_members VALUES(?,?,NULL)", (task_id, roots.pop()))


def lookup(value, key):
    for part in key.split(".") if key else []:
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def check_evidence(checks, since=0, *, execute=True):
    failures, evidence = [], []
    for check in checks:
        if check["kind"] == "command":
            if not execute:
                continue
            try:
                for source, expected in check.get("source_hashes", {}).items():
                    if hashlib.sha256(Path(source).read_bytes()).hexdigest() != expected:
                        raise ValueError(f"verifier source hash mismatch: {source}")
                completed = subprocess.run(check["argv"], cwd=check["cwd"], capture_output=True, timeout=check.get("timeout", 10), check=False)
                if completed.returncode != 0:
                    raise ValueError(f"verifier exit {completed.returncode}: {completed.stderr.decode(errors='replace')[-1000:]}")
                evidence.append({"argv": check["argv"], "source_hashes": check.get("source_hashes", {}), "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest()})
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                failures.append(str(exc))
            continue
        path = Path(check["path"])
        try:
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError("missing or empty evidence")
            if path.stat().st_size > 25 * 1024 * 1024:
                raise ValueError("evidence exceeds 25 MiB; use a bounded manifest")
            raw = path.read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            if check.get("sha256") and sha != check["sha256"]:
                raise ValueError("evidence hash mismatch")
            if check.get("fresh", True) and path.stat().st_mtime < since:
                raise ValueError("evidence predates the current contract")
            if check["kind"] == "json":
                value = json.loads(raw, parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
                for rule in check["assertions"]:
                    actual = lookup(value, rule["key"])
                    op, expected = rule["op"], rule.get("value")
                    if op in {"ge", "gt", "le", "lt"}:
                        if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual):
                            raise ValueError(f"{rule['key']}: finite number required")
                        ok = {"ge": lambda: actual >= expected, "gt": lambda: actual > expected,
                              "le": lambda: actual <= expected, "lt": lambda: actual < expected}[op]()
                    elif op == "count_ge":
                        ok = isinstance(actual, (list, dict)) and len(actual) >= expected
                    elif op == "nonempty":
                        ok = isinstance(actual, (str, list, dict)) and len(actual) > 0
                    else:
                        ok = type(actual) is type(expected) and actual == expected
                    if not ok:
                        raise ValueError(f"{rule['key']}: {op} {expected!r} failed (actual={actual!r})")
            evidence.append({"path": str(path), "sha256": sha})
        except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            failures.append(f"{path}: {exc}")
    return failures, evidence


def acceptance(conn, task_id):
    """Called under the completion transaction; fail closed for enrolled tasks."""
    from hermes_cli import kanban_db as kb
    ensure(conn)
    request = conn.execute("SELECT root FROM objective_contract_requests WHERE task=?", (task_id,)).fetchone()
    if request and not contract(conn, request[0]):
        kb._append_event(conn, task_id, "objective_acceptance_rejected", {"failures": ["Required objective contract has not been enrolled"]})
        return False
    row = contract(conn, task_id)
    if not row:
        policy = conn.execute("SELECT require_contract_since FROM objective_policy WHERE id=1").fetchone()
        task = kb.get_task(conn, task_id)
        if policy and task.goal_mode and task.created_at >= policy[0]:
            kb._append_event(conn, task_id, "objective_acceptance_rejected", {"failures": ["New goal requires a versioned objective contract; run hermes-objectives enroll"]})
            conn.execute("UPDATE tasks SET last_failure_error=? WHERE id=?", ("Objective acceptance refused: enroll the required versioned objective contract using hermes-objectives enroll.", task_id))
            return False
        return True
    spec = json.loads(row["spec"])
    validate(spec)
    stage = next((s for s in spec["stages"] if s["id"] == row["stage"]), None)
    work = conn.execute("SELECT * FROM objective_work_specs WHERE task=?", (task_id,)).fetchone()
    if work and not stage:
        stage = json.loads(work["spec"])
    checks = stage["checks"] if stage else spec["checks"]
    failures, evidence = check_evidence(checks, row["created_at"])
    if work and work["revision"] != row["revision"]:
        failures.append("task was specified for an older objective revision")
    if row["paused"]:
        failures.append("objective is owner-paused")
    if task_id == row["root"]:
        for s in spec["stages"]:
            receipt = conn.execute(
                "SELECT r.task FROM objective_receipts r JOIN objective_members m ON m.task=r.task JOIN tasks t ON t.id=r.task WHERE m.root=? AND m.stage=? AND r.revision=? AND r.digest=? AND t.status='done'",
                (row["root"], s["id"], row["revision"], row["digest"]),
            ).fetchone()
            errors, artifacts = check_evidence(s["checks"], row["created_at"])
            failures.extend(errors)
            evidence.extend(artifacts)
            if not receipt:
                failures.append(f"stage {s['id']}: current-revision acceptance receipt missing")
    if failures:
        kb._append_event(conn, task_id, "objective_acceptance_rejected", {"revision": row["revision"], "failures": failures})
        conn.execute("UPDATE tasks SET last_failure_error=? WHERE id=?", ("Objective acceptance refused; implement/repair the missing evidence: " + "; ".join(failures)[:2000], task_id))
        return False
    previous = conn.execute("SELECT * FROM objective_receipts WHERE task=?", (task_id,)).fetchone()
    if not previous or previous["revision"] != row["revision"] or previous["digest"] != row["digest"] or previous["evidence"] != canonical(evidence):
        conn.execute("INSERT OR REPLACE INTO objective_receipts VALUES(?,?,?,?,?)",
                     (task_id, row["revision"], row["digest"], canonical(evidence), int(time.time())))
        kb._append_event(conn, task_id, "objective_acceptance_passed", {"revision": row["revision"], "evidence": evidence})
    return True


def worker_context(conn, task_id):
    from hermes_cli import kanban_db as kb
    row = contract(conn, task_id)
    if not row:
        return ""
    spec = json.loads(row["spec"])
    stage = next((s for s in spec["stages"] if s["id"] == row["stage"]), None)
    work = conn.execute("SELECT spec FROM objective_work_specs WHERE task=?", (task_id,)).fetchone()
    if work and not stage:
        stage = json.loads(work["spec"])
    continuation = next((c for c in continuation_policies(conn, row, spec) if c["task_id"] == task_id), None)
    previous = conn.execute("SELECT * FROM objective_continuations WHERE task=?", (task_id,)).fetchone()
    task = kb.get_task(conn, task_id)
    return "\n## Current objective contract\n" + canonical({
        "root": row["root"], "revision": row["revision"], "digest": row["digest"],
        "objective": spec["objective"], "scope": spec.get("scope"), "constraints": spec.get("constraints", []),
        "stage": stage, "final_checks": spec["checks"], "paused": bool(row["paused"]),
        "continuation": continuation, "last_continuation": dict(previous) if previous else None,
        "current_run_id": task.current_run_id,
    }) + "\nCompletion is evidence-gated. Report blockers using hermes-objectives block; internal gaps require assigned corrective work. Read the latest contract before lifecycle handoff.\n"


def claim_allowed(conn, task_id):
    from hermes_cli import kanban_db as kb
    row = contract(conn, task_id)
    if row:
        if row["paused"]:
            return False
        policies = continuation_policies(conn, row, json.loads(row["spec"]))
        policy = next((c for c in policies if c["task_id"] == task_id), None)
        if policy:
            runs = kb.list_runs(conn, task_id)
            if runs and runs[-1].status in {"blocked", "timed_out", "gave_up"}:
                used = conn.execute("SELECT used,run_id FROM objective_continuations WHERE task=?", (task_id,)).fetchone()
                # Native automatic unblock must not skip the checkpoint gate.
                if not used or used["run_id"] != runs[-1].id or used["used"] > policy["max_runs"]:
                    return False
        return True
    policy = conn.execute("SELECT require_contract_since FROM objective_policy WHERE id=1").fetchone()
    task = kb.get_task(conn, task_id)
    return not (policy and task and task.goal_mode and task.created_at >= policy[0])


def set_paused(conn, task_id, paused):
    from hermes_cli import kanban_db as kb
    row = contract(conn, task_id)
    if not row:
        raise ValueError("unknown objective")
    with kb.write_txn(conn):
        conn.execute("UPDATE objective_contracts SET paused=? WHERE root=?", (int(paused), row["root"]))
        kb._append_event(conn, row["root"], "objective_pause" if paused else "objective_resume", {})
    if paused:
        for member in conn.execute("SELECT task FROM objective_members WHERE root=?", (row["root"],)).fetchall():
            task = kb.get_task(conn, member[0])
            if task.status == "running" and kb.block_task(conn, task.id, reason="Objective owner paused execution", kind="needs_input", expected_run_id=task.current_run_id):
                with kb.write_txn(conn):
                    conn.execute("INSERT OR IGNORE INTO objective_paused_runs VALUES(?,?)", (task.id, row["root"]))
                kb._terminate_reclaimed_worker(task.worker_pid, task.claim_lock)
    else:
        for member in conn.execute("SELECT task FROM objective_paused_runs WHERE root=?", (row["root"],)).fetchall():
            _wake(conn, member[0])
        with kb.write_txn(conn):
            conn.execute("DELETE FROM objective_paused_runs WHERE root=?", (row["root"],))


def report_blocker(conn, task_id, kind, reason, repair=None):
    from hermes_cli import kanban_db as kb
    if kind not in KINDS or not reason:
        raise ValueError("typed blocker and reason required")
    if not contract(conn, task_id):
        raise ValueError("task is not enrolled in an objective")
    if kind == "dependency":
        if not repair or not kb.get_task(conn, repair.get("task_id", "")):
            raise ValueError("dependency requires an existing prerequisite task_id")
    if kind in {"missing_artifact", "internal_repair", "transient"}:
        if not repair or not repair.get("body") or not repair.get("checks"):
            raise ValueError("internal blockers require a concrete repair spec and evidence checks")
        for check in repair["checks"]:
            validate_check(check)
        if sum(c.get("timeout", 10) for c in repair["checks"] if c["kind"] == "command") > 10:
            raise ValueError("repair verifier timeout budget must not exceed ten seconds")
        repair = dict(repair)
        task = kb.get_task(conn, task_id)
        repair.setdefault("workspace_kind", task.workspace_kind)
        repair.setdefault("workspace_path", task.workspace_path)
    with kb.write_txn(conn):
        conn.execute("INSERT OR REPLACE INTO objective_blockers VALUES(?,?,?,?,0)",
                     (task_id, kind, reason, canonical(repair) if repair else None))
        kb._append_event(conn, task_id, "objective_blocker_reported", {"kind": kind, "reason": reason})
    task = kb.get_task(conn, task_id)
    if task.status in {"ready", "running"}:
        kb.block_task(conn, task_id, reason=reason, kind="needs_input" if kind in {"external_input", "permission"} else "capability", expected_run_id=task.current_run_id)


def _create(conn, row, stage, *, key, parents=()):
    from hermes_cli import kanban_db as kb
    spec = json.loads(row["spec"])
    # Outer write transaction closes upstream's best-effort idempotency race.
    with kb.write_txn(conn):
        task_id = stage.get("task_id")
        if task_id:
            task = kb.get_task(conn, task_id)
            if not task or task_id == row["root"] or task.status == "archived":
                raise ValueError("adopted stage must be an existing active non-root task")
            prior = conn.execute("SELECT root FROM objective_members WHERE task=?", (task_id,)).fetchone()
            if prior and prior[0] != row["root"]:
                raise ValueError("task already belongs to another objective")
            for parent in parents:
                if kb._would_cycle(conn, parent, task_id):
                    raise ValueError("adopted task prerequisite would create a cycle")
                kb._link(conn, parent, task_id)
        else:
            task_id = kb.create_task(conn, title=stage["title"], body=stage["body"],
            assignee=stage.get("assignee", spec["owner"]), created_by="objective-supervisor",
            workspace_kind=stage.get("workspace_kind", "dir"), workspace_path=stage.get("workspace_path"),
            parents=parents, idempotency_key=key, creator_task_id=row["root"],
            model_override=stage.get("model_override", spec.get("model_override")),
            provider_override=stage.get("provider_override", spec.get("provider_override")),
            max_runtime_seconds=stage.get("max_runtime_seconds", 1800), max_retries=2,
            goal_mode=True, goal_max_turns=stage.get("goal_max_turns", 20))
        conn.execute("INSERT OR REPLACE INTO objective_members VALUES(?,?,?)", (task_id, row["root"], stage["id"]))
        if stage.get("task_id"):
            conn.execute("INSERT OR REPLACE INTO objective_work_specs VALUES(?,?,?)", (task_id, row["revision"], canonical(stage)))
        else:
            conn.execute("INSERT OR IGNORE INTO objective_work_specs VALUES(?,?,?)", (task_id, row["revision"], canonical(stage)))
    return task_id


def reopen_for_repair(conn, task_id, reason):
    """Owner-supervisor API for a completed implementation rejected by evidence.

    Keeps previous run/results as evidence, re-gates dependent work, and gives
    the SAME implementation card back to its implementer.
    """
    from hermes_cli import kanban_db as kb
    with kb.write_txn(conn):
        ensure(conn)
        status = kb._landing_status_after_parents(conn, task_id)
        changed = conn.execute("UPDATE tasks SET status=?, completed_at=NULL, current_run_id=NULL, claim_lock=NULL, claim_expires=NULL, worker_pid=NULL WHERE id=? AND status='done'", (status, task_id)).rowcount
        if not changed:
            return False
        conn.execute("DELETE FROM objective_receipts WHERE task=?", (task_id,))
        kb._append_event(conn, task_id, "objective_implementation_rejected", {"reason": reason, "status": status})
        # Native recent-success protection recognizes explicit lifecycle requeues.
        # Keep the completed run and all failure counters; record the owner action.
        kb._append_event(conn, task_id, "status", {"status": status, "source": "objective_reopen_for_repair"})
        kb._insert_comment(conn, task_id, "objective-supervisor", "Corrective implementation required: " + reason, int(time.time()))
    kb.invalidate_descendants_for_parent_reopen(conn, task_id, author="objective-supervisor")
    kb.recompute_ready(conn)
    return True


def _wake(conn, task_id):
    from hermes_cli import kanban_db as kb
    task = kb.get_task(conn, task_id)
    if task.status == "triage":
        kb.specify_triage_task(conn, task_id, assignee=task.assignee, author="objective-supervisor")
    elif task.status == "blocked":
        kb.unblock_task(conn, task_id)


def continuation_policies(conn, row, spec):
    policies = {c["task_id"]: c for c in spec.get("continuations", [])}
    for policy in conn.execute("SELECT * FROM objective_continuation_policies WHERE root=?", (row["root"],)):
        policies[policy["task"]] = {"task_id": policy["task"], "checkpoint": policy["checkpoint"], "max_runs": policy["max_runs"]}
    return list(policies.values())


def decomposition_allowed(conn, task_id):
    """Checkpoint-owned implementation stays on its existing card."""
    row = contract(conn, task_id)
    return not (row and any(p["task_id"] == task_id for p in continuation_policies(conn, row, json.loads(row["spec"]))))


def configure_continuation(conn, task_id, checkpoint, max_runs, member_of=None, completion_checks=None):
    """Owner maintenance of offline continuation, separate from science contracts."""
    from hermes_cli import kanban_db as kb
    if not Path(checkpoint).is_absolute() or type(max_runs) is not int or not 1 <= max_runs <= 8:
        raise ValueError("absolute checkpoint and finite one-to-eight run allowance required")
    row = contract(conn, task_id)
    if not row and member_of:
        anchor = contract(conn, member_of)
        if not anchor or task_id not in kb.parent_ids(conn, member_of):
            raise ValueError("existing child adoption requires an enrolled task that depends on it")
        if not completion_checks:
            raise ValueError("adopted implementation requires its own scoped completion checks")
        for check in completion_checks:
            validate_check(check)
        if sum(c.get("timeout", 10) for c in completion_checks if c["kind"] == "command") > 10:
            raise ValueError("continuation completion verifier budget exceeds ten seconds")
        with kb.write_txn(conn):
            inherit(conn, task_id, creator=member_of)
            task = kb.get_task(conn, task_id)
            work = {"id": "continuation:" + task_id, "title": task.title, "body": task.body,
                    "checks": completion_checks, "workspace_kind": task.workspace_kind,
                    "workspace_path": task.workspace_path}
            conn.execute("INSERT OR REPLACE INTO objective_work_specs VALUES(?,?,?)", (task_id, anchor["revision"], canonical(work)))
            kb._append_event(conn, task_id, "objective_existing_child_adopted", {"member_of": member_of, "root": anchor["root"]})
        row = contract(conn, task_id)
    if not row or task_id == row["root"]:
        raise ValueError("continuation requires an existing objective implementation member")
    with kb.write_txn(conn):
        conn.execute("INSERT INTO objective_continuation_policies VALUES(?,?,?,?) ON CONFLICT(task) DO UPDATE SET checkpoint=excluded.checkpoint,max_runs=excluded.max_runs",
                     (task_id, row["root"], str(checkpoint), max_runs))
        kb._append_event(conn, task_id, "objective_continuation_configured", {"checkpoint": str(checkpoint), "max_runs": max_runs, "scientific_contract_revision": row["revision"], "budgets_changed": False})


def _continuation_checkpoint(path, task_id, run_id, revision, previous):
    """A file outbox works even when delegated workers cannot mutate the board.

    This checks checkpoint integrity and executed regressions, not whether a
    milestone description is semantically true. Completion has separate gates.
    """
    path = Path(path)
    raw = path.read_bytes()
    data = json.loads(raw)
    if (data.get("schema") != 1 or data.get("task_id") != task_id
            or type(data.get("run_id")) is not int or data["run_id"] != run_id
            or data.get("revision") != revision or data.get("provider_calls") != 0
            or type(data.get("provider_calls")) is not int
            or data.get("internal_work_remaining") is not True
            or not isinstance(data.get("next_action"), str) or not data["next_action"].strip()):
        raise ValueError("checkpoint requires current run/revision, offline work and a concrete next action")
    completed = data.get("completed", [])
    if (not isinstance(completed, list) or not completed
            or not all(isinstance(c, str) and c.strip() for c in completed)
            or len(set(completed)) != len(completed)
            or not set(previous) < set(completed)):
        raise ValueError("continuation requires a new completed milestone; comments alone cannot resume work")
    evidence = []
    for key in ("sources", "artifacts", "test_reports"):
        entries = data.get(key, [])
        if not isinstance(entries, list) or not entries:
            raise ValueError("checkpoint needs sources, raw artifacts and executed JUnit reports")
        for entry in entries:
            check = {"kind": "file", "path": entry["path"], "sha256": entry["sha256"], "fresh": False}
            validate_check(check)
            # Empty stdout and lock files are genuine retained raw artifacts.
            # Preserve their explicit empty-byte hash without treating them as
            # evidence of successful execution. Source and test files must
            # still be nonempty, and the raw evidence set cannot be all empty.
            artifact = Path(entry["path"])
            if (key == "artifacts" and entry["sha256"] == hashlib.sha256(b"").hexdigest()
                    and artifact.is_file() and artifact.read_bytes() == b""):
                evidence.append({"path": str(artifact), "sha256": entry["sha256"], "bytes": 0})
                continue
            errors, bound = check_evidence([check])
            if errors:
                raise ValueError("; ".join(errors))
            evidence.extend(bound)
    if not any(Path(entry["path"]).stat().st_size > 0 for entry in data["artifacts"]):
        raise ValueError("nonempty raw continuation evidence required; empty files do not establish progress")
    executed = 0
    for entry in data["test_reports"]:
        for case in ET.parse(entry["path"]).iter("testcase"):
            if case.find("failure") is not None or case.find("error") is not None:
                raise ValueError("continuation regression failed")
            if case.find("skipped") is None:
                executed += 1
    if not executed:
        raise ValueError("no executed continuation regressions")
    return data, hashlib.sha256(raw).hexdigest(), evidence


def _continuable_run(run):
    if run.status in {"blocked", "timed_out"}:
        return True
    # The native iteration limiter closes these runs as gave_up after the
    # configured retry allowance. Only the explicit checkpoint policy can
    # supply another bounded slice; other gave_up reasons remain terminal.
    return (run.status == "gave_up" and isinstance(run.metadata, dict)
            and run.metadata.get("trigger_outcome") == "timed_out"
            and isinstance(run.error, str)
            and run.error.startswith("Iteration budget exhausted ("))


def _continue_internal_work(conn, row, spec):
    """Consume bounded, owner-enrolled continuation handoffs once per run.

    Preserves pauses, blockers, dependencies, scientific gates and historical
    retry counters. A checkpoint never marks a task or its dependents complete.
    """
    from hermes_cli import kanban_db as kb
    actions = []
    for policy in continuation_policies(conn, row, spec):
        tid = policy["task_id"]
        member = contract(conn, tid)
        task = kb.get_task(conn, tid)
        if (not member or member["root"] != row["root"] or not task
                or task.status not in {"blocked", "triage", "ready"}
                or task.block_kind not in {"transient", "capability", None}):
            continue
        if conn.execute("SELECT 1 FROM objective_blockers WHERE task=? AND resolved=0", (tid,)).fetchone():
            continue
        runs = kb.list_runs(conn, tid)
        if not runs or not _continuable_run(runs[-1]):
            continue
        run = runs[-1]
        prior = conn.execute("SELECT * FROM objective_continuations WHERE task=?", (tid,)).fetchone()
        if prior and prior["run_id"] == run.id:
            continue
        used = prior["used"] if prior else 0
        if used >= policy["max_runs"]:
            # One durable escalation per stopped run; do not spin or add cards.
            kind = "objective_continuation_exhausted"
            if not conn.execute("SELECT 1 FROM task_events WHERE task_id=? AND kind=? AND run_id=?", (tid, kind, run.id)).fetchone():
                with kb.write_txn(conn):
                    kb._append_event(conn, tid, kind, {"used": used, "limit": policy["max_runs"], "next_step": "owner must inspect the retained checkpoint and narrow/replan the work"}, run_id=run.id)
                    kb._insert_comment(conn, row["root"], "objective-supervisor", f"Continuation allowance exhausted for {tid}; inspect its checkpoint and replan. Task remains incomplete; no scientific budget or permission was changed.", int(time.time()))
            continue
        try:
            data, checkpoint_sha, evidence = _continuation_checkpoint(policy["checkpoint"], tid, run.id, row["revision"], json.loads(prior["completed"]) if prior else [])
        except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as error:
            kind = "objective_continuation_rejected"
            if not conn.execute("SELECT 1 FROM task_events WHERE task_id=? AND kind=? AND run_id=?", (tid, kind, run.id)).fetchone():
                with kb.write_txn(conn):
                    kb._append_event(conn, tid, kind, {"checkpoint": policy["checkpoint"], "reason": str(error)[:2000]}, run_id=run.id)
                    kb._insert_comment(conn, row["root"], "objective-supervisor", f"Internal continuation for {tid} needs a valid checkpoint: {str(error)[:1000]}. Retain evidence, repair the handoff or replan; task is not complete.", int(time.time()))
            continue
        with kb.write_txn(conn):
            latest = kb.list_runs(conn, tid)
            current = kb.get_task(conn, tid)
            consumed = conn.execute("SELECT * FROM objective_continuations WHERE task=?", (tid,)).fetchone()
            current_contract = contract(conn, tid)
            if (current.status not in {"blocked", "triage", "ready"} or latest[-1].id != run.id
                    or current.block_kind not in {"transient", "capability", None}
                    or current_contract["paused"] or current_contract["revision"] != row["revision"]
                    or conn.execute("SELECT 1 FROM objective_blockers WHERE task=? AND resolved=0", (tid,)).fetchone()
                    or (consumed["used"] if consumed else 0) != used
                    or kb._landing_status_after_parents(conn, tid) != "ready"):
                continue
            conn.execute("INSERT INTO objective_continuations VALUES(?,?,?,?,?,?) ON CONFLICT(task) DO UPDATE SET used=excluded.used,run_id=excluded.run_id,checkpoint_sha=excluded.checkpoint_sha,completed=excluded.completed,next_action=excluded.next_action",
                         (tid, used + 1, run.id, checkpoint_sha, canonical(data["completed"]), data["next_action"]))
            conn.execute("UPDATE tasks SET status='ready',current_run_id=NULL,consecutive_failures=0,last_failure_error=NULL WHERE id=? AND status IN ('blocked','triage','ready')", (tid,))
            kb._append_event(conn, tid, "objective_continued", {"used": used + 1, "limit": policy["max_runs"], "checkpoint_sha": checkpoint_sha, "evidence": evidence, "next_action": data["next_action"]}, run_id=run.id)
        actions.append({"continued_internal_work": tid, "used": used + 1})
    return actions


def tick(conn, *, now=None):
    """Deterministic bounded repair, based on evidence progress, not card count."""
    from hermes_cli import kanban_db as kb
    ensure(conn)
    now = int(time.time()) if now is None else now
    actions = []
    policy = conn.execute("SELECT require_contract_since FROM objective_policy WHERE id=1").fetchone()
    if policy:
        for task in conn.execute("SELECT t.* FROM tasks t LEFT JOIN objective_members m ON m.task=t.id WHERE t.goal_mode=1 AND t.created_at>=? AND m.task IS NULL AND t.status IN ('ready','running','triage','todo')", (policy[0],)).fetchall():
            # A concrete contract-acquisition task rather than silent deferral.
            # Independent of the root so it can run while the root is waiting.
            with kb.write_txn(conn):
                tid = kb.create_task(conn, title="Define measurable objective: " + task["title"][:120],
                    body=f"Read task {task['id']} and its user-authorized scope. Write a schema=1 objective contract with concrete implementation/acquisition stages, absolute evidence paths, deterministic verifier commands where needed, and final user-outcome checks. Preserve all existing permissions/budgets; do not introduce external sends. Enroll it using hermes-objectives enroll {task['id']} CONTRACT.json. Do not claim the original objective complete from infrastructure tests. Original specification:\n{task['body'] or ''}",
                    assignee=task["assignee"] or "default", created_by="objective-supervisor",
                    workspace_kind=task["workspace_kind"], workspace_path=task["workspace_path"],
                    model_override=task["model_override"], provider_override=task["provider_override"],
                    max_runtime_seconds=600, max_retries=1, idempotency_key=f"objective:contract:{task['id']}")
                conn.execute("INSERT OR IGNORE INTO objective_contract_requests VALUES(?,?)", (tid, task["id"]))
                if tid not in kb.parent_ids(conn, task["id"]):
                    kb._link(conn, tid, task["id"])
                    actions.append({"contract_acquisition": tid, "root": task["id"]})
    for row in conn.execute("SELECT * FROM objective_contracts ORDER BY root").fetchall():
        root = kb.get_task(conn, row["root"])
        if row["paused"] or not root or root.status in {"done", "archived"}:
            continue
        spec = json.loads(row["spec"])
        validate(spec)
        # A root explicitly waiting for permission/input stays parked.
        blocked = conn.execute("SELECT kind,resolved FROM objective_blockers WHERE task=?", (root.id,)).fetchone()
        if blocked and not blocked["resolved"] and blocked["kind"] in {"permission", "external_input"}:
            continue
        actions.extend(_continue_internal_work(conn, row, spec))
        stages, seen = {}, set()
        while len(seen) < len(spec["stages"]):
            for stage in spec["stages"]:
                if stage["id"] in seen or not set(stage.get("after", [])) <= seen:
                    continue
                tid = _create(conn, row, stage, key=f"objective:{root.id}:v{row['revision']}:{stage['id']}",
                              parents=[stages[p] for p in stage.get("after", [])])
                stages[stage["id"]] = tid
                seen.add(stage["id"])
                existing = kb.get_task(conn, tid)
                if existing.status == "done":
                    errors, _ = check_evidence(stage["checks"], row["created_at"], execute=False)
                    if errors and reopen_for_repair(conn, tid, "; ".join(errors)):
                        actions.append({"reopened_implementation": tid})
                    elif not errors:
                        with kb.write_txn(conn):
                            accepted = acceptance(conn, tid)
                        if not accepted and reopen_for_repair(conn, tid, "Current evidence verifier rejected this implementation; inspect objective_acceptance_rejected events and repair the same card."):
                            actions.append({"reopened_implementation": tid})
                # Stage -> objective. A repair must never wait on its root.
                if tid not in kb.parent_ids(conn, root.id):
                    kb.link_tasks(conn, tid, root.id)
                    actions.append({"created_stage": tid, "root": root.id})
        # Concrete internal blocker repairs. No requeue until checks pass.
        for blocker in conn.execute("SELECT b.* FROM objective_blockers b JOIN objective_members m ON m.task=b.task WHERE m.root=? AND b.resolved=0", (root.id,)).fetchall():
            if blocker["kind"] in {"permission", "external_input"}:
                continue
            repair = json.loads(blocker["repair"])
            if blocker["kind"] == "dependency":
                tid = repair["task_id"]
                if tid not in kb.parent_ids(conn, blocker["task"]):
                    kb.link_tasks(conn, tid, blocker["task"])
                if kb.get_task(conn, tid).status == "done":
                    with kb.write_txn(conn):
                        conn.execute("UPDATE objective_blockers SET resolved=1 WHERE task=?", (blocker["task"],))
                    _wake(conn, blocker["task"])
                    actions.append({"resumed_dependency": blocker["task"], "after": tid})
                continue
            repair = {**repair, "id": f"repair:{blocker['task']}", "title": repair.get("title", "Repair: " + blocker["reason"][:100])}
            tid = _create(conn, row, repair, key=f"objective:{root.id}:v{row['revision']}:repair:{digest(dict(blocker))}")
            if tid not in kb.parent_ids(conn, blocker["task"]):
                kb.link_tasks(conn, tid, blocker["task"])
                actions.append({"repair": tid, "unblocks": blocker["task"]})
            errors, _ = check_evidence(repair["checks"], row["created_at"], execute=False)
            if kb.get_task(conn, tid).status == "done" and not errors:
                with kb.write_txn(conn):
                    conn.execute("UPDATE objective_blockers SET resolved=1 WHERE task=?", (blocker["task"],))
                _wake(conn, blocker["task"])
        # Contract context for dynamic repairs is persisted in their body;
        # acceptance reads their registered checks (see repair_checks below).
        fingerprint = digest([check_evidence(s["checks"], row["created_at"], execute=False) for s in spec["stages"]])
        progress = conn.execute("SELECT * FROM objective_progress WHERE root=?", (root.id,)).fetchone()
        with kb.write_txn(conn):
            if not progress or progress["fingerprint"] != fingerprint:
                conn.execute("INSERT INTO objective_progress VALUES(?,?,?,0) ON CONFLICT(root) DO UPDATE SET fingerprint=excluded.fingerprint,changed_at=excluded.changed_at,attempts=0", (root.id, fingerprint, now))
                progress = None
        # Wake root only when its prerequisites finished. Do not disturb live claims.
        if all(kb.get_task(conn, t).status == "done" for t in stages.values()):
            _wake(conn, root.id)
        elif progress and now - progress["changed_at"] >= spec.get("stale_seconds", 1800):
            attempt = progress["attempts"] + 1
            if attempt <= spec.get("max_repairs", 2):
                # Use the contract's next unmet stage as the repair work. This
                # gives it an owner and bounded retry without inventing scope.
                for stage in spec["stages"]:
                    task = kb.get_task(conn, stages[stage["id"]])
                    if any(c["task_id"] == task.id for c in continuation_policies(conn, row, spec)):
                        continue  # This task has its own evidence-gated finite allowance.
                    blocker = conn.execute("SELECT kind,resolved FROM objective_blockers WHERE task=?", (task.id,)).fetchone()
                    if blocker and not blocker["resolved"] and blocker["kind"] in {"permission", "external_input"}:
                        continue
                    if task.status in {"triage", "blocked"} and task.block_kind != "needs_input":
                        kb.add_comment(conn, task.id, "objective-supervisor", "Evidence has not advanced. Reproduce the blocker, implement the internal prerequisite, and verify the assigned stage. External input/permission must be recorded explicitly.")
                        _wake(conn, task.id)
                        actions.append({"resumed_stalled": task.id, "attempt": attempt})
                        break
                with kb.write_txn(conn):
                    conn.execute("UPDATE objective_progress SET attempts=?,changed_at=? WHERE root=?", (attempt, now, root.id))
                    kb._append_event(conn, root.id, "objective_stagnation", {"attempt": attempt, "actions": actions})
            elif progress["attempts"] == spec.get("max_repairs", 2):
                kb.add_comment(conn, root.id, "objective-supervisor", "Repair budget exhausted; objective remains incomplete. Inspect objective_stagnation events and evidence failures.")
                with kb.write_txn(conn):
                    conn.execute("UPDATE objective_progress SET attempts=? WHERE root=?", (attempt, root.id))
    kb.recompute_ready(conn)
    return actions


def main():
    from hermes_cli import kanban_db as kb
    from hermes_cli.kanban_db_connect import connect_closing
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    enroll_p = sub.add_parser("enroll")
    enroll_p.add_argument("task")
    enroll_p.add_argument("contract", type=Path)
    for name in ("pause", "resume", "status", "context", "resolve"):
        p = sub.add_parser(name)
        p.add_argument("task")
    sub.add_parser("tick")
    sub.add_parser("enable")
    p = sub.add_parser("continuation")
    p.add_argument("task")
    p.add_argument("checkpoint", type=Path)
    p.add_argument("--max-runs", type=int, required=True)
    p.add_argument("--member-of", help="enrolled task that already depends on this pre-enrollment child")
    p.add_argument("--completion-checks", type=Path, help="owner-authored JSON check list required for an adopted child")
    p = sub.add_parser("block")
    p.add_argument("task")
    p.add_argument("kind", choices=sorted(KINDS))
    p.add_argument("reason")
    p.add_argument("--repair", type=Path)
    args = parser.parse_args()
    with connect_closing(db_path=args.db) as conn:
        ensure(conn)
        if args.command == "enroll":
            result = {"revision": enroll(conn, args.task, json.loads(args.contract.read_text()))}
        elif args.command == "tick":
            result = tick(conn)
        elif args.command == "enable":
            with kb.write_txn(conn):
                conn.execute("INSERT OR IGNORE INTO objective_policy VALUES(1,?)", (int(time.time()),))
            result = {"require_contract_since": conn.execute("SELECT require_contract_since FROM objective_policy WHERE id=1").fetchone()[0]}
        elif args.command == "block":
            report_blocker(conn, args.task, args.kind, args.reason, json.loads(args.repair.read_text()) if args.repair else None)
            result = {"recorded": args.task}
        elif args.command == "continuation":
            configure_continuation(conn, args.task, args.checkpoint, args.max_runs, args.member_of,
                                   json.loads(args.completion_checks.read_text()) if args.completion_checks else None)
            result = {"task": args.task, "checkpoint": str(args.checkpoint), "max_runs": args.max_runs}
        elif args.command == "context":
            result = worker_context(conn, args.task)
        elif args.command == "resolve":
            with kb.write_txn(conn):
                conn.execute("UPDATE objective_blockers SET resolved=1 WHERE task=?", (args.task,))
                kb._append_event(conn, args.task, "objective_blocker_resolved", {})
            row = contract(conn, args.task)
            if row and not row["paused"]:
                _wake(conn, args.task)
            result = {"resolved": args.task}
        elif args.command in {"pause", "resume"}:
            set_paused(conn, args.task, args.command == "pause")
            result = {"paused": args.command == "pause"}
        else:
            row = contract(conn, args.task)
            result = dict(row) if row else None
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
