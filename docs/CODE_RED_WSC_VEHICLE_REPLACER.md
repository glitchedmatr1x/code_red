# Code RED WSC Vehicle Replacer v7

Generic RDR1 WSC vehicle actor-ID scanner and patcher.

## Normal workflow

1. Pick a `.wsc/.xsc/.csc/.sco` file.
2. Choose the real `rdr.exe` if the AES key is not found automatically.
3. Click **Scan selected WSC**.
4. Select only IDs that appear in the decoded hit table for the selected integer format.
5. Choose a target vehicle.
6. Patch using one of the output modes below.

## Output modes

### Exact-size output

The default mode only writes a WSC if the recompressed payload is exactly the same byte size as the original. This is safest for raw exact-size archive replacement.

### Variable-size RPF output

Enable **Variable-size RPF output** when exact-size compression is impossible and you plan to inject the output through an RPF tool or Code RED path that updates the file entry size/TOC.

Do not raw-overwrite a fixed-size slot with this output. Use it only as a normal replacement file during RPF reinjection/rebuild.

### Experimental padded output

**Experimental padded output** is research-only. It appends Zstandard skippable padding to force the original payload size. It may validate in tools but crash in the retail game.

## Exact-fit search

For startup/population scripts, use **Find exact-fit variants** before patching a large group. This does not write a game file. It tries small one-ID and two-ID patches and reports whether any exact-size variant exists.

CLI:

```powershell
.\Run_CodeRED_WSC_Vehicle_Replacer.bat fit-search `
  --input imports\some_script.wsc `
  --out logs\wsc_vehicle_replacer\some_script_fit_search `
  --int-format u16be `
  --old-ids 1184 1196 1199 1200 1201 `
  --target-ids 1194 1193
```

## Variable-size CLI example

```powershell
.\Run_CodeRED_WSC_Vehicle_Replacer.bat patch `
  --input imports\some_script.wsc `
  --out patches\some_script_vehicle_replaced.wsc `
  --int-format u16be `
  --old-ids 1184 1196 1199 1200 1201 `
  --target-ids 1194 1193 `
  --variable-size-output
```

## Guardrails

- Source files are never modified.
- RSC85 type-2 scripts are AES decrypted with the local `rdr.exe` key and Zstandard-decoded before scanning.
- Vehicle replacements operate on exact decoded integer operands, not text substrings.
- Exact-size mode blocks padded Zstandard output by default.
- Variable-size output is valid only for RPF reinjection/rebuild where entry size/TOC is updated.
- Experimental padded output is for research only and may crash in-game.
