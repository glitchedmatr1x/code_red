# Code RED Runtime Menus

`tools/codered_menu_workshop.py` writes generated runtime menu JSON here when
`--emit-runtime` is used.

Generated files live under `data/codered/menus/generated/` and are ignored by
git. Keep source menu specs under `data/codered/menu_specs/` so every runtime
menu can be rebuilt and validated before the ASI reads it.
