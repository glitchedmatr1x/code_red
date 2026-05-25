#include "TargetSelector.h"
#include <cmath>
#include <limits>

namespace codered {
namespace {
constexpr float PI = 3.14159265358979323846f;
float degToRad(float d) { return d * PI / 180.0f; }
}

TargetSelector::TargetSelector(INativeBridge& bridge, SoulStealerConfig config)
    : bridge_(bridge), config_(config) {}

TargetResult TargetSelector::selectTarget() {
    TargetResult result{};
    switch (config_.targetMode) {
        case TargetMode::ReticleFirst:
            result = tryReticle();
            if (result.actor) return result;
            result = tryLastDamaged();
            if (result.actor) return result;
            return tryNearestForward();
        case TargetMode::LastDamagedFirst:
            result = tryLastDamaged();
            if (result.actor) return result;
            result = tryReticle();
            if (result.actor) return result;
            return tryNearestForward();
        case TargetMode::NearestForward:
            return tryNearestForward();
        case TargetMode::NearestRadius:
            return tryNearestRadius();
    }
    return result;
}

bool TargetSelector::isValidTarget(ActorHandle actor, std::string* reason) const {
    auto reject = [&](const std::string& why) {
        if (reason) *reason = why;
        return false;
    };
    if (actor == 0) return reject("empty handle");
    if (!bridge_.isActorValid(actor)) return reject("invalid actor");
    if (!bridge_.isActorAlive(actor)) return reject("dead actor");
    if (bridge_.isActorPlayer(actor)) return reject("player actor");
    if (!config_.allowAnimals && bridge_.isActorAnimal(actor)) return reject("animal actor blocked by config");
    if (!config_.allowMissionCritical && bridge_.isActorMissionCritical(actor)) return reject("mission-critical actor blocked by config");

    const ActorHandle player = bridge_.getPlayerActor();
    if (bridge_.isActorValid(player)) {
        const float maxD2 = config_.maxTargetDistance * config_.maxTargetDistance;
        if (distanceSquared(bridge_.getActorPos(player), bridge_.getActorPos(actor)) > maxD2) {
            return reject("target too far");
        }
    }
    if (reason) reason->clear();
    return true;
}

TargetResult TargetSelector::targetIfValid(ActorHandle actor, const std::string& source) const {
    TargetResult r{};
    r.source = source;
    if (isValidTarget(actor, &r.rejectedReason)) {
        r.actor = actor;
        r.rejectedReason.clear();
    }
    return r;
}

TargetResult TargetSelector::tryReticle() const {
    return targetIfValid(bridge_.getActorUnderReticle(), "reticle");
}

TargetResult TargetSelector::tryLastDamaged() const {
    return targetIfValid(bridge_.getLastActorDamagedByPlayer(), "last_damaged");
}

bool TargetSelector::inForwardCone(const Vec3& playerPos, float playerHeading, const Vec3& targetPos) const {
    const float dx = targetPos.x - playerPos.x;
    const float dy = targetPos.y - playerPos.y;
    const float len = std::sqrt(dx * dx + dy * dy);
    if (len <= 0.001f) return true;

    // RDR coordinate heading convention may need adjustment in the real bridge.
    // This mock assumes heading 0 points +Y and positive heading rotates toward +X.
    const float h = degToRad(playerHeading);
    const float fx = std::sin(h);
    const float fy = std::cos(h);
    const float dot = (dx / len) * fx + (dy / len) * fy;
    const float minDot = std::cos(degToRad(config_.forwardConeDegrees * 0.5f));
    return dot >= minDot;
}

TargetResult TargetSelector::tryNearestForward() const {
    TargetResult result{};
    result.source = "nearest_forward";
    const ActorHandle player = bridge_.getPlayerActor();
    if (!bridge_.isActorValid(player)) {
        result.rejectedReason = "invalid player";
        return result;
    }

    const Vec3 playerPos = bridge_.getActorPos(player);
    const float heading = bridge_.getActorHeading(player);
    float best = std::numeric_limits<float>::max();
    for (ActorHandle actor : bridge_.getAllActors()) {
        std::string reason;
        if (!isValidTarget(actor, &reason)) continue;
        const Vec3 pos = bridge_.getActorPos(actor);
        if (!inForwardCone(playerPos, heading, pos)) continue;
        const float d = distanceSquared(playerPos, pos);
        if (d < best) {
            best = d;
            result.actor = actor;
            result.rejectedReason.clear();
        }
    }
    if (!result.actor) result.rejectedReason = "no valid actor in forward cone";
    return result;
}

TargetResult TargetSelector::tryNearestRadius() const {
    TargetResult result{};
    result.source = "nearest_radius";
    const ActorHandle player = bridge_.getPlayerActor();
    if (!bridge_.isActorValid(player)) {
        result.rejectedReason = "invalid player";
        return result;
    }
    const Vec3 playerPos = bridge_.getActorPos(player);
    float best = std::numeric_limits<float>::max();
    for (ActorHandle actor : bridge_.getAllActors()) {
        std::string reason;
        if (!isValidTarget(actor, &reason)) continue;
        const float d = distanceSquared(playerPos, bridge_.getActorPos(actor));
        if (d < best) {
            best = d;
            result.actor = actor;
            result.rejectedReason.clear();
        }
    }
    if (!result.actor) result.rejectedReason = "no valid actor in radius";
    return result;
}

} // namespace codered
