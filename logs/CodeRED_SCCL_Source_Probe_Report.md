# Code RED SC-CL Source Probe Report

Generated UTC: `2026-05-03T12:03:26Z`
RDR-ready source detected: **True**
SC-CL.exe detected: `None`
Best source: `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master`

## Candidates

### `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master`
- exists: `True`
- score: `21`
- exe_found: `None`
- readme: `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\readme.md`
- markers: `README.md, llvm-14.0.0.src, include`
- rdr_tokens: `Red Dead Redemption, RDR_SCO, RDR_#SC, SCO format, XSC format, CSC format`

### `D:\Games\Red Dead Redemption\Code_RED\SC-CL`
- exists: `False`
- score: `0`
- exe_found: `None`
- readme: `None`
- markers: ``
- rdr_tokens: ``

### `D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL-master`
- exists: `False`
- score: `0`
- exe_found: `None`
- readme: `None`
- markers: ``
- rdr_tokens: ``

### `D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL`
- exists: `False`
- score: `0`
- exe_found: `None`
- readme: `None`
- markers: ``
- rdr_tokens: ``

### `D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\SC-CL-master`
- exists: `False`
- score: `0`
- exe_found: `None`
- readme: `None`
- markers: ``
- rdr_tokens: ``

### `D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\SC-CL`
- exists: `False`
- score: `0`
- exe_found: `None`
- readme: `None`
- markers: ``
- rdr_tokens: ``

## Next Steps

- This appears to be the right SC-CL source family for RDR, but no SC-CL.exe was found.
- Build SC-CL from this source or obtain its Windows executable, then place SC-CL.exe in resources\SC-CL_DROP_HERE.
- Run: py -3 tools\codered_sccl_easy_setup.py adopt --sccl resources\SC-CL_DROP_HERE\SC-CL.exe --run-validator
