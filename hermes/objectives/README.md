# Hermes objective supervision

Source: `kanban_objectives.py`. Durable state: `objective_*` tables in each Hermes Kanban board. Runtime: the pinned Hermes Nix package plus a source overlay, applied by `patch_runtime.py`. Upstream source drift fails the build.

## Behavior

- New goal-mode tasks require a versioned contract before execution or completion. The supervisor creates an assigned contract-acquisition task when one is absent. Earlier tasks retain native behavior unless enrolled explicitly.
- Dependency/creator links propagate objective ownership into new children. Every worker context includes the current revision, scope, constraints and evidence requirements.
- Each contract defines executable stages, owners, prerequisites and deterministic acceptance checks. Missing stages become assigned implementation/acquisition work. A completed stage with missing/stale evidence is reopened on the same card, preserving prior runs and re-gating dependents.
- Structured internal blockers create bounded corrective work. Known task dependencies resume after their prerequisite completes. Explicit external-input and permission blockers remain parked until resolved.
- Progress is tracked by evidence content, independently of comments, heartbeats or card counts. Stalled blocked/triage stages receive at most the contract's repair allowance. Exhaustion is recorded and the objective remains incomplete.
- Internal implementation can use an owner-enrolled continuation outbox. After each verified slice, the worker writes a current-run/current-revision checkpoint with cumulative completed milestones, a concrete next action, hash-bound sources/artifacts and passing JUnit reports. The next dispatch tick resumes that same card after it stops. Each task has a finite allowance independent of root stagnation retries; prior usage survives contract revisions. Pauses, permission/input blockers, unresolved repair dependencies, paid-call limits and completion gates remain in force. Missing or unchanged checkpoints do not trigger continuation; exhaustion creates a durable escalation for replanning.
- The shared completion transaction checks evidence for agent tools, CLI, review approval and dashboard. Root completion requires current-revision stage receipts and final outcome checks. Goal-judge failure cannot bypass this gate.
- Owner pause prevents new claims and stops current objective workers through native reclaimed-worker handling. Resume releases only runs paused by that command. Unrelated workflows retain their state.

## Commands

Use the board selected by Hermes or pass `--db /absolute/path/kanban.db` before the verb.

```sh
hermes-objectives enable
hermes-objectives enroll t_12345678 /absolute/path/contract.json
hermes-objectives tick
hermes-objectives context t_12345678
hermes-objectives status t_12345678
hermes-objectives block t_12345678 internal_repair 'Recorder is missing' --repair /absolute/path/repair.json
hermes-objectives block t_12345678 dependency 'Implementation requires correction' --repair /absolute/path/dependency.json
hermes-objectives block t_12345678 permission 'Owner approval required'
hermes-objectives resolve t_12345678
hermes-objectives pause t_12345678
hermes-objectives resume t_12345678
hermes-objectives continuation t_87654321 /absolute/path/continuation.json --max-runs 6
```

`enable` records an idempotent cutover timestamp in that board. Contract acquisition and stage repairs preserve existing permissions; the supervisor does not authorize spending, production changes or messages. `resolve` records supplied external input/approval; the next tick applies dependency rules. A dependency repair file is `{"task_id":"t_87654321"}`.

Contracts use schema 1, an objective, owner, nonempty stages and final checks. A stage needs a unique ID, title, concrete body, absolute workspace, evidence checks and optional `after` stage IDs. `task_id` adopts an existing card. Defaults: 30-minute stagnation interval, two repairs, 30-minute worker runtime and 20 goal continuations. Models/providers inherit unless pinned explicitly. Inspect `projects/nora-jev.json` for a full local contract.

Optional `continuations` entries have `task_id`, an absolute `checkpoint` path and `max_runs` between one and eight. They apply only to objective members stopped in an internal transient/capability phase. A checkpoint uses schema 1, `task_id`, integer `run_id`, `revision`, `provider_calls:0`, `internal_work_remaining:true`, cumulative unique `completed` milestone strings, and `next_action`. `sources`, `artifacts` and `test_reports` each contain absolute `{path,sha256}` references. Test reports must contain executed passing JUnit cases. This cooperative check validates retained evidence and forward progress claims; it does not independently prove milestone semantics or grant inference approval. Workers write the file locally without needing delegated-child database mutation access. The current worker context carries the policy and last consumed checkpoint. When there is a genuine external blocker, report it explicitly rather than writing a continuation checkpoint.

