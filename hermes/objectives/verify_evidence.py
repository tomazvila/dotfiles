"""Read-only verifier for Nora evidence manifests; never calls a provider.

Reject missing/stale source bindings and unsupported measurement claims.
This validates inspectable artifacts, not the truthfulness of an adversarial
writer or the semantic correctness of an LLM's assessment.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def ref(entry):
    path = Path(entry["path"])
    require(path.is_absolute() and path.is_file(), f"missing absolute artifact: {path}")
    require(path.stat().st_size > 0 and sha(path) == entry["sha256"], f"artifact hash mismatch: {path}")
    return path


def number(value, name, minimum=None):
    require(type(value) in (int, float) and math.isfinite(value), f"invalid numeric {name}")
    require(minimum is None or value >= minimum, f"invalid negative {name}")
    return value


def verify(path, kind, source_root=None, required_sources=(), required_tests=()):
    data = json.loads(Path(path).read_text())
    require(data.get("schema") == 1 and data.get("kind") == kind, "wrong evidence schema/kind")
    sources = data.get("sources", [])
    require(sources and data.get("artifacts"), "source and raw-artifact references required")
    source_map = {str(ref(entry)): entry["sha256"] for entry in sources}
    for entry in data["artifacts"]:
        ref(entry)
    if source_root:
        for relative in required_sources:
            current = str(Path(source_root) / relative)
            require(current in source_map and sha(current) == source_map[current], f"current source is unbound: {current}")
    source_digest = hashlib.sha256(json.dumps(source_map, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if kind == "capture":
        snapshots = data.get("snapshots", [])
        require(snapshots, "no captured pre-routing inputs")
        for item in snapshots:
            captured = ref(item)
            payload = json.loads(captured.read_text())
            require(payload.get("userMessage") and isinstance(payload.get("playbookOptions"), list) and payload["playbookOptions"], "native userMessage/authorized routing workflows missing")
            require("message" not in payload, "capture must preserve the native DTO without a capture-only message alias")
            replay = ref(item["round_trip"])
            require(replay != captured and sha(replay) == item["sha256"], "exact-byte round-trip artifact missing")
            require(item.get("origin") == "native-router-input", "capture must be at the native pre-routing construction point")
        require(data.get("provider_calls") == 0, "capture must use an offline test seam without inference")
    elif kind == "implementation":
        reports = data.get("test_reports", [])
        require(reports, "executed test reports required")
        names = set()
        for entry in reports:
            tree = ET.parse(ref(entry))
            for case in tree.iter("testcase"):
                require(case.find("failure") is None and case.find("error") is None, "failed regression test")
                if case.find("skipped") is None:
                    names.add(case.attrib.get("name", ""))
        require(names, "no executed tests")
        require(set(required_tests) <= names, "required direct-entry regression tests were not executed")
    elif kind == "readiness":
        review = json.loads(ref(data["review"]).read_text())
        require(review.get("verdict") == "APPROVE" and review.get("source_digest") == source_digest, "fresh exact-source independent approval missing")
        require(review.get("reviewer_task") and review.get("implementation_task"), "independent review provenance required")
        independent_task = review["reviewer_task"] != review["implementation_task"]
        independent_run = (type(review.get("reviewer_run")) is int and type(review.get("implementation_run")) is int
                           and review["reviewer_run"] > 0 and review["implementation_run"] > 0
                           and review["reviewer_run"] != review["implementation_run"])
        require(independent_task or independent_run, "fresh independent task/run required; native same-card review is supported")
        require(data.get("protocol") and data.get("budget_record"), "frozen protocol and inherited budget record required")
        ref(data["protocol"])
        ref(data["budget_record"])
    elif kind == "comparison":
        pairs = data.get("pairs", [])
        require(len(pairs) >= 2, "at least two paired observations required")
        plan_ref = data["execution_plan"]
        plan = json.loads(ref(plan_ref).read_text())
        expected = plan.get("pair_ids", [])
        actual = [pair["id"] for pair in pairs]
        require(expected and len(expected) == len(set(expected)) and len(actual) == len(set(actual))
                and set(expected) == set(actual), "paired results must cover the complete predeclared plan")
        execution_review = json.loads(ref(data["execution_review"]).read_text())
        require(execution_review.get("verdict") == "APPROVE" and execution_review.get("plan_sha256") == plan_ref["sha256"]
                and execution_review.get("source_digest") == source_digest, "comparison plan requires exact-source execution approval")
        for pair in pairs:
            raw_input = ref(pair["input"])
            input_hash = sha(raw_input)
            for arm in ("baseline", "treatment"):
                observation = pair[arm]
                require(observation["input_sha256"] == input_hash, "arms did not consume identical inputs")
                trace = json.loads(ref(observation["trace"]).read_text())
                require(trace.get("input_sha256") == input_hash, "raw trace is not bound to the pair input")
                require(observation.get("measurement_scope") in {"observed-critical-path", "frozen-response-continuation", "reconstructed"}, "measurement scope missing")
                latency = number(observation["latency_ms"], "latency", 0)
                require(trace.get("latency_ms") == latency, "latency does not match raw trace")
                cost = observation.get("cost_status")
                require(cost in {"known", "unknown"}, "cost provenance missing")
                if cost == "known":
                    require(trace.get("cost") == number(observation["cost"], "cost", 0), "cost does not match raw trace")
                judgement = json.loads(ref(observation["quality"]).read_text())
                require(judgement.get("input_sha256") == input_hash, "quality judgement is not bound to the pair input")
                number(judgement["score"], "quality")
                require(judgement.get("judge_model") == "gpt-6-astra" and judgement.get("blind") is True, "blinded Astra assessment missing")
                require(judgement.get("citations"), "evidence-grounded quality citations required")
        require(data.get("failures_and_fallbacks") is not None and data.get("limitations"), "full accounting and limitations required")
        require(data.get("supports_live_network_speedup") is False or all(p[a]["measurement_scope"] == "observed-critical-path" for p in pairs for a in ("baseline", "treatment")), "reconstructed/frozen timings cannot establish live-network speedup")
    elif kind == "outcome":
        for entry in data.get("comparisons", []):
            verify(ref(entry), "comparison")
        require(len(data.get("comparisons", [])) >= 2, "both experiment lanes must be reported")
        require(data.get("decision") in {"adopt", "reject", "inconclusive"} and data.get("limitations"), "bounded evidence-based decision required")
        require(data.get("rollback_evidence"), "tested rollback evidence required")
        ref(data["rollback_evidence"])
    return {"kind": kind, "manifest_sha256": sha(path), "source_digest": source_digest}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("kind", choices=["capture", "implementation", "readiness", "comparison", "outcome"])
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--required-source", action="append", default=[])
    parser.add_argument("--required-test", action="append", default=[])
    args = parser.parse_args()
    print(json.dumps(verify(args.manifest, args.kind, args.source_root, args.required_source, args.required_test), sort_keys=True))
