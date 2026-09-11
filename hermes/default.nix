# Hermes Agent (https://hermes-agent.nousresearch.com/), installed from the
# upstream Nix flake: the `hermes-agent` input in flake.nix (pinned to a
# release tag) provides the package and the Home Manager module, which is
# loaded through home-manager.sharedModules there. This module only turns the
# CLI on and exports HERMES_HOME. Runtime state under ~/.hermes (config.yaml,
# .env, auth.json, sessions, skills, memory) is written by `hermes setup` and
# `hermes model` and stays unmanaged, like pi's runtime state.
{ ... }:
{
  programs.hermes-agent.enable = true;

  # Same optional groups as the flake's default package, minus `voice`
  # (local speech-to-text via faster-whisper). Its wheel-only deps
  # (ctranslate2, onnxruntime) are swapped for nixpkgs builds, which are not
  # in the binary cache for Python 3.12 on aarch64-darwin, so they compile
  # from source together with torch: hours of build time. Add "voice" back
  # here to get local transcription.
  services.hermes-agent.extraDependencyGroups = [
    "anthropic"
    "azure-identity"
    "bedrock"
    "daytona"
    "dingtalk"
    "edge-tts"
    "exa"
    "fal"
    "feishu"
    "firecrawl"
    "hindsight"
    "honcho"
    "messaging"
    "modal"
    "parallel-web"
    "tts-premium"
    "vercel"
  ];
}
