# Code RED Remote Menu Puppet Marker Report

Status: logging fallback implemented and enabled by default.

Default marker mode:
- `puppet_marker_mode=log`
- `puppet_blip_enabled=false`
- `puppet_name_label_enabled=false`

Why log-only by default:
- The prior menu cursor/overlay path interfered with gameplay, so overlay remains disabled.
- Blip and overhead label natives are not yet proven crash-safe in this ASI.
- The task requires a marker fallback; logging the tracked puppet position every 5 seconds is the safest first proof.

Implemented behavior:
- After a valid puppet spawn, the ASI reads only the tracked puppet handle.
- It logs `Puppet marker:` every `puppet_marker_update_ms`.
- If `puppet_marker_mode=blip` and `puppet_blip_enabled=true`, it can attempt `ADD_BLIP_FOR_ACTOR`, but that is intentionally disabled in the installed config.
- If label mode is requested, it logs that no crash-safe overhead-label native is mapped and continues with logging.

Expected runtime proof line:

```text
Puppet marker: name=Remote Player actor=<handle> pos_read=1 pos=<x>,<y>,<z> blip=0 mode=log
```
