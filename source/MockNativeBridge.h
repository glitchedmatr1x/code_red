#pragma once
#include "NativeBridge.h"
#include <iostream>
#include <map>

namespace codered {

class MockNativeBridge : public INativeBridge {
public:
    struct ActorRecord {
        Vec3 pos{};
        float heading = 0.0f;
        std::uint32_t model = 0;
        std::string modelName;
        bool player = false;
        bool alive = true;
        bool animal = false;
        bool missionCritical = false;
        bool frozen = false;
        bool visible = true;
        bool invincible = false;
    };

    std::map<ActorHandle, ActorRecord> actors;
    ActorHandle player = 1;
    ActorHandle reticleTarget = 0;
    ActorHandle lastDamaged = 0;
    bool allowRealSwap = false;
    std::uint64_t nextBlip = 100;
    struct BlipRecord { Vec3 pos{}; float heading = 0.0f; std::string label; int icon = 0; int color = 0; bool active = true; };
    std::map<BlipHandle, BlipRecord> blips;
    std::vector<std::string> messages;
    std::vector<std::string> logs;

    MockNativeBridge();

    ActorHandle getPlayerActor() override;
    bool isActorValid(ActorHandle actor) override;
    bool isActorAlive(ActorHandle actor) override;
    bool isActorPlayer(ActorHandle actor) override;
    bool isActorAnimal(ActorHandle actor) override;
    bool isActorMissionCritical(ActorHandle actor) override;
    Vec3 getActorPos(ActorHandle actor) override;
    float getActorHeading(ActorHandle actor) override;
    std::uint32_t getActorModel(ActorHandle actor) override;
    std::string getActorModelName(ActorHandle actor) override;
    std::vector<ActorHandle> getAllActors() override;
    ActorHandle getActorUnderReticle() override;
    ActorHandle getLastActorDamagedByPlayer() override;
    void clearActorTasksImmediately(ActorHandle actor) override;
    bool setPlayerControl(bool enabled) override;
    bool swapPlayerToActor(ActorHandle actor) override;
    bool setPlayerModel(std::uint32_t model) override;
    bool setActorPos(ActorHandle actor, Vec3 pos) override;
    bool setActorHeading(ActorHandle actor, float heading) override;
    bool setActorInvincible(ActorHandle actor, bool enabled) override;
    bool setActorFrozen(ActorHandle actor, bool enabled) override;
    bool setActorVisible(ActorHandle actor, bool visible) override;
    BlipHandle createCoordBlip(Vec3 pos, const std::string& label, int icon, int color) override;
    bool updateCoordBlip(BlipHandle blip, Vec3 pos, float heading) override;
    bool setBlipLabel(BlipHandle blip, const std::string& label) override;
    bool removeBlip(BlipHandle blip) override;
    void showMessage(const std::string& text) override;
    void log(const std::string& text) override;
};

} // namespace codered
