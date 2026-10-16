"""Readiness stage accepts execution approval or a separately verified terminal stop.

A terminal stop completes the readiness assessment only. The execution verifier
and native execution permits continue to require APPROVE.
"""
import argparse
import json
from pathlib import Path

import verify_evidence as execution
import verify_terminal_readiness as terminal


def verify(path, source_root=None, required_sources=()):
    data = json.loads(Path(path).read_text())
    if data.get("kind") == "readiness":
        return execution.verify(path, "readiness", source_root, required_sources)
    execution.require(data.get("kind") == "terminal-readiness", "unsupported readiness disposition")
    if source_root:
        source_map = {item["path"]: item["sha256"] for item in data.get("sources", [])}
        for name in required_sources:
            current = str(Path(source_root) / name)
            execution.require(current in source_map and execution.sha(current) == source_map[current],
                              f"required current source is unbound: {current}")
    return terminal.verify(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--required-source", action="append", default=[])
    args = parser.parse_args()
    print(json.dumps(verify(args.manifest, args.source_root, args.required_source), sort_keys=True))
