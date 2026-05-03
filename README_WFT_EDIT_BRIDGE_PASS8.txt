Code RED WFT / RSC5 Edit Bridge - Pass 8
=========================================

Purpose
-------
This is not a game-file patch. It is a tooling proof for editing RDR/GTA-IV-style
WFT resource files inside RPF archives.

The uploaded TextureToolkit package is useful as a reference for the idea of
resource texture import/export, but its included README says it targets GTAV
formats (*.ytd, *.ydd, *.ydr, *.yft, *.ypt). Those are RSC7-era resources.
The RDR WFT samples in fragments2.rpf are RSC5 resources.

What this pass proves
---------------------
- fragments2.rpf contains 41 .wft entries.
- All 41 scanned WFT entries parse as RSC5 resource blobs.
- The WFT resource type seen in these samples is 0x8A / 138.
- The RSC5 wrapper is:
  - bytes 0..3: RSC\x05
  - bytes 4..7: resource type, little endian
  - bytes 8..11: flag/page word, little endian
  - bytes 12..end: zstd-compressed resource payload
- A WFT can be exported from RPF, decompressed, recompressed, and verified.
- A copied RPF can be patched with a recompressed WFT resource and reread.
- Resource relocation must align to 2048 bytes, not 8 bytes, because the low
  byte of the RPF resource offset word is used for resource type.

Important safety rule
---------------------
Until the RSC5 page metadata is fully decoded, edits should keep the decoded
payload size the same. The tool refuses decoded-size changes by default.

This means Pass 8 is good for:
- scanning WFT entries
- exporting WFTs from RPFs
- unpacking WFTs into decoded resource payloads
- repacking same-size payload edits
- patching copied RPF archives with same-size edited payloads
- patching copied RPF archives with replacement standalone WFTs when page flags
  and decoded payload size match

This pass is not yet a full high-level mesh editor. It does not decode vertices,
bones, hierarchy, collision, drawables, or textures into editable GUI fields.
That is the next parser layer.

Commands
--------
Scan WFT entries in an RPF:

  py -3 tools\codered_wft_rsc5_tool.py scan-rpf ^
    --rpf fragments2.rpf ^
    --out reports\fragments2_wft_scan.json

Export one WFT entry and its decompressed payload:

  py -3 tools\codered_wft_rsc5_tool.py export ^
    --rpf fragments2.rpf ^
    --entry root/fragments/zombie_mexicanrebel_01.wft ^
    --out-dir exported_wft

Unpack a standalone WFT:

  py -3 tools\codered_wft_rsc5_tool.py unpack ^
    --wft exported_wft\zombie_mexicanrebel_01.wft ^
    --out-dir unpacked_wft

Repack a standalone WFT from an edited payload:

  py -3 tools\codered_wft_rsc5_tool.py repack ^
    --original-wft exported_wft\zombie_mexicanrebel_01.wft ^
    --payload exported_wft\zombie_mexicanrebel_01.wft.rsc5_payload.bin ^
    --out-wft exported_wft\zombie_mexicanrebel_01_edited.wft ^
    --report reports\repack_report.json

Patch an RPF entry from an edited decoded payload:

  py -3 tools\codered_wft_rsc5_tool.py patch-rpf ^
    --rpf-in fragments2.rpf ^
    --entry root/fragments/zombie_mexicanrebel_01.wft ^
    --payload exported_wft\zombie_mexicanrebel_01.wft.rsc5_payload.bin ^
    --rpf-out fragments2_edited.rpf ^
    --report reports\patch_report.json ^
    --overwrite

Patch an RPF entry from a replacement standalone WFT:

  py -3 tools\codered_wft_rsc5_tool.py patch-rpf-wft ^
    --rpf-in fragments2.rpf ^
    --entry root/fragments/zombie_mexicanrebel_01.wft ^
    --replacement-wft exported_wft\zombie_mexicanrebel_01_edited.wft ^
    --rpf-out fragments2_edited.rpf ^
    --report reports\patch_wft_report.json ^
    --overwrite

Dependencies
------------
- Python 3
- zstd command-line tool available on PATH
- Python cryptography package, for the included RPF utility when parsing encrypted RPF tables

Validation performed in this environment
----------------------------------------
- scan-rpf fragments2.rpf: 41 WFT files found, 41 RSC5 OK
- exported root/fragments/zombie_mexicanrebel_01.wft
- unpacked/decompressed payload: 237,568 bytes
- repacked same payload into a new standalone WFT and verified decompressed SHA1
- patched a copied fragments2.rpf using decoded payload and reread the patched WFT
- patched a copied fragments2.rpf using replacement standalone WFT and reread the patched WFT

Next parser layer
-----------------
The next useful pass should inspect the decompressed RSC5 payload structure:
- pointer table / block map
- drawable/fragments hierarchy
- material/texture references
- vertex/index buffer regions
- bone/hierarchy regions
- WFD/WEDT partner references

Do not bulk-patch production RPFs. Always test on copied archives first.
