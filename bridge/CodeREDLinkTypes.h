#pragma once
#include "../source/NativeBridge.h"
#include "../source/RemotePuppetBlip.h"
#include <cstdint>
#include <string>

namespace codered_link {

struct RemoteFlags {
    bool running = false;
    bool aiming = false;
    bool shooting = false;
    bool mounted = false;
    bool inVehicle = false;
};

struct RemotePlayerState {
    std::string playerId;
    std::string displayName;
    std::uint64_t timestampMs = 0;
    codered::Vec3 position{};
    float heading = 0.0f;
    float speed = 0.0f;
    RemoteFlags flags{};
    std::string chat;
};

inline codered::RemotePuppetState toPuppetState(const RemotePlayerState& state) {
    codered::RemotePuppetState out;
    out.playerId = state.playerId;
    out.displayName = state.displayName;
    out.timestampMs = state.timestampMs;
    out.pos = state.position;
    out.heading = state.heading;
    out.active = !state.playerId.empty();
    return out;
}

} // namespace codered_link
