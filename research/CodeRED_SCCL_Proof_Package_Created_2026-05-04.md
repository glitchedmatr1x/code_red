# Code RED SC-CL Proof Package Created — 2026-05-04

## Result

The SC-CL vehicle menu compile proof package was created successfully.

## Command

```powershell
powershell -ExecutionPolicy Bypass -File script_compiling\sccl\package_vehicle_menu_compile_proof_windows.ps1
```

## Proof package

```text
script_compiling\sccl\output\proof_packages\vehicle_menu_probe_compile_proof_20260504_165944
script_compiling\sccl\output\proof_packages\vehicle_menu_probe_compile_proof_20260504_165944.zip
```

## ZIP SHA1

```text
F10F3E55A0700DC63927B3C26EF41EAD9ECF0EA4
```

## Compiled artifact

```text
script_compiling\sccl\output\vehicle_menu_probe\vehicle_menu_probe.xsc
length: 1462
sha1: F6BDB733B54EAAAE757984008A7804F489471A5D
```

## Boundary

Proof package only. Not installed/imported into the game.

The SC-CL compile lane and proof packaging lane are proven. The archive install/import lane remains separate and still needs controlled proof.

## Next safe pass

1. Add an archive/path research pass for where a compiled `.xsc` should live.
2. Do not patch the game yet.
3. Build a copied-archive/import proof using a harmless known script slot only after path/format is verified.
