# Code RED Soul Stealer Reconstruction Pass 4

This package extends the clean PC Soul Stealer reconstruction scaffold with:

- teleport slot tools
- actor teleport helpers
- remote player map/radar blip scaffolding
- remote puppet controller scaffolding
- mock tests for teleport/blip behavior

It is not a direct port of the old console trainer. It is a clean PC-side reconstruction scaffold for Code RED.

## Build mock tests

```bat
cd source
cmake -S . -B ..\build
cmake --build ..\build
..\build\soul_stealer_mock_test.exe
..\build\soul_stealer_runtime_test.exe
..\build\soul_stealer_pass4_test.exe
```

## Next local/Codex work

Wire `INativeBridge` to the real Code RED/RDR native invoker and compile the Windows ASI.
