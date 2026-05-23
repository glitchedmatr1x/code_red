# Code RED Multiplayer Content Restore Pass 3 Readiness Report

## Scope and safety

- Report-only source inspection and manual-test planning.
- No `content.rpf` writes.
- No bytecode patching or script wrapper conversion.
- No public-server spoofing or external-auth bypass.

## Source inventory

| Source kind | Files scanned |
| --- | --- |
| decoded_ui_scxml | 36 |
| pass1_update_decode_report | 4 |
| pc_boot_or_menu | 1 |
| pc_update_script | 9 |

- Update-thread decode status rows available from Pass 1: `9`.
- Exported-back roots with files present: `0`.

## Pass 2 import packages

| Package | Files | Key MP resources seen |
| --- | --- | --- |
| import_test_both_csc | 90 | ctf_base_game.csc, deathmatch.csc, freemode.csc, mp_idle.csc, multiplayer_system_thread.csc, multiplayer_update_thread.csc, pr_multiplayer.csc |
| import_test_release64_csc | 45 | ctf_base_game.csc, deathmatch.csc, freemode.csc, mp_idle.csc, multiplayer_system_thread.csc, multiplayer_update_thread.csc, pr_multiplayer.csc |
| import_test_release_csc | 45 | ctf_base_game.csc, deathmatch.csc, freemode.csc, mp_idle.csc, multiplayer_system_thread.csc, multiplayer_update_thread.csc, pr_multiplayer.csc |
| import_test_xsc_review | 56 | ctf_base_game.xsc, deathmatch.xsc, freemode.xsc, mp_idle.xsc, multiplayer_system_thread.xsc, multiplayer_update_thread.xsc, pr_multiplayer.xsc |

## MP route evidence

| Evidence category | Hits |
| --- | --- |
| auth_or_profile_gate | 87 |
| local_or_menu_route | 32 |
| mp_signal | 14 |
| online_route_signal | 7 |
| runtime_load_route | 15 |
| visibility_or_offline_signal | 6 |

- Decoded UI sources contain LAN/System Link route definitions, NetConf confirmation flow, auth transitions, and the multiplayer load handoff.
- Restored MP scripts are staged for isolated import tests, but their presence alone does not prove the PC loader accepts CSC or XSC donor wrappers.
- The manual matrix should answer whether restored content changes visibility, error text, or loading behavior before any patch is selected.

## Highest-priority evidence

### Local LAN route

- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:122` `NetConf_PlayLAN` - <UILabel id="NetTab_LAN" desc="mp_fe_play_lan_tab" target="NetConf_PlayLAN" consume="false"></UILabel>
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:182` `NetConf_PlayLAN` - <UILabel desc="mp_fe_play_lan_tab" target="NetConf_PlayLAN" consume="false">
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:313` `NetConf_PlayLAN` - <UIMessageBox id="NetConf_PlayLAN">
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:315` `NetConf_PlayLAN` - <action expr="Exit(NetConf_PlayLAN)"></action>
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:318` `LAN` - <include src="net/PlayMpConf.sc" arg="NetConf_PlayLAN,'LAN Multiplayer','LAN'"></include>
- `root_content_ui_pausemenu_net_plaympconf.sc.xml.decoded.xml:47` `System Link` - 3.) Changing from System Link to an Online mode in MP

### Auth gate

- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:81` `auth.success` - <transition event="auth.success" expr="SendEvent('loadStart')"></transition>
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:94` `Authenticate` - <action expr="NetMachine.Authenticate('Online Multiplayer')"></action>
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:101` `Authenticate` - <action expr="NetMachine.Authenticate('Online Multiplayer')"></action>
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:147` `auth.success` - <transition event="auth.success" expr="SendEvent('loadStart')"></transition>
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:154` `Authenticate` - <action expr="NetMachine.Authenticate('Online Multiplayer')"></action>
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:162` `Authenticate` - <action expr="NetMachine.Authenticate('Online Multiplayer')"></action>

### Runtime load handoff

- `root_content_ui_pausemenu_net_plaympconf.sc.xml.decoded.xml:51` `TriggerMultiplayerLoad` - <action expr="NetMachine.TriggerMultiplayerLoad(arg2)"></action>
- `root_content_ui_pausemenu_lobby_main.sc.xml.decoded.xml:45` `MULTI_FREE_ROAM` - <onunfocused expr="Exit(MULTI_FREE_ROAM)"></onunfocused>
- `root_content_ui_pausemenu_lobby_main.sc.xml.decoded.xml:87` `MULTI_FREE_ROAM` - <onfocused expr="OL_PlaylistsMainList.SetCurrentSelectionCB('MULTI_FREE_ROAM',false)" ></onfocused>
- `root_content_ui_pausemenu_lobby_main.sc.xml.decoded.xml:118` `MULTI_FREE_ROAM` - <UIList id="MULTI_FREE_ROAM" allowInput="false">
- `root_content_ui_pausemenu_lobby_main.sc.xml.decoded.xml:122` `MULTI_FREE_ROAM` - <onfocused expr="SetTextCB(NetGameDetail,'MULTI_FREE_ROAM_detail')"></onfocused>
- `root_content_ui_pausemenu_lobby_main.sc.xml.decoded.xml:125` `SetGameWish` - <action expr="NetMachine.SetGameWish('MULTI_FREE_ROAM')"></action>
- `root_content_ui_pausemenu_lobby_main.sc.xml.decoded.xml:126` `NetConf_StartGame` - <action expr="goto(NetConf_StartGame)"></action>
- `root_content_ui_pausemenu_lobby_main.sc.xml.decoded.xml:132` `NetConf_StartGame` - <transition event="playlist.Unlocked" target="NetConf_StartGame"></transition>

## Readiness conclusion

The content-restore tree is ready for controlled import-matrix testing. Current evidence points at menu/net-mode/auth/load routing as the first observable blocker boundary, while format/path acceptance remains the content-compatibility question to isolate with the release, release64, and both CSC lanes.

