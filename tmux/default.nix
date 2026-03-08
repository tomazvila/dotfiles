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
      # Session persistence (loaded before catppuccin so theme status bar wins)
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
      # Theme (loaded after continuum so it controls status-right)
      {
        plugin = catppuccin;
        extraConfig = ''
          set -g @catppuccin_flavor 'mocha'
          set -g @catppuccin_window_current_text "#{window_name}"
          set -g @catppuccin_status_modules_right "session battery date_time"
          set -g @catppuccin_date_time_text "%H:%M"
        '';
      }
      # Battery (loaded after catppuccin so the theme can style it)
      {
        plugin = battery;
        extraConfig = "";
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
