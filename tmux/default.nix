{ pkgs, ... }:

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
        '';
      }
    ];

    extraConfig = ''
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

      # Reload config
      bind r source-file ~/.config/tmux/tmux.conf \; display "Config reloaded!"

      # Override rename to also disable auto-rename for that window
      bind , command-prompt -I "#W" "rename-window '%%'; set-window-option automatic-rename off"
    '';
  };
}
