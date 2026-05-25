#include "PossessionController.h"
#include <sstream>

namespace codered {

const char* toString(PossessionStatus status) {
    switch (status) {
        case PossessionStatus::None: return "None";
        case PossessionStatus::ProbeOnly: return "ProbeOnly";
        case PossessionStatus::RealSwap: return "RealSwap";
        case PossessionStatus::FallbackModelTeleport: return "FallbackModelTeleport";
    }
    return "Unknown";
}

PossessionController::PossessionController(INativeBridge& bridge, SoulStealerConfig config)
    : bridge_(bridge), config_(config) {}

void PossessionController::setConfig(SoulStealerConfig config) {
    if (status_ != PossessionStatus::None) {
        cancel();
    }
    config_ = config;
}

ActorSnapshot PossessionController::snapshot(ActorHandle actor) {
    ActorSnapshot s{};
    s.actor = actor;
    s.valid = bridge_.isActorValid(actor);
    if (s.valid) {
        s.alive = bridge_.isActorAlive(actor);
        s.player = bridge_.isActorPlayer(actor);
        s.animal = bridge_.isActorAnimal(actor);
        s.missionCritical = bridge_.isActorMissionCritical(actor);
        s.pos = bridge_.getActorPos(actor);
        s.heading = bridge_.getActorHeading(actor);
        s.model = bridge_.getActorModel(actor);
    }
    return s;
}

PossessionAttemptResult PossessionController::possess(ActorHandle target) {
    if (status_ != PossessionStatus::None) {
        return {false, status_, "already possessing/probing"};
    }

    original_ = snapshot(bridge_.getPlayerActor());
    target_ = snapshot(target);
    if (!original_.valid || !target_.valid) {
        reset();
        return {false, PossessionStatus::None, "invalid original or target snapshot"};
    }

    bridge_.clearActorTasksImmediately(target);

    if (config_.possessionMode == PossessionMode::ProbeOnly) {
        status_ = PossessionStatus::ProbeOnly;
        std::ostringstream oss;
        oss << "probe target=0x" << std::hex << target << " model=0x" << target_.model;
        return {true, status_, oss.str()};
    }

    if (config_.possessionMode == PossessionMode::PreferRealSwap) {
        auto real = tryRealSwap(target);
        if (real.ok) return real;
        bridge_.log("Soul Stealer: real swap unavailable, trying fallback");
        return tryFallback(target);
    }

    return tryFallback(target);
}

PossessionAttemptResult PossessionController::tryRealSwap(ActorHandle target) {
    if (!bridge_.swapPlayerToActor(target)) {
        return {false, PossessionStatus::None, "real swap native unavailable or failed"};
    }
    bridge_.setPlayerControl(true);
    status_ = PossessionStatus::RealSwap;
    return {true, status_, "real actor swap active"};
}

PossessionAttemptResult PossessionController::tryFallback(ActorHandle target) {
    (void)target;
    ActorHandle player = bridge_.getPlayerActor();
    if (!bridge_.isActorValid(player)) {
        return {false, PossessionStatus::None, "invalid player for fallback"};
    }

    bool ok = true;
    if (config_.makeOriginalTargetInvincibleOnFallback) ok = bridge_.setActorInvincible(target_.actor, true) && ok;
    if (config_.freezeOriginalTargetOnFallback) ok = bridge_.setActorFrozen(target_.actor, true) && ok;
    if (config_.hideOriginalTargetOnFallback) ok = bridge_.setActorVisible(target_.actor, false) && ok;

    ok = bridge_.setPlayerModel(target_.model) && ok;
    ok = bridge_.setActorPos(player, target_.pos) && ok;
    ok = bridge_.setActorHeading(player, target_.heading) && ok;
    ok = bridge_.setPlayerControl(true) && ok;

    if (!ok) {
        reset();
        return {false, PossessionStatus::None, "fallback model/teleport failed"};
    }

    status_ = PossessionStatus::FallbackModelTeleport;
    return {true, status_, "fallback model/teleport active"};
}

bool PossessionController::cancel() {
    if (status_ == PossessionStatus::None) return true;

    if (target_.valid && status_ == PossessionStatus::FallbackModelTeleport) {
        if (config_.hideOriginalTargetOnFallback) bridge_.setActorVisible(target_.actor, true);
        if (config_.freezeOriginalTargetOnFallback) bridge_.setActorFrozen(target_.actor, false);
        if (config_.makeOriginalTargetInvincibleOnFallback) bridge_.setActorInvincible(target_.actor, false);
    }

    ActorHandle player = bridge_.getPlayerActor();
    if (original_.valid && bridge_.isActorValid(player)) {
        if (config_.restorePlayerPositionOnCancel) {
            bridge_.setActorPos(player, original_.pos);
            bridge_.setActorHeading(player, original_.heading);
        }
        if (status_ == PossessionStatus::FallbackModelTeleport) {
            bridge_.setPlayerModel(original_.model);
        }
    }

    bridge_.setPlayerControl(true);
    reset();
    return true;
}

void PossessionController::reset() {
    status_ = PossessionStatus::None;
    original_ = ActorSnapshot{};
    target_ = ActorSnapshot{};
}

} // namespace codered
