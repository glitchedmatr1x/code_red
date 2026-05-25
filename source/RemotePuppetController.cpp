#include "RemotePuppetController.h"

namespace codered {

RemotePuppetController::RemotePuppetController(INativeBridge& bridge)
    : bridge_(bridge), blip_(bridge), teleports_(bridge) {}

void RemotePuppetController::setControlledActor(ActorHandle actor) {
    if (bridge_.isActorValid(actor)) controlledActor_ = actor;
}

void RemotePuppetController::clearControlledActor() {
    controlledActor_ = 0;
}

bool RemotePuppetController::updateRemoteState(const RemotePuppetState& state) {
    lastRemote_ = state;
    return blip_.update(state);
}

bool RemotePuppetController::softSyncActorToRemote(float interpolation) {
    if (controlledActor_ == 0 || !bridge_.isActorValid(controlledActor_) || !lastRemote_.active) return false;
    Vec3 current = bridge_.getActorPos(controlledActor_);
    Vec3 next = lerp(current, lastRemote_.pos, interpolation);
    return bridge_.setActorPos(controlledActor_, next) && bridge_.setActorHeading(controlledActor_, lastRemote_.heading);
}

bool RemotePuppetController::snapActorToRemote() {
    if (controlledActor_ == 0 || !bridge_.isActorValid(controlledActor_) || !lastRemote_.active) return false;
    return teleports_.teleportActorTo(controlledActor_, lastRemote_.pos, lastRemote_.heading);
}

bool RemotePuppetController::teleportActorToPlayer(float behindDistance) {
    if (controlledActor_ == 0) return false;
    return teleports_.teleportActorToPlayer(controlledActor_, behindDistance);
}

bool RemotePuppetController::removeBlip() {
    return blip_.remove();
}

} // namespace codered
