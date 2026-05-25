# XSC/CSC XCompress Feasibility

This probe does not modify donor files and does not fake conversion by extension rename.

## XCompress Runtime

- `D:\Games\Red Dead Redemption\Code_RED\script_compiling\sccl\output\xcompress32.dll`
  - exists: `True`
  - status: `bitness_mismatch_32bit_dll`
  - load_error: `[WinError 193] %1 is not a valid Win32 application`
- `D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL-master\bin\xcompress32.dll`
  - exists: `False`
  - status: `missing`
  - load_error: ``
- `D:\Games\Red Dead Redemption\SC-CL-master\bin\xcompress32.dll`
  - exists: `False`
  - status: `missing`
  - load_error: ``

## Conversion Status

- `still_blocked`: `101`

## Pass 1 Decision

XSC/CSC conversion remains blocked unless a loadable XCompress bridge with validated signatures is available. The safe build lane for this pass is source-required authoring through SC-CL RDR_SCO plus PC RSC85 wrapping/repack validation.
