# CodeRED Actor Enum Editing Workflow

This pass changes the actor list from a rebuild problem into a data-file problem.

## What changed

The source now supports a runtime actor enum map:

```text
data/codered/actor_enum_map.csv
```

After the ASI is rebuilt once with the updated source, actor tests become:

```text
edit actor_enum_map.csv
press F5 in the in-game CodeRED menu
try Spawn Selected NPC again
```

No C++ source edit is needed for every new actor.

## Important

The current uploaded compiled `CodeRED_AI_Menu.asi` was left in the package as the old runtime copy. It will not use the new CSV loader until Codex / Visual Studio rebuilds the ASI from:

```text
Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.cpp
```

After that one rebuild, the CSV can be edited directly.

## CSV format

```csv
label,actor_enum,category,source,aliases,notes
player_marston,12345,player_like,manual,marston|john_marston,known-good enum
amb_prostitute,0x00003039,ambient,manual,,known-good enum
```

Rules:

- `label` is what appears in `npc_roster.txt` and in the in-game menu.
- `actor_enum` accepts decimal or hex.
- blank `actor_enum` means unresolved/research-only.
- `aliases` can contain multiple names separated by `|`.
- Press `F5` in game after editing the CSV.

## Fast manual edit

Open:

```text
data/codered/actor_enum_map.csv
```

Fill a row:

```csv
law_deputy,12345,law,manual,deputy,test enum
```

Then in game:

```text
F8 open menu
LEFT/RIGHT select law_deputy
F5 reload
ENTER on Spawn Selected NPC
```

The menu should show:

```text
ENUM: 12345 / 0x00003039
```

instead of:

```text
ENUM: unresolved
```

## Python workbench commands

Run from the project/package root:

```bat
py -3 tools\codered_actor_enum_workbench.py validate
```

List all rows:

```bat
py -3 tools\codered_actor_enum_workbench.py list
```

Search rows:

```bat
py -3 tools\codered_actor_enum_workbench.py list --filter army
py -3 tools\codered_actor_enum_workbench.py list --filter prostitute
```

Set one enum:

```bat
py -3 tools\codered_actor_enum_workbench.py set amb_prostitute 12345
py -3 tools\codered_actor_enum_workbench.py set player_marston 0x00003039 --alias john_marston --alias marston
```

Clear one enum:

```bat
py -3 tools\codered_actor_enum_workbench.py unset amb_prostitute
```

Rebuild `npc_roster.txt` from the CSV:

```bat
py -3 tools\codered_actor_enum_workbench.py build-roster
```

Build a roster containing only resolved/spawn-testable entries:

```bat
py -3 tools\codered_actor_enum_workbench.py build-roster --resolved-only
```

Build a roster with inline values for testing:

```bat
py -3 tools\codered_actor_enum_workbench.py build-roster --inline-enum
```

Import quick notes from a text file:

```text
amb_prostitute=12345
law_deputy=12346
player_marston=0x00003039
```

```bat
py -3 tools\codered_actor_enum_workbench.py import scratch\found_actor_enums.txt
```

## Validation report

Validation writes:

```text
scratch/codered_actor_enum_report.json
```

It reports:

- total rows
- resolved rows
- unresolved rows
- duplicate labels
- duplicate aliases
- invalid labels
- invalid enum values

## In-game output JSON

The ASI now writes actor enum resolution into:

```text
scratch/codered_ai_action_plan.json
```

Example resolved request:

```json
{
  "source": "CodeRED_AI_Menu",
  "action": "spawn_selected_npc_request",
  "model": "amb_prostitute",
  "actor_enum_resolved": true,
  "actor_enum": 12345,
  "actor_enum_hex": "0x00003039",
  "status": "queued",
  "timestamp": 1770000000
}
```

Example unresolved request:

```json
{
  "source": "CodeRED_AI_Menu",
  "action": "spawn_selected_npc_request",
  "model": "amb_prostitute",
  "actor_enum_resolved": false,
  "actor_enum": null,
  "actor_enum_hex": null,
  "status": "queued",
  "timestamp": 1770000000
}
```

## Recommended next testing order

1. Rebuild the ASI once.
2. Add one actor enum value only.
3. Press F5 and test spawn.
4. If it works, mark that row `known-good` in notes.
5. Add five more rows max.
6. Do not bulk-fill hundreds of enum guesses without testing; one bad slot can look like a spawn failure when the issue is the enum, layout, or actor availability.
