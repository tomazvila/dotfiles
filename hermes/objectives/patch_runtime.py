"""Apply a narrowly pinned source extension; fail loudly on upstream drift."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
path = root / "hermes_cli/kanban_db.py"
text = path.read_text()


def replace(old, new):
    global text
    if text.count(old) != 1:
        raise RuntimeError(f"Hermes source changed: expected exactly one {old!r}")
    text = text.replace(old, new)


replace("                for pid in parents:\n                    _link(conn, pid, task_id)",
        "                from hermes_cli.kanban_objectives import inherit\n"
        "                inherit(conn, task_id, parents, creator_task_id or project_source_task_id)\n"
        "                for pid in parents:\n                    _link(conn, pid, task_id)")
replace("        prior_status = _task_status(conn, task_id)\n        sql = \"\"\"",
        "        prior_status = _task_status(conn, task_id)\n"
        "        if prior_status not in {'running', 'ready', 'blocked', 'review'}:\n"
        "            return False\n"
        "        if expected_run_id is not None and _current_run_id(conn, task_id) != expected_run_id:\n"
        "            return False\n"
        "        from hermes_cli.kanban_objectives import acceptance\n"
        "        if not acceptance(conn, task_id):\n"
        "            return False\n"
        "        sql = \"\"\"")
replace("    _ctx_header(lines, task)\n    _ctx_attachments",
        "    _ctx_header(lines, task)\n"
        "    from hermes_cli.kanban_objectives import worker_context\n"
        "    lines.append(worker_context(conn, task_id))\n"
        "    _ctx_attachments")
replace("    with write_txn(conn):\n        # Single enforcement point: never ready -> running",
        "    with write_txn(conn):\n"
        "        from hermes_cli.kanban_objectives import claim_allowed\n"
        "        if not claim_allowed(conn, task_id):\n"
        "            return None\n"
        "        # Single enforcement point: never ready -> running")
# Always run independently of plugin observer presence, after dispatch lock release.
replace("    if not _kanban_observer_consumed(\"on_kanban_dispatch_tick\"):\n",
        "    if not dry_run:\n"
        "        try:\n"
        "            from hermes_cli.kanban_db_connect import connect_closing\n"
        "            from hermes_cli.kanban_objectives import tick\n"
        "            with connect_closing(board=board) as objective_conn:\n"
        "                tick(objective_conn)\n"
        "        except Exception:\n"
        "            _log.exception('Objective supervisor failed; completion remains evidence-gated')\n"
        "    if not _kanban_observer_consumed(\"on_kanban_dispatch_tick\"):\n")
path.write_text(text)

# A child can exit between the tick's initial reap pass and its liveness check.
# Reap again after liveness established death, before assigning a crash outcome.
# This retains the quota-wall exit code and avoids consuming a failure allowance.
path = root / "hermes_cli/kanban_db_dispatch.py"
text = path.read_text()
replace("import sys\nimport time\n", "import sys\nimport threading\nimport time\n")
replace('_recent_worker_exits: "dict[int, tuple[int, float]]" = {}\n',
        '_recent_worker_exits: "dict[int, tuple[int, float]]" = {}\n'
        '# All boards in this process share child wait statuses and this registry.\n'
        '# Hold through publication; RLock allows classification to retry reaping.\n'
        '_worker_exit_lock = threading.RLock()\n')
replace("    entry = _recent_worker_exits.get(int(pid))\n",
        "    with _worker_exit_lock:\n"
        "        entry = _recent_worker_exits.get(int(pid))\n")
# Pin the existing nonblocking reap loop, including its error/Windows policies.
reap_body = '''    reaped: "list[int]" = []
    if os.name != "nt":
        try:
            while True:
                try:
                    pid, status = os.waitpid(-1, os.WNOHANG)
                except ChildProcessError:
                    break
                if pid == 0:
                    break
                _record_worker_exit(pid, status)
                reaped.append(pid)
        except Exception:
            pass
    return reaped
'''
replace(reap_body, "    with _worker_exit_lock:\n" +
        "".join("    " + line for line in reap_body.splitlines(keepends=True)))
replace("    kind, code = _classify_worker_exit(pid)\n    if kind == \"clean_exit\":",
        "    with _worker_exit_lock:\n"
        "        kind, code = _classify_worker_exit(pid)\n"
        "        if kind == 'unknown':\n"
        "            reap_worker_zombies()\n"
        "            kind, code = _classify_worker_exit(pid)\n"
        "    if kind == \"clean_exit\":")
path.write_text(text)

# Refuse automatic replanning before the auxiliary model call, and enforce the
# same ownership at the shared graph mutation boundary for other callers.
path = root / "hermes_cli/kanban_decompose.py"
text = path.read_text()
replace("    routing = _load_routing()\n    raw, reason = _call_aux(",
        "    from hermes_cli.kanban_objectives import decomposition_allowed\n"
        "    with kbc.connect_closing() as conn:\n"
        "        if not decomposition_allowed(conn, task_id):\n"
        "            return DecomposeOutcome(task_id, False, 'Existing task uses owner-enrolled checkpoint continuation')\n"
        "    routing = _load_routing()\n    raw, reason = _call_aux(")
path.write_text(text)
path = root / "hermes_cli/kanban_db_graph.py"
text = path.read_text()
replace("    with write_txn(conn):\n        root_row = conn.execute(",
        "    with write_txn(conn):\n"
        "        from hermes_cli.kanban_objectives import decomposition_allowed\n"
        "        if not decomposition_allowed(conn, task_id):\n"
        "            return None\n"
        "        root_row = conn.execute(")
path.write_text(text)
