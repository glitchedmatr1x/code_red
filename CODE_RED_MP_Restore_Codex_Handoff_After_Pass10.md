# Code RED / RDR PC MP Restore — Codex Handoff After Pass 10

## Current status

We are trying to restore/offline-enable Red Dead Redemption PC multiplayer/free roam by using the PC frontend/save/load path and the newly converted MP WSC scripts.

The latest testing shows we are past the original XML/menu-only blocker, but we are not yet in a valid playable FreeMode world. The best branch reaches the loading path; more aggressive branches crash or hang.

## Major breakthrough already completed

XENON `.xsc` conversion is no longer the main blocker.

Codex previously fixed the XSC -> WSC converter:

- XENON `.xsc` needs only the 16-byte resource header word-swapped.
- Encrypted payload must stay untouched.
- AES decrypt then exposes the Xbox LZX wrapper.
- `xcompress32.dll` decompresses it.
- The remaining issue was inside the decoded script structure tables.
- Fixed converter now normalizes:
  - script header
  - code page pointer table
  - native hash table
  - static table
  - while preserving bytecode bytes

Validation already reported:

- LEVEL 1 Code RED reopen: `56/56` pass
- LEVEL 2 Magic RDR standalone WSC open/parser: `56/56` pass
- LEVEL 3 MagicRDR batch import into cloned RPF: core subset pass
- LEVEL 4 exported-back payload reopens in Magic RDR and Code RED: core subset pass
- LEVEL 5 game boot: not proven by conversion alone
- LEVEL 6 script launch/runtime: not proven

Use the fixed converted tree only:

```text
build\mp_script_conversion_probe\import_ready_xsc_magicrdr_fixed_wsc
```

Do not go back to the earlier converted WSC tree that Code RED could open but Magic RDR rejected.

## Best known baseline

The best branch is the user-tested **content loading passed** build.

It matched:

```text
A_disable_update_thread_refs.rpf
SHA1: 91304EBA24B3759AE206783EBE4CA42EA0F2A134
```

This branch is important because it reaches the loading path.

Core meaning:

```text
When multiplayer_update_thread references are disabled from main.wsc / rdr2init.wsc, the game reaches loading.
```

Do not lose this baseline.

Use this as the next base unless deliberately testing older behavior.

## Test history summary

### Pressstart / XML online work

`pressstart.wsc` is confirmed as the real PC frontend online-entry script. It contains:

```text
NET_AUTHENTICATE_GAMER(0, "Multiplayer Online")
UI_SEND_EVENT("net.EnterOnline")
UI_SEND_EVENT("net.EnterOnlineForInvite")
SSAlert_BlockedMP
SSAlert_NotSignedIn
SSAlert_NotOnline
SSAlert_NoCable
```

It also disables many MP sectors and hides DLC leaderboard categories.

Earlier full-force pressstart patches helped prove the route exists, but broad pressstart/full-sector patches caused instability.

### Save prompt finding

The user expected the game to prompt to create a save / play without saving before loading. That was correct.

An older save bypass changed:

```text
fileStartingMPWithoutAutoSave
```

away from the stock prompt path into forced verify/free-space events. That likely contributed to bad loading state.

Restoring the stock save prompt was a win:

```text
Zombie / Undead boot route reached save prompt and loading.
```

So keep the save prompt behavior sane. Do not blindly bypass save prompts again.

### Pass 4 / Zombie boot result

A zombie/undead boot route worked enough to:

```text
reach save prompt
reach loading screen
then crash 1–2 seconds after loading
```

This was a major success because it proved the UI/save front door can reach the MP loading phase.

### Pass 5 result

Variants:

- A: restore stock pressstart
- B: restore stock pressstart + stock main/main_z
- C: seed LAN mode before `net.EnterOnline`
- D: direct LAN `TriggerMultiplayerLoad`

User result:

```text
A/B/C had loading time.
D was direct crash.
```

Meaning:

```text
Direct TriggerMultiplayerLoad is too aggressive / wrong timing.
LAN-seeded net.EnterOnline path is safer than direct TriggerMultiplayerLoad.
```

Do not use direct LAN trigger as the main route.

### Pass 6 result

Tried:

- LAN + FreeRoam game wish
- defer PR_Multiplayer
- defer multiplayer_system_thread
- defer both

Latest one failed. Direct child-thread defers did not solve the after-load crash.

### Pass 7 result

Strategic variants attacked `multiplayer_update_thread` references and alternate routes.

Important result:

