#include "codered_mp/pawn_host.h"

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <sstream>
#include <utility>

#include <amxaux.h>

extern "C" int AMXEXPORT AMXAPI amx_CoreInit(AMX* amx);
extern "C" int AMXEXPORT AMXAPI amx_FloatInit(AMX* amx);

namespace codered_mp {
namespace {

constexpr long kPawnHostUserTag = AMX_USERTAG('C', 'R', 'M', 'P');

PawnHost* HostFromAmx(AMX* amx) {
    void* userData = nullptr;
    if (amx_GetUserData(amx, kPawnHostUserTag, &userData) != AMX_ERR_NONE) {
        return nullptr;
    }
    return static_cast<PawnHost*>(userData);
}

cell AMX_NATIVE_CALL NativeStrLen(AMX* amx, const cell* params) {
    PawnHost* host = HostFromAmx(amx);
    if (!host || params[0] < static_cast<cell>(sizeof(cell))) {
        return 0;
    }
    return static_cast<cell>(host->GetStringParam(params, 1).size());
}

cell AMX_NATIVE_CALL NativeStrVal(AMX* amx, const cell* params) {
    PawnHost* host = HostFromAmx(amx);
    if (!host || params[0] < static_cast<cell>(sizeof(cell))) {
        return 0;
    }
    return static_cast<cell>(std::strtol(host->GetStringParam(params, 1).c_str(), nullptr, 10));
}

cell AMX_NATIVE_CALL NativeStrCmp(AMX* amx, const cell* params) {
    PawnHost* host = HostFromAmx(amx);
    if (!host || params[0] < static_cast<cell>(sizeof(cell) * 2)) {
        return 0;
    }

    std::string left = host->GetStringParam(params, 1);
    std::string right = host->GetStringParam(params, 2);
    const bool ignoreCase = params[0] >= static_cast<cell>(sizeof(cell) * 3) && params[3] != 0;
    int maxLength = -1;
    if (params[0] >= static_cast<cell>(sizeof(cell) * 4)) {
        maxLength = static_cast<int>(params[4]);
    }

    const std::size_t limit = maxLength >= 0
        ? static_cast<std::size_t>(maxLength)
        : (std::max(left.size(), right.size()) + 1);
    for (std::size_t i = 0; i < limit; ++i) {
        const unsigned char lc = i < left.size() ? static_cast<unsigned char>(left[i]) : 0;
        const unsigned char rc = i < right.size() ? static_cast<unsigned char>(right[i]) : 0;
        const int a = ignoreCase ? std::tolower(lc) : lc;
        const int b = ignoreCase ? std::tolower(rc) : rc;
        if (a != b) {
            return a < b ? -1 : 1;
        }
        if (lc == 0 && rc == 0) {
            return 0;
        }
    }
    return 0;
}

cell AMX_NATIVE_CALL NativePrint(AMX* amx, const cell* params) {
    PawnHost* host = HostFromAmx(amx);
    if (!host || params[0] < static_cast<cell>(sizeof(cell))) {
        return 0;
    }
    host->Print(host->GetStringParam(params, 1));
    return 1;
}

cell AMX_NATIVE_CALL NativeSetGameModeText(AMX* amx, const cell* params) {
    PawnHost* host = HostFromAmx(amx);
    if (!host || params[0] < static_cast<cell>(sizeof(cell))) {
        return 0;
    }
    host->SetGameModeText(host->GetStringParam(params, 1));
    return 1;
}

cell AMX_NATIVE_CALL NativeSendClientNativeCall(AMX* amx, const cell* params) {
    PawnHost* host = HostFromAmx(amx);
    if (!host || params[0] < static_cast<cell>(sizeof(cell) * 3)) {
        return 0;
    }
    const cell playerId = params[1];
    if (playerId < 0 || playerId > 255) {
        return 0;
    }
    host->SendClientNativeCall(static_cast<std::uint8_t>(playerId),
                               host->GetStringParam(params, 2),
                               host->GetStringParam(params, 3));
    return 1;
}

cell AMX_NATIVE_CALL NativeSendClientNativeCallInt(AMX* amx, const cell* params) {
    PawnHost* host = HostFromAmx(amx);
    if (!host || params[0] < static_cast<cell>(sizeof(cell) * 3)) {
        return 0;
    }
    const cell playerId = params[1];
    if (playerId < 0 || playerId > 255) {
        return 0;
    }
    host->SendClientNativeCall(static_cast<std::uint8_t>(playerId),
                               host->GetStringParam(params, 2),
                               std::to_string(static_cast<int>(params[3])));
    return 1;
}

cell AMX_NATIVE_CALL NativeSendClientTeleport(AMX* amx, const cell* params) {
    PawnHost* host = HostFromAmx(amx);
    if (!host || params[0] < static_cast<cell>(sizeof(cell) * 5)) {
        return 0;
    }
    const cell playerId = params[1];
    if (playerId < 0 || playerId > 255) {
        return 0;
    }

    char payload[96] = {};
    std::snprintf(payload, sizeof(payload), "%.4f,%.4f,%.4f,%.2f",
                  amx_ctof(params[2]), amx_ctof(params[3]),
                  amx_ctof(params[4]), amx_ctof(params[5]));
    host->SendClientNativeCall(static_cast<std::uint8_t>(playerId),
                               "client_teleport", payload);
    return 1;
}

cell AMX_NATIVE_CALL NativeIsPlayerConnected(AMX* amx, const cell* params) {
    PawnHost* host = HostFromAmx(amx);
    if (!host || params[0] < static_cast<cell>(sizeof(cell))) {
        return 0;
    }
    const cell playerId = params[1];
    if (playerId < 0 || playerId > 255) {
        return 0;
    }
    return host->IsPlayerConnected(static_cast<std::uint8_t>(playerId)) ? 1 : 0;
}

bool SetFloatRef(AMX* amx, cell address, float value) {
    cell* physicalAddress = nullptr;
    if (amx_GetAddr(amx, address, &physicalAddress) != AMX_ERR_NONE || !physicalAddress) {
        return false;
    }
    *physicalAddress = amx_ftoc(value);
    return true;
}

cell AMX_NATIVE_CALL NativeGetPlayerPosition(AMX* amx, const cell* params) {
    PawnHost* host = HostFromAmx(amx);
    if (!host || params[0] < static_cast<cell>(sizeof(cell) * 4)) {
        return 0;
    }
    const cell playerId = params[1];
    if (playerId < 0 || playerId > 255) {
        return 0;
    }

    PlayerState state;
    if (!host->GetPlayerState(static_cast<std::uint8_t>(playerId), state)) {
        return 0;
    }

    return SetFloatRef(amx, params[2], state.x) &&
           SetFloatRef(amx, params[3], state.y) &&
           SetFloatRef(amx, params[4], state.z) ? 1 : 0;
}

cell AMX_NATIVE_CALL NativeGetPlayerHeading(AMX* amx, const cell* params) {
    PawnHost* host = HostFromAmx(amx);
    if (!host || params[0] < static_cast<cell>(sizeof(cell) * 2)) {
        return 0;
    }
    const cell playerId = params[1];
    if (playerId < 0 || playerId > 255) {
        return 0;
    }

    PlayerState state;
    if (!host->GetPlayerState(static_cast<std::uint8_t>(playerId), state)) {
        return 0;
    }

    return SetFloatRef(amx, params[2], state.heading) ? 1 : 0;
}

cell AMX_NATIVE_CALL NativeSetPlayerActorEnum(AMX* amx, const cell* params) {
    PawnHost* host = HostFromAmx(amx);
    if (!host || params[0] < static_cast<cell>(sizeof(cell) * 2)) {
        return 0;
    }
    const cell playerId = params[1];
    const cell actorEnum = params[2];
    if (playerId < 0 || playerId > 255 || actorEnum <= 0 || actorEnum > 65535) {
        return 0;
    }
    return host->SetPlayerActorEnum(static_cast<std::uint8_t>(playerId),
                                    static_cast<std::uint16_t>(actorEnum)) ? 1 : 0;
}

const AMX_NATIVE_INFO kCodeRedNatives[] = {
    {"strlen", NativeStrLen},
    {"strval", NativeStrVal},
    {"strcmp", NativeStrCmp},
    {"print", NativePrint},
    {"SetGameModeText", NativeSetGameModeText},
    {"SendClientNativeCall", NativeSendClientNativeCall},
    {"SendClientNativeCallInt", NativeSendClientNativeCallInt},
    {"SendClientTeleport", NativeSendClientTeleport},
    {"IsPlayerConnected", NativeIsPlayerConnected},
    {"GetPlayerPosition", NativeGetPlayerPosition},
    {"GetPlayerHeading", NativeGetPlayerHeading},
    {"SetPlayerActorEnum", NativeSetPlayerActorEnum},
    {nullptr, nullptr},
};

} // namespace

PawnHost::PawnHost() = default;

PawnHost::~PawnHost() {
    Unload();
}

bool PawnHost::Load(const std::string& amxPath, NativeCallSender nativeCallSender,
                    PlayerStateGetter playerStateGetter,
                    PlayerActorEnumSetter playerActorEnumSetter) {
    Unload();
    nativeCallSender_ = std::move(nativeCallSender);
    playerStateGetter_ = std::move(playerStateGetter);
    playerActorEnumSetter_ = std::move(playerActorEnumSetter);
    amx_ = new AMX{};

    const int loadError = aux_LoadProgram(amx_, const_cast<char*>(amxPath.c_str()), nullptr);
    if (loadError != AMX_ERR_NONE) {
        SetError("load " + amxPath, loadError);
        delete amx_;
        amx_ = nullptr;
        return false;
    }

    const int userDataError = amx_SetUserData(amx_, kPawnHostUserTag, this);
    if (userDataError != AMX_ERR_NONE) {
        SetError("set host userdata", userDataError);
        Unload();
        return false;
    }

    if (!RegisterNatives()) {
        Unload();
        return false;
    }

    cell mainResult = 0;
    const int mainError = amx_Exec(amx_, &mainResult, AMX_EXEC_MAIN);
    if (mainError != AMX_ERR_NONE) {
        SetError("exec main", mainError);
        Unload();
        return false;
    }
    std::printf("[pawn] main() -> %d\n", static_cast<int>(mainResult));

    lastError_.clear();
    std::printf("[pawn] loaded %s\n", amxPath.c_str());
    return true;
}

void PawnHost::Unload() {
    if (amx_) {
        if (gameModeStarted_) {
            OnGameModeExit();
            gameModeStarted_ = false;
        }
        aux_FreeProgram(amx_);
        delete amx_;
        amx_ = nullptr;
    }
    nativeCallSender_ = nullptr;
    playerStateGetter_ = nullptr;
    playerActorEnumSetter_ = nullptr;
}

bool PawnHost::IsLoaded() const {
    return amx_ != nullptr;
}

bool PawnHost::OnGameModeInit() {
    gameModeStarted_ = ExecPublic("OnGameModeInit");
    return gameModeStarted_;
}

bool PawnHost::OnGameModeExit() {
    if (!amx_) {
        return true;
    }
    return ExecPublic("OnGameModeExit");
}

bool PawnHost::OnPlayerConnect(std::uint8_t playerId) {
    return ExecPublic("OnPlayerConnect", playerId);
}

bool PawnHost::OnPlayerDisconnect(std::uint8_t playerId) {
    return ExecPublic("OnPlayerDisconnect", playerId);
}

bool PawnHost::OnPlayerText(std::uint8_t playerId, const std::string& text) {
    return ExecPublicString("OnPlayerText", playerId, text);
}

void PawnHost::Print(const std::string& message) {
    std::printf("[pawn] %s\n", message.c_str());
}

void PawnHost::SetGameModeText(const std::string& text) {
    gameModeText_ = text;
    std::printf("[pawn] SetGameModeText(%s)\n", gameModeText_.c_str());
}

void PawnHost::SendClientNativeCall(std::uint8_t playerId, const std::string& callName, const std::string& payload) {
    std::printf("[pawn] SendClientNativeCall(playerid=%u, call=%s, payload=%s)\n",
                playerId, callName.c_str(), payload.c_str());
    if (nativeCallSender_) {
        nativeCallSender_(playerId, callName, payload);
    }
}

bool PawnHost::IsPlayerConnected(std::uint8_t playerId) {
    PlayerState state;
    return GetPlayerState(playerId, state);
}

bool PawnHost::GetPlayerState(std::uint8_t playerId, PlayerState& outState) {
    if (!playerStateGetter_) {
        return false;
    }
    return playerStateGetter_(playerId, outState);
}

bool PawnHost::SetPlayerActorEnum(std::uint8_t playerId, std::uint16_t actorEnum) {
    if (!playerActorEnumSetter_ || actorEnum == 0) {
        return false;
    }
    return playerActorEnumSetter_(playerId, actorEnum);
}

const std::string& PawnHost::GameModeText() const {
    return gameModeText_;
}

const std::string& PawnHost::LastError() const {
    return lastError_;
}

bool PawnHost::ExecPublic(const char* name) {
    if (!amx_) {
        return false;
    }

    int index = AMX_EXEC_MAIN;
    const int findError = amx_FindPublic(amx_, name, &index);
    if (findError == AMX_ERR_NOTFOUND) {
        return true;
    }
    if (findError != AMX_ERR_NONE) {
        SetError(std::string("find public ") + name, findError);
        return false;
    }

    cell retval = 0;
    const int execError = amx_Exec(amx_, &retval, index);
    if (execError != AMX_ERR_NONE) {
        SetError(std::string("exec public ") + name, execError);
        return false;
    }
    std::printf("[pawn] %s() -> %d\n", name, static_cast<int>(retval));
    return retval != 0;
}

bool PawnHost::ExecPublic(const char* name, std::uint8_t playerId) {
    if (!amx_) {
        return false;
    }

    int index = 0;
    const int findError = amx_FindPublic(amx_, name, &index);
    if (findError == AMX_ERR_NOTFOUND) {
        return true;
    }
    if (findError != AMX_ERR_NONE) {
        SetError(std::string("find public ") + name, findError);
        return false;
    }

    int pushError = amx_Push(amx_, static_cast<cell>(playerId));
    if (pushError != AMX_ERR_NONE) {
        SetError(std::string("push args for ") + name, pushError);
        return false;
    }

    cell retval = 0;
    const int execError = amx_Exec(amx_, &retval, index);
    if (execError != AMX_ERR_NONE) {
        SetError(std::string("exec public ") + name, execError);
        return false;
    }
    std::printf("[pawn] %s(%u) -> %d\n", name, playerId, static_cast<int>(retval));
    return retval != 0;
}

bool PawnHost::ExecPublicString(const char* name, std::uint8_t playerId, const std::string& text) {
    if (!amx_) {
        return false;
    }

    int index = 0;
    const int findError = amx_FindPublic(amx_, name, &index);
    if (findError == AMX_ERR_NOTFOUND) {
        return true;
    }
    if (findError != AMX_ERR_NONE) {
        SetError(std::string("find public ") + name, findError);
        return false;
    }

    cell stringAddress = 0;
    cell* physicalAddress = nullptr;
    int pushError = amx_PushString(amx_, &stringAddress, &physicalAddress, text.c_str(), 0, 0);
    if (pushError != AMX_ERR_NONE) {
        SetError(std::string("push string for ") + name, pushError);
        return false;
    }

    pushError = amx_Push(amx_, static_cast<cell>(playerId));
    if (pushError != AMX_ERR_NONE) {
        amx_Release(amx_, stringAddress);
        SetError(std::string("push playerid for ") + name, pushError);
        return false;
    }

    cell retval = 0;
    const int execError = amx_Exec(amx_, &retval, index);
    amx_Release(amx_, stringAddress);

    if (execError != AMX_ERR_NONE) {
        SetError(std::string("exec public ") + name, execError);
        return false;
    }
    std::printf("[pawn] %s(%u, %s) -> %d\n",
                name, playerId, text.c_str(), static_cast<int>(retval));
    return retval != 0;
}

bool PawnHost::RegisterNatives() {
    const int coreError = amx_CoreInit(amx_);
    if (coreError != AMX_ERR_NONE && coreError != AMX_ERR_NOTFOUND) {
        SetError("register core natives", coreError);
        return false;
    }
    const int floatError = amx_FloatInit(amx_);
    if (floatError != AMX_ERR_NONE && floatError != AMX_ERR_NOTFOUND) {
        SetError("register float natives", floatError);
        return false;
    }
    const int nativeError = amx_Register(amx_, kCodeRedNatives, -1);
    if (nativeError != AMX_ERR_NONE) {
        SetError("register Code RED natives", nativeError);
        return false;
    }
    return true;
}

std::string PawnHost::GetStringParam(const cell* params, int index) {
    if (!amx_ || index <= 0 || params[0] < static_cast<cell>(sizeof(cell) * index)) {
        return "";
    }

    cell* source = nullptr;
    if (amx_GetAddr(amx_, params[index], &source) != AMX_ERR_NONE || !source) {
        return "";
    }

    int length = 0;
    if (amx_StrLen(source, &length) != AMX_ERR_NONE || length <= 0) {
        return "";
    }

    std::string out(static_cast<size_t>(length + 1), '\0');
    amx_GetString(&out[0], source, 0, static_cast<size_t>(length + 1));
    out.resize(std::strlen(out.c_str()));
    return out;
}

void PawnHost::SetError(const std::string& context, int error) {
    std::ostringstream out;
    out << context << " failed: " << aux_StrError(error) << " (" << error << ")";
    lastError_ = out.str();
    std::fprintf(stderr, "[pawn] %s\n", lastError_.c_str());
}

} // namespace codered_mp
