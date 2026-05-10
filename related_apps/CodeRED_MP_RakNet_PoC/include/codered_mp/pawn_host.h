#pragma once

#include <cstdint>
#include <functional>
#include <string>

#include <amx.h>

#include "codered_mp/protocol.h"

namespace codered_mp {

class PawnHost {
public:
    using NativeCallSender = std::function<void(std::uint8_t, const std::string&, const std::string&)>;
    using PlayerStateGetter = std::function<bool(std::uint8_t, PlayerState&)>;
    using PlayerActorEnumSetter = std::function<bool(std::uint8_t, std::uint16_t)>;

    PawnHost();
    ~PawnHost();

    PawnHost(const PawnHost&) = delete;
    PawnHost& operator=(const PawnHost&) = delete;

    bool Load(const std::string& amxPath, NativeCallSender nativeCallSender,
              PlayerStateGetter playerStateGetter = {},
              PlayerActorEnumSetter playerActorEnumSetter = {});
    void Unload();
    bool IsLoaded() const;

    bool OnGameModeInit();
    bool OnGameModeExit();
    bool OnPlayerConnect(std::uint8_t playerId);
    bool OnPlayerDisconnect(std::uint8_t playerId);
    bool OnPlayerText(std::uint8_t playerId, const std::string& text);

    void Print(const std::string& message);
    void SetGameModeText(const std::string& text);
    void SendClientNativeCall(std::uint8_t playerId, const std::string& callName, const std::string& payload);
    bool IsPlayerConnected(std::uint8_t playerId);
    bool GetPlayerState(std::uint8_t playerId, PlayerState& outState);
    bool SetPlayerActorEnum(std::uint8_t playerId, std::uint16_t actorEnum);
    std::string GetStringParam(const cell* params, int index);

    const std::string& GameModeText() const;
    const std::string& LastError() const;

private:
    bool ExecPublic(const char* name);
    bool ExecPublic(const char* name, std::uint8_t playerId);
    bool ExecPublicString(const char* name, std::uint8_t playerId, const std::string& text);
    bool RegisterNatives();
    void SetError(const std::string& context, int error);

    AMX* amx_ = nullptr;
    NativeCallSender nativeCallSender_;
    PlayerStateGetter playerStateGetter_;
    PlayerActorEnumSetter playerActorEnumSetter_;
    bool gameModeStarted_ = false;
    std::string gameModeText_ = "Code RED MP";
    std::string lastError_;
};

} // namespace codered_mp
