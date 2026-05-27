# Code RED Script Lanes

Use this file to decide where a task belongs before writing code.

## 1. Trainer / ScriptHook / RedHook lane

Purpose: real Code RED menu work.

Use for:

- actor selection
- actor spawn
- actor travel / follow / guard / attack commands
- player teleport
- selected actor teleport
- weather and time controls
- animation playback
- outfit / weapon / inventory menu controls
- live debug overlays
- runtime logging

Rules:

- Use only verified wrappers or exact signatures.
- Add one menu feature at a time.
- Log actor handles, coordinates, command names, and failures.
- Failed calls must safely do nothing.

Status: main lane for the menu.

## 2. SC-CL lane

Purpose: tiny internal script experiments.

Use for:

- minimal compile proofs
- single-native experiments
- controlled `.sco` / `.xsc` tests
- header/signature validation

Rules:

- Do not rebuild the full Code RED menu here.
- Use only real SC-CL headers from the known source-of-truth include folder.
- Do not use fake proof headers as evidence.
- Only actual compiled output counts as compile proof.

Status: research/proof lane only.

## 3. RPF / resource lane

Purpose: archive and resource work.

Use for:

- RPF inspection
- tune edits
- WSI / WGD / WVD / WBD exploration
- refgroup/event/resource correlation
- copied-archive patch tests
- export/import proof logs

Rules:

- Use copied archives.
- Change one placement/resource at a time.
- Reopen/verify patched archives.
- Never bulk patch unknown structures.

Status: separate from script/menu work.

## 4. Cleanroom research lane

Purpose: learn from existing tools without copying them.

Use for:

- feature inventories
- menu category comparison
- strings/config/dependency inspection
- behavior notes from public trainers/tools
- native/wrapper clues that still require verification

Rules:

- Do not copy proprietary code, assets, or tables.
- Record observations as behavior, not as lifted implementation.
- Promote findings to a build lane only after verification.

Status: research only.

## 5. Demo / arcade lane

Purpose: test feel outside the game.

Use for:

- camera feel
- menu UX prototypes
- companion behavior concepts
- vehicle/combat feel
- proof videos/screenshots for Code RED ideas

Rules:

- Do not treat demo behavior as game-native proof.
- Keep it clearly separated from RDR script logic.

Status: prototype lane.
