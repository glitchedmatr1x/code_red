# Code RED Mod Workbench v0.3

Conservative scanner/patcher for Red Dead Redemption PC files.

## Supported lanes

- Raw XML/SCXML/text: normal text replacement.
- Binary files: same-size or shorter ASCII/UTF-16 replacements.
- WSC/RSC85: decode, patch decoded payload, repack, reopen/decode validate.
- Integer/enum patching: values like `1166 -> 1193`.
- New v0.3 sector lane: scan and patch world/child sector entries.

## Sector commands

Scan a WSC:

```bat
py -3 codered_mod_workbench.py sector-scan medium_update_thread.wsc --out reports\medium_sector_scan
```

Patch all matching sector entries:

```bat
py -3 codered_mod_workbench.py sector-patch medium_update_thread.wsc --sector esc_villaWall04x --set-state enabled --all --out patched\medium_update_thread.wsc
```

Rename a sector and convert to an enabled world sector:

```bat
py -3 codered_mod_workbench.py sector-patch medium_update_thread.wsc --sector beh_grave01x --replace-with dlc02x --set-type world --set-state enabled --all --out patched\medium_update_thread.wsc
```

## Marker map

From the proven Morning Star workflow:

- `0xF6` = `ENABLE_WORLD_SECTOR`
- `0xF7` = `DISABLE_WORLD_SECTOR` provisioned/inferred for tooling
- `0xF8` = `DISABLE_CHILD_SECTOR`
- `0xF9` = `ENABLE_CHILD_SECTOR`

## Safety

The tool never overwrites the input unless you explicitly point output to the same file. The Start Here menu saves into `patched\`.

For WSC/RSC85 it validates by reopening and decoding the patched file.
