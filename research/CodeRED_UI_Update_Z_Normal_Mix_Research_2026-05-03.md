# Code RED UI Update / Z-to-Normal Mix Research — 2026-05-03

## User question

Can we bypass the UI update files? There is a lot in them that should be mixed from Z into normal.

## Answer from scan

Do not bypass/delete the UI update files.

The safer interpretation is:

```text
UI XML = menu router / layer entry / event sender
system scripts = update/pause/event behavior
native UI methods = mode validation and some hidden backing logic
Flash/PPP/strings = visual and text support
```

So the better route is to leave the XML router intact and compare/mix one script or asset lane at a time.

## Archives scanned locally

The scanner was run against the assembled resource folder containing:

```text
content.rpf
flash.rpf
tune_d11generic.rpf
strings_d11generic.rpf
camera.rpf
gringores.rpf
blackwater.rpf
dlc01x.rpf through dlc10x.rpf
```

## Strong findings

1. `boot.sc.xml` already exposes mode routing for Z/normal through compile/runtime flags:

```text
NORMAL_ZOMBIE
NORMAL_NOZOMBIE
STANDALONE
ULTIMATE
```

2. `boot.sc.xml` calls both mode validators:

```text
UIGame.ValidateZombieMode()
UIGame.ValidateNormalMode()
```

3. Zombie Pack declares its entry script through:

```text
root/content/dlc/0x22398628/0x21572403
```

with contents:

```text
ContentFlags 32
LicenseFlags 32
Script content\DLC\ZombiePack\init_zombiepack
Name RDRUNDEADNGHTPAK
MountOrder 7
Version Undead Nightmare Pack v25
```

4. Normal and Zombie Pack have parallel system script groups:

```text
normal: root/content/release64/scripting/0x604B6817/pause.wsc
zombie: root/content/release64/0x06C35575/zombiepack/system/pause_z.wsc/.sco

normal: root/content/release64/scripting/0x604B6817/short_update_thread.wsc
zombie: root/content/release64/0x06C35575/zombiepack/system/short_update_thread_z.wsc/.sco

normal: root/content/release64/scripting/0x604B6817/medium_update_thread.wsc
zombie: root/content/release64/0x06C35575/zombiepack/system/medium_update_thread_z.wsc/.sco

normal: root/content/release64/scripting/0x604B6817/long_update_thread.wsc
zombie: root/content/release64/0x06C35575/zombiepack/system/long_update_thread_z.wsc/.sco

normal: root/content/release64/scripting/0x604B6817/0x1B2D32DB/fuieventmonitor.wsc
zombie: root/content/release64/0x06C35575/zombiepack/system/designerdefined/0x1B2D32DB/fuieventmonitor_z.wsc/.sco
```

5. Z-only player/fast-travel leads exist:

```text
root/content/release64/0x06C35575/zombiepack/system/player_z.wsc/.sco
root/content/release64/0x06C35575/zombiepack/system/designerdefined/player/fasttravel_z.wsc/.sco
```

6. Visual/support assets exist for Z pause presentation:

```text
root/flash/brplru/pause_main_z.wsf
root/tune/ppp/ui_pausezombie.ppp
```

But the visible pause XML path found in the scan references:

```text
movie="pause_main"
```

not `pause_main_z`.

## Tool added

```text
tools/codered_ui_update_mix_research.py
```

Example:

```bat
py -3 tools\codered_ui_update_mix_research.py path\to\resources --out reports\ui_update_mix_research
```

Outputs:

```text
ui_update_mix_research.md
ui_update_mix_summary.json
ui_update_entries.csv
ui_route_actions.csv
sp_z_system_script_pairs.csv
```

## Recommendation

Do not wholesale replace `long_update_thread.wsc` with `long_update_thread_z.wsc` yet.

Safer sequence:

1. Compare normal/Z pairs by hash, entry path, and launch role.
2. Try visual/string support first, because it is less likely to break save/game mode state.
3. Prototype any Z behavior with ScriptHook/AI Trainer controls where possible.
4. If archive testing is needed, use copied `content.rpf` only, one changed script at a time.
5. Log proof after each test.

## Current status

Research-only. No archive patch performed.
