# Code RED Multiplayer Content Restore Pass 2 Format Compatibility

Pass 2 probes wrappers and raw import folder copies only. No RPF or compiled script logic is changed.

## Current PC examples

- Current extracted script/hash rows scanned: `1085`
- Extensions: `.sco:197 | .wsc:888`
- Header families: `RSC85:888 | other:197`
- Path families: `content/release64:1085`

The extracted PC tree inspected here exposes comparable compiled scripts under `content/release64` as WSC/SCO resources. Pass 2 does not assume donor CSC or XSC is accepted by the PC loader until import/export verification proves it.

## Donor compatibility result

- Pass 1 selected PSN CSC files probed: `45`
- XENON XSC review files probed: `56`
- CSC headers: `CSC_SWAPPED_RSC86:45`
- XSC headers: `XSC_SWAPPED_RSC85:56`
- File classifications: `conversion_blocked:56 | raw_import_candidate:45`

Current evidence keeps the Pass 1 CSC payloads as isolated raw import candidates, not proven PC-ready files: they are swapped RSC86 while current extracted PC WSC examples are RSC85. The XENON XSC donor is version-closer to PC at swapped RSC85, but raw XSC paths are not present in the extracted PC examples checked here, so it stays in the separate review lane until raw import or validated rewrap is proven.

## Byte preservation

- Raw copies checked: `236`
- Every staged copy byte-matches donor: `True`

Magic RDR post-import export verification is still required. Folder-copy hash preservation does not prove RPF import behavior.

