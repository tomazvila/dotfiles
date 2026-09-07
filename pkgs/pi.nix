{ pkgs }:
let
  version = "0.84.1";

  artifacts = {
    aarch64-darwin = {
      file = "pi-darwin-arm64.tar.gz";
      hash = "sha256-aDyEJh9AuHC0p8zxgaSK1uzXGFOwES0bthdTlTDGEh0=";
    };
    x86_64-linux = {
      file = "pi-linux-x64.tar.gz";
      hash = "sha256-VjTX69GCdLY68zcelC80LXS+oBI4lXXB0f8VzmyoDC8=";
    };
  };

  system = pkgs.stdenv.hostPlatform.system;
  artifact = artifacts.${system} or (throw "pi: unsupported system ${system}");
in
pkgs.stdenvNoCC.mkDerivation {
  pname = "pi";
  inherit version;

  src = pkgs.fetchurl {
    url = "https://github.com/earendil-works/pi/releases/download/v${version}/${artifact.file}";
    inherit (artifact) hash;
  };

  sourceRoot = "pi";
  dontConfigure = true;
  dontBuild = true;

  nativeBuildInputs = pkgs.lib.optionals pkgs.stdenv.hostPlatform.isLinux [
    pkgs.autoPatchelfHook
  ];

  buildInputs = pkgs.lib.optionals pkgs.stdenv.hostPlatform.isLinux [
    pkgs.stdenv.cc.libc
  ];

  installPhase = ''
    runHook preInstall

    mkdir -p "$out/bin" "$out/lib/pi"
    cp -R ./. "$out/lib/pi/"
    ln -s "$out/lib/pi/pi" "$out/bin/pi"

    runHook postInstall
  '';

  meta = {
    description = "Minimal terminal coding harness";
    homepage = "https://pi.dev/";
    license = pkgs.lib.licenses.mit;
    mainProgram = "pi";
    platforms = builtins.attrNames artifacts;
  };
}
