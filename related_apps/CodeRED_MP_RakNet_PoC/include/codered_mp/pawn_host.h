#pragma once

#include <cstdint>
#include <functional>
#include <string>

#include <amx.h>

namespace codered_mp {

class PawnHost {
public:
    using NativeCallSender = std::function<void(std::uint8_t, const std::string&, const std::string&)>;

    PawnHost();
    ~PawnHost();

    PawnHost(const PawnHost&) = delete;
    PawnHost& operator=(const PawnHost&) = delete;

    bool Load(const std::string& amxPath, NativeCallSender nativeCallSender);
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
    bool gameModeStarted_ = false;
    std::string gameModeText_ = "Code RED MP";
    std::string lastError_;
};

} // namespace codered_mp