```text
A_disable_update_thread_refs got the game to loading and became the best baseline.
```

This strongly implicates `multiplayer_update_thread` or the way main/rdr2init launches it.

### Pass 8 result

Built from `content loading passed`.

Variants included:

- loading base + freeroam boot
- pressstart small sector
- reroute update refs to freemode
- freemode reroute combinations
- restore update slot but stub with freemode/system thread

User result:

```text
Nothing useful.
A was probably the only one that did not crash.
```

Meaning:

```text
Basic freeroam boot seed may be tolerated.
Rerouting update refs directly to freemode or system thread is unsafe / wrong timing.
```

### Pass 9 result

Single native/sector flips in pressstart were tested one at a time.

User result:

```text
All were stuck in loading.
```

Meaning:

```text
Tiny sector/native flips do not crash, but they do not resolve loading.
World/sector activation alone is not enough.
```

### UI XML include audit

Uploaded old non-PC UI set was compared conceptually against current UI graph.

Key finding:

```text
ui/pausemenu/net/ is present in current RPF as hashed folder 0x007B97C6.
networking.sc.xml -> net/PlayMpConf.sc resolves.
PlayMpConf -> NetMachine.TriggerMultiplayerLoad(arg2) exists.
boot.sc.xml contains net.EnterOnline / fileSetForMPLoad / LoadingScreen / waitforInTransition.
```

Conclusion:

```text
Networking XML is mostly connected. Stuck loading is probably after UI handoff, not before.
```

Do not spend the next pass chasing missing XML includes unless a specific broken include is proven.

### Pass 10 result — important failure

Pass 10 tried an offline freemode strategy.

Patched `freemode.wsc` strings:

```text
NetConf_AvatarPicker -> mp_fe_freeroam
mp_avatarpicker_conf_lobby -> mp_fe_freeroam
mp_avatarpicker_conf -> mp_fe_freeroam
netNoAmbientWorld -> mp_fe_freeroam
SG_AutoSaveDisabled -> fileSetForMPLoad
NetAlert_NatWarning -> fileSetForMPLoad
MP_Tutorial -> FREEMODE
NetAlert_FailedInviteJoin_NoPlaylist -> mp_fe_freeroam
```

Variants:

- A: patched freemode only control
- B: route directly to patched freemode
- C: local-load route to patched freemode
- D: update-thread slot stubbed with patched freemode

User result:

```text
All Pass 10 variants crashed.
```

Important conclusion:

```text
Do NOT keep the Pass 10 patched freemode.wsc as a base.
The freemode string patches themselves may be bad.
```

Since even the “patched freemode only control” crashed, next step should be a diff/isolation pass against freemode itself.

## Current interpretation

The most likely current blockers are:

1. `multiplayer_update_thread` is unsafe to launch in current state or at current timing.
2. Direct `TriggerMultiplayerLoad` is too aggressive and crashes.
3. Direct freemode routing / patched freemode also crashes.
4. The stable route reaches loading only when update-thread references are disabled.
5. Save prompt restoration was correct and should stay.
6. XML network routing seems connected enough; blocker is likely WSC/runtime state after UI handoff.
7. Freemode likely contains useful world/free-roam logic, but the Pass 10 string hacks broke it or started it with invalid state.

## What Codex should do next

### Do not do another broad gameplay patch.

First build a **Pass 11 Differential Crash Localization** pass.

Use this base:

```text
content loading passed / A_disable_update_thread_refs
SHA1: 91304EBA24B3759AE206783EBE4CA42EA0F2A134
```

### Required analysis before building variants

Compare these RPFs at file level:

```text
content loading passed baseline
Pass 10 A patched freemode only control
Pass 10 B route to patched freemode
Pass 10 C local-load route to patched freemode
Pass 10 D stub update thread with patched freemode
```

Produce a report:

```text
reports/mp_pass11_diff/freemode_crash_diff_report.md
reports/mp_pass11_diff/changed_files_by_variant.csv
reports/mp_pass11_diff/wsc_string_diffs_freemode.csv
```

Answer:

```text
Which exact files changed between stable baseline and Pass 10 A?
Was freemode.wsc the only changed file in Pass 10 A?
Did any RPF metadata/resource flags change for freemode.wsc?
Can Magic RDR open baseline freemode and patched freemode?
Can Code RED reopen both?
Do decoded string counts/function counts/native counts match?
```

If Pass 10 A changed only `freemode.wsc`, then the patched freemode resource is the crash cause.

### Pass 11 test variants to build

