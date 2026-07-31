{ pkgs }:

pkgs.buildGoModule rec {
  pname = "mermaid-ascii";
  version = "1.3.0";

  src = pkgs.fetchFromGitHub {
    owner = "AlexanderGrooff";
    repo = "mermaid-ascii";
    rev = version;
    hash = "sha256-lACyrxum1YjIXfoajO7YQdz+pZtQZdZhMqOaa82tsPs=";
  };

  vendorHash = "sha256-aB9sbTtlHbptM2995jizGFtSmEIg3i8zWkXz1zzbIek=";

  # The web UI ships templates/static assets; the CLI itself is self-contained.
  subPackages = [ "." ];

  meta = {
    description = "Render Mermaid graphs as ASCII/Unicode art in your terminal";
    homepage = "https://github.com/AlexanderGrooff/mermaid-ascii";
    license = pkgs.lib.licenses.mit;
    mainProgram = "mermaid-ascii";
  };
}
