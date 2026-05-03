CODE RED -
================================
by GLITCHED MATRIX Prototype Lab

Introduction
------------
Code RED is a portable prototype lab for researching, viewing, tuning, and packaging Red Dead Redemption-style resources and experimental vehicle/gameplay patches. This build keeps the current workbench, the CodeRED Tuner, the arcade test demo, the MP Companion lane, RPF edit helpers, CodeX/XML bundle tools, and the prepared faction-war/plugin reference project while removing large editor/build caches that do not need to ship with a user-facing package.

The goal of this pass is simple: keep the working tools, keep the current relative folder layout, remove stale clutter, remove old tuner-path references, and make the package easier for a new user to install and run.

Script work source of truth
---------------------------
Use this section before adding, editing, or compiling script/menu features.

Core rule:
- Do not guess native names, hashes, function signatures, or argument counts.
- A script/menu command is allowed only after it is verified from real headers, a known working wrapper/API, or a tiny compile/runtime proof.
- Research notes are not production code until the native/wrapper proof is recorded.

Keep script work separated into these lanes:

1. Trainer / ScriptHook / RedHook lane
   - Main menu path for live actor control, teleport, weather, spawn, animation, and debug commands.
   - This is the correct lane for the Code RED actor travel menu.
   - Start with selected actor + destination + log result before adding advanced pathing.

2. SC-CL lane
   - Tiny internal script experiments only.
   - Do not rebuild the full Code RED menu through SC-CL.
   - Use only real SC-CL headers and actual compiled output as proof.

3. RPF/resource lane
   - Archive inspection, tune edits, WSI/WGD correlation, resource exports, copied-archive patch tests.
   - Never bulk patch live archives. Test one copied archive and one changed placement at a time.

4. Research lane
   - Silent Virtues/other trainer observations, string scans, native maps, menu feature comparisons, and behavior notes.
   - Do not copy third-party trainer code/assets. Use clean-room feature mapping only.

Recommended script proof order:

    show player coordinates
    save location slot
    select nearest actor
    teleport selected actor to saved location
    command selected actor to follow/regroup
    command selected actor to guard/travel to a coordinate

Every script proof should record:
- lane used
- source/header/wrapper used
- exact function signature if known
- tiny proof file or runtime test
- result
- failure behavior
- next safe step

Key features
------------
1. Code RED Resource Workbench
   - Main launch surface for file/resource inspection.
   - Workspace staging folders for imports, exports, game files, logs, and proof output.
   - RPF/lab launch buttons for related tools.
   - One-click access to the current CodeRED Tuner and current Test Demo.

2. CodeRED Tuner
   - Red/black themed vehicle-tuning interface.
   - Car01 and Truck01 tune controls.
   - Safe preset save/load flow.
   - Stock reload support from bundled stock_vehicle_files/.
   - Patch export to exports/ without overwriting source archives.
   - Optional mod-pack/export lanes for controlled experiments.
   - Built-in guide tab and smoke-test helpers.

3. Code Red Arcade demo
   - External Panda3D-preferred demo for testing feel before archive work.
   - 1920x1080 default window.
   - Esc/P pause and mouse-operable settings.
   - F fullscreen toggle.
   - Mouse look, mousewheel zoom, and zoom-linked FOV.
   - Shift boost, target lock, enemy waves, pickups, explosions, part damage, and replaceable SFX.
   - F12 screenshots to screenshots/.
   - Tk fallback path retained for machines that cannot run Panda3D in auto mode.

4. Companion and helper apps
   - MP Companion v19 research lane.
   - RPF edit lab launcher.
   - Cleanroom world prototype launcher.
   - CodeX/XML export/import helpers.
   - Script compile lab materials kept lightweight; the oversized third-party source archive cache was removed from this lite package.

5. Prepared plugin/reference project
   - Source, headers, RedHook runtime reference files, and final .red build output are retained.
   - Visual Studio cache, intermediate object files, PDBs, precompiled headers, and temporary build logs were removed.

Requirements
------------
Recommended:
- Windows 10 or newer.
- Python 3.10 or newer. Python 3.12 is fine.
- Internet access for first-time Python package install.
- A GPU/OpenGL-capable driver for the Panda3D arcade renderer.

Python packages used by the full package:
- panda3d
- pygame
- cryptography
- pillow
- numpy
- matplotlib

The tuner itself primarily needs panda3d, pygame, and cryptography. The full workbench requirements file also includes pillow, numpy, and matplotlib for helper/viewer lanes.

Installation
------------
1. Extract the zip. Do not run the tools directly from inside the zip preview window.
2. Open the extracted Code_RED folder.
3. Run Code_RED_Dependency_Installer.bat once.
4. Run Run_Code_RED.bat to open the main Code RED workbench.
5. From the workbench, use Open Tuner or Test Demo.

