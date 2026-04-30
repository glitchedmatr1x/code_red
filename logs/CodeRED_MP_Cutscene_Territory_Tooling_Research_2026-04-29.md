# Code RED — MP, Cutscene, Territory, and RDR Tooling Research Notes

Date: 2026-04-29
Scope: Consolidated notes from the uploaded mixed-version multiplayer files, current content.rpf, cutscene.rpf, territory_swall resources, RAGE string database/tooling review, ClosedIV review, CodeX.Games.RDR1 review, and RDR-Script-Decompiler review.

This is a repo research log. Large CSV/JSON extraction outputs were intentionally kept out of GitHub unless they become build inputs.

---

## 1. Mixed-version multiplayer working.zip research

Uploaded donor pack: `working.zip`.

The archive contains SCXML/XML UI state-machine files. It is not the full multiplayer runtime; it is a front-end route into native engine calls.

Important donor files:

```text
boot.sc.xml
networking.sc.xml
plaympconf.sc.xml
lanmenu.sc.xml
taskmachine.sc.xml
hudsceneonline.sc.xml
```

Strongest flow clue:

```text
boot.sc.xml
  -> auto-enters NetConf_PlayLAN from the start screen
networking.sc.xml
  -> includes net/PlayMpConf.sc
plaympconf.sc.xml
  -> calls NetMachine.TriggerMultiplayerLoad(arg2)
taskmachine.sc.xml
  -> handles net.StartOnline with NetMachine.StartMultiplayer()
NM_JoinProcess
  -> can call NetScene.RequestJoin()
failure paths
  -> can call NetMachine.ReturnToFreeRoam()
```

Interpretation:

- These donor files explain why mixed-version mods can sometimes reach multiplayer menus or partial MP behavior.
- They are not a full multiplayer fix.
- The target version still needs compatible native runtime/session support.

Important donor behavior:

- `plaympconf.sc.xml` is the risky/interesting file.
- In the donor version, auth failures such as not signed in, no cable, not online, privilege fail, or wrong disc can still flow into `NetMachine.TriggerMultiplayerLoad(arg2)`.
- This is likely the donor trick that makes some multiplayer front-end flow work.

Do not bulk merge:

- Donor `boot.sc.xml` is not safe as a full replacement.
- It failed strict XML parsing because the outer `Startup` object appears to be left unclosed after nested `Startup_Checks`.
- Treat it as a reference/donor only.

Recommended Code RED feature:

```text
MP SCXML Analyzer
- scan UI SCXML/XML files
- find NetConf_PlayLAN, PlayMpConf.sc, TriggerMultiplayerLoad, StartMultiplayer
- find RequestJoin, ReturnToFreeRoam, HudSceneOnline
- compare donor/current versions side by side
- stage optional LAN-only patches separately from Public/Private patches
```

---

## 2. Current content.rpf multiplayer research

Target archive: uploaded current `content.rpf`.

Current `content.rpf` opened cleanly with the Code RED RPF6 parser.

Inventory summary:

```text
entries: 1636
.wsc:    886
.sco:    197
.xml:    177
.tr:      25
.strtbl:  14
```

Current content already has the real multiplayer front-end route:

```text
root/content/ui/boot.sc.xml
root/content/ui/pausemenu/networking.sc.xml
root/content/ui/pausemenu/0x007B97C6/plaympconf.sc.xml
root/content/ui/net/taskmachine.sc.xml
root/content/ui/net/hudsceneonline.sc.xml
root/content/ui/pausemenu/lobby/0x2B5C38A8
```

Major discovery:

- `taskmachine.sc.xml` in donor `working.zip` is byte-identical to the current `content.rpf` version.
- The native launch bridge already exists in current content.

Confirmed current bridge:

```text
net.StartOnline
  -> StackPush(HudSceneOnline)
  -> Enter(NM_JoinProcess)
  -> NetMachine.StartMultiplayer()
```

Confirmed invite/join clue:

```text
net.readyForInvite
  -> NetScene.RequestJoin()
```

Donor/current difference:

- Current `plaympconf.sc.xml` only triggers multiplayer load on auth success.
- Donor `plaympconf.sc.xml` changes several auth failure paths into `NetMachine.TriggerMultiplayerLoad(arg2)`.

Resolved donor hash-name files:

```text
0x118473D0.xml = offlinemenu.sc.xml
0x1374443B.xml = plaympconf.sc.xml
```

Current recommendation:

