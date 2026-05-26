# Online HudScene / Avatar Picker Probe Pass 1

- source zip: `D:\Games\Red Dead Redemption\game\content zombie mp loading.zip`
- source RPF SHA1: `970BFC26D438CBBDB453BC82ADB0F6AC89DA789F`
- SteamGG path used: `false`
- live content.rpf edited by builder: `false`

## Variants
- `V0_zip_as_is_control`: `pass` `970BFC26D438CBBDB453BC82ADB0F6AC89DA789F` - Direct copy of content zombie mp loading zip content.rpf.
- `V1_profile_editor_direct`: `pass` `45C7C84E695E150149F35A2C12DFBF6AEB033D39` - Avatar picker tab directly enters MP_ProfileEditor and includes ../net/profileeditor/main.sc.xml.
- `V2_online_hudscene_direct`: `pass` `8DD5750327AD737F7EE1269FBE05ABBA4E6D1389` - Adds a pause-menu CodeRED online HUD label and includes ../net/hudsceneonline.sc.xml.
- `V3_profile_plus_hudscene`: `pass` `CFDD0AC7ED5EE057F66571E04E0F326C52B8DE9C` - Combines direct MP_ProfileEditor route with direct HudSceneOnline route.

## Test Order

1. Test `V0_zip_as_is_control` first. If it closes under 2 minutes, stop.
2. Test `V1_profile_editor_direct` for avatar/profile editor reachability.
3. Test `V2_online_hudscene_direct` for online HUD scene reachability.
4. Test `V3_profile_plus_hudscene` only if V1 and V2 both survive.

Restore the previous `game/content.rpf` between tests.
