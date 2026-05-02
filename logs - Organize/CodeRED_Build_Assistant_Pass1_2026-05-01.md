# CodeRED Build Assistant — Pass 1

Date: 2026-05-01
Branch: `codered-build-assistant-pass1`

## Goal

Remove the manual Visual Studio compile friction for the CodeRED ScriptHookRDR AI Menu.

This pass adds a local Python/Tkinter Build Assistant that can:

- scan the Code_RED project folder
- scan the selected RDR game folder
- detect Visual Studio C++ Build Tools through `cl.exe`, `vswhere.exe`, `VsDevCmd.bat`, or `vcvars64.bat`
- refuse to build when required source/compiler files are missing
- build `CodeRED_AI_Menu.cpp` into `CodeRED_AI_Menu.asi`
- validate the ASI output with a Windows PE/MZ signature check
- back up existing runtime files before install
- install the ASI, INI, `data/codered`, and `scratch` folder into the selected game folder
- write readable logs and JSON scan reports

## Added

```text
tools/codered_build_assistant.py
Run_CodeRED_Build_Assistant.bat
logs/CodeRED_Build_Assistant_Pass1_2026-05-01.md
```

## Primary target

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.cpp
```

Build output:

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/build/CodeRED_AI_Menu.asi
```

## Runtime install target

The assistant installs only runtime files beside `RDR.exe`:

```text
CodeRED_AI_Menu.asi
CodeRED_AI_Menu.ini
data/codered/*
scratch/
```

It avoids copying build clutter:

```text
*.obj
*.pdb
*.lib
build/
```

## Usage

From the repo root:

```bat
Run_CodeRED_Build_Assistant.bat
```

Or from command line:

```bat
py -3 tools\codered_build_assistant.py scan --project-root "%CD%"
py -3 tools\codered_build_assistant.py build --project-root "%CD%"
py -3 tools\codered_build_assistant.py build-install --project-root "%CD%" --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET"
```

## Safety rules

The assistant refuses to build if:

- the project folder is missing
- `CodeRED_AI_Menu.cpp` is missing
- Visual Studio C++ tools cannot be found

The assistant refuses to install if:

- the selected game folder does not contain `RDR.exe`
- the ASI has not been built
- the ASI does not look like a Windows PE/MZ binary
- `CodeRED_AI_Menu.ini` is missing

## Local syntax check

The script was syntax-checked with:

```text
python3 -m py_compile tools/codered_build_assistant.py
```

## Next pass

After this app is confirmed on the user's machine, the next useful pass is the no-recompile actor data layer:

- generate `data/codered/actor_enum_map.csv` from `Enums.h`
- validate roster entries before spawn
- write actor-resolution proof JSON before native spawn
- make roster/profile edits through Python tools instead of recompiling
