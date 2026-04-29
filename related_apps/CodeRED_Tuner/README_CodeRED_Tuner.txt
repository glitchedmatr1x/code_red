Code RED Tuner v2.5.4 Final Pass
=================================
by GLITCHED MATRIX Prototype Lab

Purpose
-------
Code RED Tuner is a portable Windows-focused tuning and test package for the recovered Car01 / Truck01 vehicle lane. It edits safe XML-style tune values, exports patch trees, provides optional mod-pack export helpers, and launches the Code Red Arcade demo so vehicle changes can be tested immediately before you touch game archives.

Final-pass goal check
---------------------
Reached:
- Portable launchers: no user-specific desktop, drive, or old absolute paths are required.
- Tuner theme: red/black Code RED interface pass with muted footer credit.
- Arcade/demo theme: red/black HUD and fallback renderer, plus a small out-of-the-way credit.
- Main tuner goal: tune Car01 and Truck01 vehsim/vehinput values, save presets, reload stock, export patch packages.
- Demo goal: launch a separate arcade process that reads runtime/arcade_settings.json and keeps working even if the tuner renderer is asleep.
- Controls goal: Esc pause/settings, mouse-operated pause UI, F fullscreen, mouse look, mousewheel zoom with linked FOV, Space target-lock, Shift boost without blocking movement/weapon controls.
- Regression repair: the old embedded blue Drive 3D/Tk preview is not built into the visible tuner UI. The visible demo defaults to the current external arcade.
- Path cleanup: the visible final pass uses stock_vehicle_files, assets/vehicles/concept_vehicle_baked_wire.json, assets/sfx/arcade, input_profiles, runtime, exports, presets_custom, and Mods only. Old shipped .obj/.glb/.fbx/.egg model paths are not required.

Folder layout
-------------
Keep these folders/files together:
- codered_tuner.py: main tuner interface.
- code_red_arcade.py: external arcade/demo.
- Launch_CodeRED_Tuner.py / .pyw: dependency-aware launcher.
- run_CodeRED_Tuner.bat: normal launcher.
- run_CodeRed_Arcade.bat: direct arcade launcher.
- run_Test_Demo.bat: launcher for the demo only.
- Install_CodeRED_Tuner_Dependencies.bat: installs/checks required Python packages.
- requirements.txt: panda3d, pygame, cryptography.
- stock_vehicle_files/: required stock-derived tune XML files used by the sliders.
- input_profiles/: input_car.xml, packaged with exports.
- assets/vehicles/: baked wire vehicle data for the arcade; no external model source is needed.
- assets/sfx/arcade/: replaceable demo sounds.
- Mods/: optional patch/mod packs.
- exports/: created when you export patches or run selftests.
- runtime/: created when the tuner saves arcade settings.
- logs/: created when launchers/selftests write diagnostics.

Installation
------------
1. Extract the complete CodeRED_Tuner folder from the zip. Do not run directly from inside the zip viewer.
2. Install Python 3.10 or newer from python.org if Python is not already installed.
3. Keep “Add Python to PATH” enabled during Python installation when possible.
4. Double-click run_CodeRED_Tuner.bat.
5. The launcher checks dependencies. If anything is missing, it runs pip install -r requirements.txt.
6. If the launcher closes early, open logs/dependency_check_latest.txt or logs/tuner_crash_latest.log.

Manual dependency install
-------------------------
Open Command Prompt inside the CodeRED_Tuner folder and run:

    py -3 -m pip install -r requirements.txt

If py is not available, use:

    python -m pip install -r requirements.txt

How to use the tuner
--------------------
1. Launch run_CodeRED_Tuner.bat.
2. Pick Car01 or Truck01 on the left.
3. Use a preset or adjust sliders manually.
4. Optional: enable Show help inside a slider tab to view compact explanations.
5. Optional: Save Current Preset to presets_custom/.
6. Press Export Patch Files for a normal loose patch package.
7. Use Open Export Folder to inspect the output.

Important tuner sections
------------------------
- Body: mass, center of mass, bound gravity, stability.
- Engine: horsepower, RPM, boost torque, boost duration.
- Transmission: gears, gear delay, forward/reverse MPH targets.
- Axles/Grip: front/rear torque and friction.
- Steering: steering limit, downforce, tire drag.
- Drag: aerodynamic, off-road, vehicle-path drag.
- Damage: burn/damage thresholds.
- Input: vehinput assist thresholds and auto reverse behavior.
- Guide: in-app quick start and safe usage notes.
- Code Red Arcade: save/apply arcade settings, smoke test, launch demo, stop demo, renderer/settings controls.
- Patch Options: optional loose mod-pack export lane.
- RPF Builder: loose patch or copied full tune RPF patch builder. It does not overwrite your selected original archive.
- Spawn Slot: experimental payload/carrier loose export lane for controlled wagon-slot tests.

