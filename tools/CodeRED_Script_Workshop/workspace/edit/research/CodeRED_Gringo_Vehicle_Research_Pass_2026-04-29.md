# Code RED — Gringo Vehicle Research Pass

Date: 2026-04-29

## Why this pass happened

The Blackwater WSI test changed the old broken-car prop reference:

```text
p_gen_carblocked01x -> car01
```

In-game result: the car was missing.

Interpretation:

- The WSI edit worked enough to alter/remove the original static prop reference.
- `car01` is not a valid standalone static world prop replacement in that WSI slot.
- A real vehicle likely needs the gringo/script vehicle system instead of a simple prop-name swap.

## Stronger vehicle lead

The strongest lead is the Gringo dictionary layer, especially:

```text
gringores.rpf/root/gringores/commongringos.wgd
```

CodeX.Games.RDR1 confirms that `.wgd` is a `WgdFile` wrapping `Rsc6GringoDictionary`. The dictionary is read through `Rsc6DataReader` from an RPF6 resource entry and exposes `Gringos` / `Hashes` arrays.

CodeX structure reference:

```text
Rsc6GringoDictionary
- VFT: 0x0091BC40
- Hashes: Rsc6Arr<JenkHash>
- Gringos: Rsc6PtrArr<Rsc6GringoBase>

Rsc6GringoBase
- QueryName
- HashCode
- ParentComponent

Rsc6Gringo / ggoItemGringo
- ScriptName
- GringoName
- Childs
- InstancedItems
- HashedName
- MessageMask
- ActivationRadius
- InstanceSlotCount
- Critical
- LargeScript
- MaintainState

Rsc6GringoUseContext / ggoComponentUseContext
- Facing
- LocalPosition
- Radius
- UserTag
- PlayerUsable
- ActorBecomesObstacle
- GringoHandlesMovement
- RequiresPhysicsCheck
- RequiresNavProbeCheck
- AllowAiShoot
- AutoPlayForPlayer
- AllowNavigateTo
```

## Tool added

This pass adds:

```text
tools/codered_gringo_wgd_export.py
```

The exporter scans decoded or raw WGD payloads for known gringo component VFTs:

```text
0x01979634 = ItemGringo / ggoItemGringo
0xE03269C1 = UseContext / ggoComponentUseContext
0xB16C14A8 = ItemAttributes / ggoItemPureAttribList
```

It exports:

```text
*.components.csv
*.components.json
*.keyword_hits.csv
all_components.csv
keyword_hits.csv
gringo_wgd_export_master.json
```

## Local commongringos result

Test file:

```text
commongringos.wgd.decoded
```

Result:

```text
2524 gringo components exported
```

Vehicle-related ItemGringo roots found:

```text
content\scripting\gringo\CommonScripts\Vehicle_Generator
content\scripting\gringo\CommonScripts\car_gringo
content\scripting\gringo\CommonScripts\PlayerCar
content\scripting\gringo\CommonScripts\CarCrank_gringo
content\scripting\gringo\GringoBrains\GringoBrainScripts\Gen_Vehicle_Brain
content\scripting\gringo\CommonScripts\trainCar_gringo
content\scripting\gringo\CommonScripts\trainCarArmored_gringo
content\scripting\gringo\CommonScripts\trainCarBaggage_gringo
content\scripting\gringo\CommonScripts\trainCarBox01_gringo
content\scripting\gringo\CommonScripts\trainCarBox02_gringo
content\scripting\gringo\CommonScripts\trainCarBox03_gringo
content\scripting\gringo\CommonScripts\trainCarBox04_gringo
content\scripting\gringo\CommonScripts\trainCarBox05_gringo
content\scripting\gringo\CommonScripts\trainCarCaboose_gringo
content\scripting\gringo\CommonScripts\trainCarCattle_gringo
content\scripting\gringo\CommonScripts\trainCarFlat_gringo
content\scripting\gringo\CommonScripts\trainCarSteamer_gringo
content\scripting\gringo\CommonScripts\trainCarWood_gringo
```

Important root samples:

