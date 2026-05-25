# Code RED MP Avatar Picker / Outfitter Access - Research Report

## Summary

The avatar picker/outfitter path is real and is much narrower than the full MP freeroam problem.

The strongest local path is:

```text
NetworkingLayerOffline
-> NetOfflineTabs / NetTabs
-> NetConf_AvatarPicker
-> NetMachine.SendScriptEvent('LaunchAvatarPicker')
-> fuieventmonitor event type 75
-> DECOR_CHECK_STRING Param LaunchAvatarPicker
-> PC Global_124888 = 4294967294
```

The first safe patch should be SCXML-only. It should expose the existing avatar picker event from offline/single-player networking UI without touching WSC bytecode or authentication.

## Key Findings

### 1. PC fuieventmonitor already has the event

Local `imports/fuieventmonitor.wsc` contains:

```text
LaunchAvatarPicker
MP_AvatarQuit
nMPProfile
Net_Profile_Mount_Select
Net_titles
MPP_TitleValue
MpTitleStringId
GET_ACTOR_ENUM_FROM_STRING
UPDATE_STRING_PROFILE_STAT
```

Code RED WSC inspection:

```text
reports/avatar_picker/pc_fuieventmonitor_inspect/
reports/avatar_picker/pc_fuieventmonitor_z_inspect/
reports/avatar_picker/pc_fuieventmonitor_map/
```

### 2. Public decompile confirms owner/handler

The Red-Mods decompiled `pc_scripts/fuieventmonitor.c` shows:

```text
DECOR_CHECK_STRING(..., "Param", "LaunchAvatarPicker")
```

and the handler sets:

```text
Global_124888 = 4294967294
```

The Xbox standard/GOTY versions do the same logical thing through `Global_79960 = 4294967294`.

### 3. The UI route already exists, but mostly in online/lobby surfaces

Decoded `networking.sc.xml` has an avatar picker button in online `NetTabs`:

```text
desc="mp_fe_avatarpicker_tab"
goto(NetConf_AvatarPicker)
```

But single-player/offline mode enters `NetOfflineTabs`, which currently exposes public/private/LAN, not avatar picker.

Decoded `lobby/main.sc.xml` contains the actual confirmation:

```text
NetConf_AvatarPicker
NetMachine.LeavePosse()
NetMachine.SendScriptEvent('LaunchAvatarPicker')
stackPush(HudSceneOnline)
```

### 4. The profile editor UI exists separately

Decoded `root_content_ui_net_profileeditor_main.sc.xml.decoded.xml` contains:

```text
UILayer id="MP_ProfileEditor"
UIButton id="mp_fe_profile_avatar" target="Enter(MP_AvatarGroupSelector)"
UIScrollableList id="MP_AvatarGroupSelector"
Mount_Selected
Profile_Selected
Profile_Cancelled
MP_AvatarQuit
```

This is the likely visible outfitter/profile editor surface. It is a good fallback if the script event only sets the global and no runtime owner opens the UI.

## Public Context

The Red Dead Wiki describes the Outfitter as the multiplayer UI for choosing characters, mounts, and titles, and notes that entering it normally disconnects the player from other players while they are in the outfitter. That matches the local `NetConf_AvatarPicker` confirmation and `LeavePosse` behavior.

Magic-RDR is relevant because its public project page lists RDR RPF support and a `#SC` script decompiler; the Red-Mods public decompiles used here are MagicRDR outputs.

RDRMP is a separate custom multiplayer project. It is useful public context that PC multiplayer restoration is being worked on externally, but it does not directly solve this avatar-picker SCXML/WSC route.

Sources checked:

```text
https://github.com/Red-Mods/RDR2-Decompiled-Scripts/blob/ef4da4f45c6594da0d325237baa569e9d1b22f23/pc_scripts/fuieventmonitor.c
https://github.com/Red-Mods/RDR2-Decompiled-Scripts/blob/ef4da4f45c6594da0d325237baa569e9d1b22f23/pc_scripts/fuieventmonitor_z.c
https://github.com/Red-Mods/RDR2-Decompiled-Scripts/blob/ef4da4f45c6594da0d325237baa569e9d1b22f23/xbox360_scripts%20(standard)/fuieventmonitor.c
https://github.com/Red-Mods/RDR2-Decompiled-Scripts/blob/ef4da4f45c6594da0d325237baa569e9d1b22f23/xbox360_scripts%20(goty)/fuieventmonitor.c
https://github.com/Red-Mods/RDR2-Decompiled-Scripts/blob/ef4da4f45c6594da0d325237baa569e9d1b22f23/xbox360_scripts%20(goty)/fuieventmonitor_z.c
https://reddead.fandom.com/wiki/Outfitter
https://github.com/Foxxyyy/Magic-RDR
https://redmods.com/rdrmp/
```

## Candidate Built

Variant A was generated:

```text
build/avatar_picker_access_pass1/variant_a_offline_networking_avatar_event/
```

It changes only:

```text
root/content/ui/pausemenu/networking.sc.xml
```

It adds:

```text
NetOfflineTabs -> avatar picker button
NetConf_AvatarPicker messagebox copied from lobby/main
```

It does not:

```text
patch WSC
bypass auth
spoof public services
start full MP freeroam
edit live game files
```

## Current Risk

The event may only set `Global_124888`, and another runtime system may be responsible for opening the actual profile editor. If that runtime owner is inactive in single-player, Variant A may show the confirmation but do nothing after accept.

That result is still useful: it proves whether the frontend event reaches the persistent FUI monitor.

## Next Decision

Test Variant A first. If it reaches confirmation but does not open the picker, build Variant B as direct SCXML entry to:

```text
MP_ProfileEditor
MP_AvatarGroupSelector
```

Keep save/auth bypasses separate until a specific blocker appears.
