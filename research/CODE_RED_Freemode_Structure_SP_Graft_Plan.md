# Code RED / RDR PC — FreeMode Structure and Single-Player Graft Plan

## Purpose

We are no longer treating FreeMode as just one script to force-launch. The better path is to reconstruct its surrounding UI/session/save shell inside the single-player PC flow, then let the FreeMode controller run only after the needed frontend state exists.

This note is for the next Codex pass.

---

## Current working baseline

Use the user-tested loading baseline as the base:

```text
A_disable_update_thread_refs / content loading passed
SHA1: 91304EBA24B3759AE206783EBE4CA42EA0F2A134
```

Meaning:

```text
Disabling direct multiplayer_update_thread references gets the game to the loading path.
```

Do not use Pass 10 patched freemode as a base. Pass 10 crashed even when the patched freemode resource was only present.

---

## Main conclusion

The next step should not be another broad WSC force-route.

The next step should be:

```text
Single-player UI graft + FreeMode shell reconstruction
```

Goal:

```text
Bring the MP lobby/profile/HUD/task-machine menus into the PC single-player frontend,
then trigger FreeMode from a valid menu/session/save state.
```

---

## FreeMode structure overview

### 1. Start / boot layer

Important file:

```text
content/ui/boot.sc.xml
```

Known important events/actions:

```text
net.EnterOnline
net.EnterOnlineForInvite
fileSetForMPLoad
LoadingScreen
waitforInTransition
NetMachine.SetMultiplayerModeToLaunch('Public')
NetMachine.SetMultiplayerModeToLaunch('JoinWish')
```

The Zombie/Undead boot slot has already proven valuable because it can reach save prompt and loading.

Working idea:

```text
Use Zombie/Undead or Hardcore slot as the safe alternate boot door.
Do not use direct TriggerMultiplayerLoad immediately.
```

---

### 2. Pause networking layer

Important file:

```text
content/ui/pausemenu/networking.sc.xml
```

Key connected IDs:

```text
NetworkingLayerOffline
NetConf_PlayLAN
NetConf_PlayPrivate
NetConf_PlayPublic
NetConf_AvatarPicker
NetConf_JoinWish
Net_LANMenu
Net_PublicMenu
Net_PrivateMenu
```

This layer is already mostly connected. The old UI audit showed that the `net` folder may be represented as a hashed folder in PC RPF, but the logical includes resolve.

Do not keep chasing this as the primary missing link unless a specific broken include is proven.

---

### 3. MP lobby / Free Roam game selection layer

Important old/non-PC files:

```text
ui/pausemenu/lobby/main.sc.xml
ui/pausemenu/lobby/currentgamers.sc.xml
ui/pausemenu/lobby/friends.sc.xml
ui/pausemenu/lobby/netplayercontextmenu.sc.xml
ui/pausemenu/lobby/recentgamers.sc.xml
```

Critical IDs and actions from `lobby/main.sc.xml`:

```text
OL_NetworkingMenu
LobbyTabs
NetTab_Games
OL_PlaylistsMainList
MULTI_FREE_ROAM
NetConf_AvatarPicker
NetConf_StartGame
NetConf_PlaylistLocked
NetConf_BarkerLocked
NetMachine.SetGameWish('MULTI_FREE_ROAM')
NetMachine.StartGameWish()
```

This is the strongest menu-side counterpart to FreeMode.

Recommended graft:

```text
Add/restore lobby files into content/ui/pausemenu/lobby/
Expose OL_NetworkingMenu from the single-player pause menu.
Initially do not allow StartGameWish to launch MP directly.
First prove the menu can open.
```

---

### 4. Net task machine / loading/session UI layer

Important old/non-PC file:

```text
ui/net/taskmachine.sc.xml
```

Critical IDs:

```text
NetMachine
NetTasks
NM_LoadingWorld
NM_JoinProcess
NetConf_FRDTeleport
NetConf_JoinWish
NetConf_JoinWishXPad
NetAlert_LostNet
NetAlert_FailedInviteJoin
NetAlert_FailedInviteValidation
```

Critical terms/actions:

```text
TriggerMultiplayerLoad
auth.success
FreeRoam
JoinWish
```

This file is probably a missing frontend bridge for proper MP loading behavior. It may be safer to add this UI shell than to keep patching WSC routes blindly.

Recommended graft:

