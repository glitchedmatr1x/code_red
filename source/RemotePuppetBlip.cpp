#include "RemotePuppetBlip.h"

namespace codered {

RemotePuppetBlip::RemotePuppetBlip(INativeBridge& bridge) : bridge_(bridge) {}
RemotePuppetBlip::~RemotePuppetBlip() { remove(); }

bool RemotePuppetBlip::update(const RemotePuppetState& state) {
    if (!state.active) return remove();
    const std::string label = state.displayName.empty() ? "Remote Player" : state.displayName;
    if (blip_ == 0) {
        blip_ = bridge_.createCoordBlip(state.pos, label, /*icon*/0, /*color*/2);
        if (blip_ == 0) return false;
    }
    bridge_.setBlipLabel(blip_, label);
    bool ok = bridge_.updateCoordBlip(blip_, state.pos, state.heading);
    if (ok) last_ = state;
    return ok;
}

bool RemotePuppetBlip::remove() {
    if (blip_ == 0) return true;
    bool ok = bridge_.removeBlip(blip_);
    if (ok) blip_ = 0;
    return ok;
}

} // namespace codered
