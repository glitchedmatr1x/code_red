# Code RED Tune - Max Render and Spawns Research

Purpose: identify how the tune-side render/spawn performance layer can support the faction-war/living-world project.

## Status

No exact repo file named `Tune - Max Render and Spawns` was found in the indexed repository during this research pass. The current research is based on the active/uploaded `tune_d11generic.rpf` structure plus the existing Pass 15 faction-war baseline.

## Strong tune-side files to track

These files are the first candidates for a render/spawn support layer:

- `root/tune/settings/ambientmgrtuning.xml`
- `root/tune/settings/componentallocations.xml`
- `root/tune/level/territory/level.pop`
- `root/tune/settings/default.traffic`
- `root/tune/level/playgrounds/level.streaming`
- `root/tune/level/playgrounds/low_level.streaming`
- `root/tune/level/playgrounds/designer_level.streaming`
- `root/tune/settings/bucket.cfg`
- `root/tune/settings/buckets.csv`
- `root/tune/settings/shadowmap.xml`
- `root/tune/settings/fastshadowmap.xml`
- `root/tune/template/template_base_human.xml`
- `root/tune/template/template_base_domesticated_dog.xml`
- `root/tune/settings/targettuning.xml`

## Key current values found

### Ambient manager

`ambientmgrtuning.xml` currently exposes:

- `MaxVisibleRange value="40.000000"`
- `DespawnMaxCheckDistance value="15.000000"`
- `DespawnNotVisibleTime value="3.000001"`
- `MaxNumActorsTotal value="50"`
- `NumActorsPreemptiveDestroy value="1"`
- `SpawnExcludeTime value="3.000000"`

This is a major living-world candidate. If faction-war events feel too sparse or actors despawn too quickly, this file can support more visible/lasting activity. It should be changed conservatively.

### Component allocations

`componentallocations.xml` currently exposes resource allocation counts. Important examples:

- `Mind = 80`
- `Animator = 80`
- `Behavior = 80`
- `BehaviorAnimal = 80`
- `Entity = 80`
- `Target = 80`
- `Vehicle = 20`
- `VehicleAudio = 20`
- `VehicleAnimator = 16`
- `DraftVehicle = 9`
- `Horse = 32`
- `BipedIK = 80`

This is probably the support file behind higher NPC/vehicle density. Raising population/event pressure without enough allocation headroom can cause missing actors, invisible behavior, or instability. This should be layered before very aggressive faction-war density.

### Population

`level.pop` exposes region-conditioned ped densities. Current examples include:

- `cond_Cholla_Springs Density 0.001 Ref "ped_wilderness"`
- `cond_Armadillo Density 0.009 Ref "ped_armadillo"`
- `cond_Escalera Density 0.008 Ref "ped_escalera"`
- `cond_Hennigans_Ranch Density 0.006 Ref "ped_hennigans_ranch"`
- `cond_Tumbleweed Density 0.001 Ref "ped_tumbleweed"`
- `cond_Town_Border Density 0.0001 Ref "ped_wilderness"`
- `cond_Thieves_Landing Density 0.009 Ref "ped_thieves_landing"`
- `cond_Fort_Mercer Density 0.002 Ref "ped_fort_mercer"`
- `cond_Ridgewood_Farm Density 0.001 Ref "ped_ridgewood_farm"`
- `cond_Twin_Rocks Density 0.001 Ref "ped_twin_rocks"`

This is useful for faction wars because it can make quiet regions less empty before event-specific pressure is added.

### Streaming / render

The three `.streaming` files expose world streaming ranges and LOD activation. Examples:

`level.streaming`:

- `ProxyCutoff: 500.000000`
- Physics: `MinDist 100`, `MaxDist 270`, `Scale 1.599996`
- LowLod: `MinDist 95`, `MaxDist 300`, `Scale 1.099999`
- MediumLod: `MinDist 21`, `MaxDist 200`, `Scale 0.250000`
- HighLod: `MinDist 10`, `MaxDist 50`, `Scale 0.099996`
- UltraHighLod: `MinDist 5`, `MaxDist 50`, `Scale 0.0059996`

These are useful for a performance mod, but they should not be blindly maxed. If draw/streaming distance is too high while spawn pressure is also high, faction wars may look better at distance but become less stable.

### Draw buckets

`bucket.cfg` and `buckets.csv` expose draw bucket sizes. `buckets.csv` has larger apparent capacities for shadow, reflection, rain, and main render buckets. These can support more visible activity/props, but they are render-side and should be tested separately from actor density.

## What this can add to faction wars

1. More staying power for spawned ambient actors and faction-war pressure.
2. More visible range before actors are culled/despawned.
3. More resource headroom for higher NPC, animal, horse, vehicle, and wagon counts.
4. Higher wilderness/town ped density before event-specific faction pressure is layered.
5. Render/streaming support so camps, props, events, and actors do not vanish too aggressively.
6. Better support for road trouble, law response, gang pressure, and camp/refgroup persistence.

## Recommended layer order

1. Baseline: validated Pass 15 / Pass 15.30 faction-war lineage.
2. Add conservative allocation headroom from `componentallocations.xml`.
3. Add conservative ambient manager range/actor cap changes.
4. Add region population density changes in `level.pop`.
5. Add render/streaming changes separately.
6. Add event/refgroup/camp pressure only after the support layer is stable.

## Do not do yet

- Do not max every value at once.
- Do not combine render distance increases and spawn pressure increases in one blind pass.
- Do not edit source archives directly.
- Do not use live plugin spawning as the first test.

## Best next pass

Code RED Living World Pass 16A - Tune Support Layer

Goal: build a small copied-archive patch that only adds spawn/render support, then test whether faction-war Pass 15 keeps its preserved features while gaining more visible world activity.
