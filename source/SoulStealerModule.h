#pragma once
#include "NativeBridge.h"
#include "PossessionController.h"
#include "SoulStealerConfig.h"
#include "TargetSelector.h"
#include <string>

namespace codered {

class SoulStealerModule {
public:
    enum class State {
        Idle,
        Armed,
        Possessing,
        ProbeOnly,
    };

    SoulStealerModule(INativeBridge& bridge, SoulStealerConfig config = {});

    void setConfig(SoulStealerConfig config);
    SoulStealerConfig config() const { return config_; }

    void toggleArmed();
    bool arm();
    bool captureBestTarget();
    bool captureActor(ActorHandle actor);
    bool cancel();
    void tick();

    State state() const { return state_; }
    ActorHandle targetActor() const { return possession_.targetActor(); }
    PossessionStatus possessionStatus() const { return possession_.status(); }
    std::string debugStatus() const;

private:
    INativeBridge& bridge_;
    SoulStealerConfig config_;
    TargetSelector selector_;
    PossessionController possession_;
    State state_ = State::Idle;

    void rebuildHelpers();
};

const char* toString(SoulStealerModule::State state);

} // namespace codered
