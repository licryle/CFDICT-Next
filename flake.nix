{
  description = "CFDICT-Next — Chinese-French dictionary: CFDICT + CC-CEDICT scope + LLM-generated French";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = with pkgs; [
            python312
            python312Packages.pytest
            python312Packages.pyyaml
            python312Packages.jsonschema
            git
            gzip
          ];

          # Importable package without installation: `import cfdict_next`
          # works in `nix develop`, and scripts/*.py shims resolve it.
          PYTHONPATH = "src";

          shellHook = ''
            echo "CFDICT-Next dev shell — $(python3 --version)"
          '';
        };
      });
    };
}
