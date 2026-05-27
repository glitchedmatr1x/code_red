# Code RED / RDR PC — Piece-by-Piece FreeMode Content Graft Plan

## Correction

Do **not** keep trying to activate/boot full multiplayer modes.

The user’s goal is:

```text
Extract what FreeMode/MP modes contain and graft those features into single-player piece by piece.
```

That means:

```text
No net.EnterOnline as the main plan.
No TriggerMultiplayerLoad as the main plan.
No StartGameWish as the main plan.
No direct freemode.wsc launch as the main plan.
No multiplayer_update_thread launch as the main plan.
```

The next pass should treat FreeMode as a **content library**, not as a mode to enter.

---

## Current best branch to preserve

Use the user-tested loading branch only as a reference baseline:

```text
A_disable_update_thread_refs / content loading passed
SHA1: 91304EBA24B3759AE206783EBE4CA42EA0F2A134
```

But do not build the next work around “enter MP.” Build around harvesting MP content into SP.

---

## Main objective

Build an offline/single-player “FreeMode content graft” in stages:

```text
Stage 1: Identify what FreeMode owns.
Stage 2: Enable/import only passive world pieces.
Stage 3: Add UI menu entries that expose content, not MP launch.
Stage 4: Add spawn volumes and blips as SP-safe content.
Stage 5: Add ambient events/action areas one at a time.
Stage 6: Add actors/NPCs one group at a time.
Stage 7: Add optional save/profile/player progression only after content is stable.
```

---

## What to extract from FreeMode/MP

### From freemode.wsc

Inventory and classify, do not patch broadly:

```text
SpawnVolGroup_set
SpawnVol_0 ... SpawnVol_57
PlayerLayout
Respawn
FREEMODE
MULTI_FREE_ROAM
FreeModeThread
Enabling the Ambient World
netNoAmbientWorld
BLIP_ACTIVE_ACTION_AREA
net_aa_hunting_ground_icon
net_pl_unsession
net_name_hcfm
net_name_friendlyfm
MP_Tutorial
mpskiptutorial
NetConf_AvatarPicker
mp_avatarpicker_conf
mp_avatarpicker_conf_lobby
```

Wanted output:

```text
reports/freemode_piece_graft/freemode_spawnvols.csv
reports/freemode_piece_graft/freemode_blips.csv
reports/freemode_piece_graft/freemode_action_areas.csv
reports/freemode_piece_graft/freemode_ui_events.csv
reports/freemode_piece_graft/freemode_script_launches.csv
reports/freemode_piece_graft/freemode_sector_refs.csv
```

### From PR_Multiplayer.wsc

Use as a source of features, not as a runtime launch target:

```text
mp_Help_Barker
mp_Teleport
mp_FreeRoamDefense
MP_ActorPicker
gametype_lobby
NetConf_FRDTeleport
mploadgamemode
mploadplaylist
FREEROAM
Private Session
Invite to FreeMode Received
```

Potential content to graft later:

```text
Teleport menu
Help barker prompts
Free roam defense events
Actor picker / character selection UI concepts
```

### From multiplayer_system_thread.wsc

Use as a support-feature library:

```text
MPReward
MP_Ticker
Reticle
WeaponAmmo
MPSplash
Playerlayout
SaveLoad
CanSaveNowAutoSave
XP_Avatar_Unlock
net_aa_completed
net_player_entered
```

Potential content to graft later:

```text
HUD ticker
MP reward splash
Weapon/ammo HUD behavior
Action-area completed events
Player-entered-area event hooks
```

### Avoid for now

```text
multiplayer_update_thread.wsc
```

It is still the main suspect for the loading/crash path. Use it only for inventorying strings/action areas, not as a launch target.

---

## SP counterpart mapping

Codex should find single-player counterparts for each FreeMode system.

### Menus

Compare MP menus to SP menus:

```text
content/ui/pausemenu/main.sc.xml
content/ui/pausemenu/networking.sc.xml
content/ui/pausemenu/lobby/main.sc.xml
content/ui/pausemenu/net/plaympconf.sc.xml
content/ui/pausemenu/net/lanmenu.sc.xml
content/ui/pausemenu/netstats/main.sc.xml
content/ui/net/profileeditor/main.sc.xml
content/ui/net/hudsceneonline.sc.xml
content/ui/net/taskmachine.sc.xml
```

Goal:

```text
Add a single-player "FreeMode Content" menu page.
It should list content toggles.
It should not start multiplayer.
```

Example entries:

```text
Enable FreeMode spawn volumes
Enable FreeMode blips
Enable hunting action areas
Enable FreeRoam defense props
Open actor picker UI
Open teleport menu
```

### World/sectors

Compare MP sector strings to SP sector strings in:

```text
pressstart.wsc
sp_idle.wsc
main.wsc
rdr2init.wsc
freemode.wsc
```

Goal:

```text
Create a conservative sector whitelist.
Enable 1-4 sectors at a time in SP.
Do not flip broad native tables.
Do not enable every MP sector at once.
```

### Spawn volumes

Find how SP scripts spawn ambient populations, then map FreeMode spawn volume names into SP-safe equivalents.

