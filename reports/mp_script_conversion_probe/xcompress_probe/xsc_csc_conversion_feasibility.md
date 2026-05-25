# XSC/CSC XCompress Feasibility

This probe does not modify donor files and does not fake conversion by extension rename.

## XCompress Runtime

- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\bin\xcompress32.dll`
  - exists: `True`
  - status: `bitness_mismatch_32bit_dll`
  - load_error: `[WinError 193] %1 is not a valid Win32 application`
- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\bin\Release\xcompress32.dll`
  - exists: `True`
  - status: `bitness_mismatch_32bit_dll`
  - load_error: `[WinError 193] %1 is not a valid Win32 application`
- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\bin\xcompress32.dll`
  - exists: `True`
  - status: `bitness_mismatch_32bit_dll`
  - load_error: `[WinError 193] %1 is not a valid Win32 application`
- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\bin\Release\xcompress32.dll`
  - exists: `True`
  - status: `bitness_mismatch_32bit_dll`
  - load_error: `[WinError 193] %1 is not a valid Win32 application`
- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\lib\xcompress64.lib`
  - exists: `True`
  - status: `static_or_import_library_needs_native_bridge`
  - load_error: `not a DLL; link this from a small native bridge executable or DLL`
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
