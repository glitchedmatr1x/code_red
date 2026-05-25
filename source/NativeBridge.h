#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace codered {

using ActorHandle = std::uint64_t;
using BlipHandle = std::uint64_t;

struct Vec3 {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
};

struct ActorSnapshot {
    ActorHandle actor = 0;
    Vec3 pos{};
    float heading = 0.0f;
    std::uint32_t model = 0;
    bool valid = false;
    bool alive = false;
    bool player = false;
    bool animal = false;
    bool missionCritical = false;
};

struct ActorDebugInfo {
    ActorHandle actor = 0;
    std::uint32_t model = 0;
    std::string modelName;
    std::string typeName;
    Vec3 pos{};
    float heading = 0.0f;
};

class INativeBridge {
public:
    virtual ~INativeBridge() = default;

    // Core actor access.
    virtual ActorHandle getPlayerActor() = 0;
    virtual bool isActorValid(ActorHandle actor) = 0;
    virtual bool isActorAlive(ActorHandle actor) = 0;
    virtual bool isActorPlayer(ActorHandle actor) = 0;
    virtual bool isActorAnimal(ActorHandle actor) = 0;
    virtual bool isActorMissionCritical(ActorHandle actor) = 0;
    virtual Vec3 getActorPos(ActorHandle actor) = 0;
    virtual float getActorHeading(ActorHandle actor) = 0;
    virtual std::uint32_t getActorModel(ActorHandle actor) = 0;
    virtual std::string getActorModelName(ActorHandle actor) = 0;
    virtual std::vector<ActorHandle> getAllActors() = 0;

    // Optional targeting sources. Return 0 when unsupported/not available.
    virtual ActorHandle getActorUnderReticle() = 0;
    virtual ActorHandle getLastActorDamagedByPlayer() = 0;

    // Task/control primitives.
    virtual void clearActorTasksImmediately(ActorHandle actor) = 0;
    virtual bool setPlayerControl(bool enabled) = 0;
    virtual bool swapPlayerToActor(ActorHandle actor) = 0; // Preferred real possession path. Return false if unavailable.

    // Fallback possession primitives.
    virtual bool setPlayerModel(std::uint32_t model) = 0;
    virtual bool setActorPos(ActorHandle actor, Vec3 pos) = 0;
    virtual bool setActorHeading(ActorHandle actor, float heading) = 0;
    virtual bool setActorInvincible(ActorHandle actor, bool enabled) = 0;
    virtual bool setActorFrozen(ActorHandle actor, bool enabled) = 0;
    virtual bool setActorVisible(ActorHandle actor, bool visible) = 0;

    // Blip/radar primitives for Code RED Link and remote puppet visibility.
    // Return 0 when unsupported or creation failed.
    virtual BlipHandle createCoordBlip(Vec3 pos, const std::string& label, int icon, int color) = 0;
    virtual bool updateCoordBlip(BlipHandle blip, Vec3 pos, float heading) = 0;
    virtual bool setBlipLabel(BlipHandle blip, const std::string& label) = 0;
    virtual bool removeBlip(BlipHandle blip) = 0;

    // Diagnostics/UI.
    virtual void showMessage(const std::string& text) = 0;
    virtual void log(const std::string& text) = 0;
};

inline float distanceSquared(const Vec3& a, const Vec3& b) {
    const float dx = a.x - b.x;
    const float dy = a.y - b.y;
    const float dz = a.z - b.z;
    return dx * dx + dy * dy + dz * dz;
}

inline Vec3 lerp(const Vec3& a, const Vec3& b, float t) {
    if (t < 0.0f) t = 0.0f;
    if (t > 1.0f) t = 1.0f;
    return {a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, a.z + (b.z - a.z) * t};
}

} // namespace codered
