# Code RED MP UI Networking Crosscheck

The crosscheck scans decoded UI resources, current PC update-thread resources, and existing update-thread decode reports for MP route terms.

## Hit categories

| Category | Hits |
| --- | --- |
| auth_or_profile_gate | 87 |
| local_or_menu_route | 32 |
| mp_signal | 14 |
| online_route_signal | 7 |
| runtime_load_route | 15 |
| visibility_or_offline_signal | 6 |

## Highest-signal files

| Relative source | Hits | Terms | Reason |
| --- | --- | --- | --- |
| ui/boot.sc.xml | 42 | Authenticate, Multiplayer, NetMachine, Online, auth.success, offline | current PC boot/menu text resource |
| root_content_ui_pausemenu_networking.sc.xml.decoded.xml | 41 | Authenticate, LAN, Multiplayer, NetConf_PlayLAN, NetMachine, NetworkingLayerOffline, Online, Private, Public, auth.success | priority decoded UI route |
| root_content_ui_pausemenu_lobby_main.sc.xml.decoded.xml | 25 | MULTI_FREE_ROAM, NetConf_StartGame, NetMachine, Posse, SetGameWish, StartGameWish | priority decoded UI route |
| root_content_ui_pausemenu_netstats_main.sc.xml.decoded.xml | 14 | Authenticate, NetMachine, Online, auth.success | decoded UI route corpus |
| root_content_ui_pausemenu_net_plaympconf.sc.xml.decoded.xml | 11 | Authenticate, NetMachine, Online, Private, Public, System Link, TriggerMultiplayerLoad, auth.success | priority decoded UI route |
| root_content_ui_pausemenu_net_lanmenu.sc.xml.decoded.xml | 8 | Authenticate, Multiplayer, NetMachine, Online | priority decoded UI route |
| root_content_ui_pausemenu_net_offlinemenu.sc.xml.decoded.xml | 5 | Authenticate, Multiplayer, NetMachine, Online | priority decoded UI route |
| root_content_ui_pausemenu_netstats_errormsgrecovery.sc.xml.decoded.xml | 5 | Authenticate, NetMachine, Online | decoded UI route corpus |
| root_content_ui_net_hudsceneonline.sc.xml.decoded.xml | 2 | NetMachine, Online | decoded UI route corpus |
| update_script_reference_report.md | 2 | Multiplayer | Pass 1 update-thread decode evidence |
| root_content_ui_generalmenus.sc.xml.decoded.xml | 1 | auth.success | decoded UI route corpus |
| root_content_ui_pausemenu_lobby_currentgamers.sc.xml.decoded.xml | 1 | NetMachine | decoded UI route corpus |
| root_content_ui_pausemenu_net_privatemenu.sc.xml.decoded.xml | 1 | NetConf_PlayLAN | decoded UI route corpus |
| root_content_ui_pausemenu_net_publicmenu.sc.xml.decoded.xml | 1 | NetConf_PlayLAN | decoded UI route corpus |
| root_content_ui_pausemenu_options.sc.xml.decoded.xml | 1 | Multiplayer | decoded UI route corpus |
| root_content_ui_pausemenu_pausemenuscene.sc.xml.decoded.xml | 1 | NetworkingLayerOffline | priority decoded UI route |

## Priority route evidence

### NetConf_PlayLAN

- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:122` `NetConf_PlayLAN` - <UILabel id="NetTab_LAN" desc="mp_fe_play_lan_tab" target="NetConf_PlayLAN" consume="false"></UILabel>
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:182` `NetConf_PlayLAN` - <UILabel desc="mp_fe_play_lan_tab" target="NetConf_PlayLAN" consume="false">
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:313` `NetConf_PlayLAN` - <UIMessageBox id="NetConf_PlayLAN">
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:315` `NetConf_PlayLAN` - <action expr="Exit(NetConf_PlayLAN)"></action>
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:318` `NetConf_PlayLAN` - <include src="net/PlayMpConf.sc" arg="NetConf_PlayLAN,'LAN Multiplayer','LAN'"></include>
- `root_content_ui_pausemenu_net_privatemenu.sc.xml.decoded.xml:11` `NetConf_PlayLAN` - <UIButton text="mp_fe_goto_lan" target="NetConf_PlayLAN"></UIButton>
- `root_content_ui_pausemenu_net_publicmenu.sc.xml.decoded.xml:12` `NetConf_PlayLAN` - <UIButton text="mp_fe_goto_lan" target="NetConf_PlayLAN"></UIButton>

### Authentication and auth.success

- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:81` `auth.success` - <transition event="auth.success" expr="SendEvent('loadStart')"></transition>
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:94` `Authenticate` - <action expr="NetMachine.Authenticate('Online Multiplayer')"></action>
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:101` `Authenticate` - <action expr="NetMachine.Authenticate('Online Multiplayer')"></action>
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:147` `auth.success` - <transition event="auth.success" expr="SendEvent('loadStart')"></transition>
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:154` `Authenticate` - <action expr="NetMachine.Authenticate('Online Multiplayer')"></action>
- `root_content_ui_pausemenu_networking.sc.xml.decoded.xml:162` `Authenticate` - <action expr="NetMachine.Authenticate('Online Multiplayer')"></action>
- `root_content_ui_pausemenu_net_plaympconf.sc.xml.decoded.xml:32` `auth.success` - <transition event="auth.success_NoComm" target="NetAlert_NoComm"></transition>
- `root_content_ui_pausemenu_net_plaympconf.sc.xml.decoded.xml:41` `auth.success` - <transition event="auth.success" consume="false">
- `root_content_ui_pausemenu_net_plaympconf.sc.xml.decoded.xml:55` `Authenticate` - <UIButton text="Common_Yes" icon="action" target="NetMachine.Authenticate(arg1)"></UIButton>
- `root_content_ui_pausemenu_net_lanmenu.sc.xml.decoded.xml:13` `Authenticate` - <action expr="NetMachine.Authenticate('Online Multiplayer')"></action>

### Multiplayer load / game wish

- `root_content_ui_pausemenu_net_plaympconf.sc.xml.decoded.xml:51` `TriggerMultiplayerLoad` - <action expr="NetMachine.TriggerMultiplayerLoad(arg2)"></action>
- `root_content_ui_pausemenu_lobby_main.sc.xml.decoded.xml:45` `MULTI_FREE_ROAM` - <onunfocused expr="Exit(MULTI_FREE_ROAM)"></onunfocused>
- `root_content_ui_pausemenu_lobby_main.sc.xml.decoded.xml:87` `MULTI_FREE_ROAM` - <onfocused expr="OL_PlaylistsMainList.SetCurrentSelectionCB('MULTI_FREE_ROAM',false)" ></onfocused>
- `root_content_ui_pausemenu_lobby_main.sc.xml.decoded.xml:118` `MULTI_FREE_ROAM` - <UIList id="MULTI_FREE_ROAM" allowInput="false">
- `root_content_ui_pausemenu_lobby_main.sc.xml.decoded.xml:122` `MULTI_FREE_ROAM` - <onfocused expr="SetTextCB(NetGameDetail,'MULTI_FREE_ROAM_detail')"></onfocused>
- `root_content_ui_pausemenu_lobby_main.sc.xml.decoded.xml:125` `SetGameWish` - <action expr="NetMachine.SetGameWish('MULTI_FREE_ROAM')"></action>
- `root_content_ui_pausemenu_lobby_main.sc.xml.decoded.xml:186` `StartGameWish` - <UIButton text="Common_Continue" icon="{@UI.ACCEPT}" e_action_released="NetMachine.StartGameWish()"></UIButton>

