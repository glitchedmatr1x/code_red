#include "TeleportManager.h"
#include <cmath>
#include <sstream>

namespace codered {
namespace {
constexpr float kPi = 3.14159265358979323846f;
Vec3 behindOffset(Vec3 pos, float headingDeg, float distance) {
    const float rad = headingDeg * kPi / 180.0f;
    return {pos.x - std::sin(rad) * distance, pos.y - std::cos(rad) * distance, pos.z};
}
}

TeleportManager::TeleportManager(INativeBridge& bridge) : bridge_(bridge) {}

bool TeleportManager::savePlayerSlot(int slot, const std::string& label) {
    if (slot < 0 || slot >= static_cast<int>(slots_.size())) return false;
    ActorHandle player = bridge_.getPlayerActor();
    if (!bridge_.isActorValid(player)) return false;
    slots_[slot] = {true, bridge_.getActorPos(player), bridge_.getActorHeading(player), label.empty() ? ("slot_" + std::to_string(slot)) : label};
    bridge_.showMessage("Teleport: saved " + slots_[slot].label);
    return true;
}

bool TeleportManager::teleportPlayerToSlot(int slot) {
    if (slot < 0 || slot >= static_cast<int>(slots_.size()) || !slots_[slot].valid) return false;
    return teleportPlayerTo(slots_[slot].pos, slots_[slot].heading, slots_[slot].label);
}

bool TeleportManager::teleportPlayerTo(Vec3 pos, float heading, const std::string& reason) {
    ActorHandle player = bridge_.getPlayerActor();
    if (!bridge_.isActorValid(player)) return false;
    bool ok = bridge_.setActorPos(player, pos) && bridge_.setActorHeading(player, heading);
    if (ok) bridge_.showMessage(reason.empty() ? "Teleport: moved player" : ("Teleport: " + reason));
    return ok;
}

bool TeleportManager::teleportPlayerToActor(ActorHandle actor) {
    if (!bridge_.isActorValid(actor)) return false;
    return teleportPlayerTo(bridge_.getActorPos(actor), bridge_.getActorHeading(actor), "to actor " + std::to_string(actor));
}

bool TeleportManager::teleportActorTo(ActorHandle actor, Vec3 pos, float heading) {
    if (!bridge_.isActorValid(actor)) return false;
    return bridge_.setActorPos(actor, pos) && bridge_.setActorHeading(actor, heading);
}

bool TeleportManager::teleportActorToPlayer(ActorHandle actor, float behindDistance) {
    ActorHandle player = bridge_.getPlayerActor();
    if (!bridge_.isActorValid(actor) || !bridge_.isActorValid(player)) return false;
    Vec3 target = behindOffset(bridge_.getActorPos(player), bridge_.getActorHeading(player), behindDistance);
    return teleportActorTo(actor, target, bridge_.getActorHeading(player));
}

const TeleportSlot* TeleportManager::slot(int slot) const {
    if (slot < 0 || slot >= static_cast<int>(slots_.size())) return nullptr;
    return &slots_[slot];
}

std::string TeleportManager::debugSlots() const {
    std::ostringstream out;
    for (int i = 0; i < static_cast<int>(slots_.size()); ++i) {
        if (!slots_[i].valid) continue;
        out << "slot " << i << " " << slots_[i].label << " @ "
            << slots_[i].pos.x << "," << slots_[i].pos.y << "," << slots_[i].pos.z << "\n";
    }
    return out.str();
}

} // namespace codered
