# Code RED MP LAN Fallback Pretest

Date: 2026-05-07

## Purpose

Prepare candidate-only LAN/System Link SCXML changes before any RPF build or install.

## Tools

- `tools\codered_mp_lan_fallback_candidate.py`
  - Generates decoded XML candidate copies.
  - Generates unified diffs.
  - Validates candidate scope.
  - Zstandard encodes, decodes, and hashes the candidate XML.
  - Maps decoded file names back to real archive paths.
- `tools\codered_mp_lan_fallback_rpf_builder.py`
  - Dry-run is default.
  - Reports exact `content.rpf` entries that would be replaced.
  - Does not build or install an RPF.
  - Provides optional `--verify-built` checks for a future copied test RPF.

## Approved Candidate Targets

- `root/content/ui/pausemenu/net/lanmenu.sc.xml`
- `root/content/ui/pausemenu/net/plaympconf.sc.xml`

No online/profile/netstats/Gamespy files are candidate targets.

## Generated Local Outputs

These are intentionally generated under ignored log/build locations:

- `logs\content_mp_lan_fallback_candidate\candidate_summary.json`
- `logs\content_mp_lan_fallback_candidate\LAN_FALLBACK_CANDIDATE_REPORT.md`
- `logs\content_mp_lan_fallback_candidate\candidate_diffs\`
- `logs\content_mp_lan_fallback_candidate\decoded_candidates\`
- `logs\content_mp_lan_fallback_candidate\zstd_encoded\`
- `logs\content_mp_lan_fallback_candidate\zstd_roundtrip_report.json`
- `logs\content_mp_lan_fallback_candidate\rpf_builder_dryrun_report.json`
- `logs\content_mp_lan_fallback_candidate\RPF_TEST_PREP_REPORT.md`

## Validation Result

The candidate validator passed:

- only the two approved files changed
- no online/profile/netstats/Gamespy files changed
- `NetMachine.Authenticate` calls were not globally removed
- `NetMachine.ShowSignInUI` calls were not globally removed
- `NetMachine.TriggerMultiplayerLoad(arg2)` remains present
- `arg2` reference count did not change
- Zstandard encode/decode round trip passed

## Dry-Run RPF Result

Dry-run replacement map passed:

- `root/content/ui/pausemenu/net/lanmenu.sc.xml`
  - entry index `235`
  - compressed file entry
- `root/content/ui/pausemenu/net/plaympconf.sc.xml`
  - entry index `234`
  - compressed file entry

The dry-run did not write `content.rpf`.

## Important Warning

The current source `D:\Games\Red Dead Redemption\game\content.rpf` dry-run inventory reports no multiplayer `.csc` entries, and these required entries are missing there:

- `root/content/release/multiplayer/freemode/freemode.csc`
- `root/content/release64/multiplayer/freemode/freemode.csc`

That means the first full RPF test archive must be based on the MP-content candidate/injected archive or another content RPF that already has the MP CSC tree. The post-build verification gate should fail if those entries are absent.

## Test Prep Paths

- backup: `D:\Games\Red Dead Redemption\game\content.rpf`
- candidate: `D:\Games\Red Dead Redemption\Code_RED\build\content_mp_lan_fallback_test\content.rpf`
- install target: `D:\Games\Red Dead Redemption\game\content.rpf`

No auto-copy or install is allowed in this lane.

## First RPF Test Questions

- Does the game boot?
- Does the pause menu still open?
- Does LAN/System Link route show or behave differently?
- Does it reach loading/MP transition or fail at a later runtime state?
