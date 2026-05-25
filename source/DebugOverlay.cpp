#include "DebugOverlay.h"

namespace codered {

DebugOverlay::DebugOverlay(INativeBridge& bridge) : bridge_(bridge) {}

void DebugOverlay::showStatus(const std::string& text) {
    if (!enabled_) return;
    bridge_.showMessage(text);
}

void DebugOverlay::showTransient(const std::string& text) {
    if (!enabled_) return;
    bridge_.showMessage(text);
}

} // namespace codered
