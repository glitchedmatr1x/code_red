#pragma once
#include "NativeBridge.h"
#include "SoulStealerConfig.h"
#include <optional>

namespace codered {

struct TargetResult {
    ActorHandle actor = 0;
    std::string source;
    std::string rejectedReason;
};

class TargetSelector {
public:
    TargetSelector(INativeBridge& bridge, SoulStealerConfig config);

    void setConfig(SoulStealerConfig config) { config_ = config; }
    TargetResult selectTarget();
    bool isValidTarget(ActorHandle actor, std::string* reason = nullptr) const;

private:
    INativeBridge& bridge_;
    SoulStealerConfig config_;

    TargetResult tryReticle() const;
    TargetResult tryLastDamaged() const;
    TargetResult tryNearestForward() const;
    TargetResult tryNearestRadius() const;
    TargetResult targetIfValid(ActorHandle actor, const std::string& source) const;
    bool inForwardCone(const Vec3& playerPos, float playerHeading, const Vec3& targetPos) const;
};

} // namespace codered
