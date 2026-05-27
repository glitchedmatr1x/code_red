# WSC Binary Edit Workspace: long_update_thread.wsc

Issue: https://github.com/GLITCHEDMATR1X/Code_RED/issues/11

## Scope

Created an existing-file binary edit workspace for:

`root/content/release64/scripting/designerdefined/long_update_thread.wsc`

This used the default WSC binary edit lane. It did not use `full-replace-init`, did not generate `src/main.c`, did not replace the WSC with a WAIT-loop scaffold, and did not write to the live game folder.

## Source

- Source RPF: `D:\Games\Red Dead Redemption\game\content.rpf`
- Source RPF SHA1: `02F62FD6D91CA923573E3C67F99A1C3EBF692E49`

## Workspace

`build\wsc_edit\binary_long_update_thread\`

Expected files were created:

- `original\content\release64\scripting\designerdefined\long_update_thread.wsc`
- `edited\long_update_thread.wsc`
- `strings.json`
- `patches.json`
- `README_WSC_BINARY_EDIT.md`
- `codered_wsc_workspace.json`

Confirmed no `src` folder exists in this workspace.

## Hashes

- Original WSC SHA1: `0806E5B49EACA462E10CFDFCF73C85CB977D260A`
- Editable WSC SHA1: `0806E5B49EACA462E10CFDFCF73C85CB977D260A`
- WSC size: `194` bytes

The matching hashes confirm the editable file starts as an exact original-derived copy.

## Inspection Outputs

- Inspect report: `logs\wsc_binary_long_update_thread\inspect.json`
- Strings report: `logs\wsc_binary_long_update_thread\strings.json`

Extracted printable strings: `2`

| Offset | Length | Text |
|---:|---:|---|
| `0x64` | `6` | `ihpQP_` |
| `0xB0` | `4` | `0VMg` |

No extracted printable string contained obvious `mp`, `freeroam`, `net`, `session`, `region`, or UI wording.

## Recommended First Safe Edit Candidates

No semantic string edit is recommended from this file yet because the extracted strings look like incidental printable byte runs, not meaningful labels.

If a mechanical smoke edit is needed later, use only the controlled binary edit commands with exact expected bytes and keep the output in a copied RPF. Do not make length-changing edits unless a real WSC section/container rebuilder is implemented.