```text
Do not merge working.zip wholesale.
Build a guarded MP Companion lane:
1. Stage A: expose/repair network menus only.
2. Stage B: optional auto-enter LAN from start screen.
3. Stage C: LAN-only PlayMpConf bypass.
4. Stage D: verify taskmachine launch flow exists before patching.
5. Stage E: keep ReturnToFreeRoam / MP_Enter_Freemode as recovery/freemode clues.
```

Keep this separate from faction-war/event resource passes.

---

## 3. Cutscene RPF and cutbin research

Found archive path:

```text
game 1.zip -> base.zip -> base/cutscene.rpf
```

`cutscene.rpf` opens cleanly as RPF6.

Files found:

```text
root/cutscene/cutscenelist.txt
root/cutscene/cutscenelist_z.txt
root/cutscene/rebel_leader_06/rebel_leader_06.cutbin
root/cutscene/rebel_leader_06/dict-0.wcdt
root/cutscene/rebel_leader_06/dict-1.wcdt
root/cutscene/rebel_leader_06/dict-2.wcdt
```

Cutscene list status:

- `cutscenelist.txt` and `cutscenelist_z.txt` decode as coordinate catalogs.
- Format is essentially:

```text
scene_name Offset: x y z
```

Recovered around 368 scene-offset rows including Rebel, FBI, Marshal, Mexico, zombie/outbreak, merchant, intro, and other mission/cutscene groups.

Cutbin status:

```text
file: rebel_leader_06.cutbin
magic/type: RBF0 / rage__cutfCutsceneFile2
objects recovered: 13
event-argument records recovered: 89
timeline/load events recovered: 142
main event time range: 0.0s to about 124.566s
```

Useful actor/prop/camera identity clues:

```text
PLAYER_cs:character_root
COMPANION_Rebel_cs:character_root
MISC_Abes_Girl_cs:character_root
p_gen_chair03x:root
p_gen_doorStandard14x:root
ExportCamera
Reyes
Marston
```

Staged object instances:

```text
PLAYER_cs-0 through PLAYER_cs-6
COMPANION_Rebel_cs-0 through COMPANION_Rebel_cs-2
MISC_Abes_Girl_cs-0 through MISC_Abes_Girl_cs-1
p_gen_chair03x-0 through p_gen_chair03x-6
p_gen_doorStandard14x-0 through p_gen_doorStandard14x-1
```

Timeline structure clues:

```text
event_id 22 / 23 = likely object show/hide or stage toggles
event_id 43      = likely camera cuts
event_id 30 / 31 = subtitle start/end pairs
event_id 28 / 29 = low-count name/audio/phase events
```

Best interpretation:

- `.cutbin` is not a free-roam population spawner.
- It is a cutscene object/event timeline that tells the game which actors, props, cameras, subtitles, and animation dictionaries to load and when to stage them.
- It is useful for actor names, staged sequence clues, and mission/cutscene correlation.
- Do not use it directly as a persistent world-spawn patch source yet.

WCDT status:

- `.wcdt` files are RSC resources with zstd payloads after a 12-byte RSC header.
- All three WCDT payloads decompressed successfully:

```text
dict-0.wcdt -> 1,220,608 bytes decoded
dict-1.wcdt -> 1,032,192 bytes decoded
dict-2.wcdt ->   712,704 bytes decoded
```

These decoded bodies are dense animation-dictionary data, not clean text yet. Current safe support is extract/decompress/fingerprint, not full animation editing.

Related content.rpf files to correlate:

```text
root/content/ui/cutscenes.sc.xml
root/content/release64/scripting/cutsceneplayer/cutsceneplayer.wsc
root/content/release64/mexico/0xDCF649E3/rebel06/rebel06.wsc
root/content/release64/0xC06BF8AB/crimeresponse/event_first_pay_cutscene.wsc
```

Recommended Code RED feature:

```text
Cutscene RPF Inspector
- read cutscenelist.txt / cutscenelist_z.txt as searchable scene tables
- parse RBF0 cutbin strings/classes/objects/event args
- export timeline CSV/JSON
- decompress WCDT RSC zstd payloads
- correlate cutscene names back to content.rpf WSC/SCO mission scripts
```

---

## 4. Territory resource research

Primary uploads checked:

```text
redemption part1.zip
territory_swall dlc.zip
mapres.zip
terrainboundres.zip
```

`redemption part1.zip` contains:

```text
territory_swall/blackwater.rpf
```

`blackwater.rpf` opens cleanly and contains:

```text
616 files
420 .wvd drawable/model resources
195 .wbd bounds/collision resources
1 .wsi sector/streaming info resource
```

`territory_swall dlc.zip` contains DLC territory chunks:

```text
dlc01x.rpf through dlc10x.rpf
```

These mostly include:

