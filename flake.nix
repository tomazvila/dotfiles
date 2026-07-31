{
  description = "My Darwin system configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    nix-darwin.url = "github:nix-darwin/nix-darwin/master";
    nix-darwin.inputs.nixpkgs.follows = "nixpkgs";
    home-manager.url = "github:nix-community/home-manager";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";
    codexHooks.url = "path:./codex";
    codexHooks.inputs.nixpkgs.follows = "nixpkgs";
    codexHooks.inputs.home-manager.follows = "home-manager";
    nixvim.url = "github:nix-community/nixvim";
    nixvim.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = inputs@{ self, nix-darwin, nixpkgs, home-manager, nixvim, ... }: let
    system = "aarch64-darwin";
    linuxSystem = "x86_64-linux";

    # Build neovim package from our config
    mkNeovim = sys: nixvim.legacyPackages.${sys}.makeNixvim (
      import ./neovim { inherit nixpkgs; system = sys; }
    );
    neovimPackage = mkNeovim system;
  in {
    darwinConfigurations."mac" = nix-darwin.lib.darwinSystem {
      inherit system;
      specialArgs = { inherit inputs neovimPackage; };
      modules = [
        ./configuration.nix
        home-manager.darwinModules.home-manager
        {
          nixpkgs.config.allowUnfree = true;
          home-manager.useGlobalPkgs = true;
          home-manager.useUserPackages = true;
          home-manager.backupFileExtension = "backup";
          home-manager.sharedModules = [
            inputs.codexHooks.homeModules.default
          ];
          home-manager.users.lilvilla = import ./home.nix;
          home-manager.extraSpecialArgs = { inherit neovimPackage; };
        }
      ];
    };

    # Standalone home-manager config for the homelab server
    homeConfigurations."deploy" = home-manager.lib.homeManagerConfiguration {
      pkgs = import nixpkgs {
        system = linuxSystem;
        config.allowUnfree = true;
      };
      modules = [ ./home-linux.nix ];
      extraSpecialArgs = { neovimPackage = mkNeovim linuxSystem; };
    };

    # Also export neovim as a standalone package for testing
    packages.${system} = {
      neovim = neovimPackage;
      default = neovimPackage;
    };
    packages.${linuxSystem} = {
      neovim = mkNeovim linuxSystem;
      default = mkNeovim linuxSystem;
    };
  };
}
