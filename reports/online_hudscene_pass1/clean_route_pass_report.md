# Clean Base Online/Avatar Route Probe

- clean source: `D:\Games\Red Dead Redemption\game\clean\content.rpf`
- clean SHA1: `E063FBEC79941AD2CA2504BA616596B1BB332B49`
- live content.rpf edited by builder: `false`

## Variants
- `C0_clean_copy_control`: `pass` `E063FBEC79941AD2CA2504BA616596B1BB332B49` - Direct copy of clean stock content.rpf.
- `C1_visible_network_only`: `pass` `2A0C83A61048EC42F486E857D9C2496D1DD1392D` - Only exposes the existing NetworkingLayerOffline parent route from the pause menu.
- `C2_avatar_send_event`: `pass` `A2DDFFDD6FA975AAC55B4ABE9D14D3EF4A852842` - Adds an offline networking avatar button that sends LaunchAvatarPicker; no new includes.
- `C3_avatar_goto`: `pass` `A18584A1C1FA68D4272C5EB5FBEFA7CB66D02756` - Adds an offline networking avatar button that goto(NetConf_AvatarPicker); no new includes.

## Runtime Smoke Results

Automated smoke tests on `D:\Games\Red Dead Redemption\RDR.exe` closed all clean-route variants before the two-minute threshold:

- `C1_visible_network_only`: closed after `46` seconds, exit `0`
- `C2_avatar_send_event`: closed after `47` seconds, exit `0`
- `C3_avatar_goto`: closed after `49` seconds, exit `0`

These are not accepted as stable under the current rule. The exit code was clean (`0`), so the result may be manual-close/inconclusive rather than a hard crash. No SteamGG folder was used. The live `game\content.rpf` and `CodeRED_Runtime_Probe.asi` were restored after testing.
