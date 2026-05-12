{ pkgs }:
let
  python3 = pkgs.python3;

  cargo-python = python3.pkgs.buildPythonPackage rec {
    pname = "cargo";
    version = "0.3";
    pyproject = true;

    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/8d/ac/d3ac29288dde6e7358af4340c736334ac5fe99d601df3ab4805cf31ae59c/cargo-0.3.tar.gz";
      hash = "sha256-OFNKh3st8486tsJ2fmczUYiN/rBizm8qcVs9zmyh+P4=";
    };

    postPatch = ''
      substituteInPlace pyproject.toml \
        --replace-fail 'requires = ["poetry>=0.12"]' 'requires = ["poetry-core"]' \
        --replace-fail 'build-backend = "poetry.masonry.api"' 'build-backend = "poetry.core.masonry.api"'
    '';

    build-system = [ python3.pkgs.poetry-core ];
    doCheck = false;
  };
in
python3.pkgs.buildPythonApplication rec {
  pname = "utt";
  version = "1.32";
  pyproject = true;

  src = pkgs.fetchFromGitHub {
    owner = "larose";
    repo = "utt";
    rev = "v${version}";
    hash = "sha256-blqFj6GfEyzcxFeFfbCOJhsPpnYezS1rqyt92IbRO+E=";
  };

  postPatch = ''
    substituteInPlace pyproject.toml \
      --replace-fail 'requires = ["poetry>=0.12"]' 'requires = ["poetry-core"]' \
      --replace-fail 'build-backend = "poetry.masonry.api"' 'build-backend = "poetry.core.masonry.api"'
  '';

  build-system = [ python3.pkgs.poetry-core ];

  dependencies = [
    python3.pkgs.argcomplete
    cargo-python
  ];

  doCheck = false;

  meta = {
    description = "Ultimate Time Tracker - a simple command-line time tracking tool";
    homepage = "https://github.com/larose/utt";
    license = pkgs.lib.licenses.gpl3Only;
  };
}
