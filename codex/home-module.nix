{ config, lib, pkgs, ... }:

let
  codexHome = "${config.home.homeDirectory}/.codex";
  tmuxStatusHook = "${codexHome}/hooks/tmux-codex-status.sh";
  hookCommand = state: {
    type = "command";
    command = "${tmuxStatusHook} ${state}";
    timeout = 2;
  };
  legacyClearWaitingCommand = {
    type = "command";
    command = "[ -n \"$TMUX_PANE\" ] && tmux set-option -w -u -t \"$TMUX_PANE\" @ai-waiting 2>/dev/null; true";
    timeout = 2;
  };
in
{
  home.file.".codex/hooks/tmux-codex-status.sh" = {
    source = ./hooks/tmux-codex-status.sh;
    executable = true;
  };

  home.file.".codex/hooks.json".text = builtins.toJSON {
    hooks = {
      SessionStart = [
        {
          matcher = "startup|resume|clear";
          hooks = [ (hookCommand "idle") ];
        }
      ];
      UserPromptSubmit = [
        {
          hooks = [ (hookCommand "running") ];
        }
      ];
      PreToolUse = [
        {
          hooks = [ legacyClearWaitingCommand ];
        }
        {
          hooks = [ (hookCommand "running") ];
        }
      ];
      PermissionRequest = [
        {
          hooks = [ (hookCommand "waiting") ];
        }
      ];
      PostToolUse = [
        {
          hooks = [ (hookCommand "running") ];
        }
      ];
      Stop = [
        {
          hooks = [ (hookCommand "idle") ];
        }
      ];
    };
  } + "\n";

  home.activation.codexHooksFeatureFlag = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    ${pkgs.python3}/bin/python3 ${./scripts/enable-hooks-feature.py}
  '';
}