```text
.wsi  sector info resources
.wvd  drawable/model resources
.wbd  bounds/collision resources
.dlc  small plain-text bounding boxes
```

Supporting archives:

```text
mapres.rpf
- 2348 files
- 2048 .wtd
- 294 .wtx
- 6 .xlist

terrainboundres.rpf
- 5378 files
- 5376 .wtb terrain-bound chunks
- 2 validinstance text lists
```

RSC6 container layer:

- The tested W-resource files follow this pattern:

```text
RSC\x05 + 8 bytes metadata + zstd payload
```

- The zstd payload starts at byte 12.
- Code RED can decode/recompress the RSC6 zstd payload layer.

Confirmed resource families:

```text
.wsi      resource type 134
.wvd      resource type 133
.wbd      resource type 31
.wtb      resource type 36
.wtd/.wtx resource type 10
```

Fully readable/editable now:

```text
DLC boundingbox.dlc
terrainboundres validinstance_*.txt
```

Example bounding box data:

```text
-4762.667969 -1.201777 3329.937988 -2600.855713 74.738579 4743.480469
```

WSI partial decoding:

- `blackwater.wsi` contains resolved RDR name-hash references to `.wvd` and `.wbd` chunks in `blackwater.rpf`.
- A scan detected 207 resolved model/bounds hash references from 421 checked `.wvd/.wbd` base names.

Examples:

```text
blk_alleyprops01x
blk_archeologist01x
blk_bank01x
blk_generalstore01x
blackwater
```

Interpretation:

- `.wsi` is the best candidate for a real semantic editor.
- It appears to be a territory streaming/sector index connecting Blackwater chunks to world sectors.
- It includes placement-like records, names, hashes, coordinates, AABB-looking float ranges, and RAGE internal pointers.

Safe resource edit proof:

- A copy-only test was performed on `dlc03x.rpf` / `dlc03x.wsi`.
- The RSC zstd payload was decoded, one byte was changed in the decoded payload, the payload was recompressed, appended back into the copied RPF at safe alignment, TOC metadata was updated, then the RPF was reopened and the decoded bytes verified.

Critical patching rule:

```text
For RSC resources:
- preserve 12-byte RSC header
- decode/recompress zstd payload
- append relocated resource at 2048-byte alignment
- update size and offset metadata
- reopen and verify decoded payload
```

Important alignment note:

- Resource replacements need 2048-byte alignment.
- 8-byte append alignment is not enough because resource offsets encode the low byte as resource type.

Not fully solved yet:

```text
.wvd = readable/replaceable as full resource, not mesh-editable yet
.wbd = readable/replaceable as full resource, not collision-editable yet
.wtb = readable/replaceable as full resource, terrain-bound structure still needs decoding
.wsi = best semantic editor target
```

Recommended Code RED feature:

```text
Territory RPF Inspector
- RPF6 inventory and extractor
- RSC6 zstd decoder
- WSI hash resolver
- WSI sector/object CSV exporter
- safe resource replacer with 2048-byte alignment
- Magic RDR / CodeX handoff exports for visual checking
```

---

## 5. Deeper WSI structure notes

Further WSI probing showed that `.wsi` is not just a flat hash list.

It contains:

- placement-like records with world coordinates
- string pointers
- model/light names
- sector AABBs
- RAGE-style internal pointers of the form `0x50000000 + offset`

Practical decode direction:

```text
WSI Explorer v1
- identify payload strings
- identify 0x50000000 pointer fields
- resolve pointer targets to strings or record blocks
- identify vec3/vec4 coordinate candidates
- correlate hash fields to WVD/WBD base names
- export candidate placement rows
```

Safe edit direction:

```text
Start with coordinate-only edits and controlled hash swaps.
Do not attempt full WVD/WBD geometry mutation until structure is understood.
```

---

## 6. RAGE-StringsDatabase / hash resolver notes

Source reviewed:

```text
https://github.com/OpenIV-Team/RAGE-StringsDatabase
```

Usefulness:

- Valuable as a hash/name resolver for RAGE/JOOAT-style names.
- Not a model editor.
- Useful to label unknown WSI/WVD/WBD/WSC references.

Local JOOAT verification examples:

```text
dlc03x                  -> 0xA79C05A9
dlc_placeholder03x      -> 0xA061A1D0
blackwater              -> 0x3EC4B1F5
day_fill_bounce_05Shape -> 0xCE85561D
blk_bank01x             -> 0x4B8FAB27
```

Result:

- The WSI hashes match the expected lowercase RAGE/JOOAT-style path.
- Code RED should import string databases, hash every candidate, then build a `hash32 -> name` map for WSI/WVD/WBD/WSC analysis.

Recommended Code RED feature:

