# Code RED Arm Population Micro Tests

This is a narrow rollback-safe tool for `arm_population.wsc`.

It is **not** a broad population replacer. The prior broad patch replaced 12 actor IDs and crashed when entering Armadillo. This tool makes one-ID-at-a-time variants so each ID can be tested separately.

## Workflow

```powershell
$env:CODERED_RDR_EXE="D:\Games\Red Dead Redemption\rdr.exe"
.\Run_CodeRED_ArmPopulation_MicroTests.bat scan --input imports\arm_population.wsc --out logs\arm_population_microtests\scan
```

Preview variants only:

```powershell
.\Run_CodeRED_ArmPopulation_MicroTests.bat make-micro-tests --input imports\arm_population.wsc --out-dir logs\arm_population_microtests\preview --preview-only
```

Generate one-ID Car01 variants:

```powershell
.\Run_CodeRED_ArmPopulation_MicroTests.bat make-micro-tests --input imports\arm_population.wsc --out-dir patches\arm_population_microtests_car --target-ids 1194 --max-replacements 4
```

Generate one-ID Truck01 variants:

```powershell
.\Run_CodeRED_ArmPopulation_MicroTests.bat make-micro-tests --input imports\arm_population.wsc --out-dir patches\arm_population_microtests_truck --target-ids 1193 --max-replacements 4
```

Test **one output WSC at a time**. Restore the original `arm_population.wsc` between tests if anything crashes.

## Guardrails

- Decodes RSC85 type-2 WSC using `rdr.exe` AES key.
- Uses Zstandard decode/repack.
- Patches only exact `u16be` actor IDs.
- Generates one-old-ID variants, not broad all-ID changes.
- Blocks variants with too many hits by default.
- Writes CSV reports for preview and replacements.
- Validates the repacked WSC before saving.


## v1.1 notes

- Fixes mixed-status summary CSV writing. Preview, blocked, skipped, and patched rows can now appear in the same summary without crashing.
- Keep testing one generated WSC at a time. Population scripts load early and can crash a town if too many IDs are changed.
- The broad population patch that changed 12 IDs is not recommended. Use the one-ID micro variants only.