```text
Add ui/net/taskmachine.sc.xml.
Add include from userinterface.sc.xml or another already-loaded UI root if needed.
Do not make it authenticate online.
Use it as the local loading/session state shell.
```

---

### 5. Online HUD / playerlist / action-area prompts

Important old/non-PC file:

```text
ui/net/hudsceneonline.sc.xml
```

Key IDs:

```text
HudSceneOnline
HudDefaultOnlineState
PlayerList
AAPrompts_Playerlist
AAPrompts_Stats
Lobby_ReplayOnly
Lobby_NaviReplay
HudGamerList
```

This is the HUD counterpart for MP. If FreeMode expects online HUD objects/prompts, missing HUD UI could cause bad state or crash later.

Recommended graft:

```text
Add ui/net/hudsceneonline.sc.xml.
Do not force it active on boot.
Let lobby/freemode enter it later, or expose it only in a test variant.
```

---

### 6. Profile / avatar picker layer

Important old/non-PC files:

```text
ui/net/profileeditor/main.sc.xml
ui/net/profileeditor/titles.sc.xml
ui/net/profileeditor/titles/*.sc.xml
```

Key IDs:

```text
MP_ProfileEditor
MP_ProfileMenu
mp_fe_profile_avatar
mp_fe_profile_mount
mp_fe_profile_title
MP_AvatarGroupSelector
MP_TitleGroupXp
MP_TitleGroupAmbient
MP_TitleGroupWeapon
MP_TitleGroupPvP
MP_TitleGroupDLC1-DLC4
```

FreeMode contains avatar picker strings, so adding profile editor UI may be better than patching avatar picker strings out of `freemode.wsc`.

Recommended graft:

```text
Add profile editor tree.
Do not bypass avatar picker inside freemode yet.
Instead, provide the UI objects it expects.
```

---

### 7. NetStats / leaderboard / DLC categories

Important old/non-PC files:

```text
ui/pausemenu/netstats/main.sc.xml
ui/pausemenu/netstats/boards.sc.xml
ui/pausemenu/netstats/prompts.sc.xml
ui/pausemenu/netstats/errormsg.sc.xml
ui/pausemenu/netstats/errormsgrecovery.sc.xml
```

These expose DLC leaderboard categories and Gamespy-dependent logic.

Do not make this a launch requirement yet. Add only as UI support if missing, and avoid Gamespy auth traps.

---

## WSC runtime roles

### freemode.wsc

Likely gameplay/world FreeMode controller.

Known roles from previous scans:

```text
FreeModeThread
MULTI_FREE_ROAM
mp_fe_freeroam
mp_fe_resession
NetConf_AvatarPicker
mp_avatarpicker_conf_lobby
mp_avatarpicker_conf
mpskiptutorial
netNoAmbientWorld
MP_Tutorial
LoadingScreen
SG_AutoSaveDisabled
SpawnVolGroup_set
SpawnVol_0 ... SpawnVol_57
PlayerLayout
Respawn
FREEMODE
Enabling the Ambient World
net_pl_unsession
BLIP_ACTIVE_ACTION_AREA
net_name_hcfm
net_name_friendlyfm
```

Do not use the Pass 10 patched `freemode.wsc`; it crashed.

Use clean MagicRDR-fixed converted `freemode.wsc` only until proven otherwise.

---

### PR_Multiplayer.wsc

Likely network/session/invite/lobby shell, not the world itself.

Known roles:

```text
PR_MULTIPLAYER_NET_EVENTS
net.readyForInvite
netRandomSessioning
Private Session
FREEROAM
Invite to FreeMode Received
MP_ActorPicker
gametype_lobby
mp_Help_Barker
mp_Teleport
NetConf_FRDTeleport
mp_FreeRoamDefense
OUT OF SESSION
mploadgamemode
mploadplaylist
```

Could be useful after UI/lobby shell is restored, but do not force it early.

---

### multiplayer_system_thread.wsc

Likely HUD/reward/player/save support shell.

Known roles:

```text
MultSysThread
MPReward
MP_Ticker
Reticle
WeaponAmmo
MPSplash
net_player_joined
Playerlayout
SaveLoad
Multiplayer Save Triggered
CanSaveNowAutoSave
MULTIPLAYER_THUNK_MASTER
XP_Avatar_Unlock
net_aa_completed
net_player_entered
```

Could be useful after FreeMode is stable.

---

### multiplayer_update_thread.wsc

Currently suspect.

Known behavior:

