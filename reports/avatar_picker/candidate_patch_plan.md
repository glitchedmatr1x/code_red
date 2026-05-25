# Code RED Avatar Picker Candidate Patch Plan

Goal: expose the multiplayer avatar picker/outfitter path from regular PC single-player/offline networking UI without trying to boot full multiplayer.

## Recommended Variant A - Offline Networking Avatar Event

Output created:

```text
build/avatar_picker_access_pass1/variant_a_offline_networking_avatar_event/
```

Candidate payload:

```text
candidate_zstd/zstd_encoded/root_content_ui_pausemenu_networking.sc.xml.zstd
```

Archive replacement path:

```text
root/content/ui/pausemenu/networking.sc.xml
```

Patch contents:

1. Add an avatar picker tab to `NetOfflineTabs`.
2. Add local `NetConf_AvatarPicker` messagebox definition copied from `lobby/main`.
3. On confirmation, call:

```text
NetMachine.SendScriptEvent('LaunchAvatarPicker')
```

This avoids:

```text
NetMachine.Authenticate(...)
public matchmaking
full MP freeroam boot
WSC bytecode patching
savegame/netstats bypassing
```

## Why This Is The Smallest Safe Patch

`networking.sc.xml` already has the avatar button in online `NetTabs`, but offline/single-player mode enters `NetOfflineTabs`, which lacks that button. The lobby already has a valid confirmation block that sends `LaunchAvatarPicker`; Variant A simply moves that existing path into the offline route.

## Validation Already Done

The candidate tool encoded the decoded XML to Zstandard and decoded it back successfully:

```text
status: pass
candidate_file_count: 1
decoded_size: 16986
encoded_size: 3204
```

Manifest:

```text
build/avatar_picker_access_pass1/variant_a_offline_networking_avatar_event/manifest.json
```

Diff:

```text
build/avatar_picker_access_pass1/variant_a_offline_networking_avatar_event/networking_avatar_event.diff
```

## Test Procedure

Do not replace live files directly. Import only this one replacement into a copied/test `content.rpf` first.

1. Use a known-booting `content.rpf`.
2. Replace only:

```text
root/content/ui/pausemenu/networking.sc.xml
```

with:

```text
build/avatar_picker_access_pass1/variant_a_offline_networking_avatar_event/candidate_zstd/zstd_encoded/root_content_ui_pausemenu_networking.sc.xml.zstd
```

3. Reopen/export the file and confirm byte match against the candidate.
4. Launch.
5. Open pause menu -> networking/offline menu.
6. Look for avatar/outfitter tab.
7. Select it and confirm.
8. Record whether:

```text
avatar picker opens
confirmation appears only
nothing happens after confirm
not signed in/save/auth blocker appears
hard crash
return to menu
```

## Follow-Up Variant B

Only if Variant A shows the confirmation but no avatar UI:

- Include or expose `root/content/ui/net/profileeditor/main.sc.xml`.
- Try direct `Enter(MP_ProfileEditor)` or `Enter(MP_AvatarGroupSelector)` from the offline button.
- Keep this as SCXML-only.

## Do Not Patch Yet

```text
Do not patch fuieventmonitor.wsc.
Do not force NET_IS_IN_SESSION.
Do not bypass all auth checks.
Do not mix this with full MP freeroam bootstrap work.
```
