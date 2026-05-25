#include "MockNativeBridge.h"

namespace codered {

MockNativeBridge::MockNativeBridge() {
    actors[1] = {{0,0,0}, 0, 0x111, "PLAYER_JOHN", true, true, false, false};
    actors[2] = {{0,8,0}, 180, 0x222, "NPC_RANCHER", false, true, false, false};
    actors[3] = {{6,3,0}, 45, 0x333, "NPC_LAWMAN", false, true, false, false};
    actors[4] = {{4,1,0}, 90, 0x444, "HORSE01", false, true, true, false};
    reticleTarget = 2;
}

ActorHandle MockNativeBridge::getPlayerActor() { return player; }
bool MockNativeBridge::isActorValid(ActorHandle actor) { return actors.count(actor) != 0; }
bool MockNativeBridge::isActorAlive(ActorHandle actor) { return isActorValid(actor) && actors[actor].alive; }
bool MockNativeBridge::isActorPlayer(ActorHandle actor) { return isActorValid(actor) && actors[actor].player; }
bool MockNativeBridge::isActorAnimal(ActorHandle actor) { return isActorValid(actor) && actors[actor].animal; }
bool MockNativeBridge::isActorMissionCritical(ActorHandle actor) { return isActorValid(actor) && actors[actor].missionCritical; }
Vec3 MockNativeBridge::getActorPos(ActorHandle actor) { return actors[actor].pos; }
float MockNativeBridge::getActorHeading(ActorHandle actor) { return actors[actor].heading; }
std::uint32_t MockNativeBridge::getActorModel(ActorHandle actor) { return actors[actor].model; }
std::string MockNativeBridge::getActorModelName(ActorHandle actor) { return actors[actor].modelName; }
std::vector<ActorHandle> MockNativeBridge::getAllActors() {
    std::vector<ActorHandle> out;
    for (auto& [handle, _] : actors) out.push_back(handle);
    return out;
}
ActorHandle MockNativeBridge::getActorUnderReticle() { return reticleTarget; }
ActorHandle MockNativeBridge::getLastActorDamagedByPlayer() { return lastDamaged; }
void MockNativeBridge::clearActorTasksImmediately(ActorHandle actor) { log("clear tasks actor=" + std::to_string(actor)); }
bool MockNativeBridge::setPlayerControl(bool enabled) { log(std::string("player control ") + (enabled ? "on" : "off")); return true; }
bool MockNativeBridge::swapPlayerToActor(ActorHandle actor) {
    if (!allowRealSwap || !isActorValid(actor)) return false;
    actors[player].player = false;
    player = actor;
    actors[player].player = true;
    return true;
}
bool MockNativeBridge::setPlayerModel(std::uint32_t model) { actors[player].model = model; return true; }
bool MockNativeBridge::setActorPos(ActorHandle actor, Vec3 pos) { if (!isActorValid(actor)) return false; actors[actor].pos = pos; return true; }
bool MockNativeBridge::setActorHeading(ActorHandle actor, float heading) { if (!isActorValid(actor)) return false; actors[actor].heading = heading; return true; }
bool MockNativeBridge::setActorInvincible(ActorHandle actor, bool enabled) { if (!isActorValid(actor)) return false; actors[actor].invincible = enabled; return true; }
bool MockNativeBridge::setActorFrozen(ActorHandle actor, bool enabled) { if (!isActorValid(actor)) return false; actors[actor].frozen = enabled; return true; }
bool MockNativeBridge::setActorVisible(ActorHandle actor, bool visible) { if (!isActorValid(actor)) return false; actors[actor].visible = visible; return true; }
BlipHandle MockNativeBridge::createCoordBlip(Vec3 pos, const std::string& label, int icon, int color) {
    const BlipHandle handle = nextBlip++;
    blips[handle] = {pos, 0.0f, label, icon, color, true};
    log("create blip " + std::to_string(handle) + " label=" + label);
    return handle;
}
bool MockNativeBridge::updateCoordBlip(BlipHandle blip, Vec3 pos, float heading) {
    if (!blips.count(blip) || !blips[blip].active) return false;
    blips[blip].pos = pos;
    blips[blip].heading = heading;
    return true;
}
bool MockNativeBridge::setBlipLabel(BlipHandle blip, const std::string& label) {
    if (!blips.count(blip) || !blips[blip].active) return false;
    blips[blip].label = label;
    return true;
}
bool MockNativeBridge::removeBlip(BlipHandle blip) {
    if (!blips.count(blip) || !blips[blip].active) return false;
    blips[blip].active = false;
    log("remove blip " + std::to_string(blip));
    return true;
}
void MockNativeBridge::showMessage(const std::string& text) { messages.push_back(text); std::cout << text << "\n"; }
void MockNativeBridge::log(const std::string& text) { logs.push_back(text); std::cout << "[log] " << text << "\n"; }

} // namespace codered
