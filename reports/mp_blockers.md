# Code RED MP Blockers

- Route evidence present: NetConf_PlayLAN=`True`, auth route=`True`, TriggerMultiplayerLoad=`True`.
- Pass 2 import package files indexed: `236`.

| Blocker | Evidence | Consequence | Allowed next move |
| --- | --- | --- | --- |
| LAN route is conditionally visible | decoded `networking.sc.xml` excludes tabs first, then includes LAN from net-mode events | UI can remain unreachable even when route definitions exist | small local UI reachability review |
| Auth/profile gate before load | PlayMpConf path contains `Authenticate`, auth failure transitions, and `auth.success` before `TriggerMultiplayerLoad` | report-only in this pass | local/LAN candidate only after matrix evidence |
| Wrapper/path compatibility unresolved | PC examples are WSC RSC85; PSN CSC is swapped RSC86; XENON XSC is swapped RSC85 | restored files may import yet be ignored by loader | release/release64 matrix and export-byte proof |
| Update-thread linkage not directly named | Pass 1 decoded update-thread strings found zero direct donor filename-token hits | dependency may be hashed/runtime-table driven | do not infer missing or loaded scripts from strings alone |

Public matchmaking and external platform authentication remain report-only. Pass 3 does not spoof them or bypass them.

