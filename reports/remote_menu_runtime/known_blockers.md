# Code RED Remote Menu Puppet Known Blockers

- Runtime spawn is not yet user-confirmed. The ASI compiles and installs, but `F9` has not been tested in-game in this pass.
- Raw `CREATE_ACTOR_IN_LAYOUT` was previously marked as a crash trigger in Code RED menu data. This build uses hard guards and a single owned actor, but the native path still needs runtime proof.
- No safe actor delete/despawn native is mapped. `Backspace` clears/hides/releases the tracked handle instead of deleting it.
- Blip creation is disabled by default. `ADD_BLIP_FOR_ACTOR` exists in the SDK, but this pass keeps it gated behind config because visual marker natives are not proven crash-safe here.
- Overhead/name label is disabled by default. No safe overhead-label native is mapped.
- `F10` puppet movement is implemented but blocked by `puppet_move_enabled=false` until spawn and marker logging are stable.
- Soul Stealer remains disabled and should stay disabled while puppet spawn is being tested.
