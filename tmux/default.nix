{ pkgs, ... }:

let
  tokyoNight = pkgs.tmuxPlugins.tokyo-night-tmux;
  cnScript = "${tokyoNight}/share/tmux-plugins/tokyo-night-tmux/src/custom-number.sh";
  # Conditional color based on window state:
  #   AI waiting (needs permission/input) = red, silent (idle) = green, active (output) = yellow, default = foreground
  stateColor = "#{?#{==:#{@codex-state},waiting},#[fg=#f7768e],#{?#{==:#{@codex-state},running},#[fg=#e0af68],#{?#{==:#{@codex-state},idle},#[fg=#73daca],#{?#{@ai-waiting},#[fg=#f7768e],#{?#{window_silence_flag},#[fg=#73daca],#{?#{window_activity_flag},#[fg=#e0af68],#[fg=#a9b1d6]}}}}}}";
in
{
  programs.tmux = {
    enable = true;
    shell = "${pkgs.zsh}/bin/zsh";
    terminal = "tmux-256color";
    prefix = "C-a";
    mouse = true;
    keyMode = "vi";
    baseIndex = 1;
    escapeTime = 10;
    historyLimit = 50000;
    sensibleOnTop = true;

    plugins = with pkgs.tmuxPlugins; [
      # Session persistence
      {
        plugin = resurrect;
        extraConfig = "set -g @resurrect-strategy-nvim 'session'";
      }
      {
        plugin = continuum;
        extraConfig = ''
          set -g @continuum-restore 'on'
          set -g @continuum-save-interval '10'
        '';
      }
      # Theme
      {
        plugin = tokyo-night-tmux;
        extraConfig = ''
          set -g @tokyo-night-tmux_show_battery_widget 1
          set -g @tokyo-night-tmux_show_path 1
          set -g @tokyo-night-tmux_path_format relative
          set -g @tokyo-night-tmux_show_datetime 1
          set -g @tokyo-night-tmux_date_format YMD
          set -g @tokyo-night-tmux_time_format 24H
          set -g @tokyo-night-tmux_show_git 0
        '';
      }
    ];

    extraConfig = ''
      # Automatically renumber windows when one is deleted
      set -g renumber-windows on

      # Send C-a to shell with C-a C-a (for beginning of line)
      bind C-a send-prefix

      # True color support
      set -ag terminal-overrides ",xterm-256color:RGB"

      # Split panes with | and - (preserve current path)
      bind | split-window -h -c "#{pane_current_path}"
      bind - split-window -v -c "#{pane_current_path}"
      # Also override default split bindings to preserve path
      bind % split-window -h -c "#{pane_current_path}"
      bind '"' split-window -v -c "#{pane_current_path}"

      # Vi-style pane navigation
      bind h select-pane -L
      bind j select-pane -D
      bind k select-pane -U
      bind l select-pane -R

      # Resize panes with Ctrl+hjkl
      bind -r C-h resize-pane -L 5
      bind -r C-j resize-pane -D 5
      bind -r C-k resize-pane -U 5
      bind -r C-l resize-pane -R 5

      # New window in current path
      bind c new-window -c "#{pane_current_path}"

      # Vi copy mode bindings
      bind -T copy-mode-vi v send-keys -X begin-selection
      bind -T copy-mode-vi y send-keys -X copy-selection-and-cancel
      bind -T copy-mode-vi C-v send-keys -X rectangle-toggle

      # Cycle to last window
      bind Tab last-window

      # Reload config
      bind r source-file ~/.config/tmux/tmux.conf \; display "Config reloaded!"

      # Override rename to also disable auto-rename for that window
      bind , command-prompt -I "#W" "rename-window '%%'; set-window-option automatic-rename off"

      # Dynamic window status colors based on activity/silence
      # Yellow = process producing output (working), Green = no output for 10s (idle/waiting)
      set -g monitor-activity on
      set -g monitor-silence 10
      set -g visual-activity off
      set -g visual-silence off
      set -g activity-action any
      set -g silence-action any

      # Disable theme's activity style so our format conditionals control the color
      set -g window-status-activity-style default

      # Override window-status-format with state-aware colors
      set -g window-status-format "${stateColor}#[bg=#1A1B26,nobold,noitalics,nounderscore,nodim] #{?#{==:#{pane_current_command},ssh},󰣀 , }${stateColor}#[bg=#1A1B26,nobold,noitalics,nounderscore,nodim]#(${cnScript} #I digital)#W#[nobold,dim]#{?window_zoomed_flag, #(${cnScript} #P dsquare), #(${cnScript} #P hsquare)}${stateColor}#{?window_last_flag,󰁯  , }"
    '';
  };
}
