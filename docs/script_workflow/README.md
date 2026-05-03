# Code RED Script Workflow

This folder is the permanent source of truth for script work in Code RED.

The goal is to stop mixing unrelated lanes and to prevent guessed native calls from entering the real menu path.

## Active lanes

### 1. ScriptHook / AI Trainer lane

Use this for the real Code RED menu.

Allowed work:

- actor selection
- actor spawn/control commands
- follow, regroup, guard, attack, mount, dismiss
- save destination slots
- actor travel commands once the exact wrapper/signature is verified
- runtime logs and state files

This is the preferred lane for trainer-style features because normal trainers expose menu actions through a live hook/wrapper layer instead of forcing every feature through internal script compilation.

### 2. SC-CL proof lane

Use this only for tiny compile proofs.

Allowed work:

- one-native-at-a-time experiments
- real SC-CL headers only
- minimal `.xsc` / `.sco` output proof
- hash and document outputs before any install attempt

Do not use this lane for the full Code RED menu until every required native signature has been proven against the real headers.

### 3. Archive patch lane

Use this for RPF/tune/content/world edits.

Allowed work:

- copied archives only
- one changed placement at a time
- proof JSON
- reopen verification
- reversible patch packages

Do not bulk patch WSI, WGD, WVD, WBD, tune, or content archives without a small proof pass first.

### 4. Research lane

Use this for scanners, exporters, correlators, and read-only inventory tools.

Allowed work:

- native inventory
- actor enum inventory
- WSI/WGD correlation
- gringo/vehicle/event research
- string/table exports

Research output does not become patch code until it is promoted with proof.

## No-guess rule

A script feature is not real until at least one of these is true:

1. The native exists in real headers.
2. The function signature is verified from real headers or a known working wrapper/API.
3. A tiny compile or runtime proof works.
4. The command logs the actor handle, destination, and result.
5. Failed calls safely do nothing instead of breaking the menu.

## Current script direction

The real Code RED menu should be built in the ScriptHook / AI Trainer lane.

SC-CL remains useful, but only for minimal internal script experiments until the native signatures are proven.

Actor travel should start with safe, proven steps:

1. show player coordinates
2. save destination slot
3. select nearest actor
4. teleport selected actor to saved location
5. command selected actor to travel there only after the movement/task native is verified
