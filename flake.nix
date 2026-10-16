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
    # Hermes Agent ships its own flake (uv2nix build) with a Home Manager
    # module. Pinned to a release tag; bump the tag to update. It keeps its
    # own nixpkgs pin: its package needs packages (e.g. tirith) that are
    # newer than this repo's nixpkgs, and upstream only tests its own pin.
    hermes-agent.url = "github:NousResearch/hermes-agent/v2026.9.7";
    hermes-agent.inputs.home-manager.follows = "home-manager";
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
            inputs.hermes-agent.homeManagerModules.default
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
      hermes-objectives = self.darwinConfigurations.mac.config.home-manager.users.lilvilla.home.file.".hermes/objective-runtime".source;
      neovim = neovimPackage;
      default = neovimPackage;
    };
    packages.${linuxSystem} = {
      neovim = mkNeovim linuxSystem;
      default = mkNeovim linuxSystem;
    };
    checks.${system}.hermes-objectives = let
      pkgs = import nixpkgs { inherit system; };
      package = self.packages.${system}.hermes-objectives;
    in pkgs.runCommand "hermes-objectives-regressions" {} ''
      export HERMES_TEST_KANBAN_API=${package.upstream}/share/hermes-agent/plugins/kanban/dashboard/plugin_api.py
      export HERMES_TEST_EVIDENCE_VERIFIER=${./hermes/objectives/verify_evidence.py}
      mkdir -p "$TMPDIR/objectives/tests"
      cp ${./hermes/objectives/tests}/*.py "$TMPDIR/objectives/tests/"
      cp ${./hermes/objectives/verify_evidence.py} "$TMPDIR/objectives/verify_evidence.py"
      cp ${./hermes/objectives/verify_terminal_readiness.py} "$TMPDIR/objectives/verify_terminal_readiness.py"
      cp ${./hermes/objectives/verify_readiness_disposition.py} "$TMPDIR/objectives/verify_readiness_disposition.py"
      ${package}/bin/python -m unittest discover -s "$TMPDIR/objectives/tests" -v
      touch $out
    '';
  };
}