```text
RAGE String DB Importer
- import OpenIV/RAGE-StringsDatabase style text files
- normalize names
- compute JOOAT/hash32
- merge with local RPF file basenames
- label unknown hashes in WSI and script/resource scans
- cache hash maps in the workspace
```

---

## 7. GTA/RDR2 tool mapping notes

The user's W-to-Y comparison is directionally correct, but rename-only conversion is not enough.

Conceptual mapping:

```text
.wvd       -> .ydr-like drawable/model
.wbd       -> .ybn-like bounds/collision
.wtd/.wtx  -> .ytd-like texture dictionary/texture
.wcdt      -> .ycd-like animation/clip dictionary
.wsi       -> ymap-like sector/streaming/map-placement data
```

Why simple renaming fails:

- RDR1 files are still RPF6/RSC6 W-resources.
- GTA V tools expect GTA V Y-resource container/type/structure details.
- Renaming `.wvd` to `.ydr` or `.wbd` to `.ybn` does not change the internal RDR1 resource type or payload layout.

Best use of GTA/RDR2 tools:

```text
Use as conceptual references for record names and structures.
Use Magic RDR for visual proof where possible.
Use Code RED for RDR1-specific RPF6/RSC6 decode/patch operations.
```

---

## 8. ClosedIV notes

Source reviewed:

```text
https://github.com/martonp96/ClosedIV
```

ClosedIV is useful for the runtime override/loading layer, not for WSI/WVD/WBD semantic decoding.

What it is:

- Archived open-source alternative to OpenIV.asi for GTA V.
- Redirects file reads so modded files in a mods folder can override original game files.
- Not a `.wsi`, `.wvd`, `.wbd`, `.wtd`, or `.wtb` parser/editor.

Useful design idea:

```text
Runtime/loose-file override model
- check mods/<requested path> first
- if a modded file exists, load it
- otherwise fall back to the original file
- log which path was used
```

For Code RED territory work:

```text
Code RED Territory Lab
1. Decode/edit RDR1 WSI/WVD/WBD resources offline.
2. Repack or export only changed resources.
3. Generate a mods-folder style mirror if a loader path is ever available.
4. Add logging so users can see exactly which modded file is being used.
5. Avoid touching original archives.
```

Recommended Code RED feature:

```text
Virtual Override Manifest
original: territory_swall/blackwater.rpf/root/blackwater.wsi
patched:  exports/territory_patch/root/blackwater.wsi
status:   decoded, recompressed, 2048-aligned, verified
```

---

## 9. CodeX.Games.RDR1 notes

Source reviewed:

```text
https://github.com/Foxxyyy/CodeX.Games.RDR1
```

The repo is described as a research project for Red Dead Redemption intended to be used with CodeX.

Important repo structure observed:

```text
Files/
Prefabs/
RPF6/
RSC6/
CodeX.Games.RDR1.mapstates.txt
CodeX.Games.RDR1.shaders.xml
CodeX.Games.RDR1.strings.txt
RDR1Game.cs
RDR1Map.cs
RDR1Prefabs.cs
```

Major match to our current territory work:

- CodeX.Games.RDR1 already implements an RDR1 map/streaming view concept.
- `RDR1Map.cs` loads WSI files from RPF6 stream entries, creates `RDR1MapNode` instances, registers sectors by hash, loads terrain tiles, then streams WSI entities, terrain bounds, terrain visuals, trees, and grass around the current stream position.
- It includes an `EnableWSI <wsiname> <false/disable/0>` command that attempts to replicate `ENABLE_WORLD_SECTOR` / `DISABLE_WORLD_SECTOR` and child sector toggles.
- It uses named start positions for major RDR1 locations, including Blackwater, Armadillo, Chuparosa, Fort Mercer, Thieve's Landing, Tumbleweed, etc.

Important CodeX WSI implementation details:

```text
Files/WsiFile.cs
- WsiFile wraps Rsc6SectorInfo.
- Load uses Rsc6DataReader at e.FlagInfos.RSC85_ObjectStart + VIRTUAL_BASE.
- Save writes SectorInfo and builds resource type 134.
```

This confirms our resource type finding:

```text
.wsi = RSC6 resource type 134
```

Important `Rsc6SectorInfo` details from CodeX:

```text
Rsc6SectorInfo // sagSectorInfo
BlockLength = 480
VFT = 0x01909C38
Name
PropsGroup
ScopedNameHash
CurveArrays[24]
MinAndBoundingRadius
MaxAndInscribedRadius
BoundMin
BoundMax
PlacedLightsGroup
Props / Rsc6PropInstanceInfo
DoorsAttributes
Children
ChildGroup / Rsc6ScopedSectors
ChildPtrs
DrawableInstances
DrawableInstances2
Portals
Attributes
VisualDictionary
MedVisualDictionary
VLowVisualDictionary
BoundDictionary
NameHash
Occluders
PropNames
Locators
Scope
District
Flags
BoundInstances
NamedNodeMap
```

