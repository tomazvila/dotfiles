# Shared home-manager config: used by both the mac (home.nix) and the
# homelab server (home-linux.nix).
{ pkgs, neovimPackage, ... }: {
  imports = [
    ./tmux
    ./pi
  ];

  home.stateVersion = "24.11";

  # Available to login and non-interactive shells, including Codex over SSH.
  home.sessionPath = [
    "$HOME/.local/bin"
    "/opt/homebrew/bin"
  ];

  home.packages = [
    pkgs.git
    pkgs.ripgrep
    pkgs.fd
    pkgs.bat
    pkgs.difftastic
    pkgs.diffnav
    pkgs.jq
    pkgs.hyperfine
    pkgs.procs
    pkgs.nodejs_22
    pkgs.tree
    pkgs.tbls
    pkgs.d2
    neovimPackage
    (import ./pkgs/utt.nix { inherit pkgs; })
    (import ./pkgs/mermaid-ascii.nix { inherit pkgs; })
    (import ./pkgs/headroom.nix { inherit pkgs; })
  ];

  xdg.configFile."diffnav/config.yml".text = ''
    ui:
      showFileTree: true
      showDiffStats: true
      sideBySide: true
      icons: nerd-fonts-filetype
  '';

  programs.ssh = {
    enable = true;
    enableDefaultConfig = false;
    matchBlocks."gitlab.com" = {
      hostname = "gitlab.com";
      identityFile = "~/.ssh/id_ed25519";
    };
    matchBlocks."workofo-target" = {
      hostname = "192.168.1.207";
      user = "lilvilla";
      identityFile = "~/.ssh/id_ed25519";
      identitiesOnly = true;
    };
  };

  programs.git = {
    enable = true;
    settings.user.name = "tomazvila";
    settings.user.email = "tomazvila@outlook.com";
    settings.push.autoSetupRemote = true;
    settings.pager.diff = "diffnav";
    settings.pager.show = "diffnav";
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
      # macOS-only path; harmless no-op on Linux
      export PATH="/opt/homebrew/bin:$PATH"

      export MCP_TIMEOUT=60000

      # Edit command line in $EDITOR with Ctrl+X Ctrl+E
      autoload -U edit-command-line
      zle -N edit-command-line
      bindkey '^X^E' edit-command-line
    '';
  };
}