How to use the arcade/demo
--------------------------
From the tuner:
1. Open the Code Red Arcade tab.
2. Press Smoke Test. This validates settings/assets without opening a renderer.
3. Press Save / Apply Arcade Settings.
4. Press Test Demo or Launch Code Red Arcade.
5. Use Stop Arcade before relaunching a clean copy from the tuner.

Direct launch:
1. Run run_CodeRed_Arcade.bat.
2. It reads runtime/arcade_settings.json if the tuner has already created it.
3. If no settings file exists, the arcade uses safe fallback Car01 values.

Arcade controls
---------------
- WASD / Arrow keys: drive.
- Shift: boost only; holding Shift does not block steering or weapons.
- Mouse: orbit/look camera.
- Mousewheel: zoom camera and automatically adjust FOV with zoom.
- Space: target-lock / cycle live enemies.
- LMB / Q / E: right seeker / weapon lane.
- RMB / Ctrl: left seeker / weapon lane.
- Esc or P: pause/settings.
- F: fullscreen toggle.
- H or F1: help overlay.
- F12: save screenshot to screenshots/.

Bonus demo features
-------------------
- 1920x1080 default window with resizable 16:9 behavior.
- Fullscreen toggle from keyboard or pause/settings menu.
- Procedural red desert arena with visible hills, valleys, ramps, wreck props, and moving terrain tiles.
- Enemy waves increase by +1 each wave, up to the internal performance cap.
- Targetable enemy vehicle parts: panels can break away before a rival is destroyed.
- Player vehicle uses stronger multi-part armor so it does not vanish instantly.
- Boost heat, pickup, repair, score, explosions, shrapnel-style burst effects, electrical hit flashes, muzzle flashes, and splatter marks.
- Pedestrians are spawned for splatter tests.
- Replaceable sound bank for boost, engine, fire, hit, break, explosion, pickup, jump, and land.
- Optional UDP LAN ghost clients for lightweight local peer cars.
- Panda3D renderer by default, with Tk fallback retained for machines that cannot run Panda when launched in auto mode.

Replaceable sounds
------------------
Drop replacement .wav, .ogg, or .mp3 files into:

    assets/sfx/arcade

Supported prefixes:

    fire_left, fire_right, hit, break, explosion, pickup, boost, jump, land, engine

Examples:

    boost_custom.wav
    explosion_big.ogg
    engine_loop.mp3

Screenshots
-----------
Press F12 in the arcade. Files are saved into:

    screenshots/

Selftests
---------
Tuner export selftest:

    py -3 codered_tuner.py --selftest

Arcade no-window selftest:

    py -3 code_red_arcade.py --selftest --settings runtime\arcade_settings.json

The tuner’s Code Red Arcade tab also has a Smoke Test button that runs the arcade selftest through the current Python executable.

Safe export rules
-----------------
- Normal exports are written to exports/.
- The full-RPF builder creates a copied patched archive and does not overwrite the selected original.
- Always back up real game archives before importing or replacing anything.
- Treat Spawn Slot and Train Spawns Cars packs as experimental. Test one change at a time.
- If a patch causes bad behavior, restore the backup archive and export a smaller patch.

Troubleshooting
---------------
- Tuner missing stock files: make sure stock_vehicle_files/ stayed beside codered_tuner.py.
- Demo cannot start Panda3D: run Install_CodeRED_Tuner_Dependencies.bat, then retry. Direct auto fallback can be launched from a command prompt with --renderer auto if needed.
- No sound: the game still runs. Check pygame installation, audio device availability, and assets/sfx/arcade.
- Dependency install fails: open logs/dependency_check_latest.txt, then run py -3 -m pip install -r requirements.txt manually.
- Crash before interface appears: check logs/tuner_crash_latest.log.
- Arcade crash: check logs/arcade_crash.log.

Final package notes
-------------------
This package intentionally avoids relying on old shipped model-source folders. The arcade uses baked wire data and procedural meshes, while the tuner exports XML-style tune files and optional loose patch packs. The only required paths are relative to the folder you extracted.