This gives Code RED a real semantic target for WSI editing instead of blind pointer scanning.

Best Code RED implementation change after this discovery:

```text
Port/translate the CodeX WSI reader shape into Python:
1. RSC6 reader with virtual pointer support.
2. Rsc6SectorInfo class, 480-byte root block.
3. Pointer array and managed array readers.
4. Sector hierarchy export: roots, children, child group, child pointers.
5. Entity export: props, drawable instances, locators, portals, bounds.
6. Safe XML/JSON export matching CodeX field names.
7. Coordinate-only and sector-enable patch lanes first.
```

Most useful fields to expose first:

```text
Name / Scope / NameHash / ScopedNameHash
BoundMin / BoundMax
Props
DrawableInstances
PropNames
Locators
Children / ChildGroup / ChildPtrs
VisualDictionary / BoundDictionary names
Flags / District / ResidentStatus
```

This should be prioritized above blind WSI heuristics.

Relevant CodeX release clues:

- Release 026.7 mentions PC support, terrain collisions rendered in the map viewer, map states and Undead assets load/unload in the viewer, a command to load/unload sectors, particle viewing, and continued research on `#si` resources.
- Release 027.1 mentions navmesh early work, proper terrain tinting, vertex normal/lighting fixes, flash UI research, and TODO editing support for WSF/WFT.
- Release 028.1 mentions research for gringos/navmesh and fixes for drawables/fragments.
- Release 028.2 mentions STRTBL/WST string editing being displayed/editable as plain text and manually reimported into RPF.
- Release 029.1 updates the project to CodeX 029.

Implication:

- CodeX.Games.RDR1 is the most directly useful technical reference found so far for WSI, terrain, map state, collision, and world streaming.
- Magic RDR remains better as a readily available RPF/editor/viewer reference.
- Code RED should not attempt a W-to-Y rename converter before implementing real RSC6/WSI semantics.

---

## 10. RDR-Script-Decompiler notes

Source reviewed:

```text
https://github.com/Foxxyyy/RDR-Script-Decompiler
```

Repo README summary:

- It is marked outdated and says to use MagicRDR.
- It decompiles XSC scripts from RDR1.
- SCO files are not supported.
- Scripts must be decompressed first with a third-party tool such as AreDeAre xPlorer.

Code RED implication:

```text
Do not build future script work around this as the primary path.
Use it only as a historical reference for XSC script expectations.
Keep the active Code RED script lane centered on:
- Magic RDR script viewer/decompiler behavior
- Code RED's own WSC/SCO string/native-table recovery
- decompressed script payload handling
- separate WSC/XSC/SCO detection
```

For our current scripts:

- `content.rpf` contains many `.wsc` and `.sco` files.
- This decompiler does not solve `.sco` and is not a full current-version workflow.
- It reinforces the need to separate raw resource decompression from script bytecode interpretation.

---

## 11. Updated implementation priority for Code RED

Recommended order after checking these resources:

```text
1. Add RAGE String DB Importer.
2. Add reusable RSC6 zstd/resource reader-writer.
3. Port/translate CodeX WSI reader shape into Python.
4. Add Territory RPF Inspector.
5. Add WSI Explorer with sector hierarchy, props, drawables, locators, bounds, and hash/name export.
6. Add safe WSI coordinate-only patching.
7. Add safe full-resource replacement with 2048-byte alignment verification.
8. Add Cutscene RPF Inspector.
9. Add MP SCXML Analyzer.
10. Add optional MP LAN-only PlayMpConf experiment.
11. Keep WVD/WBD mesh/collision editing as later work.
12. Keep script decompile work focused on WSC/SCO native/string recovery first.
```

Risk rules:

```text
Do not pretend WVD/WBD are fully editable yet.
Do not bulk-merge donor MP files.
Do not patch Public/Private multiplayer auth globally before proving LAN flow.
Do not use cutbin as persistent world spawning until script/runtime launch logic is found.
Do not rely on extension renames such as WVD->YDR as a real converter.
Do not use outdated RDR-Script-Decompiler as the main future script path.
```

Best practical targets:

```text
WSI semantic decode/export/edit
RAGE hash/name resolution
safe RSC6 replacement
cutscene timeline inspection
MP UI/state-machine diffing
WSC/SCO script clue recovery
```
