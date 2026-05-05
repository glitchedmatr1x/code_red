# Cleanroom Research Rules

This file keeps trainer/tool research useful without turning it into copied code.

## Allowed research

Allowed:

- list public feature categories
- inspect dependency names
- inspect config names and file layout
- observe menu behavior in-game/offline
- compare feature coverage
- map behavior to possible native categories
- record likely functions as unverified clues

## Not allowed

Do not:

- copy proprietary source code
- copy private tables/assets
- repackage another trainer
- bypass protections
- use findings for online cheating
- treat strings as proof of exact signatures

## How to record findings

Use behavior-focused notes:

```text
Observed behavior: trainer can spawn an actor from menu.
Likely native category: actor/model create.
Evidence status: research only.
Next step: verify exact wrapper/native signature locally.
```

Do not record copied code as implementation.

## Promotion rule

Research can become Code RED code only after verification:

```text
observation -> candidate native/wrapper -> verified signature -> tiny proof -> Code RED implementation
```

## Silent Virtues / other trainer research

Use external trainers as proof that a feature class is possible, not as source code to copy.

Good use:

```text
Trainer has actor spawn, vehicle spawn, weather, animation, and menu categories. Code RED should build equivalent categories with verified wrappers.
```

Bad use:

```text
Copy trainer implementation, menus, tables, or assets.
```

## Offline/private only

Code RED trainer experiments should be offline/private and focused on local research, debugging, and single-player modding.