```text
0x0003BED0 ItemGringo Vehicle_Generator activation_radius=200 child_count=2
0x0003CF24 ItemGringo Vehicle_Generator activation_radius=200 child_count=2
0x0003D398 ItemGringo car_gringo activation_radius=200 child_count=0 critical=1 maintain_state=1
0x000420A8 ItemGringo Gen_Vehicle_Brain activation_radius=2147483648 critical=1 maintain_state=1
0x0004B4CC ItemGringo CarCrank_gringo activation_radius=100 child_count=1 instanced_item_count=3 instance_slot_count=3
0x0004C8FC ItemGringo PlayerCar activation_radius=200 child_count=1 instanced_item_count=3 instance_slot_count=3 maintain_state=1
```

`PlayerCar` and `CarCrank_gringo` each have a `UseContext` child and instanced items. This suggests they are more than static props: they describe interaction/use contexts and probably vehicle behavior attachment.

## FBI / mission vehicle clues inside commongringos

The same decoded `commongringos.wgd` contains mission/FBI vehicle string tokens:

```text
VEHICLE_WagonPrison01
VEHICLE_Coach01
VEHICLE_Wagon02
VEHICLE_Cart01
TURRET_Browning
$\Companion\Fbi
FBI01_gang
fbi02_cs03
fbi02_cs03_b
FBI05_CS03B
comp_FBI_01_PIQ
comp_FBI_02_PIQ
comp_FBI_03_PIQ
comp_FBI_04_PIQ
```

This lines up with the user's note that FBI mission/cutscene files contain vehicle setups.

## Current interpretation

The car did not appear from the WSI `car01` test because a real drivable/animated car is not a simple WSI static prop reference.

The better target is likely one of these lanes:

```text
Lane A — WSI places a gringo host/reference.
Lane B — WGD defines the vehicle/playercar gringo behavior and use contexts.
Lane C — WSC mission scripts or gringo scripts call vehicle spawn/setup natives.
Lane D — FBI cutscene/mission resources provide vehicle model names and staged vehicle examples.
```

## Best next experiment direction

Do not randomly replace static props with `car01` again.

Better next tests:

```text
1. Export Blackwater WSI gringo placement rows.
2. Find existing harmless Blackwater gringo placements near town.
3. Compare those WSI references to names in commongringos.wgd.
4. Try swapping a WSI gringo reference to an existing Vehicle_Generator gringo name/path, not to a raw model name.
5. Separately inspect FBI mission WSC/cutscene data for the exact vehicle token used with the vehicle generator.
```

Potential string targets to test only after confirming the WSI gringo path format:

```text
content\scripting\gringo\CommonScripts\Vehicle_Generator
content\scripting\gringo\CommonScripts\PlayerCar
content\scripting\gringo\CommonScripts\car_gringo
```

Potential vehicle tokens to research:

```text
VEHICLE_Coach01
VEHICLE_Cart01
VEHICLE_Wagon02
VEHICLE_WagonPrison01
```

The vehicle token may be an attribute/parameter to `Vehicle_Generator`, not the WSI object name itself.

## Next Code RED pass

Recommended next pass:

```text
WSI <-> WGD Gringo Correlator
```

Tasks:

```text
1. Export every Blackwater WSI reference containing `gringo`, `has_gringo`, or `gringo_available`.
2. Hash/resolve those names against commongringos.wgd component names and hashes.
3. Export a correlation table:
   - WSI record offset
   - WSI object/name string
   - WSI coordinates/transform candidates
   - matching WGD component/script path
   - activation radius
   - child/use-context counts
4. Identify one safe, visible, non-critical gringo placement for a Vehicle_Generator test.
```

Risk note:

```text
Vehicle_Generator and PlayerCar are higher-risk than static props. They should be tested in a copied RPF only, with one placement changed at a time.
```

## Relation to faction-war pass

Gameplay pass 15.60 already held exact actor loadouts, gatling/Maxim vehicle assault spawns, and map markers until the exact actor/event/vehicle table is found. This gringo vehicle research is the right direction for that missing vehicle-spawn lane.
