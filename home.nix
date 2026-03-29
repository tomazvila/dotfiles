{ pkgs, neovimPackage, ... }: {
  imports = [
    ./tmux
    ./aerospace
  ];

  home.stateVersion = "24.11";

  home.packages = [
    pkgs.git
    pkgs.ripgrep
    pkgs.bat
    pkgs.difftastic
    pkgs.jq
    pkgs.hyperfine
    pkgs.procs
    pkgs.nodejs_22
    pkgs.tree
    neovimPackage
  ];

  programs.git = {
    enable = true;
    settings.user.name = "tomazvila";
    settings.user.email = "tomazvila@outlook.com";
  };

  programs.zsh = {
    enable = true;
    enableCompletion = true;
    shellAliases = {
      ll = "ls -l";
    };
    initContent = ''
      export NPM_CONFIG_PREFIX="$HOME/.npm-global"
      export PATH="$HOME/.npm-global/bin:$PATH"
      export PATH="$HOME/.opencode/bin:$PATH"
      export PATH="$HOME/.local/bin:$PATH"
      export PATH="/opt/homebrew/bin:$PATH"
    '';
  };

  programs.ghostty = {
    enable = true;
    package = null;  # Installed via Homebrew, not nix
    settings = {
      font-family = "JetBrainsMono Nerd Font";
      window-padding-y = "2,0";
      command = "/bin/zsh -l -c '${pkgs.tmux}/bin/tmux new-session -A -s main'";
    };
  };
}
