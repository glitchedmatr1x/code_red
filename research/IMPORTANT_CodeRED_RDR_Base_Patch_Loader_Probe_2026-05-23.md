# IMPORTANT - Code RED RDR Base/Patch Loader Probe - 2026-05-23

Scope: read-only probe of the main Red Dead Redemption install under `D:\Games\Red Dead Redemption`.

Do not use this note for `RDR-SteamGG.NET`; that folder is out of scope unless explicitly requested.

## Summary

`patch1.rpf` by itself is not enough for this PC build to load an override patch. The executable contains a hard-coded base archive list and a separate patch mechanism string set, but the current main install does not have the live patch control files needed to prove `patch1.rpf` discovery.

The safest conclusion is:

- `game\base\*.rpf` is not enumerated generically.
- The known base RPFs are explicitly referenced by `RDR.exe`.
- Patch RPF loading likely depends on `patchversion.txt` and sequential `patch%i` naming, but this install currently has no active `patchversion.txt`, `patch0.rpf`, `patch1.rpf`, or `patchlist.txt` in the root/game folders.
- A bare `patch1.rpf` failed because the patch loader path was not activated or the naming/version sequence was incomplete.

## Main Install State Checked

Current `D:\Games\Red Dead Redemption\game\base` files:

```text
base.zip
content.rpf
cutscene.rpf
fragments.rpf
mapres.rpf
saves.rar
```

Current `game\base` RPFs:

```text
content.rpf
cutscene.rpf
fragments.rpf
mapres.rpf
```

No active patch control files were found directly under:

```text
D:\Games\Red Dead Redemption\
D:\Games\Red Dead Redemption\game\
```

Checked names:

```text
patch0.rpf
patch1.rpf
patchversion.txt
patchlist.txt
```

## Executable String Evidence

`D:\Games\Red Dead Redemption\RDR.exe` contains these embedded strings:

```text
0x1C791B0: $/content-patch/patch/patchlist
0x1C79538: base/content
0x1C79548: base/cutscene
0x1C79558: base/mapres
0x1C79568: base/fragments
0x1C79580: patchversion.txt
0x1C79598: patch%i
0x1C795A0: .rpf
0x1C795A8: .sdat
0x1C795B0: .edat
0x1C795B8: d11generic
```

Likely RIP-relative references were found for the relevant strings:

```text
$/content-patch/patch/patchlist: 1 code reference
base/content: 1 code reference
base/cutscene: 1 code reference
base/mapres: 1 code reference
base/fragments: 1 code reference
patchversion.txt: 4 code references
patch%i: 1 code reference
.rpf: 2 code references
```

This means the executable is actively referencing these names from code. It is not just dead text.

## Filename Index Evidence

`Code_RED\research\menu resources\ImportedFileNames.txt` contains:

```text
61700:plaympconf.sc.xml
61704:patchlist.txt
61705:content-patch
61706:patch
91815:patchversion.txt
```

This supports the executable string evidence that a Rockstar-style patch route exists conceptually, but the currently installed live archives did not expose a ready-to-use `content-patch/patch/patchlist` entry during the read-only inventory pass.

## RPF Inventory Evidence

Live main `game\content.rpf` inventory:

```text
entry_count: 1636
file_count: 1320
dir_count: 316
resolved_count: 1636
encrypted: true
```

No resolved inventory path matched:

```text
content-patch
patchlist
patchversion
patch
```

Main `game\base\content.rpf` inventory contains only:

```text
root/content/release64/frontier/missions/marshal04/marshal04.sco
root/content/release64/frontier/missions/marshal04/marshal04.wsc
```

Main `game\base\fragments.rpf` inventory contains only:

```text
root/fragments/anc_abes_girl_cs.wedt
root/fragments/anc_abes_girl_cs.wft
root/fragments/anc_abes_girl_cs_fexp.wedt
```

## Answer: Can EXE/Loader Be Modified To Read All RPF Names From `game\base`?

Yes, likely, but there are two very different risk levels:

1. Safer route: ASI/DLL loader hook.
   - Hook the archive mount/open path at runtime.
   - Enumerate `game\base\*.rpf`.
   - Mount additional RPFs without editing `RDR.exe` bytes directly.
   - Easier to disable by removing the ASI/DLL.

2. Riskier route: binary patch `RDR.exe`.
   - Patch the hard-coded base archive table or patch loader logic.
   - Must be done only on a copied EXE.
   - Needs a reversible patcher and validation.
   - A bad patch can prevent launch.

Given the recent hard crashes, the ASI/DLL hook is the better next route. Do not blind-edit `RDR.exe` in place.

## Why `patch1.rpf` Probably Failed

The executable string `patch%i` suggests numbered patch archives may be expected, but `patch1.rpf` alone is probably not the first archive checked. The usual pattern would be `patch0.rpf`, then `patch1.rpf`, controlled by a version/count file such as `patchversion.txt`.

Because the current install has no active `patchversion.txt`, and no visible patchlist resource was found in the live content inventory, the game likely never asked for `patch1.rpf`.

## Safe Next Tests

These should stay read-only or copy-only:

1. Build a tiny file-open logger ASI for local testing.
   - Log attempted `.rpf`, `.sdat`, `.edat`, `patchversion.txt`, and `patch%i` opens.
   - Do not modify game state.
   - This proves exact loader behavior without guessing.

2. Build a copied-sandbox patch probe.
   - Never modify live `RDR.exe`.
   - Test whether `patchversion.txt` with `patch0.rpf` is requested.
   - Keep it outside the active game folder unless explicitly approved.

3. Prefer a `base` RPF mount hook over EXE binary editing.
   - Runtime hook can enumerate extra `game\base\*.rpf`.
   - It should log every archive it attempts to mount.
   - It should have an INI kill switch.

## Do Not Do Yet

```text
Do not edit RDR.exe in place.
Do not add random patch*.rpf files to the live game folder and launch blindly.
Do not touch RDR-SteamGG.NET.
Do not rebuild or overwrite live content.rpf as part of this probe.
```
