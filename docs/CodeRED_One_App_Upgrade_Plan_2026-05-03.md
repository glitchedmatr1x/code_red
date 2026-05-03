# Code RED One-App Upgrade Plan

Date: 2026-05-03
Branch: `codered-one-app-planning`

## Purpose

Make Code RED easier to use by turning the current main workbench plus related apps into one organized app shell with clear tabs, guided actions, validation, and logs.

This is a planning pass only. The next coding passes should be small and proof-driven so existing tools do not regress.

## Current Findings

### Main collision

There are two root-level launch paths that point at the same workbench in different ways:

- `main.py` loads `python_workbench.py`, starts at the repo root, and titles the app `Code RED`.
- `run_workbench.py` loads `python_workbench.py`, but redirects startup to `related_apps/Code_RED_MP_Companion_v19` if present, and titles the app `Code RED Resource Workbench`.

This creates confusion over which main is authoritative. The upgrade should keep one canonical app entry point and demote the other to compatibility wrapper or remove it after launchers are updated.

### Workbench size risk

`python_workbench.py` is currently doing too much in one file:

- UI shell
- workspace scanning
- archive proofing
- script tooling detection
- source validation probes
- related-app launch paths
- patch helper calls
- report generation
- utility functions

Do not keep adding major systems directly into `python_workbench.py`. The correct approach is a main shell plus focused modules.

### Related apps to unify

The one-app shell should expose these lanes from inside Code RED:

1. Dashboard / status / repo doctor.
2. RPF archive tools and proof passes.
3. Tuner and Code Red Arcade demo.
4. AI Trainer / ScriptHookRDR AI Menu setup.
5. Actor enum / roster / behavior action editor.
6. Native database and native bridge builder.
7. Script compile/recompile lab.
8. WSI / map / terrain tools.
9. Vehicle/gringo research tools.
10. Logs, reports, and generated proof browser.
11. Packaging/export/install helpers.

## What Is Needed

### Needed now

#### 1. Canonical main launcher

Choose `main.py` as the only real app entry point.

Recommended behavior:

```text
Run_Code_RED.bat -> main.py -> Code RED app shell
run_workbench.py -> compatibility wrapper that imports/calls main.py, or remove later
```

Do not let MP Companion own the startup workspace by default. MP Companion should be a tab/lane inside the app.

#### 2. Modular app shell

Create a package such as:

```text
codered_app/
  __init__.py
  app.py
  paths.py
  launcher_registry.py
  tabs/
  services/
```

Keep `python_workbench.py` available while migrating. Do not break it in the first pass.

#### 3. Related-app launcher registry

Replace scattered launcher buttons with a registry file or Python registry:

```text
name
category
path
command
required_files
status_probe
notes
```

The app should show whether each lane is ready, missing dependencies, or missing files.

#### 4. Script compile/recompile center

Bring the script compile lab into the app as a guided lane.

Needed actions:

- Detect SC-CL/Magic-RDR/toolchain folders.
- Detect Visual Studio / cl.exe where needed.
- Open compile lab folder.
- Compile test script.
- Recompile known safe sample.
- Write proof logs.
- Do not promise existing `.wsc` binary roundtrip until proven.

#### 5. Actor enum and trainer center

This should be one of the first real work lanes.

Needed actions:

- Rebuild `data/codered/actor_enum_map.csv` from local `Enums.h` or bundled consts/source.
- Validate known actor sanity values.
- Edit/validate `npc_roster.txt`.
- Generate safe inline roster.
- Edit `ai_behavior_actions.csv`.
- Build/install AI Menu only after validation passes.
- Write actor resolution proof before spawn.

#### 6. Native database center

Add a native database/import lane before trying to program every native into C++.

Needed actions:

- Import native CSV files if present.
- Scan source/header files for native hashes and names.
- Scan readable extracted files for native-like symbols and usage clues.
- Store discovered natives in a local database/CSV/JSON.
- Categorize natives: actor, AI task, faction, vehicle, camera, UI, world, input, inventory, weapon, debug.
- Generate C++ wrapper stubs only for selected/validated natives.
- Do not auto-wire all discovered natives directly into the ASI.

#### 7. Logs and proof browser

Make logs usable from the app:

- Read `logs/CodeRED_LOG_INDEX.md`.
- Read `research/CodeRED_RESEARCH_MANIFEST.csv`.
- Show current reports by lane.
- Surface validation errors.
- Link generated proof JSON/MD files.

