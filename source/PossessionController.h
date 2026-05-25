#pragma once
#include "NativeBridge.h"
#include "SoulStealerConfig.h"
#include <string>

namespace codered {

enum class PossessionStatus {
    None,
    ProbeOnly,
    RealSwap,
    FallbackModelTeleport,
};

struct PossessionAttemptResult {
    bool ok = false;
    PossessionStatus status = PossessionStatus::None;
    std::string message;
};

class PossessionController {
public:
    PossessionController(INativeBridge& bridge, SoulStealerConfig config);

    void setConfig(SoulStealerConfig config);
    PossessionAttemptResult possess(ActorHandle target);
    bool cancel();
    bool isPossessing() const { return status_ != PossessionStatus::None && status_ != PossessionStatus::ProbeOnly; }
    PossessionStatus status() const { return status_; }
    ActorHandle targetActor() const { return target_.actor; }
    ActorSnapshot originalPlayer() const { return original_; }
    ActorSnapshot targetSnapshot() const { return target_; }

private:
    INativeBridge& bridge_;
    SoulStealerConfig config_;
    PossessionStatus status_ = PossessionStatus::None;
    ActorSnapshot original_{};
    ActorSnapshot target_{};

    ActorSnapshot snapshot(ActorHandle actor);
    PossessionAttemptResult tryRealSwap(ActorHandle target);
    PossessionAttemptResult tryFallback(ActorHandle target);
    void reset();
};

const char* toString(PossessionStatus status);

} // namespace codered
