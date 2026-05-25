#include "SoulStealerRuntime.h"

namespace codered {

SoulStealerRuntime::SoulStealerRuntime(INativeBridge& bridge, IInputBridge& input, SoulStealerConfig config)
    : bridge_(bridge), input_(input), config_(config), module_(bridge, config), hotkeys_(input, config), overlay_(bridge), teleports_(bridge), remotePuppet_(bridge) {}

void SoulStealerRuntime::setConfig(SoulStealerConfig config) {
    config_ = config;
    module_.setConfig(config);
    hotkeys_.setConfig(config);
    logger_.log("Soul Stealer runtime config updated");
}

void SoulStealerRuntime::openLogFile(const std::string& path) {
    if (logger_.openFile(path)) {
        logger_.log("Soul Stealer runtime log opened: " + path);
    }
}

void SoulStealerRuntime::tick() {
    RuntimeCommands cmd = hotkeys_.poll();
    handleCommands(cmd);
    module_.tick();
    if (config_.enableRemotePuppetSoftSync) {
        remotePuppet_.softSyncActorToRemote(config_.remotePuppetInterpolation);
    }
}

void SoulStealerRuntime::handleCommands(const RuntimeCommands& cmd) {
    if (cmd.cancel) {
        logger_.log("cancel hotkey pressed");
        module_.cancel();
        return;
    }
    if (cmd.toggleArmed) {
        logger_.log("toggle hotkey pressed");
        module_.toggleArmed();
    }
    if (cmd.capture) {
        logger_.log("capture hotkey pressed");
        if (!module_.captureBestTarget()) {
            logger_.log("capture failed: " + module_.debugStatus());
        }
    }
    if (cmd.dumpDebug) {
        std::string status = module_.debugStatus();
        logger_.log(status);
        overlay_.showStatus(status);
    }
    if (cmd.saveTeleportSlot0) {
        logger_.log("save teleport slot 0");
        teleports_.savePlayerSlot(0, "SoulStealer Slot 0");
    }
    if (cmd.loadTeleportSlot0) {
        logger_.log("load teleport slot 0");
        if (!teleports_.teleportPlayerToSlot(0)) overlay_.showTransient("Teleport slot 0 is empty");
    }
    if (cmd.teleportControlledActorToPlayer) {
        logger_.log("teleport controlled actor to player");
        if (!remotePuppet_.teleportActorToPlayer()) overlay_.showTransient("No remote puppet actor bound");
    }
    if (cmd.reloadConfig) {
        logger_.log("reload hotkey pressed; integration layer should reload JSON and call setConfig");
        overlay_.showTransient("Soul Stealer: reload requested");
    }
}

} // namespace codered
