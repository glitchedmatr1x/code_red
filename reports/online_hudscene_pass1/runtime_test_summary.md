# Online HudScene Runtime Test Summary

- live content restored: `true`
- test target: `D:\Games\Red Dead Redemption\RDR.exe`
- SteamGG used: `false`
- CodeRED_Runtime_Probe.asi was quarantined during tests and restored afterward.

## Results

- `V0_zip_as_is_control`: `bad_closed_under_2min` after `85` seconds, exit `1`, SHA1 `970BFC26D438CBBDB453BC82ADB0F6AC89DA789F`
- `V1_profile_editor_direct`: `bad_closed_under_2min` after `10` seconds, exit `-1073741819`, SHA1 `45C7C84E695E150149F35A2C12DFBF6AEB033D39`
- `V2_online_hudscene_direct`: `bad_closed_under_2min` after `11` seconds, exit `-1073741819`, SHA1 `8DD5750327AD737F7EE1269FBE05ABBA4E6D1389`
- `V3_profile_plus_hudscene`: `bad_closed_under_2min` after `4` seconds, exit `-1073740791`, SHA1 `CFDD0AC7ED5EE057F66571E04E0F326C52B8DE9C`

## Event Viewer Evidence

- V0 produced `AppHangB1` / Application Hang at about 85 seconds.
- Later direct-include variants produced `RDR.exe` crashes in `ucrtbase.dll` with `0xc0000409` or access violation style exit codes.

## Decision

All four variants failed the under-2-minute rule. Do not install these as working builds. Next pass should avoid direct SCXML includes of `../net/profileeditor/main.sc.xml` and `../net/hudsceneonline.sc.xml`; use existing loaded states/events or the runtime probe instead.

## Clean-Base Route Follow-Up

Clean-base route variants were built from `D:\Games\Red Dead Redemption\game\clean\content.rpf` instead of the donor `content zombie mp loading.zip`.

- `C1_visible_network_only`: `bad_closed_under_2min` after `46` seconds, exit `0`, SHA1 `2A0C83A61048EC42F486E857D9C2496D1DD1392D`
- `C2_avatar_send_event`: `bad_closed_under_2min` after `47` seconds, exit `0`, SHA1 `A2DDFFDD6FA975AAC55B4ABE9D14D3EF4A852842`
- `C3_avatar_goto`: `bad_closed_under_2min` after `49` seconds, exit `0`, SHA1 `A18584A1C1FA68D4272C5EB5FBEFA7CB66D02756`

The clean-route variants did not show the donor direct-include crash codes, but they still failed the automated two-minute rule. Because exit code was `0`, treat these as inconclusive unless the process was closed manually during testing.

After clean-route testing, `D:\Games\Red Dead Redemption\game\content.rpf` was restored to SHA1 `707EE65FC0D84CCF39519E3F75A2FF5569651F43`, matching `content_before_clean_variant_tests.rpf`. `CodeRED_Runtime_Probe.asi` was restored to the game root.