The owner `continuation` command registers this operational policy without reenrolling the scientific contract or resetting its root repair counters. Prior continuation usage also survives policy updates. Missing/invalid handoffs and allowance exhaustion each produce a durable escalation rather than silently parking the task. No notifications are sent.

Native stopped runs may omit a blocker category or escalate to triage after retries. These phases require the same current-closed-run verified checkpoint with explicit `internal_work_remaining:true` before continuation. A native automatic unblock to ready also cannot bypass the checkpoint or finite allowance: the claim boundary requires that the latest stopped run's handoff was consumed. Explicit native input/permission categories and objective blockers remain protected. Triage without a qualifying stopped run and verified checkpoint stays parked.

Checkpoint-owned cards are excluded from native automatic decomposition before an auxiliary model call and at the shared graph mutation boundary. They keep their existing owner and scoped checks. Unrelated triage retains its native behavior. Replanning after allowance exhaustion requires owner inspection rather than an automatic new child graph.

Operational checkpoint artifacts may include empty stdout or lock files with the exact empty-byte SHA-256. They are retained with a zero-byte marker, alongside required nonempty raw evidence. Empty files never establish successful execution; sources and JUnit reports remain nonempty. This does not relax scientific experiment acceptance checks.

For a prerequisite created before its parent was enrolled, add `--member-of t_parent --completion-checks /absolute/path/checks.json`. Adoption requires that the enrolled parent already depends on this task and that the owner supplies a JSON list of scoped implementation acceptance checks. The child can finish its implementation without depending on the entire objective's outcome; the parent's independent review and final scientific gates remain separate. Adoption records ownership for the existing card; it does not create a child graph or authorize an unrelated task.

Checks support absolute file paths, optional SHA-256 pins, JSON assertions and fixed-argv verifier commands. Files must be nonempty and newer than enrollment by default. `fresh:false` permits historical inputs when the contract explicitly allows them. Verifiers execute without a shell, with a total timeout allowance of ten seconds per contract; keep them read-only and lightweight. Heavy tests belong in stage work. Completion records artifact hashes and verifier-output hashes.

Nora's `verify_evidence.py` verifies source/trace references, actual JUnit outcomes, exact-byte capture/replay artifacts, current-source independent approval and paired latency/cost/quality records covering the full predeclared approved plan. Negative and inconclusive outcomes are valid. Frozen/reconstructed timing cannot establish live-network speedup. Workers must produce the manifest schema consumed by this verifier; an assertion that tests passed is insufficient.

`verify_readiness_disposition.py` completes readiness assessment through either the unchanged execution-APPROVE verifier or `verify_terminal_readiness.py`. Terminal readiness requires independent current-source rejection evidence, a bound actual-runner reproduction, preserved inherited budget and explicit disabled execution. It grants no trial or diagnostic permission. Partial-output evaluation uses its own separately reviewed protocol; missing slots and failed outcomes retain their original denominators.

Owner corrective reopen emits a native `status` requeue event as well as `objective_implementation_rejected`. This lets the native recent-success guard recognize deliberate rework immediately. Completed run history, failure counters, prerequisites, pauses and evidence gates remain intact.

## Build and verify

```sh
cd /Users/lilvilla/dotfiles
nix build .#hermes-objectives
nix build .#checks.aarch64-darwin.hermes-objectives
```

The Home Manager module preserves these runtime links on rebuild: `~/.hermes/objective-runtime`, `~/.local/bin/hermes`, and `~/.local/bin/hermes-objectives`. Launchd gateway/dashboard services must use this runtime, including subprocesses. Runtime activation changes only those links/services; it does not apply unrelated dirty dotfiles changes.

## Boundaries and rollback

This is a cooperative workflow guard. A process with direct access to SQLite or older unpatched Python can bypass it. Artifact hashes establish identity; semantic truth and LLM quality judgments still require review. A poorly specified contract can validate the wrong outcome. Contract authors must define the user-visible result, preserve authorization and include decisive checks.

Already-running old workers must drain before switching the gateway. Completion/claim gates fail closed; supervisor faults log an exception and retain incomplete work. The supervisor runs on gateway dispatch ticks, so an unavailable gateway cannot dispatch repairs.

Rollback: pause enrolled objectives; restore the saved runtime links and LaunchAgent plists; restart the two services. `objective_*` tables and events may remain for audit. To remove cutover enforcement while retaining the runtime, delete the singleton `objective_policy` row through an explicit owner maintenance action. Stop/remove this extension if representative workflows demonstrate incorrect reopening or permission handling; retain the failing board and evidence for reproduction.
