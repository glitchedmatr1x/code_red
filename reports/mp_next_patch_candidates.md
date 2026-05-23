# Code RED MP Next Patch Candidates

Candidate classes are ordered around the smallest observable blocker.

| Class | Target | Why it matters | Pass 3 action |
| --- | --- | --- | --- |
| safe_ui_unhide_candidate | NetTab_LAN include/exclude and offline networking entry | Only if matrix proves LAN route exists in files but never becomes visible | UI visibility review only before any edit |
| local_lan_route_candidate | NetConf_PlayLAN -> net/PlayMpConf.sc -> LAN arg2 route | Local/System Link reachability evidence exists | Keep LAN-only scope and preserve arg2 |
| resource_path_candidate | release CSC vs release64 CSC vs both package lanes | Need observable runtime difference first | Use matrix before changing paths |
| auth_gate_candidate_report_only | NetMachine.Authenticate and auth.success/fail transitions | Auth blocks occur before TriggerMultiplayerLoad | Report only in this pass |
| conversion_candidate | XENON swapped RSC85 XSC vs PSN swapped RSC86 CSC | Wrapper compatibility remains unproven | No conversion until import/loader evidence |
| do_not_patch_yet | public/private online, matchmaking, profile, service routes | External-auth/public-server behavior | Do not spoof public services |

