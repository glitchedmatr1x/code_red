# Code RED Decompile / Recompile Hub

Generated UTC: `2026-05-07T05:17:25Z`

Status: **READY_WITH_BLOCKED_SOURCE_DECOMPILER**

## Capability Matrix

| Lane | State | Tool | Proof / Boundary |
|---|---|---|---|
| `rpf_inventory_extract` | `ready` | `tools/codered_rpf_utils.py` | RPF6 parse + extract through python_workbench backend |
| `rpf_patch_copied_archive` | `ready` | `tools/codered_rpf_utils_patch.py` | Patch-folder apply writes a copied archive, not the source archive |
| `file_io_full_decode` | `ready` | `tools/codered_file_io_validation.py` | Full-file and RPF sample extraction validation |
| `script_read_decode` | `ready` | `tools/codered_script_pipeline.py` | Source/text decode plus compiled-script binary string/hash/native mining |
| `script_source_compile` | `ready` | `script_compiling/sccl/compile_vehicle_menu_probe_windows.bat` | SC-CL compile lane has produced real .xsc/.sco/.wsc proof artifacts where present |
| `compiled_script_source_decompile` | `blocked` | `` | No proven WSC/CSC/XSC/SCO bytecode-to-source decompiler was found; keep binary pseudo-decompile/export honest |

## Important Boundary

Code RED can extract/decode RPF entries, patch supported entries into copied archives, and compile source through SC-CL proof lanes. It still does not have a proven compiled-script bytecode-to-source decompiler, so `.wsc/.csc/.xsc/.sco` binary decompile remains readable/pseudo-decompile only until a real decompiler is found or built.

## Main Commands

```bat
Run_CodeRED_RPF_Edit_Lab.bat
Run_CodeRED_Decompile_Recompile_Hub.bat --validate
script_compiling\sccl\compile_vehicle_menu_probe_windows.bat
```
