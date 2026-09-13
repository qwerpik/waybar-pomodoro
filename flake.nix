{
  description = "A lightweight, race-free Pomodoro timer module for Waybar";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      packages = forAllSystems (pkgs: {
        default = pkgs.callPackage ./default.nix { };
        waybar-pomodoro = pkgs.callPackage ./default.nix { };
      });

      apps = forAllSystems (pkgs: {
        default = {
          type = "app";
          program = "${self.packages.${pkgs.system}.default}/bin/waybar-pomodoro";
        };
      });

      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          inputsFrom = [ self.packages.${pkgs.system}.default ];
          packages = with pkgs; [
            python3Packages.ruff
            python3Packages.mypy
            python3Packages.pytest
          ];
        };
      });

      homeManagerModules.default = import ./nix/home-manager.nix self;
      homeManagerModules.waybar-pomodoro = self.homeManagerModules.default;

      overlays.default = final: prev: {
        waybar-pomodoro = final.callPackage ./default.nix { };
      };
    };
}
