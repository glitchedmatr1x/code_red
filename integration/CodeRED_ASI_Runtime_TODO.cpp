// Code RED Soul Stealer Pass 3 runtime integration sketch.
// This is intentionally not compiled here because the real Windows ASI build needs
// the local Code RED ScriptHook/native-invoker headers and project layout.

#include "../source/SoulStealerRuntime.h"

namespace codered_integration_todo {

class Win32InputBridge final : public codered::IInputBridge {
public:
    bool wasKeyPressed(std::uint32_t vkCode) override {
        // TODO: edge-detect GetAsyncKeyState(vkCode) or use Code RED's input helper.
        // Return true only on the transition from up -> down.
        (void)vkCode;
        return false;
    }
    bool isKeyDown(std::uint32_t vkCode) override {
        // TODO: return (GetAsyncKeyState(vkCode) & 0x8000) != 0.
        (void)vkCode;
        return false;
    }
};

// RdrNativeBridge should be copied from CodeRED_ASI_Integration_TODO.cpp and wired
// to the real native invoker.
class RdrNativeBridge; // implemented in the local ASI project.

// Example plugin-level state once RdrNativeBridge exists:
// static RdrNativeBridge g_native;
// static Win32InputBridge g_input;
// static codered::SoulStealerConfig g_config;
// static codered::SoulStealerRuntime g_runtime(g_native, g_input, g_config);

void OnPluginInit() {
    // TODO:
    // - load Code_RED/config/SoulStealerConfig.json
    // - create logs directory
    // - g_runtime.openLogFile("Code_RED/logs/soul_stealer.log")
    // - show boot message once
}

void OnPluginTick() {
    // TODO:
    // g_runtime.tick();
}

void OnPluginShutdown() {
    // TODO:
    // g_runtime.module().cancel();
}

} // namespace codered_integration_todo
