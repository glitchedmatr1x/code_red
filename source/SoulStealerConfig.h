#pragma once
#include <cstdint>
#include <string>

namespace codered {

enum class TargetMode {
    ReticleFirst,
    LastDamagedFirst,
    NearestForward,
    NearestRadius,
};

enum class PossessionMode {
    PreferRealSwap,
    ForceFallbackModelTeleport,
    ProbeOnly,
};

struct SoulStealerConfig {
    TargetMode targetMode = TargetMode::ReticleFirst;
    PossessionMode possessionMode = PossessionMode::PreferRealSwap;

    float maxTargetDistance = 35.0f;
    float forwardConeDegrees = 70.0f;

    bool allowAnimals = false;
    bool allowMissionCritical = false;
    bool freezeOriginalTargetOnFallback = true;
    bool hideOriginalTargetOnFallback = false;
    bool makeOriginalTargetInvincibleOnFallback = true;
    bool restorePlayerPositionOnCancel = true;
    bool debugLogging = true;

    // Hotkeys are intentionally expressed as VK codes for the Windows integration layer.
    // Mock tests do not use these directly.
    std::uint32_t toggleHotkeyVk = 0x77; // F8
    std::uint32_t captureHotkeyVk = 0x45; // E
    std::uint32_t cancelHotkeyVk = 0x08; // Backspace
    std::uint32_t saveTeleportSlot0Vk = 0x74; // F5
    std::uint32_t loadTeleportSlot0Vk = 0x75; // F6
    std::uint32_t teleportControlledActorToPlayerVk = 0x76; // F7

    bool enableRemoteBlip = true;
    bool enableRemotePuppetSoftSync = false;
    float remotePuppetInterpolation = 0.35f;
};

const char* toString(TargetMode mode);
const char* toString(PossessionMode mode);
TargetMode targetModeFromString(const std::string& value, TargetMode fallback = TargetMode::ReticleFirst);
PossessionMode possessionModeFromString(const std::string& value, PossessionMode fallback = PossessionMode::PreferRealSwap);

} // namespace codered
