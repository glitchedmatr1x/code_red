# Runtime Restore: Restored or Suspect Files

Generated: 2026-05-23T22:50:09

No avatar picker, savegame, netstats, sector, MP bootstrap, XML, or WSC variant was applied in this pass. No content archive was modified.

## Known-Risk Target Check
```text
Target                                        LiveLooseFileFound Action Note                                                                               
------                                        ------------------ ------ ----                                                                               
root/content/ui/pausemenu/networking.sc.xml   no                 none   No loose live replacement found in executable root or game root during restore pass
root/content/ui/net/profileeditor/main.sc.xml no                 none   No loose live replacement found in executable root or game root during restore pass
root/content/ui/savegame.sc.xml               no                 none   No loose live replacement found in executable root or game root during restore pass
root/content/ui/savegame2.sc.xml              no                 none   No loose live replacement found in executable root or game root during restore pass
netstats/*.sc.xml                             no                 none   No loose live replacement found in executable root or game root during restore pass
fuieventmonitor.wsc                           no                 none   No loose live replacement found in executable root or game root during restore pass
fuieventmonitor_z.wsc                         no                 none   No loose live replacement found in executable root or game root during restore pass
rdr2init.wsc                                  no                 none   No loose live replacement found in executable root or game root during restore pass
medium_update_thread.wsc                      no                 none   No loose live replacement found in executable root or game root during restore pass
long_update_thread.wsc                        no                 none   No loose live replacement found in executable root or game root during restore pass
```

## Suspect Files Left Untouched
```text
Path                                                 Status        Reason                                                                                         SHA1                                    
----                                                 ------        ------                                                                                         ----                                    
D:\Games\Red Dead Redemption\content.rpf             left_in_place Potential live content archive; hard rule says do not touch content.rpf before clean launch    E063FBEC79941AD2CA2504BA616596B1BB332B49
D:\Games\Red Dead Redemption\game\content.rpf        left_in_place Main game content archive; not modified                                                        E063FBEC79941AD2CA2504BA616596B1BB332B49
D:\Games\Red Dead Redemption\game\content pass 1.rpf left_in_place Loose test archive in game folder but not named content.rpf                                    E0C19C0BD85D5E0A6720B96CD8916037780ADD37
D:\Games\Red Dead Redemption\game\gent.xml           left_in_place Loose XML in game folder, not a known runtime root path; not moved until clean launch baseline 2E560D5CA32752CEF4C937C53AE2F40CE7107DD8
```

Note: root `content.rpf` and `game\content.rpf` are byte-identical by SHA1, so no archive replacement was attempted.
