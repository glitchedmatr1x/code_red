# Code Red WGD Inspector Report

Input: `commongringos.wgd_unpacked.wgd`
Size: 806,912 bytes

## Parse summary
- Root top-level gringo pointers: **950**
- Hash entries: **950**
- Parsed components: **5480**
- Item gringos: **950**
- Use contexts: **1082**
- Vehicle-related components: **129**
- Vehicle-related use contexts: **18**
- Parse errors: **0**

## Vehicle/driving findings
The file contains real common vehicle gringo data, not just incidental strings. The most useful outputs are `vehicle_candidates.csv` and `vehicle_use_contexts.csv`.

### PlayerCar / car_gringo use contexts
- `0x35A00` owner=`content\scripting\gringo\CommonScripts\PlayerCar` user_tag=`@GENERIC.USE` bone=`` radius=0.5 flags=player_usable, allow_navigate_to, fix_user_mover

### Truck-related use contexts
- No decoded truck UseContext rows matched; truck references may be animation strings or child components not yet decoded.

### Wagon/coach/stagecoach/cart use contexts
- `0x2AC80` owner=`content\scripting\gringo\CommonScripts\ClimbOntoWagon` user_tag=`@GENERIC.USE` bone=`` radius=0.5 flags=player_usable, allow_navigate_to, fix_user_mover

## First patch candidates
Do not patch yet unless a row shows a clear PlayerCar/car_gringo UseContext with `PlayerUsable=False` or `StartUnavailable=True` while a comparable wagon/truck context is usable. The likely safe fields to compare are:

```text
PlayerUsable, StartUnavailable, AllowNavigateTo, AlwaysApproach, AutoPlayForPlayer,
GringoHandlesMovement, FixUserMover, SuspendMover, Radius, UseButton, ParentTransformRemappedBone
```

## Files emitted
- `all_item_gringos.csv`
- `all_use_contexts.csv`
- `vehicle_candidates.csv`
- `vehicle_use_contexts.csv`
- `vehicle_string_hits.csv`
