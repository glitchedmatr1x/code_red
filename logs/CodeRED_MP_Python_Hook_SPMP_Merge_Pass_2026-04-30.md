# Code RED MP Python Hook — SP/MP Merge Pass

Date: 2026-04-30

## Summary

The MP Python hook now supports a stronger `sp-mp-merged` mode for the multiplayer/singleplayer hybrid experiment.

The key rule is preserved: do not bulk-replace the current-version boot flow with mixed-version donor files. Instead, keep stock single-player boot alive and push multiplayer/freemode through the already-present NetMachine route.

## Updated Tool

- `tools/codered_mp_python_hook.py`

## New Build Mode

```powershell
python tools\codered_mp_python_hook.py build --content "D:\Games\Red Dead Redemption\game\content.rpf" --mode sp-mp-merged
```

This mode:

- Extracts the current content.rpf MP UI flow files.
- Patches `root/content/ui/pausemenu/0x007B97C6/plaympconf.sc.xml` from the live file.
- Converts auth failure routes to `NetMachine.TriggerMultiplayerLoad(arg2)`.
- Scans previous/default Code RED UI update folders.
- Blocks mixed-version `boot.sc.xml` replacement.
- Blocks wholesale `taskmachine.sc.xml` replacement because the current archive already has the native `NetMachine.StartMultiplayer()` bridge.
- Optionally merges only XML-valid/safe MP UI update candidates such as networking/lobby/menu/HUD layers.
- Writes a copied `content.rpf` plus JSON/MD/diff proof reports.
- Writes MP Companion bridge descriptors for `MULTI_FREE_ROAM` / recovered freemode routing.

## UI Update Scan Behavior

Safe merge candidates:

- `root/content/ui/pausemenu/networking.sc.xml`
- `root/content/ui/pausemenu/0x007B97C6/offlinemenu.sc.xml`
- `root/content/ui/pausemenu/0x007B97C6/lanmenu.sc.xml`
- `root/content/ui/pausemenu/0x007B97C6/publicmenu.sc.xml`
- `root/content/ui/pausemenu/0x007B97C6/privatemenu.sc.xml`
- `root/content/ui/pausemenu/lobby/0x2B5C38A8`
- `root/content/ui/pausemenu/lobby/netplayercontextmenu.sc.xml`
- `root/content/ui/net/hudsceneonline.sc.xml`
- `root/content/ui/net/main.sc.xml`

Blocked from automatic merge:

- `root/content/ui/boot.sc.xml`
- `root/content/ui/net/taskmachine.sc.xml`
- `root/content/ui/pausemenu/0x007B97C6/plaympconf.sc.xml`

Reasons:

- Boot replacement can break single-player startup and one donor boot was previously invalid XML.
- TaskMachine already has `NetMachine.StartMultiplayer()` in the current archive, so replacement is unnecessary risk.
- PlayMpConf is patched from the current live file instead of copied wholesale.

## Generated Bridge Files

In `sp-mp-merged` mode the hook writes:

- `config/mp_python_hook_state.json`
- `config/synthetic_freemode_bridge.json`
- `config/synthetic_activation_request.json`
- `reports/mp_python_hook_report.json`
- `reports/mp_python_hook_report.md`
- `reports/plaympconf_override.diff`

## Activate / Restore

Activate after reviewing the copied archive report:

```powershell
python tools\codered_mp_python_hook.py activate --target "D:\Games\Red Dead Redemption\game\content.rpf"
```

Restore from a backup:

```powershell
python tools\codered_mp_python_hook.py restore --target "D:\Games\Red Dead Redemption\game\content.rpf" --backup "D:\Games\Red Dead Redemption\game\Code_RED_Backups\content.before_mp_python_hook_YYYYMMDD_HHMMSS.rpf"
```

## Expected Result

This pass gives Code RED the cleanest current multiplayer experiment path:

1. Preserve single-player boot.
2. Override PlayMpConf gate behavior.
3. Keep current-version TaskMachine native bridge.
4. Carry MULTI_FREE_ROAM / recovered freemode route data into the MP Companion.
5. Merge only safe MP UI update layers when they validate.

## Still Not Proven

This still needs in-game testing. The copied archive and UI route can be built/proven by Code RED, but native multiplayer runtime acceptance must be verified inside the game.
