# Code RED SCO Workflow

## Scope

This workflow is for safe SCO/RPF investigation before any risky gameplay edit.

## Order Of Operations

1. **No-change roundtrip first**
   - Extract an RPF entry.
   - Copy it unchanged.
   - Compare original and copy.
   - Reinsert the identical copy into a cloned RPF.
   - Re-open and extract it back out.

2. **Same-size patches second**
   - Patch only strings/bytes where old and new byte lengths match.
   - Use exact offsets or `max_replacements` to avoid accidental global edits.
   - Compare before/after bytes.
   - Replace into a cloned RPF only.

3. **Padding only when explicit**
   - Shorter replacements require `--allow-padding`.
   - Padding uses NUL bytes and is reported in the manifest.

4. **No compiler needed for same-size patching**
   - Same-size patches do not require bytecode reassembly because offsets remain stable.

5. **Compiler/reassembler required for inserted logic**
   - New instructions, changed control flow, new strings, or longer strings require a proven SCO/WSC compiler or rebuilder.

## Current Targets

- `content/release64/init/rdr2init.wsc`
- `content/release64/init/rdr2init.sco`
- `content/scripting/gringo/SimpleGringo/playercar.wsc`
- `content/North/Missions/FBI04/FBI04.wsc`
- `content/ai/game_main.tr`
- `content/ai/general_rules.tr`
- `content/ai/human_reactions.tr`
- `content/ai/tasks.tr`

## Rules

- Do not overwrite live `content.rpf`.
- Do not commit game files.
- Do not treat string hits as behavior proof.
- Do not patch branch/native/control-flow bytes until ownership is mapped.
