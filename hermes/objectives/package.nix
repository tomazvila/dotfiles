{ pkgs, base }:
pkgs.lib.makeOverridable
  ({ extraPythonPackages ? [], extraDependencyGroups ? [] }:
    let
      upstream = base.override { inherit extraPythonPackages extraDependencyGroups; };
      runtime = pkgs.runCommand "hermes-objective-runtime" {} ''
        mkdir -p $out
        cp -R -L ${upstream.hermesVenv}/lib/python3.12/site-packages/hermes_cli $out/hermes_cli
        chmod -R u+w $out/hermes_cli
        cp ${./kanban_objectives.py} $out/hermes_cli/kanban_objectives.py
        ${upstream.hermesVenv}/bin/python ${./patch_runtime.py} $out
      '';
    in pkgs.runCommand "hermes-agent-objectives" {
      nativeBuildInputs = [ pkgs.makeWrapper ];
      passthru = { inherit upstream runtime; hermesVenv = upstream.hermesVenv; };
      meta = upstream.meta;
    } ''
      mkdir -p $out/bin
      ln -s ${upstream}/share $out/share
      for program in hermes hermes-agent hermes-acp; do
        makeWrapper ${upstream}/bin/$program $out/bin/$program \
          --prefix PYTHONPATH : ${runtime} --prefix PATH : $out/bin
      done
      for program in python python3 python3.12; do
        makeWrapper ${upstream.hermesVenv}/bin/$program $out/bin/$program \
          --prefix PYTHONPATH : ${runtime} --prefix PATH : $out/bin
      done
      makeWrapper ${upstream.hermesVenv}/bin/python $out/bin/hermes-objectives \
        --prefix PYTHONPATH : ${runtime} --prefix PATH : $out/bin \
        --add-flags '-m hermes_cli.kanban_objectives'
    '') {}
