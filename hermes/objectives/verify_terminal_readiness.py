"""Verify a stopped readiness decision without granting execution approval.

This owner-side stage verifier is separate from verify_evidence.readiness,
whose APPROVE requirement remains unchanged. It performs no provider calls.
"""
import argparse
import hashlib
import json
from pathlib import Path

from verify_evidence import ref, require, sha


def verify(path):
    data = json.loads(Path(path).read_text())
    require(data.get("schema") == 1 and data.get("kind") == "terminal-readiness",
            "terminal readiness schema required")
    require(data.get("sources") and data.get("artifacts"), "source and raw evidence required")
    sources = {str(ref(item)): item["sha256"] for item in data["sources"]}
    require(len(sources) == len(data["sources"]), "duplicate source references")
    for item in data["artifacts"]:
        ref(item)
    source_digest = hashlib.sha256(json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    review = json.loads(ref(data["review"]).read_text())
    verdict = "DO_NOT_RUN_TECHNICAL_INCOMPATIBILITY"
    require(data.get("readiness") == review.get("verdict") == verdict, "explicit stopped verdict required")
    require(data.get("source_digest") == review.get("source_digest") == source_digest,
            "current-source independent review binding required")
    require(review.get("reviewer_task") and review.get("implementation_task"), "review provenance required")
    distinct_task = review["reviewer_task"] != review["implementation_task"]
    distinct_run = all(type(review.get(k)) is int and review[k] > 0 for k in ("reviewer_run", "implementation_run"))
    distinct_run = distinct_run and review["reviewer_run"] != review["implementation_run"]
    require(distinct_task or distinct_run, "independent review required")
    require(review.get("execution_approved") is False and review.get("comparison_enabled") is False,
            "terminal review cannot authorize execution")
    verification = json.loads(ref(review["verification"]).read_text())
    require(verification.get("source_digest") == source_digest and verification.get("new_provider_calls") == 0
            and verification.get("credentials_accessed") is False, "offline independent verification required")
    snapshot = json.loads(ref(review["snapshot"]).read_text())
    require(snapshot.get("sourceDigest") == source_digest, "independently reviewed snapshot binding required")
    protocol = json.loads(ref(data["protocol"]).read_text())
    budget = ref(data["budget_record"])
    require(protocol.get("source_digest") == source_digest and protocol.get("review") == data["review"],
            "negative protocol must bind the review and current source")
    require(protocol.get("budget_record") == data["budget_record"], "inherited budget must be preserved")
    for key in ("comparison_enabled", "execution_approved", "supports_live_network_speedup", "comparison_complete"):
        require(data.get(key) is False, f"terminal decision requires {key}=false")
    require(type(data.get("provider_calls")) is int and data["provider_calls"] == 0,
            "terminal reconciliation makes zero provider calls")
    require(type(data.get("diagnostics_remaining")) is int and data["diagnostics_remaining"] == 0,
            "closed diagnostic budget required")
    require(protocol.get("executable") is False and protocol.get("comparison_complete") is False
            and protocol.get("execution_allowlist") == [] and protocol.get("new_provider_calls") == 0,
            "negative protocol must keep execution disabled")
    require(data.get("limitations"), "bounded conclusion limitations required")
    replay_path = ref(data["reproduction"])
    require(snapshot.get("artifactHashes", {}).get(str(replay_path)) == data["reproduction"]["sha256"],
            "reproduction must be bound by independent review")
    replay = json.loads(replay_path.read_text())
    require(replay.get("unsupported") is True and replay.get("generatorCalls") == 0,
            "actual runner must preserve the rejected result with no subsequent generation")
    require("JEV_INVALID_REQUIRES_NEW_FREEZE" in replay.get("gateFailures", []), "retained transport stop required")
    for item in data.get("preserved_empty_artifacts", []):
        p = Path(item["path"])
        require(p.is_absolute() and p.is_file() and p.read_bytes() == b"" and sha(p) == item["sha256"],
                "preserved empty artifact changed")
    return {"kind": data["kind"], "manifest_sha256": sha(path), "source_digest": source_digest,
            "readiness": verdict, "execution_approved": False, "comparison_enabled": False,
            "budget_sha256": sha(budget)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.manifest), sort_keys=True))
