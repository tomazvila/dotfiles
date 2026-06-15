{ pkgs, ... }: {
  environment.systemPackages = [
    # System-wide packages (user packages go in home.nix)
  ];

  nix.settings.experimental-features = "nix-command flakes";

  programs.zsh.enable = true;

  security.pam.services.sudo_local.touchIdAuth = true;

  system.stateVersion = 6;
  system.primaryUser = "lilvilla";

  system.defaults.spaces.spans-displays = true;

  # Keep macOS from jumping to a different Space when an app is activated.
  system.defaults.NSGlobalDomain.AppleSpacesSwitchOnActivate = false;

  users.users.lilvilla = {
    name = "lilvilla";
    home = "/Users/lilvilla";
  };

  homebrew = {
    enable = true;
    onActivation = {
      autoUpdate = true;
      cleanup = "none";
    };
    casks = [
      "font-jetbrains-mono-nerd-font"
      "font-noto-sans-symbols-2"
      "codex"
      "anki"
      "dbeaver-community"
      "discord"
      "docker-desktop"
      "ghostty"
      "libreoffice"
      "obsidian"
      "openmtp"
      "pritunl"
      "steam"
      "telegram"
    ];
  };
}
