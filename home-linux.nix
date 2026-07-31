# Standalone home-manager config for the homelab server (deploy@homelab).
# Apply with: home-manager switch --flake ~/dotfiles#deploy
{ ... }: {
  imports = [
    ./common.nix
  ];

  home.username = "deploy";
  home.homeDirectory = "/home/deploy";

  # Standalone home-manager manages itself (provides the `home-manager` command)
  programs.home-manager.enable = true;
}
