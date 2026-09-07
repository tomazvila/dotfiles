# Headroom (headroom-ai): context-compression proxy for coding agents.
# Not in nixpkgs (the nixpkgs `headroom` is an unrelated Haskell license-header
# tool), and its dependency closure (Rust core, transformers, onnxruntime with
# tight version pins) is impractical to package from source. Instead this pins
# the PyPI release and runs it through uv's ephemeral tool runner: the env
# lives in ~/.cache/uv, nothing is installed into a global site-packages.
# Usage: `headroom wrap claude` launches Claude Code behind the local proxy.
{ pkgs }:
let
  version = "0.37.0";
in
pkgs.writeShellScriptBin "headroom" ''
  exec ${pkgs.uv}/bin/uv tool run \
    --python ${pkgs.python313}/bin/python3 \
    --from "headroom-ai[proxy,code]==${version}" \
    headroom "$@"
''
