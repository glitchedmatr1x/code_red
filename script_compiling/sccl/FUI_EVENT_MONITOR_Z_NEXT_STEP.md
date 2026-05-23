# FuiEventMonitor_z caller-patch next step

Current finding:

- `main_z` launches `DLC/ZombiePack/system/DesignerDefined/UI/FuiEventMonitor_z`.
- The active tree has both `FuiEventMonitor_z.wsc` and `FuiEventMonitor_z.sco`.
- The suspected blocker is a call/request from this monitor path to missing `multiplayer_update_thread` content.
- The direct goal is to patch only that missing request/load path, not replace the whole monitor.

Target active path:

```text
release64/dlc/zombiepack/system/designerdefined/ui/FuiEventMonitor_z.sco
```

Patch boundary:

- Keep existing monitor/UI behavior.
- Remove, guard, or bypass only the request/load/launch block for `multiplayer_update_thread`.
- Recompile or stage only the edited `FuiEventMonitor_z.sco`.
- Do not use the empty stub as a replacement for `FuiEventMonitor_z`; it is too important in the `main_z` boot chain.

Search terms in MagicRDR decompile/source view:

```text
multiplayer_update_thread
REQUEST_ASSET
LAUNCH_NEW_SCRIPT
HAS_SCRIPT_LOADED
SCRIPT_DONE_LOADING
WAIT
net.StartOnline
```

Preferred patch shape:

```c
// Before:
REQUEST_ASSET("$/content/multiplayer/multiplayer_update_thread", 4);

// Probe patch:
// Disabled for zombie standalone loader test: missing active WSC/SCO asset.
// REQUEST_ASSET("$/content/multiplayer/multiplayer_update_thread", 4);
```

or, if source cleanup requires keeping structure:

```c
if (false)
{
    REQUEST_ASSET("$/content/multiplayer/multiplayer_update_thread", 4);
}
```

Expected result:

- If loading proceeds further, the missing multiplayer update thread request is likely the blocker.
- If loading does not change, either the loader path is not using the edited SCO, the WSC is preferred, or another missing dependency is blocking.
- If the game crashes earlier, the caller path was active and the removed block may be needed in a different form.
