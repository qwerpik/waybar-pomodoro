self: { config, lib, pkgs, ... }:

with lib;

let
  cfg = config.programs.waybar-pomodoro;
in
{
  options.programs.waybar-pomodoro = {
    enable = mkEnableOption "waybar-pomodoro timer module for Waybar";

    package = mkOption {
      type = types.package;
      default = self.packages.${pkgs.system}.default or (pkgs.callPackage ../default.nix { });
      description = "The waybar-pomodoro package to install.";
    };

    settings = mkOption {
      type = types.attrsOf types.anything;
      default = { };
      example = literalExpression ''
        {
          work_duration = 25;
          short_break_duration = 5;
          long_break_duration = 15;
          cycles_before_long_break = 4;
          sound_enabled = true;
          notification_enabled = true;
        }
      '';
      description = "Declarative configuration written to ~/.config/waybar-pomodoro/config.json.";
    };
  };

  config = mkIf cfg.enable {
    home.packages = [ cfg.package ];

    xdg.configFile."waybar-pomodoro/config.json" = mkIf (cfg.settings != { }) {
      text = builtins.toJSON cfg.settings;
    };
  };
}
