# Compile / Integration Notes

This package compiles as a standalone C++17 mock test on Linux/macOS/Windows, but the actual `.asi` needs the user's local Windows Code RED ScriptHook/native-invoker project.

## Mock compile

```powershell
cd source
cmake -S . -B build
cmake --build build --config Release
.\build\Release\soul_stealer_mock_test.exe
```

or with g++ directly:

```bash
g++ -std=c++17 -I source \
  source/SoulStealerConfig.cpp \
  source/TargetSelector.cpp \
  source/PossessionController.cpp \
  source/SoulStealerModule.cpp \
  source/MockNativeBridge.cpp \
  mock_tests/mock_console_test.cpp \
  -o soul_stealer_mock_test
```

## ASI integration

Add these files to the local Code RED ASI/trainer project:

- `source/NativeBridge.h`
- `source/SoulStealerConfig.h/.cpp`
- `source/TargetSelector.h/.cpp`
- `source/PossessionController.h/.cpp`
- `source/SoulStealerModule.h/.cpp`

Then implement the real bridge using:

- `integration/CodeRED_ASI_Integration_TODO.cpp`

Do not compile `MockNativeBridge.*` into the final ASI unless the project wants built-in debug tests.
