# pi coding agent (https://pi.dev/), installed from the upstream release
# binary via pkgs/pi.nix. Runtime state written by pi itself (auth.json,
# settings.json, models-store.json) stays unmanaged. models.json is the
# exception: it is user-authored provider config that pi only reads, so it
# is managed declaratively here.
{ pkgs, ... }:
let
  pi = import ../pkgs/pi.nix { inherit pkgs; };

  # Self-hosted LLM gateway on the Mac, reached over WireGuard via the
  # llm-proxy on the homelab server (10.8.0.1:8081 -> Mac 10.8.0.3:8080).
  piModels = {
    providers.mac = {
      baseUrl = "http://10.8.0.1:8081/v1";
      api = "openai-completions";
      apiKey = "local";
      authHeader = true;
      compat = {
        supportsDeveloperRole = false;
        supportsReasoningEffort = false;
      };
      models = [
        {
          id = "qwen-coder";
          name = "Qwen3-Coder 30B 4-bit (self-hosted)";
          reasoning = false;
          contextWindow = 262144;
          maxTokens = 65536;
        }
        {
          id = "qwen-coder-8bit";
          name = "Qwen3-Coder 30B 8-bit (self-hosted)";
          reasoning = false;
          contextWindow = 262144;
          maxTokens = 65536;
        }
      ];
    };
  };
in
{
  home.packages = [ pi ];
  home.file.".pi/agent/models.json".text = builtins.toJSON piModels;
}
