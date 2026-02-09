{ pkgs, ... }: {
  environment.systemPackages = [
    # System-wide packages (user packages go in home.nix)
  ];

  nix.settings.experimental-features = "nix-command flakes";

  programs.zsh.enable = true;

  security.pam.services.sudo_local.touchIdAuth = true;

  system.stateVersion = 6;
  system.primaryUser = "lilvilla";

  users.users.lilvilla = {
    name = "lilvilla";
    home = "/Users/lilvilla";
  };

  homebrew = {
    enable = true;
    onActivation = {
      autoUpdate = true;
      cleanup = "zap";
    };
    taps = [
      "nikitabobko/tap"
    ];
    casks = [
      "anki"
      "discord"
      "docker"
      "ghostty"
      "nikitabobko/tap/aerospace"
      "obsidian"
      "steam"
      "telegram"
    ];
  };
}
