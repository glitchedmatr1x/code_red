# HANDOFF — Code RED Faction Wars Pipeline — 2026-05-04

## Goal

Move faction wars away from the crashing in-game menu/native-spawn lane and into the proven Code RED override/research lanes:

```text
Script Workshop
Script Compile Lab
Archive/RPF copied patch proof
Tune/content pressure patches
WSI/WGD/gringo world-host research
```

## Added

```text
tools/codered_faction_wars_pipeline.py
Run_CodeRED_Faction_Wars.bat
```

## What the pipeline does

It scans existing Code RED source/text/research/script-workshop exports and ranks faction-war targets by:

```text
factions
war behavior
spawning/encounter terms
world hosts / WSI / WGD / gringo terms
weapon pressure
scripting/native terms
regions
high-value native/resource markers
```

It writes:

```text
data/codered/faction_wars_targets.json
data/codered/faction_wars_targets.csv
data/codered/faction_wars_capabilities.json
research/faction_wars/FW_TARGET_PLAN.md
logs/CodeRED_Faction_Wars_Pipeline_Report.json
logs/CodeRED_Faction_Wars_Pipeline_Report.md
```

## Command

From repo root:

```bat
Run_CodeRED_Faction_Wars.bat
```

or:

```powershell
py -3 tools\codered_faction_wars_pipeline.py scan
```

For best results, run Script Workshop first:

```powershell
py -3 related_apps\CodeRED_Script_Workshop\CodeRED_Script_Workshop.py scan --refresh
py -3 tools\codered_faction_wars_pipeline.py scan
```

## Safety rules

```text
No menu spawning.
No raw CREATE_ACTOR_IN_LAYOUT faction-war spawns.
No source RPF mutation.
Use copied archives only.
Patch one script/resource/event at a time.
Require proof JSON and reopen verification.
Prefer existing event/tune/refgroup/WSI/WGD/gringo hosts.
```

## Next pass

Run the pipeline after Script Workshop refresh, then start FW-1/FW-2:

```text
FW-1: tune/content pressure without script install
FW-2: existing event/script target discovery
```

Do not revive the AI menu for faction wars until this lane has target proof.
