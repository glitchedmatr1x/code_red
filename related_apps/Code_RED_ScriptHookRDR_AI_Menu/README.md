# CodeRED ScriptHookRDR AI Menu

Source-only scaffold for an in-game CodeRED AI companion menu for Red Dead Redemption PC using ScriptHookRDR.

This first pass is intentionally conservative:

- Proves ScriptHookRDR script registration.
- Proves keyboard input capture.
- Proves `drawRect` / `drawText` overlay rendering.
- Loads editable roster/config text files.
- Writes a selected action plan to `scratch/codered_ai_action_plan.json`.
- Does **not** spawn actors yet.
- Does **not** call risky actor/native spawn functions yet.

## Codex target

Ask Codex to compile `main` and focus only this folder:

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/