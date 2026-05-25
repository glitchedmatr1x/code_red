# Avatar Picker Access Pass 4 - Patch Plan

All outputs are plain XML:

```text
D:\Games\Red Dead Redemption\Code_RED\build\avatar_picker_access_pass4
```

Install target for every variant:

```text
root/content/ui/pausemenu/networking.sc.xml
```

Do not install more than one variant at a time.

## Variant A - Cancel/Back Only

Output:

```text
build/avatar_picker_access_pass4/variant_A_cancel_back_only/networking.sc.xml
```

Purpose:

```text
Restore usable Cancel/Back behavior on network nag states.
No avatar route added.
```

Changes:

```text
Adds @UI.CANCEL*RELEASED -> Exit(...) to NetAlert_* and NetConf_Play* states.
Adds visible Common_Back/Common_Cancel-style prompt buttons where missing.
```

Test first. If this does not restore back/cancel from the nag, stop and report which nag/title is visible.

## Variant B - Visible LAN Slot To Avatar Confirmation

Output:

```text
build/avatar_picker_access_pass4/variant_B_visible_button_launchavatar/networking.sc.xml
```

Purpose:

```text
Use the confirmed visible offline LAN slot, but route it to NetConf_AvatarPicker.
```

Changes:

```text
NetOfflineTabs LAN label becomes avatar picker label.
target="NetConf_AvatarPicker"
Adds local NetConf_AvatarPicker messagebox copied from lobby/main.
Includes Variant A cancel/back fixes.
```

## Variant C - Direct Pause Route

Output:

```text
build/avatar_picker_access_pass4/variant_C_direct_pause_route/networking.sc.xml
```

Purpose:

```text
Bypass the nag and confirmation. Repurpose the first visible offline networking button to send LaunchAvatarPicker directly.
```

Changes:

```text
Offline public button becomes mp_fe_avatarpicker_tab.
On accept:
  NetMachine.SendScriptEvent('LaunchAvatarPicker')
  stackPush(HudSceneOnline)
Includes Variant A cancel/back fixes.
```

Use this if Variant B still opens a network blocker instead of the avatar confirmation/picker.

## Variant D - Nag Accept LaunchAvatar

Output:

```text
build/avatar_picker_access_pass4/variant_D_nag_accept_launchavatar/networking.sc.xml
```

Purpose:

```text
Only for the case where the network nag is the only reachable network UI.
```

Changes:

```text
NetAlert_NotOnline OK -> LaunchAvatarPicker
NetAlert_NotSignedIn OK -> LaunchAvatarPicker
NetAlert_NotSignedInSysLink OK -> LaunchAvatarPicker
NetAlert_NoCable OK -> LaunchAvatarPicker
NetConf_PlayLAN accept -> LaunchAvatarPicker
Includes Variant A cancel/back fixes.
```

This is the highest-risk SCXML-only variant because it uses the blocker itself as the trigger.

## Validation

All variants parse as XML:

```text
reports/avatar_picker_pass4/xml_parse_validation.csv
```

## Test Order

1. Variant A: confirm the nag can be canceled/backed out of.
2. Variant B: check for visible avatar/outfitter route replacing LAN slot.
3. Variant C: check whether direct `LaunchAvatarPicker` event opens anything.
4. Variant D: only if the nag is the only reachable network UI.

Record:

```text
which variant
which menu option appeared
which button was pressed
whether picker/profile/editor appeared
whether nag changed
whether cancel/back works
whether crash/hang occurred
```