Do not spawn all 58 spawn volumes at once.

Build variants:

```text
A_spawnvol_inventory_only
B_spawnvol_group_0_only
C_spawnvol_group_1_only
D_spawnvol_group_hunting_only
```

### Blips/action areas

Find FreeMode blip/action-area refs and add only map/UI blips first.

No AI/gameplay yet.

Build variants:

```text
A_blip_inventory_only
B_one_action_area_blip
C_hunting_ground_icons_only
D_free_roam_defense_icon_only
```

### Actors/events

Only after sectors/spawnvols/blips are safe:

```text
one actor/event group per test
no full FreeModeThread
no multiplayer_update_thread
```

---

## Next Codex pass: FreeMode Content Graft Inventory Pass 1

This pass should not build a “playable MP mode.”

It should produce reports and a tiny non-launching test patch.

### Required reports

```text
reports/freemode_content_graft_pass1/freemode_structure_map.md
reports/freemode_content_graft_pass1/freemode_strings.csv
reports/freemode_content_graft_pass1/freemode_spawnvols.csv
reports/freemode_content_graft_pass1/freemode_blips.csv
reports/freemode_content_graft_pass1/freemode_action_areas.csv
reports/freemode_content_graft_pass1/freemode_ui_events.csv
reports/freemode_content_graft_pass1/freemode_script_refs.csv
reports/freemode_content_graft_pass1/sp_counterpart_map.csv
reports/freemode_content_graft_pass1/recommended_piecewise_tests.md
```

### Scans to run

Run on clean MagicRDR-fixed converted WSCs:

```powershell
py -3 -m codered_wsc scan freemode.wsc --terms "SpawnVol,SpawnVolGroup,BLIP,AA,Action_Area,action area,hunting,FREEMODE,MULTI_FREE_ROAM,PlayerLayout,Respawn,Ambient,MP_Tutorial,AvatarPicker,Teleport,FreeRoamDefense,SaveLoad" --out reports\freemode_content_graft_pass1\freemode_scan --rdr-exe "..\RDR.exe"

py -3 -m codered_wsc control-flow freemode.wsc --terms "SpawnVolGroup_set,SpawnVol,BLIP_ACTIVE_ACTION_AREA,PlayerLayout,Respawn,Enabling the Ambient World,FREEMODE,MULTI_FREE_ROAM,SaveLoad" --out reports\freemode_content_graft_pass1\freemode_control --rdr-exe "..\RDR.exe"

py -3 -m codered_wsc scan PR_Multiplayer.wsc --terms "mp_Teleport,mp_Help_Barker,mp_FreeRoamDefense,MP_ActorPicker,gametype_lobby,NetConf_FRDTeleport,mploadgamemode,mploadplaylist,FREEROAM" --out reports\freemode_content_graft_pass1\pr_multiplayer_scan --rdr-exe "..\RDR.exe"

py -3 -m codered_wsc scan multiplayer_system_thread.wsc --terms "MPReward,MP_Ticker,MPSplash,Playerlayout,SaveLoad,CanSaveNowAutoSave,XP_Avatar_Unlock,net_aa_completed,net_player_entered" --out reports\freemode_content_graft_pass1\system_thread_scan --rdr-exe "..\RDR.exe"
```

Also scan SP counterpart scripts:

```powershell
py -3 -m codered_wsc scan sp_idle.wsc --terms "SpawnVol,BLIP,PlayerLayout,Respawn,Ambient,SaveLoad,LoadingScreen,sector,ENABLE_CHILD_SECTOR,ENABLE_WORLD_SECTOR" --out reports\freemode_content_graft_pass1\sp_idle_counterpart --rdr-exe "..\RDR.exe"

py -3 -m codered_wsc scan main.wsc --terms "SpawnVol,BLIP,PlayerLayout,Respawn,Ambient,SaveLoad,LoadingScreen,sector,ENABLE_CHILD_SECTOR,ENABLE_WORLD_SECTOR" --out reports\freemode_content_graft_pass1\main_counterpart --rdr-exe "..\RDR.exe"
```

### Optional tiny test patch

Only if reports are clear, build one safe test:

```text
SP_FreeMode_Content_Menu_A
```

It should only add a menu entry:

```text
Pause Menu -> FreeMode Content
```

The page can show text/options but should not start MP or launch FreeMode.

Purpose:

```text
Prove we can graft MP menu/UI pieces into SP without activating a mode.
```

---

## Things not to do

Do not:

```text
- call net.EnterOnline
- call TriggerMultiplayerLoad
- call StartGameWish
- launch freemode.wsc directly
- launch multiplayer_update_thread.wsc
- patch broad freemode string sets
- remove save prompts
- enable all sectors at once
- spawn all FreeMode volumes at once
```

---

## Success criteria

A good next result is **not** “entered MP.”

A good next result is:

```text
We know FreeMode's pieces.
We know their SP counterparts.
We can open an SP menu page listing those pieces.
We can toggle or test one passive piece at a time.
The game does not crash.
```

Only after that should we build actual SP FreeMode gameplay features.