### Needed later

#### 1. Full semantic WSI editing

WSI byte patching and scanning are available, but full semantic WSI editing should wait until structure readers are proven.

#### 2. Full WVD/WBD model/collision editing

Do not present this as complete. Keep it in research/tools only until real structure editing and viewer proof exist.

#### 3. Full script binary decompile/recompile

Only expose proven compile/recompile flows. Existing binary script roundtrip should remain research until confirmed.

#### 4. Auto-patching live game archives

Never make this the default. Use copied archive patching, proof, and user-controlled install/export.

#### 5. Auto-programming all natives into ASI

Risky and unnecessary. Use a native database, selected wrappers, and proof gates.

## What Is Not Needed

- More root launchers.
- More separate GUI apps for every lane.
- Another broad repo cleanup pass before the app architecture is chosen.
- Direct edits to live game archives as the default workflow.
- Putting every tool function into `python_workbench.py`.
- Treating psocache as gameplay/spawn/AI data.
- Guessing WSC binary patches without compile/decode proof.
- Installing old crashing `CodeRED_AI_Menu.asi` builds.

## Proposed One-App Layout

```text
Code RED
├─ Dashboard
│  ├─ readiness score
│  ├─ staged game path
│  ├─ latest proof logs
│  └─ quick actions
├─ Archives
│  ├─ inventory RPF
│  ├─ extract readable files
│  ├─ patch copied archive
│  └─ proof pass
├─ AI Trainer
│  ├─ actor enum map
│  ├─ NPC roster
│  ├─ behavior actions
│  ├─ build/install AI Menu
│  └─ spawn proof logs
├─ Natives
│  ├─ import CSV
│  ├─ scan files
│  ├─ categorize discovered natives
│  ├─ generate wrappers
│  └─ bridge compile proof
├─ Scripts
│  ├─ detect SC-CL/Magic-RDR
│  ├─ compile sample
│  ├─ recompile lane
│  └─ output proof
├─ Vehicles / Gringos
│  ├─ vehicle generator trace
│  ├─ car/truck templates
│  ├─ locsets
│  └─ gringo scripts
├─ World / WSI / Terrain
│  ├─ WSI explorer
│  ├─ map layer correlator
│  ├─ terrainboundres tools
│  └─ proof-only patching
├─ Tuner / Arcade
│  ├─ open tuner embedded-or-launched
│  ├─ arcade settings
│  ├─ smoke test
│  └─ screenshots/logs
└─ Logs / Research
   ├─ log index
   ├─ research manifest
   ├─ reports
   └─ handoffs
```

## Recommended Pass Order

### Pass 1 - Planning and launcher cleanup

- Create this plan.
- Confirm `main.py` is canonical.
- Make `run_workbench.py` a compatibility wrapper or mark for removal.
- Do not change large app behavior yet.

### Pass 2 - App shell registry

- Add `codered_app/paths.py`.
- Add `codered_app/launcher_registry.py`.
- Add a related-app status scanner.
- Add dashboard output without breaking old workbench.

### Pass 3 - Logs/research browser

- Load `logs/CodeRED_LOG_INDEX.md`.
- Load `research/CodeRED_RESEARCH_MANIFEST.csv`.
- Show indexed notes inside the app.

### Pass 4 - AI trainer enum lane

- Fix actor enum map generation.
- Validate roster and action CSV.
- Add actor resolution proof output.

### Pass 5 - Native database lane

- Add native CSV import.
- Add file scanner for native names/hashes.
- Add categorized native database export.

### Pass 6 - Script compile lane

- Add toolchain detection panel.
- Add compile sample action.
- Add proof logs.

### Pass 7 - Related app consolidation

- Move tuner, arcade, MP companion, WSI, terrain, and vehicle tools into the registry with status and launch buttons.
- Keep external launch for heavy renderers until embedding is safe.

## Safety Rules

- One change lane per pass.
- Keep old workbench working until replacement shell is proven.
- Every compile/build/patch action writes logs.
- Every archive patch targets a copied archive unless user explicitly exports/install files.
- Every AI trainer spawn requires enum validation.
- Every native wrapper must come from an explicit selected native, not a blind full import.

## Immediate Decision

Use `main.py` as canonical.
Use `python_workbench.py` as the old workbench host during migration.
Use `codered_app/` for new modular code.
Use tabs/registry instead of more root launchers.
