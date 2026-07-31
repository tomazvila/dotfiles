# Standalone home-manager config for the homelab server (deploy@homelab).
# Apply with: home-manager switch --flake ~/dotfiles#deploy
{ ... }: {
  imports = [
    ./common.nix
  ];

  home.username = "deploy";
  home.homeDirectory = "/home/deploy";

  # Server-specific SSH hosts (previously hand-managed in ~/.ssh/config):
  # read-only GitHub deploy key + Hetzner Storage Box for restic
  programs.ssh.matchBlocks = {
    "github.com" = {
      identityFile = "~/.ssh/github_homelab";
      identitiesOnly = true;
    };
    "storagebox" = {
      hostname = "u641176.your-storagebox.de";
      user = "u641176";
      port = 23;
      identityFile = "~/.ssh/id_ed25519";
    };
    # Account-level GitHub access for dev clones (the plain github.com entry
    # stays pinned to the homelab repo's read-only deploy key):
    #   git clone git@github-dev:tomazvila/<repo>.git
    "github-dev" = {
      hostname = "github.com";
      identityFile = "~/.ssh/id_ed25519";
      identitiesOnly = true;
    };
  };

  # Standalone home-manager manages itself (provides the `home-manager` command)
  programs.home-manager.enable = true;
}
