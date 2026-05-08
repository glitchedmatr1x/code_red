# Code RED Decompile / Recompile Hub

Generated UTC: `2026-05-08T08:04:24Z`

Status: **READY_WITH_BLOCKED_SOURCE_DECOMPILER**

## Capability Matrix

| Lane | State | Tool | Proof / Boundary |
|---|---|---|---|
| `magic_rdr_name_recovery` | `ready` | `python_workbench.py + tools/codered_magic_rdr_bridge.py` | Magic-RDR imported filename lists restore RPF6 hash-name resolution for inventory/extract |
| `rpf_inventory_extract` | `ready` | `tools/codered_rpf_utils.py` | RPF6 parse + extract through python_workbench backend |
| `rpf_patch_copied_archive` | `ready` | `tools/codered_rpf_utils_patch.py` | Patch-folder apply writes a copied archive, not the source archive |
| `file_io_full_decode` | `ready` | `tools/codered_file_io_validation.py` | Full-file and RPF sample extraction validation |
| `script_read_decode` | `ready` | `tools/codered_script_pipeline.py` | Source/text decode plus compiled-script binary string/hash/native mining |
| `script_source_compile` | `ready` | `script_compiling/sccl/compile_vehicle_menu_probe_windows.bat` | SC-CL compile lane has produced real .xsc/.sco/.wsc proof artifacts where present |
| `wsc_source_edit_compile_pack` | `ready` | `tools/codered_wsc_edit_workflow.py` | Creates a safe edit workspace, compiles source to WSC/RSC85 through SC-CL, and packs only a copied RPF output under build/ |
| `compiled_script_source_decompile` | `blocked` | `` | No proven WSC/CSC/XSC/SCO bytecode-to-source decompiler was found; keep binary pseudo-decompile/export honest |

## Important Boundary

Code RED can extract/decode RPF entries, patch supported entries into copied archives, and compile source through SC-CL proof lanes. It still does not have a proven compiled-script bytecode-to-source decompiler, so `.wsc/.csc/.xsc/.sco` binary decompile remains readable/pseudo-decompile only until a real decompiler is found or built.

## Magic-RDR Parity / Name Recovery

Code RED now uses local Magic-RDR `ImportedFileNames.txt` resources for RPF6 hash-name recovery. Validated result: live `content.rpf` resolved `1636/1636` entries and extracted `1320/1320` files through the internal RPF6 extractor.

Primary proof log: `logs\IMPORTANT_CodeRED_Magic_RDR_Parity_Extraction_2026-05-06.md`

Important distinction: the live PC `content.rpf` extracted here contains `release64` SP/system/gringo content, while the older extracted root reference under `game\BACKUP BEFORE MODDING\rdr1\mods\root` contains the `content\release\multiplayer` `.csc` branch. Keep those as correlated evidence, not automatically identical archive versions.

## Main Commands

```bat
Run_CodeRED_RPF_Edit_Lab.bat
Run_CodeRED_Decompile_Recompile_Hub.bat --validate
Run_CodeRED_WSC_Edit_Workflow.bat --help
python tools\codered_wsc_edit_workflow.py decompile --name codered_wait_probe --archive-path root/content/release64/init/initpopulation.wsc
python tools\codered_wsc_edit_workflow.py recompile --workspace build\wsc_edit\codered_wait_probe --clean
python tools\codered_wsc_edit_workflow.py pack --workspace build\wsc_edit\codered_wait_probe --write
script_compiling\sccl\compile_vehicle_menu_probe_windows.bat
```
