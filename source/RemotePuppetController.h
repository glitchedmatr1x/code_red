#pragma once
#include "NativeBridge.h"
#include "RemotePuppetBlip.h"
#include "TeleportManager.h"

namespace codered {

class RemotePuppetController {
public:
    explicit RemotePuppetController(INativeBridge& bridge);

    void setControlledActor(ActorHandle actor);
    ActorHandle controlledActor() const { return controlledActor_; }
    void clearControlledActor();

    bool updateRemoteState(const RemotePuppetState& state);
    bool softSyncActorToRemote(float interpolation = 0.35f);
    bool snapActorToRemote();
    bool teleportActorToPlayer(float behindDistance = 2.0f);
    bool removeBlip();

private:
    INativeBridge& bridge_;
    RemotePuppetBlip blip_;
    TeleportManager teleports_;
    ActorHandle controlledActor_ = 0;
    RemotePuppetState lastRemote_{};
};

} // namespace codered
