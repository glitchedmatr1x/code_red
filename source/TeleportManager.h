#pragma once
#include "NativeBridge.h"
#include <array>
#include <string>

namespace codered {

struct TeleportSlot {
    bool valid = false;
    Vec3 pos{};
    float heading = 0.0f;
    std::string label;
};

class TeleportManager {
public:
    explicit TeleportManager(INativeBridge& bridge);

    bool savePlayerSlot(int slot, const std::string& label = {});
    bool teleportPlayerToSlot(int slot);
    bool teleportPlayerTo(Vec3 pos, float heading, const std::string& reason = {});
    bool teleportPlayerToActor(ActorHandle actor);
    bool teleportActorTo(ActorHandle actor, Vec3 pos, float heading);
    bool teleportActorToPlayer(ActorHandle actor, float behindDistance = 2.0f);

    const TeleportSlot* slot(int slot) const;
    std::string debugSlots() const;

private:
    INativeBridge& bridge_;
    std::array<TeleportSlot, 10> slots_{};
};

} // namespace codered
