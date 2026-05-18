# ASI/runtime notes

This folder is source/reference only. It is not a compiled ASI.

Use the same native/ScriptHook setup as the RDR1 trainer. The known trainer vehicle spawn chain explicitly:
- streams a vehicle actor
- creates it
- calls `SET_VEHICLE_ALLOWED_TO_DRIVE`
- enables seat 0
- puts the player in seat 0
- starts the vehicle
- turns the engine on

For Code RED, the runtime unlocker should not spawn new vehicles first.
It should find nearby event-spawned `1193` / `1194` vehicles and re-enable their seats/controls.