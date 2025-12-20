{ pkgs, neovimPackage, ... }: {
  imports = [
    ./tmux
    ./aerospace
  ];

  home.stateVersion = "24.11";

  home.packages = [
    pkgs.git
    pkgs.ripgrep
    pkgs.nodejs_22
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
    initContent = ''
      export NPM_CONFIG_PREFIX="$HOME/.npm-global"
      export PATH="$HOME/.npm-global/bin:$PATH"
    '';
  };
}