Build cloned RPFs only. Do not touch live `content.rpf`.

#### A0_baseline_repack_control

Repack the exact loading-passed baseline without content changes.

Purpose:

```text
Make sure builder/repack process is not causing the crash.
```

#### A1_stock_freemode_reimport_control

Take the baseline’s existing freemode.wsc, export/extract it, reimport same bytes, validate readback.

Purpose:

```text
Prove that replacing/reimporting freemode as a resource is safe when bytes are unchanged.
```

#### A2_freemode_magicrdr_fixed_unmodified

Import the MagicRDR-fixed converted freemode.wsc with no string patches.

Purpose:

```text
Prove the clean converted freemode itself is runtime-safe.
```

#### A3_freemode_one_patch_avatar_only

Only patch one lowest-risk avatar picker string or one single blocker.

Do not patch all avatar/save/tutorial/ambient strings at once.

#### A4_freemode_one_patch_save_only

Only patch one save blocker string.

#### A5_freemode_one_patch_ambient_only

Only patch `netNoAmbientWorld`.

#### A6_freemode_one_patch_tutorial_only

Only patch `MP_Tutorial`.

Purpose:

```text
Find which freemode string patch causes crash.
```

### Do not route to freemode yet

Until A2/A3/A4/A5/A6 are known safe, do not route directly to freemode.

Pass 10 proved direct route + patched freemode is too much.

### Inspect freemode instead of hacking it

Run Code RED scans on baseline and MagicRDR-fixed `freemode.wsc`:

```powershell
py -3 -m codered_wsc scan freemode.wsc --terms "NET_IS_IN_SESSION,SESSION,FreeModeThread,MULTI_FREE_ROAM,mp_fe_freeroam,mp_avatarpicker_conf,NetConf_AvatarPicker,SG_AutoSaveDisabled,netNoAmbientWorld,MP_Tutorial,SpawnVolGroup_set,PlayerLayout,Respawn,FREEMODE,LoadingScreen,SaveLoad" --out reports\mp_pass11\freemode_scan --rdr-exe "..\RDR.exe"

py -3 -m codered_wsc control-flow freemode.wsc --terms "NET_IS_IN_SESSION,FreeModeThread,MULTI_FREE_ROAM,FREEMODE,LoadingScreen,Respawn,SpawnVolGroup_set,PlayerLayout,SaveLoad,MP_Tutorial" --out reports\mp_pass11\freemode_control --rdr-exe "..\RDR.exe"

py -3 -m codered_wsc candidates freemode.wsc --kind strings --out reports\mp_pass11\freemode_strings --rdr-exe "..\RDR.exe"
```

If available, also map natives and ownership:

```powershell
py -3 -m codered_wsc map freemode.wsc --out reports\mp_pass11\freemode_map --rdr-exe "..\RDR.exe"
```

### Next likely strategic direction

The next successful route is probably not:

```text
direct TriggerMultiplayerLoad
direct multiplayer_update_thread
direct freemode after many string patches
```

The next better route is likely:

```text
stable zombie/save/loading route
+ stock or minimally patched freemode safe in RPF
+ runtime trainer/ASI probe to call one thing at a time after loading
```

Use trainer/ASI as a probe harness, not as a giant force-everything-on hack.

Suggested runtime probes later:

```text
F6: UI_SEND_EVENT("net.EnterOnline")
F7: fileSetForMPLoad + LAN + MULTI_FREE_ROAM
F8: try launching freemode/freemode
F9: try launching multiplayer_system_thread
F10: try PR_Multiplayer
F11: try multiplayer_update_thread LAST
F12: enable small freemode sector/action-area set
```

But do this only after Pass 11 determines whether clean freemode is runtime-safe.

## Rules for next Codex pass

- Do not edit RDR.exe.
- Do not touch ASI/trainer files unless explicitly asked.
- Do not touch live content.rpf.
- Build cloned RPF variants only.
- Do not patch broad freemode string sets.
- Do not use Pass 10 freemode as a base.
- Keep the save prompt restored.
- Keep the `content loading passed` baseline safe.
- Validate WSCs with Code RED and Magic RDR where possible.
- Generate exact file diff reports before making more guesses.

## Short version

Current best path:

```text
1. Baseline that loads = A_disable_update_thread_refs.
2. Pass 10 patched freemode crashes even when only present.
3. Therefore isolate freemode changes first.
4. Build Pass 11 as differential one-file/one-string tests.
5. Only after clean freemode is safe should we route into it or trigger it with trainer/ASI.
```
