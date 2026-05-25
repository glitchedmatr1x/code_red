# WSC Authoring Pass 1

This pass builds minimal local/offline script resources only. It does not spoof public servers, patch matchmaking, or overwrite game archives.

- Template PC WSC: `D:\Games\Red Dead Redemption\Code_RED\game\content_extracted\release64\scripting\designerdefined\short_update_thread.wsc`
- RDR.exe for AES key: `D:\Games\Red Dead Redemption\RDR.exe`
- Build folder: `build\wsc_authoring_pass1`
- Validated WSC outputs: `2/2`

## Outputs

### hello_bootstrap
- status: `generated_wsc_validated`
- output: `build\wsc_authoring_pass1\hello_bootstrap.wsc`
- decoded matches SCO: `True`
- inspect reopen ok: `True`
- repack reopen ok: `True`
- runtime status: `not_game_runtime_proven`

### codered_mp_bootstrap_minimal
- status: `generated_wsc_validated`
- output: `build\wsc_authoring_pass1\codered_mp_bootstrap_minimal.wsc`
- decoded matches SCO: `True`
- inspect reopen ok: `True`
- repack reopen ok: `True`
- runtime status: `not_game_runtime_proven`

## Boundary

These WSC files are valid Code RED-decodable PC RSC85 resources containing SC-CL RDR_SCO decoded payloads. That proves authoring, wrapping, inspect, and repack. It does not prove the game runtime will execute the SCO payload from a WSC path until imported and tested.
