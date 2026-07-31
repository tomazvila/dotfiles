{ config, lib, pkgs, ... }:

let
  codexHome = "${config.home.homeDirectory}/.codex";
  tmuxStatusHook = "${codexHome}/hooks/tmux-codex-status.sh";
  sessionCheckpointHook = "${codexHome}/hooks/session_checkpoint.py";
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
  checkpointCommand = timeout: statusMessage: {
    type = "command";
    command = "${pkgs.python3}/bin/python3 ${sessionCheckpointHook}";
    inherit timeout statusMessage;
  };
in
{
  home.file.".codex/hooks/tmux-codex-status.sh" = {
    source = ./hooks/tmux-codex-status.sh;
    executable = true;
  };

  home.file.".codex/hooks/session_checkpoint.py" = {
    source = ./hooks/session_checkpoint.py;
    executable = true;
    force = true;
  };

  home.file.".codex/hooks/analyze_session.py" = {
    source = ./hooks/analyze_session.py;
    executable = true;
    force = true;
  };

  home.file.".codex/hooks.json" = {
    force = true;
    text = builtins.toJSON {
      description = "Global status and lossless session-checkpoint hooks.";
      hooks = {
      SessionStart = [
        {
          matcher = "startup|resume|clear";
          hooks = [ (hookCommand "idle") ];
        }
        {
          matcher = "compact";
          hooks = [ (checkpointCommand 30 "Linking the pre-compaction checkpoint") ];
        }
      ];
      SessionEnd = [
        {
          hooks = [ (checkpointCommand 3 "Saving the final session checkpoint") ];
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
      PreCompact = [
        {
          matcher = "manual|auto";
          hooks = [ (checkpointCommand 120 "Saving lossless session checkpoint") ];
        }
      ];
      PostCompact = [
        {
          matcher = "manual|auto";
          hooks = [ (checkpointCommand 30 "Recording completed compaction") ];
        }
      ];
      Stop = [
        {
          hooks = [ (hookCommand "idle") ];
        }
      ];
      };
    } + "\n";
  };

  home.activation.codexHooksFeatureFlag = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    ${pkgs.python3}/bin/python3 ${./scripts/enable-hooks-feature.py}
  '';
}
