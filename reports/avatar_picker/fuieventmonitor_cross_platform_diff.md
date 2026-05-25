# Code RED Avatar Picker - fuieventmonitor Cross-Platform Diff

Scope: compare the persistent FUI event monitor lane for `LaunchAvatarPicker`, profile, mount, and title handling.

## Local PC evidence

Local WSC inspection:

```text
imports/fuieventmonitor.wsc
  strings: 442
  functions: 87
  natives: 487

imports/fuieventmonitor_z.wsc
  strings: 382
  functions: 88
  natives: 422
```

Important local string offsets from `reports/avatar_picker/pc_fuieventmonitor_inspect/strings.csv`:

```text
0x1C4  NetTab_ProfileTitles
0x1DE  NetTab_Profile
0x1F2  Net_titles
0x240  MPP_TitleValue
0x30C  Net_Profile_Mount_Select
0x5BB  MpTitleStringId
0x1094 MP_AvatarQuit
0x10CD AvatarQuit
0x4479 LaunchAvatarPicker
```

The map pass places `LaunchAvatarPicker` in `Function_80`, decoded offset range `0x445C..0x4582`.

## Public decompile comparison

Source: Red-Mods/RDR2-Decompiled-Scripts, decompiled with MagicRDR.

| Variant | Event handler | LaunchAvatarPicker action | Profile/mount/title handling |
|---|---:|---|---|
| PC `pc_scripts/fuieventmonitor.c` | `Function_80` | `Function_85()` sets `Global_124888 = 4294967294` | Handles `nMPProfile`, `Net_Profile_Mount_Select`, `Net_titles`, `MpTitleStringId` |
| PC zombie `pc_scripts/fuieventmonitor_z.c` | `Function_81` | `Function_86()` equivalent | Same profile/mount/title terms present |
| Xbox standard `xbox360_scripts (standard)/fuieventmonitor.c` | `Function_80` | `Function_83()` sets `Global_79960 = 4294967294` | Same logical profile/mount/title handling with Xbox global names |
| Xbox GOTY `xbox360_scripts (goty)/fuieventmonitor.c` | `Function_83` | `Function_88()` sets `Global_79960 = 4294967294` | Same logical profile/mount/title handling with Xbox global names |
| Xbox GOTY zombie `xbox360_scripts (goty)/fuieventmonitor_z.c` | `Function_84` | `Function_89()` equivalent | Same logical profile/mount/title terms present |

## Interpretation

`LaunchAvatarPicker` is not a direct UI transition in `fuieventmonitor`. It is a persistent script event handled from FUI event type 75. The handler sets a global sentinel:

```text
PC:   Global_124888 = 4294967294
Xbox: Global_79960  = 4294967294
```

That means the first patch should not modify WSC control flow. The safest route is to expose the existing SCXML event path and observe whether the engine/runtime watcher reacts to the sentinel.

## Handler facts

`fuieventmonitor`:

- persists via `ADD_PERSISTENT_SCRIPT(GET_THIS_SCRIPT_ID())`.
- processes event type `75`.
- routes `generalMenus`, `NetworkingLayerOffline`, and `nPauseMenu`.
- checks event decor `Param`.
- handles `LaunchAvatarPicker`, `RequestPosseTeleport`, `net.RequestHardSave`, and related frontend events.
- handles `MP_AvatarQuit`, `MP_BarkerPosseLeave`, XP rollover popups, mount selection, and title selection.

## Patchability

| Area | Status |
|---|---|
| SCXML button exposure | Safe candidate |
| SCXML copy of `NetConf_AvatarPicker` confirmation | Safe candidate |
| Direct `Enter(MP_ProfileEditor)` fallback | Medium risk, still SCXML-only |
| WSC string replacement | Not needed for pass 1 |
| WSC branch/native edit | Do not use |
| Save/auth bypass | Keep separate |
