# Avatar Picker Pass 5 Blank Menu Trace

Generated: 2026-05-23T16:19:43

## Confirmed State

- Variant C opened the avatar picker, proving the `LaunchAvatarPicker` route reaches the runtime handler.
- Variant D fixed nag/cancel behavior but did not open the picker.
- Variant E now combines C's direct avatar launch route with D's clean cancel/no-nag behavior.
- No live `content.rpf` was modified.

## Variant E Output

- Raw XML: `D:\Games\Red Dead Redemption\Code_RED\build\avatar_picker_access_pass5\variant_E_direct_avatar_plus_clean_cancel\networking.sc.xml`
- Install target: `root/content/ui/pausemenu/networking.sc.xml`
- Validation: see `pass5_xml_parse_validation.csv`

## Blank Menu Root-Cause Evidence

`content/ui/net/profileeditor/main.sc.xml` already contains the avatar-picker UI nodes:

- `MP_ProfileEditor` layer
- `MP_ProfileMenu` with avatar/mount/title entries
- `MP_AvatarGroupSelector` using `mp_avatar_group0` through `mp_avatar_group25`
- `MP_AvatarModelSelector` using `mp_avatar0` through `mp_avatar13`

The same file does not stream `mp_avatarpicker`. Other UI files do use `StreamStringTable(...)`, for example pause menu stats and random character missions.

Current PC `strings_d11generic.rpf` contains `root/strings/mp_avatarpicker-*.wst` and `root/strings/mp_avatarpicker_win32.strtbl`. That means the string resources exist, but the profile editor layer is probably not loading them in this offline route.

## Decision

Build Variant F as a UI data-source patch: stream `multiplayer` and `mp_avatarpicker` while `MP_ProfileEditor` is active. This avoids WSC, auth, session, and savegame changes.
