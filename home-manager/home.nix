{ config, pkgs, ... }:

{
  home.username = "tomasmazvila";
  home.homeDirectory = "/Users/tomasmazvila";

  home.packages = [
    pkgs.ripgrep
    pkgs.htop
    pkgs.tmux
  ];

  programs.git = {
    enable = true;
    userName = "tomasmazvila";
    userEmail = "tomas.mazvila@nosto.com";
  };

  programs.home-manager.enable = true;

  home.stateVersion = "25.05";
}
