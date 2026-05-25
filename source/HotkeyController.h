#pragma once
#include "SoulStealerConfig.h"
#include <cstdint>

namespace codered {

class IInputBridge {
public:
    virtual ~IInputBridge() = default;
    virtual bool wasKeyPressed(std::uint32_t vkCode) = 0;
    virtual bool isKeyDown(std::uint32_t vkCode) = 0;
};

struct RuntimeCommands {
    bool toggleArmed = false;
    bool capture = false;
    bool cancel = false;
    bool reloadConfig = false;
    bool dumpDebug = false;
    bool saveTeleportSlot0 = false;
    bool loadTeleportSlot0 = false;
    bool teleportControlledActorToPlayer = false;
};

class HotkeyController {
public:
    HotkeyController(IInputBridge& input, SoulStealerConfig config);
    void setConfig(SoulStealerConfig config);
    RuntimeCommands poll();

private:
    IInputBridge& input_;
    SoulStealerConfig config_;
};

} // namespace codered
