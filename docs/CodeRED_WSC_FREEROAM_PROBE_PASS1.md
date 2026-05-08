# Code RED WSC Freeroam Probe Pass 1

Pass 1 uses the source-first WSC edit lane against the current launch archive:

`D:\Games\Red Dead Redemption\game\content.rpf`

Launch archive SHA1 observed during this pass:

`8F46569AFF45CC162711C879A2C14F53FE06DC37`

## Candidate Ranking

The launch archive inventoried cleanly:

- Entries: `1636`
- Files: `1320`
- Resolved names: `1636`
- WSC files: `886`

Ranking outputs:

- `logs\wsc_freeroam_probe_pass1\wsc_candidate_rank.json`
- `logs\wsc_freeroam_probe_pass1\wsc_candidate_rank.md`

## Built Probe Archives

Each probe is a separate copied `content.rpf` with one WSC replacement. None of these outputs are written into the live game folder.

| Probe | Replaced WSC | Copied RPF |
|---|---|---|
| `probe_initpopulation` | `root/content/release64/init/initpopulation.wsc` | `build\wsc_freeroam_probe_pass1\probe_initpopulation\packed\content.rpf` |
| `probe_rdr2init_each_load` | `root/content/release64/init/rdr2init_each_load.wsc` | `build\wsc_freeroam_probe_pass1\probe_rdr2init_each_load\packed\content.rpf` |
| `probe_long_update_thread` | `root/content/release64/scripting/designerdefined/long_update_thread.wsc` | `build\wsc_freeroam_probe_pass1\probe_long_update_thread\packed\content.rpf` |
| `probe_medium_update_thread` | `root/content/release64/scripting/designerdefined/medium_update_thread.wsc` | `build\wsc_freeroam_probe_pass1\probe_medium_update_thread\packed\content.rpf` |
| `probe_sc_mp_challenge_wrapper` | `root/content/release64/scripting/designerdefined/socialclub/multiplayer/actionareas/sc_mp_aa_challenge_wrapper.wsc` | `build\wsc_freeroam_probe_pass1\probe_sc_mp_challenge_wrapper\packed\content.rpf` |

## Verification

Every packed archive was inventoried, the replaced WSC was extracted, and the extracted WSC hash matched the compiled WSC hash.

Compiled/extracted probe WSC SHA1:

`0806E5B49EACA462E10CFDFCF73C85CB977D260A`

Verification output:

`logs\wsc_freeroam_probe_pass1\probe_verify_results.json`

## Runtime Use

These are not installed automatically. Test one copied RPF at a time through the game loader/override path being used for manual runtime testing. If a probe changes the loading-screen behavior, the replaced WSC is on the path to the failing handoff.
