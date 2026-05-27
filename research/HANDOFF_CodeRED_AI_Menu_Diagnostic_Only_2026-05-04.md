# HANDOFF — Code RED AI Menu Diagnostic-Only Fallback — 2026-05-04

## Why this exists

The user confirmed the game still crashes after removing direct `Car01` / `Truck01` from the raw spawn roster.

That means the problem may be deeper than unsafe vehicle entries:

```text
- ASI spawn action path may be unsafe
- CREATE_ACTOR_IN_LAYOUT argument packing may be wrong
- task/faction natives may be firing against invalid actors
- the ASI itself may crash even before selecting spawn
```

## Safety fallback committed

Disabled spawn/task/faction actions in:

```text
data/codered/ai_behavior_actions.csv
```

Added a new installer:

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/install_diagnostic_only_menu_data_windows.ps1
```

Commit IDs:

```text
79cd2c83cd09e50e56def17125d424b2882a2965
1bb1353227c704afe90ed0855a413eac11b71d2f
```

## User command after pulling

Run from repo root:

```powershell
powershell -ExecutionPolicy Bypass -File related_apps\Code_RED_ScriptHookRDR_AI_Menu\install_diagnostic_only_menu_data_windows.ps1 -GameRoot "D:\Games\Red Dead Redemption"
```

## Expected behavior

The menu should have only safe diagnostics enabled:

```text
Status / Native Bridge Check
Dismiss Tracked Actors
```

Spawn should be disabled.

## Interpret the result

If the game no longer crashes:

```text
Crash is inside spawn/task/faction native path.
Next pass: patch ASI source so disabled actions cannot execute, add hard guards around CREATE_ACTOR_IN_LAYOUT, and log before every native call.
```

If the game still crashes even with diagnostic-only data:

```text
Crash is likely ASI load/registration/draw/native bridge initialization.
Next step: rename CodeRED_AI_Menu.asi to CodeRED_AI_Menu.asi.disabled in the game root and verify the game boots. Then rebuild a true overlay-only ASI with no native bridge resolution.
```

## Do not do

Do not re-add Car01 or Truck01 to the default roster.
Do not test the 413-entry roster.
Do not test full combat/faction actions until the diagnostic-only menu is stable.
