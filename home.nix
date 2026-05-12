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
    pkgs.tbls
    pkgs.d2
    neovimPackage
    (import ./pkgs/utt.nix { inherit pkgs; })
  ];

  programs.ssh = {
    enable = true;
    enableDefaultConfig = false;
    matchBlocks."gitlab.com" = {
      hostname = "gitlab.com";
      identityFile = "~/.ssh/id_ed25519";
    };
  };

  programs.git = {
    enable = true;
    settings.user.name = "tomazvila";
    settings.user.email = "tomazvila@outlook.com";
    settings.push.autoSetupRemote = true;
    includes = [
      {
        condition = "hasconfig:remote.*.url:git@gitlab.com:*/**";
        contents = {
          user.name = "KibirVibir";
        };
      }
    ];
  };

  programs.zsh = {
    enable = true;
    enableCompletion = true;
    shellAliases = {
      ll = "ls -l";
    };
    initContent = ''
      export EDITOR=nvim
      export NPM_CONFIG_PREFIX="$HOME/.npm-global"
      export PATH="$HOME/.npm-global/bin:$PATH"
      export PATH="$HOME/.opencode/bin:$PATH"
      export PATH="$HOME/.local/bin:$PATH"
      export PATH="/opt/homebrew/bin:$PATH"

      export MCP_TIMEOUT=60000

      # Edit command line in $EDITOR with Ctrl+X Ctrl+E
      autoload -U edit-command-line
      zle -N edit-command-line
      bindkey '^X^E' edit-command-line
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
