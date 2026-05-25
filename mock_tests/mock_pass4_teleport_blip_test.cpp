#include "MockNativeBridge.h"
#include "TeleportManager.h"
#include "RemotePuppetController.h"
#include <cassert>
#include <iostream>

using namespace codered;

int main() {
    MockNativeBridge bridge;

    TeleportManager teleports(bridge);
    assert(teleports.savePlayerSlot(0, "start"));
    assert(bridge.setActorPos(bridge.getPlayerActor(), {100, 100, 0}));
    assert(teleports.teleportPlayerToSlot(0));
    Vec3 playerPos = bridge.getActorPos(bridge.getPlayerActor());
    assert(playerPos.x == 0 && playerPos.y == 0);

    RemotePuppetController puppet(bridge);
    RemotePuppetState state;
    state.playerId = "p2";
    state.displayName = "Remote Architect";
    state.pos = {50, 60, 0};
    state.heading = 123.0f;
    state.timestampMs = 1000;
    state.active = true;
    assert(puppet.updateRemoteState(state));
    assert(bridge.blips.size() == 1);

    puppet.setControlledActor(2);
    assert(puppet.snapActorToRemote());
    Vec3 actorPos = bridge.getActorPos(2);
    assert(actorPos.x == 50 && actorPos.y == 60);

    state.pos = {70, 80, 0};
    assert(puppet.updateRemoteState(state));
    assert(puppet.softSyncActorToRemote(0.5f));
    actorPos = bridge.getActorPos(2);
    assert(actorPos.x > 50 && actorPos.x < 70);

    assert(puppet.teleportActorToPlayer());
    assert(puppet.removeBlip());

    std::cout << "soul_stealer_pass4_teleport_blip_test: passed\n";
    return 0;
}
