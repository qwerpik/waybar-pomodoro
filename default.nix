{ pkgs ? import <nixpkgs> { }
, lib ? pkgs.lib
, python3Packages ? pkgs.python3Packages
, makeWrapper ? pkgs.makeWrapper
, procps ? pkgs.procps
, libcanberra-gtk3 ? pkgs.libcanberra-gtk3
}:

python3Packages.buildPythonApplication rec {
  pname = "waybar-pomodoro";
  version = "1.0.3";
  format = "pyproject";

  src = lib.cleanSourceWith {
    src = ./.;
    filter = path: type:
      let
        baseName = baseNameOf path;
      in
      !(
        baseName == ".git" ||
        baseName == "dist" ||
        baseName == "build" ||
        baseName == ".pytest_cache" ||
        baseName == ".mypy_cache" ||
        baseName == ".ruff_cache" ||
        lib.hasSuffix ".pyc" baseName ||
        lib.hasSuffix ".egg-info" baseName
      );
  };

  nativeBuildInputs = [
    python3Packages.setuptools
    makeWrapper
  ];

  checkPhase = ''
    runHook preCheck
    PYTHONPATH=src python3 -m unittest discover -s tests -v
    runHook postCheck
  '';

  postInstall = ''
    wrapProgram $out/bin/waybar-pomodoro \
      --prefix PATH : ${lib.makeBinPath [ procps libcanberra-gtk3 ]}
  '';

  meta = with lib; {
    description = "A lightweight, race-free Pomodoro timer module for Waybar";
    homepage = "https://github.com/mangowm/waybar-pomodoro";
    license = licenses.mit;
    platforms = platforms.linux;
    mainProgram = "waybar-pomodoro";
  };
}
