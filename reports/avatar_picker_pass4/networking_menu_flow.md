# Avatar Picker Access Pass 4 - Networking Menu Flow

Scope: `root/content/ui/pausemenu/networking.sc.xml` only.

This pass does not touch live `content.rpf` and does not output compressed/Zstandard files. All build outputs are plain editable XML.

## Source Used

Readable source:

```text
D:\Games\Red Dead Redemption\Code_RED\logs\content_mp_scxml_zstd_probe\decoded\root_content_ui_pausemenu_networking.sc.xml.decoded.xml
```

Install/import target:

```text
root/content/ui/pausemenu/networking.sc.xml
```

## Flow Map

`NetworkingLayerOffline` is the parent state for the pause menu networking screen.

On focus it asks the engine to emit a network mode event:

```text
NetMachine.SendNetModeEvent(NetworkingLayerOffline)
```

Then it routes:

```text
net.playingPublic  -> NetTabs
net.playingPrivate -> NetTabs
net.modeLAN        -> NetTabs
net.modeSingle     -> NetOfflineTabs
```

In normal local/single-player conditions, the likely active route is:

```text
NetworkingLayerOffline
-> net.modeSingle
-> NetOfflineTabs
```

## Important Difference

Online `NetTabs` has an avatar picker button:

```text
desc="mp_fe_avatarpicker_tab"
goto(NetConf_AvatarPicker)
```

Offline `NetOfflineTabs` does not. It only exposes:

```text
mp_fe_play_online_tab -> NetConf_PlayPublic
mp_fe_play_private_tab -> NetConf_PlayPrivate
mp_fe_play_lan_tab -> NetConf_PlayLAN
```

That explains why prior patches that used online-only tab logic may not have appeared.

## Network Nag Problem

The network blocker/nag states mostly have OK/Accept routes but no Cancel/Back routes:

```text
NetAlert_NotOnline
NetAlert_NotSignedIn
NetAlert_NotSignedInSysLink
NetAlert_NoCable
NetConf_PlayPublic
NetConf_PlayPrivate
NetConf_PlayLAN
```

`NetConf_PlayLAN` also forwards into:

```text
net/PlayMpConf.sc arg="NetConf_PlayLAN,'LAN Multiplayer','LAN'"
```

and has an auth failure route:

```text
auth.fail_NotSignedIn -> NetAlert_NotSignedInSysLink
```

So the nag the user sees is probably either:

```text
NetConf_PlayLAN -> PlayMpConf -> auth.fail_NotSignedIn -> NetAlert_NotSignedInSysLink
```

or a direct public/private online blocker:

```text
NetConf_PlayPublic / NetConf_PlayPrivate -> NetAlert_NotOnline or NetAlert_NotSignedIn
```

## Pass 4 Strategy

1. Restore usable back/cancel first.
2. Avoid hidden online-only tabs.
3. Use visible offline slots.
4. Keep `LaunchAvatarPicker` as the only event goal.
5. Do not add savegame/netstats/auth bypasses in this pass.

See:

```text
network_nag_routes.csv
online_offline_tabs.csv
xml_parse_validation.csv
```
