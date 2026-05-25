#pragma once
#include "NativeBridge.h"
#include <string>

namespace codered {

class DebugOverlay {
public:
    DebugOverlay(INativeBridge& bridge);
    void showStatus(const std::string& text);
    void showTransient(const std::string& text);
    void setEnabled(bool enabled) { enabled_ = enabled; }
    bool enabled() const { return enabled_; }

private:
    INativeBridge& bridge_;
    bool enabled_ = true;
};

} // namespace codered
