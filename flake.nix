{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-22.11";
    #add vscode as a input
    vscode-server.url = "github:msteen/nixos-vscode-server";
  };
  outputs = {
    self,
    nixpkgs,
    vscode-server,
  } @ inputs: {
    nixosConfigurations.nixos = nixpkgs.lib.nixosSystem {
      #      change this^ to your desired hostname with networking.hostName
      modules = [
        #import the nixosModule from the vscode input
        vscode-server.nixosModule
        ./configuration.nix
      ];
    };
  };
}
