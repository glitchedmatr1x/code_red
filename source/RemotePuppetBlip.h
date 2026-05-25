#pragma once
#include "NativeBridge.h"
#include <cstdint>
#include <string>

namespace codered {

struct RemotePuppetState {
    std::string playerId;
    std::string displayName;
    Vec3 pos{};
    float heading = 0.0f;
    std::uint64_t timestampMs = 0;
    bool active = false;
};

class RemotePuppetBlip {
public:
    explicit RemotePuppetBlip(INativeBridge& bridge);
    ~RemotePuppetBlip();

    bool update(const RemotePuppetState& state);
    bool remove();
    bool isActive() const { return blip_ != 0; }
    BlipHandle handle() const { return blip_; }
    RemotePuppetState lastState() const { return last_; }

private:
    INativeBridge& bridge_;
    BlipHandle blip_ = 0;
    RemotePuppetState last_{};
};

} // namespace codered
