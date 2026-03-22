{
  description = "My Darwin system configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    nix-darwin.url = "github:nix-darwin/nix-darwin/master";
    nix-darwin.inputs.nixpkgs.follows = "nixpkgs";
    home-manager.url = "github:nix-community/home-manager";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";
    nixvim.url = "github:nix-community/nixvim";
    nixvim.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = inputs@{ self, nix-darwin, nixpkgs, home-manager, nixvim, ... }: let
    system = "aarch64-darwin";

    # Build neovim package from our config
    neovimPackage = nixvim.legacyPackages.${system}.makeNixvim (
      import ./neovim { inherit nixpkgs system; }
    );
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
          home-manager.users.lilvilla = import ./home.nix;
          home-manager.extraSpecialArgs = { inherit neovimPackage; };
        }
      ];
    };

    # Also export neovim as a standalone package for testing
    packages.${system} = {
      neovim = neovimPackage;
      default = neovimPackage;
    };
  };
}
