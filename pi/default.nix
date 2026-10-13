# pi coding agent (https://pi.dev/), installed from the upstream release
# binary via pkgs/pi.nix. Runtime state written by pi itself (auth.json,
# settings.json, models-store.json) stays unmanaged. models.json is the
# exception: it is user-authored provider config that pi only reads, so it
# is managed declaratively here.
{ pkgs, config, ... }:
let
  pi = import ../pkgs/pi.nix { inherit pkgs; };

  openRouterKeyFile = "${config.home.homeDirectory}/dotfiles/open-router-deepkseek-api-key.txt";

  # Self-hosted LLM gateway on the Mac. The Mac calls it on loopback; other
  # hosts reach it over WireGuard via the llm-proxy on the homelab server
  # (10.8.0.1:8081 -> Mac 10.8.0.3:8080). The gateway runs one model at a time
  # and swaps on demand, so every model below stays selectable.
  piModels = {
    providers.mac = {
      baseUrl =
        if pkgs.stdenv.isDarwin then "http://127.0.0.1:8080/v1" else "http://10.8.0.1:8081/v1";
      api = "openai-completions";
      apiKey = "local";
      authHeader = true;
      compat = {
        supportsDeveloperRole = false;
        supportsReasoningEffort = false;
      };
      models = [
        {
          # Qwen3.8-Flash-Next MoE, MLX 4-bit, served by Slotstream behind the
          # gateway (experts stream from SSD). The default model. It takes
          # reasoning_effort, so pi's thinking level applies. A full 262144-token
          # prompt reads in about 2 h; follow-up turns read only what is new.
          id = "qwen-flash-next";
          name = "Qwen3.8-Flash-Next (self-hosted)";
          reasoning = true;
          compat.supportsReasoningEffort = true;
          thinkingLevelMap = {
            minimal = null;
            xhigh = null;
            max = null;
          };
          input = [ "text" "image" ];
          contextWindow = 262144;
          maxTokens = 8192;
        }
        {
          # Ornith-1.5-35B-A3B MoE, MLX 6-bit. A reasoning model: each turn
          # opens with a <think> block. The Mac gateway allows 97535 tokens
          # (prompt + output) for this model in GPU memory (memory_budget.py)
          # and rejects more; 96000 makes pi compact first.
          id = "ornith-coder";
          name = "Ornith 1.5 35B 6-bit (self-hosted)";
          reasoning = true;
          contextWindow = 96000;
          maxTokens = 32768;
        }
        {
          id = "qwen-coder";
          name = "Qwen3-Coder 30B 4-bit (self-hosted)";
          reasoning = false;
          contextWindow = 75000; # gateway memory limit: 76422
          maxTokens = 65536;
        }
        {
          id = "qwen-coder-8bit";
          name = "Qwen3-Coder 30B 8-bit (self-hosted)";
          reasoning = false;
          contextWindow = 24000; # gateway memory limit: 24721
          maxTokens = 65536;
        }
      ];
    };

    providers.openrouter = {
      baseUrl = "https://openrouter.ai/api/v1";
      api = "openai-completions";
      apiKey = "!cat ${openRouterKeyFile}";
      models = [
        {
          id = "deepseek/deepseek-v4.1-flash";
          compat.openRouterRouting.ignore = [ "together" ];
          name = "DeepSeek V4.1 Flash";
          reasoning = true;
          input = [ "text" "image" ];
          contextWindow = 1048576;
          maxTokens = 384000;
          cost = {
            input = 0.15;
            output = 0.6;
            cacheRead = 0.003;
            cacheWrite = 0;
          };
        }
      ];
    };
  };
in
{
  home.packages = [ pi ];
  home.file.".pi/agent/models.json".text = builtins.toJSON piModels;
}
