#include "SoulStealerModule.h"
#include <sstream>

namespace codered {

const char* toString(SoulStealerModule::State state) {
    switch (state) {
        case SoulStealerModule::State::Idle: return "Idle";
        case SoulStealerModule::State::Armed: return "Armed";
        case SoulStealerModule::State::Possessing: return "Possessing";
        case SoulStealerModule::State::ProbeOnly: return "ProbeOnly";
    }
    return "Unknown";
}

SoulStealerModule::SoulStealerModule(INativeBridge& bridge, SoulStealerConfig config)
    : bridge_(bridge), config_(config), selector_(bridge, config), possession_(bridge, config) {}

void SoulStealerModule::setConfig(SoulStealerConfig config) {
    if (state_ != State::Idle) {
        bridge_.log("Soul Stealer: config change requested while active; canceling first");
        cancel();
    }
    config_ = config;
    rebuildHelpers();
}

void SoulStealerModule::rebuildHelpers() {
    selector_.setConfig(config_);
    possession_.setConfig(config_);
}

bool SoulStealerModule::arm() {
    if (state_ == State::Possessing || state_ == State::ProbeOnly) {
        bridge_.showMessage("Soul Stealer is already active");
        return false;
    }
    state_ = State::Armed;
    bridge_.showMessage("Soul Stealer armed - target an NPC");
    if (config_.debugLogging) {
        bridge_.log(std::string("Soul Stealer armed. targetMode=") + toString(config_.targetMode) +
                    " possessionMode=" + toString(config_.possessionMode));
    }
    return true;
}

void SoulStealerModule::toggleArmed() {
    if (state_ == State::Idle) {
        arm();
    } else {
        cancel();
    }
}

bool SoulStealerModule::captureBestTarget() {
    TargetResult target = selector_.selectTarget();
    if (!target.actor) {
        bridge_.showMessage("Soul Stealer: no valid actor");
        if (config_.debugLogging) bridge_.log("Soul Stealer target failed: " + target.source + " " + target.rejectedReason);
        return false;
    }
    if (config_.debugLogging) {
        std::ostringstream oss;
        oss << "Soul Stealer selected actor 0x" << std::hex << target.actor << " via " << target.source;
        bridge_.log(oss.str());
    }
    return captureActor(target.actor);
}

bool SoulStealerModule::captureActor(ActorHandle actor) {
    if (state_ != State::Armed) {
        bridge_.showMessage("Soul Stealer is not armed");
        return false;
    }

    std::string reason;
    if (!selector_.isValidTarget(actor, &reason)) {
        bridge_.showMessage("Soul Stealer: invalid target");
        if (config_.debugLogging) bridge_.log("Soul Stealer rejected actor: " + reason);
        return false;
    }

    PossessionAttemptResult result = possession_.possess(actor);
    if (!result.ok) {
        bridge_.showMessage("Soul Stealer failed");
        if (config_.debugLogging) bridge_.log("Soul Stealer possession failed: " + result.message);
        state_ = State::Idle;
        return false;
    }

    if (result.status == PossessionStatus::ProbeOnly) {
        state_ = State::ProbeOnly;
        bridge_.showMessage("Soul Stealer probe captured target");
    } else {
        state_ = State::Possessing;
        bridge_.showMessage(std::string("Soul Stealer: ") + result.message);
    }
    if (config_.debugLogging) bridge_.log(result.message);
    return true;
}

bool SoulStealerModule::cancel() {
    if (state_ == State::Idle) return true;
    possession_.cancel();
    state_ = State::Idle;
    bridge_.showMessage("Soul Stealer canceled");
    return true;
}

void SoulStealerModule::tick() {
    if (state_ == State::Possessing) {
        ActorHandle player = bridge_.getPlayerActor();
        if (!bridge_.isActorValid(player) || !bridge_.isActorAlive(player)) {
            bridge_.showMessage("Soul Stealer: player invalid, restoring");
            cancel();
        }
    }
}

std::string SoulStealerModule::debugStatus() const {
    std::ostringstream oss;
    oss << "SoulStealer[state=" << toString(state_)
        << ", target=0x" << std::hex << targetActor()
        << ", possession=" << toString(possessionStatus())
        << "]";
    return oss.str();
}

} // namespace codered
