# pi coding agent (https://pi.dev/), installed from the upstream release
# binary via pkgs/pi.nix. Runtime state and settings live in ~/.pi/agent/
# (auth.json, settings.json, ...) and are written by pi itself, so they are
# intentionally not managed here.
{ pkgs, ... }:
let
  pi = import ../pkgs/pi.nix { inherit pkgs; };
in
{
  home.packages = [ pi ];
}
