# Code RED MP Observable Indicators

Pass 3 needs signs of life, not a broad patch. Record the first observable change per lane.

| Indicator | What to observe | Evidence to keep |
| --- | --- | --- |
| Menu reachability | Pause menu opens Networking/LAN/System Link route | baseline vs CSC package lane screenshot |
| UI visibility | LAN tab or MP confirmation appears, disappears, or changes label | menu screenshot and lane |
| Auth/profile gate | sign-in/profile alert text changes or auth failure moves later | exact alert text and log |
| Load transition | fade/loading screen starts after NetConf_PlayLAN confirmation | video timestamp and hang/return result |
| Resource effect | release vs release64 vs both changes result | matrix lane comparison |
| Crash boundary | start screen, pause menu, confirmation, load, or return-to-menu crash point | crash log and last visible screen |
| Export integrity | Magic RDR export bytes still match imported package bytes | SHA1/CRC worksheet |

