Code RED MP Companion boot route validator

Portable default. Choose a local content source inside the companion before validating real files.

# Code RED boot-route validation

- Timestamp: 2026-04-19T06:28:15
- Mode preset: LAN Multiplayer
- Boot target: NetConf_PlayLAN
- Route note: Networking -> Play LAN -> PlayMpConf(LAN) -> Lobby / TaskMachine
- Overall pass: yes

## Checked files

### root/content/ui/net/main.sc.xml
- Present: yes
- Required strings: 1 / 1
- Matched strings:
  - playerlist

### root/content/ui/net/taskmachine.sc.xml
- Present: yes
- Required strings: 2 / 2
- Matched strings:
  - NetMachine.StartMultiplayer()
  - NetTaskMachine id="NetMachine"

### root/content/ui/pausemenu/networking.sc.xml
- Present: yes
- Required strings: 3 / 3
- Matched strings:
  - NetConf_PlayLAN
  - LAN Multiplayer
  - net.modeLAN

### root/content/ui/pausemenu/lobby/0x2B5C38A8
- Present: yes
- Required strings: 2 / 2
- Matched strings:
  - NetConf_StartGame
  - playerlist

### root/content/ui/net/hudsceneonline.sc.xml
- Present: yes
- Required strings: 2 / 2
- Matched strings:
  - net.modeLAN
  - multiplayerIcons

## Entry route chain
- networking.sc.xml
- PlayMpConf.sc (LAN)
- taskmachine.sc.xml
- hudsceneonline.sc.xml
