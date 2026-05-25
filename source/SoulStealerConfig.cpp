#include "SoulStealerConfig.h"
#include <algorithm>

namespace codered {
namespace {
std::string norm(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c){ return static_cast<char>(std::tolower(c)); });
    s.erase(std::remove_if(s.begin(), s.end(), [](char c){ return c == '_' || c == '-' || c == ' '; }), s.end());
    return s;
}
}

const char* toString(TargetMode mode) {
    switch (mode) {
        case TargetMode::ReticleFirst: return "ReticleFirst";
        case TargetMode::LastDamagedFirst: return "LastDamagedFirst";
        case TargetMode::NearestForward: return "NearestForward";
        case TargetMode::NearestRadius: return "NearestRadius";
    }
    return "Unknown";
}

const char* toString(PossessionMode mode) {
    switch (mode) {
        case PossessionMode::PreferRealSwap: return "PreferRealSwap";
        case PossessionMode::ForceFallbackModelTeleport: return "ForceFallbackModelTeleport";
        case PossessionMode::ProbeOnly: return "ProbeOnly";
    }
    return "Unknown";
}

TargetMode targetModeFromString(const std::string& value, TargetMode fallback) {
    const std::string v = norm(value);
    if (v == "reticlefirst" || v == "reticle") return TargetMode::ReticleFirst;
    if (v == "lastdamagedfirst" || v == "lastdamaged") return TargetMode::LastDamagedFirst;
    if (v == "nearestforward" || v == "forward") return TargetMode::NearestForward;
    if (v == "nearestradius" || v == "radius") return TargetMode::NearestRadius;
    return fallback;
}

PossessionMode possessionModeFromString(const std::string& value, PossessionMode fallback) {
    const std::string v = norm(value);
    if (v == "preferrealswap" || v == "real" || v == "swap") return PossessionMode::PreferRealSwap;
    if (v == "forcefallbackmodelteleport" || v == "fallback" || v == "modelteleport") return PossessionMode::ForceFallbackModelTeleport;
    if (v == "probeonly" || v == "probe") return PossessionMode::ProbeOnly;
    return fallback;
}

} // namespace codered
