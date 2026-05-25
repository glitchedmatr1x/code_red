#pragma once
#include "DebugOverlay.h"
#include "HotkeyController.h"
#include "RuntimeLogger.h"
#include "SoulStealerModule.h"
#include "TeleportManager.h"
#include "RemotePuppetController.h"
#include <string>

namespace codered {

class SoulStealerRuntime {
public:
    SoulStealerRuntime(INativeBridge& bridge, IInputBridge& input, SoulStealerConfig config = {});

    void setConfig(SoulStealerConfig config);
    SoulStealerConfig config() const { return config_; }
    void openLogFile(const std::string& path);
    void tick();
    SoulStealerModule& module() { return module_; }
    const SoulStealerModule& module() const { return module_; }
    RuntimeLogger& logger() { return logger_; }
    TeleportManager& teleports() { return teleports_; }
    RemotePuppetController& remotePuppet() { return remotePuppet_; }

private:
    INativeBridge& bridge_;
    IInputBridge& input_;
    SoulStealerConfig config_;
    SoulStealerModule module_;
    HotkeyController hotkeys_;
    RuntimeLogger logger_;
    DebugOverlay overlay_;
    TeleportManager teleports_;
    RemotePuppetController remotePuppet_;

    void handleCommands(const RuntimeCommands& cmd);
};

} // namespace codered
