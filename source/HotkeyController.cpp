#include "HotkeyController.h"

namespace codered {

HotkeyController::HotkeyController(IInputBridge& input, SoulStealerConfig config)
    : input_(input), config_(config) {}

void HotkeyController::setConfig(SoulStealerConfig config) {
    config_ = config;
}

RuntimeCommands HotkeyController::poll() {
    RuntimeCommands cmd{};
    cmd.toggleArmed = input_.wasKeyPressed(config_.toggleHotkeyVk);
    cmd.capture = input_.wasKeyPressed(config_.captureHotkeyVk);
    cmd.cancel = input_.wasKeyPressed(config_.cancelHotkeyVk);
    cmd.reloadConfig = input_.wasKeyPressed(0x79); // F10, integration may remap later.
    cmd.dumpDebug = input_.wasKeyPressed(0x78);    // F9.
    cmd.saveTeleportSlot0 = input_.wasKeyPressed(config_.saveTeleportSlot0Vk);
    cmd.loadTeleportSlot0 = input_.wasKeyPressed(config_.loadTeleportSlot0Vk);
    cmd.teleportControlledActorToPlayer = input_.wasKeyPressed(config_.teleportControlledActorToPlayerVk);
    return cmd;
}

} // namespace codered
