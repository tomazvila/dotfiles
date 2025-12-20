{ pkgs, ... }: {
  environment.systemPackages = [
    # System-wide packages (user packages go in home.nix)
  ];

  nix.settings.experimental-features = "nix-command flakes";

  programs.zsh.enable = true;

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
    casks = [
      "ghostty"
    ];
  };
}