```text
Launching/referencing this directly causes or contributes to crash.
Disabling update-thread refs produced the best loading baseline.
```

Do not make this the primary launch target yet.

---

## What we can add into single-player

### Safe to add first as structure-only support

Add these UI files from the old/non-PC UI source into the PC content RPF, if they are missing:

```text
content/ui/pausemenu/lobby/main.sc.xml
content/ui/pausemenu/lobby/currentgamers.sc.xml
content/ui/pausemenu/lobby/friends.sc.xml
content/ui/pausemenu/lobby/netplayercontextmenu.sc.xml
content/ui/pausemenu/lobby/recentgamers.sc.xml

content/ui/net/taskmachine.sc.xml
content/ui/net/hudsceneonline.sc.xml

content/ui/net/profileeditor/main.sc.xml
content/ui/net/profileeditor/titles.sc.xml
content/ui/net/profileeditor/titles/ambient.sc.xml
content/ui/net/profileeditor/titles/dlc1.sc.xml
content/ui/net/profileeditor/titles/dlc2.sc.xml
content/ui/net/profileeditor/titles/dlc3.sc.xml
content/ui/net/profileeditor/titles/dlc4.sc.xml
content/ui/net/profileeditor/titles/pvp.sc.xml
content/ui/net/profileeditor/titles/stat.sc.xml
content/ui/net/profileeditor/titles/weapon.sc.xml
content/ui/net/profileeditor/titles/xp.sc.xml

content/ui/pausemenu/net/publicmenu.sc.xml
content/ui/pausemenu/net/privatemenu.sc.xml
content/ui/pausemenu/net/lanmenu.sc.xml

content/ui/pausemenu/netstats/boards.sc.xml
content/ui/pausemenu/netstats/prompts.sc.xml
content/ui/pausemenu/netstats/errormsg.sc.xml
```

### Potential single-player menu replacement slots

Use one of these as a test entry point:

```text
Pause menu -> Social Club
Pause menu -> Leaderboards
Pause menu -> Network
Start screen -> Hardcore slot
Start screen -> Zombie/Undead slot
```

Best first target:

```text
Pause menu -> Network or Social Club replaced with OL_NetworkingMenu
```

Do not use a direct MP launch as the first test. Just prove the lobby menu opens.

---

## Suggested next pass: SP FreeMode Shell Pass 11

### Base

```text
content loading passed / A_disable_update_thread_refs
```

### Variant A — structure-only UI graft

Add the lobby, net task, online HUD, and profile editor UI files.

No WSC route changes.

Expected result:

```text
Game boots.
Zombie loading route still works.
No new crash.
```

### Variant B — expose MP lobby in pause menu

Add Variant A plus one menu hook:

```text
Pause menu Network/SocialClub/Leaderboards -> Enter(OL_NetworkingMenu)
```

Expected result:

```text
Single-player pause menu can open MP lobby/free roam menu shell.
```

### Variant C — Free Roam menu selection only

Add Variant B plus keep:

```text
MULTI_FREE_ROAM
NetMachine.SetGameWish('MULTI_FREE_ROAM')
```

But block/avoid immediate `NetMachine.StartGameWish()` until manually tested.

Expected result:

```text
Can select/hover Free Roam without crashing.
```

### Variant D — StartGameWish test

Allow `NetMachine.StartGameWish()` only after C is proven stable.

Expected result:

```text
This may reach loading or crash; if it crashes, the blocker is after gamewish, not menu structure.
```

### Variant E — trainer/ASI runtime probe base

Same as B/C, no launch.

Use trainer hotkeys to trigger one runtime call at a time after UI/menu state is active.

---

## Avoid in next pass

Do not:

```text
- Use Pass 10 patched freemode.
- Broadly patch freemode strings.
- Directly launch multiplayer_update_thread.
- Directly trigger LAN load at boot.
- Remove save prompts.
- Chase missing networking includes unless a specific include fails.
```

---

## Immediate Codex task

Before patching, Codex should generate:

```text
reports/mp_freemode_structure_pass11/ui_file_inventory.csv
reports/mp_freemode_structure_pass11/ui_include_graph.md
reports/mp_freemode_structure_pass11/mp_menu_graft_plan.md
```

Then build only structure/menu variants.

This pass should answer:

```text
Can we restore the MP lobby/profile/HUD/task-machine UI inside single-player without crashing?
```

If yes, then the next pass can start wiring FreeMode launch from inside that menu.
