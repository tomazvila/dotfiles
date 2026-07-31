# macOS-specific home config on top of common.nix
{ pkgs, ... }: {
  imports = [
    ./common.nix
  ];

  programs.ghostty = {
    enable = true;
    package = null;  # Installed via Homebrew, not nix
    settings = {
      font-family = "JetBrainsMono Nerd Font";
      # Match Ghostty's background to the tmux Tokyo Night status bar so the
      # sub-cell residual gap at the bottom (the window height isn't an exact
      # multiple of the cell height under tiling) blends in instead of showing.
      background = "1a1b26";
      window-padding-y = "0,0";
      window-padding-balance = true;
      window-padding-color = "background";
      window-step-resize = true;
      command = "/bin/zsh -l -c '${pkgs.tmux}/bin/tmux new-session -A -s main'";
    };
  };
}