Direct tuner install/launch:
1. Open Code_RED\related_apps\CodeRED_Tuner\.
2. Run Install_CodeRED_Tuner_Dependencies.bat once if dependencies are missing.
3. Run run_CodeRED_Tuner.bat.
4. Run run_Test_Demo.bat for the arcade demo only.

Manual install from Command Prompt:

    cd /d path\to\Code_RED
    py -3 -m pip install -r requirements.txt

Manual tuner-only install:

    cd /d path\to\Code_RED\related_apps\CodeRED_Tuner
    py -3 -m pip install -r requirements.txt

How to use Code RED
-------------------
1. Start with Run_Code_RED.bat.
2. Open a workspace or use the extracted Code_RED folder as the workspace.
3. Use the workbench buttons to open imports, logs, the RPF editor, the tuner, or the test demo.
4. Put test archives/resources in imports/ or a copied workspace folder.
5. Export generated files to exports/ and review them before replacing anything in a real game directory.
6. Keep backups of original archives before importing patches.

How to use the CodeRED Tuner
----------------------------
1. Open related_apps\CodeRED_Tuner\run_CodeRED_Tuner.bat.
2. Choose Car01 or Truck01.
3. Adjust sliders or load a preset.
4. Save a custom preset if the settings feel good.
5. Use the Code Red Arcade tab to save/apply settings and run a smoke test.
6. Launch the demo to test vehicle feel.
7. Export patch files only after the demo and settings look correct.
8. Review the export folder before using the files in any live archive workflow.

How to use the Arcade demo
--------------------------
From the tuner:
1. Open the Code Red Arcade tab.
2. Press Smoke Test.
3. Press Save / Apply Arcade Settings.
4. Press Launch Code Red Arcade or Test Demo.
5. Press Stop Arcade before launching a fresh copy.

Direct demo launch:
- Run Code_RED\related_apps\CodeRED_Tuner\run_CodeRed_Arcade.bat.

Arcade controls:
- WASD / Arrow keys: drive.
- Shift: boost.
- Mouse: look/orbit camera.
- Mousewheel: zoom and linked FOV.
- Space: target lock / recenter behavior depending on mode.
- LMB / Q / E: right weapon lane.
- RMB / Ctrl: left weapon lane.
- Esc or P: pause/settings.
- F: fullscreen.
- H or F1: help overlay.
- F12: screenshot.

Bonus demo features
-------------------
- Red desert test arena.
- Hills, ramps, terrain variation, wreck props, and moving scenery.
- Enemy waves with scaling pressure.
- Breakable target parts on rival vehicles.
- Pickups, boost heat, score, hit flashes, shrapnel-style bursts, electrical effects, and explosion effects.
- Replaceable sound folder at related_apps\CodeRED_Tuner\assets\sfx\arcade\.
- Optional lightweight LAN ghost-client broadcasting for local peer cars.
- Runtime settings stored relative to the tuner folder, not a user-specific path.

Folder notes
------------
Keep these together:
- main.py
- python_workbench.py
- requirements.txt
- Run_Code_RED.bat
- tools\
- related_apps\
- related_apps\CodeRED_Tuner\

Generated folders:
- logs\ may be created at runtime.
- exports\ may be created by patch tools.
- screenshots\ may be created by the arcade demo.
- runtime\ inside CodeRED_Tuner stores arcade settings.
- presets_custom\ inside CodeRED_Tuner stores custom tuner presets.

Cleanup performed in this pass
---------------------------------------
Removed from the shipped package:
- Visual Studio .vs cache.
- Browse.VC.db and Solution.VC.db editor databases.
- Precompiled header cache .pch.
- Intermediate .obj, .iobj, .ipdb, .pdb, .tlog, .log, and recipe build files.
- Python __pycache__ folders.
- Old stale tuner-folder references in launcher/probe paths.
- Oversized nested SC-CL-master.zip cache from the experimental compile bundle.
- Temporary compile output logs.

Kept because they are useful or required:
- CodeRED_Tuner source, stock files, presets, mods, sounds, and arcade assets.
- MP Companion v19.
- RPF edit lab.
- CodeX/model XML import/export tools.
- Faction War source/reference runtime and final .red output.
- Lightweight SCCL include/source lab files.

Troubleshooting
---------------
- Python not found: install Python 3.10+ and enable Add Python to PATH.
- Dependency install fails: run py -3 -m pip install -r requirements.txt from the Code_RED folder and read logs if generated.
- Tuner does not open from workbench: run related_apps\CodeRED_Tuner\run_CodeRED_Tuner.bat directly.
- Panda3D demo fails: install dependencies, update graphics drivers, then retry. The demo can still use its fallback path in auto mode.
- No sound: the demo still runs. Check pygame, the active audio device, and assets\sfx\arcade\.
- Patch causes bad behavior: restore your backup archive and export a smaller patch.

Safety notes
------------
This package is for research, prototype testing, and controlled patch creation. Do not overwrite original game archives without backups. Test one change at a time.
