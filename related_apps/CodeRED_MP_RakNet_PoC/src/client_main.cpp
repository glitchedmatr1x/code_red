#include "codered_mp/client_net_stack.h"

#include <chrono>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <fstream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <sys/stat.h>
#include <sys/types.h>
#endif

namespace {

struct RuntimeStatus {
    std::string path;
    std::string state = "starting";
    std::string summary = "starting";
    std::string lastEvent;
    std::string nativeCall;
    std::uint8_t playerId = codered_mp::kInvalidPlayerId;
    std::size_t snapshotPlayers = 0;
};

struct BridgeInput {
    bool hasState = false;
    std::uint32_t stateSeq = 0;
    std::uint32_t chatSeq = 0;
    std::string chat;
    codered_mp::PlayerState state;
};

std::uint16_t ParseU16(const char* text, std::uint16_t fallback) {
    if (!text) {
        return fallback;
    }
    const long value = std::strtol(text, nullptr, 10);
    if (value <= 0 || value > 65535) {
        return fallback;
    }
    return static_cast<std::uint16_t>(value);
}

int ParseInt(const char* text, int fallback) {
    if (!text) {
        return fallback;
    }
    return static_cast<int>(std::strtol(text, nullptr, 10));
}

std::string JsonEscape(const std::string& value) {
    std::ostringstream out;
    for (char c : value) {
        switch (c) {
            case '\\': out << "\\\\"; break;
            case '"': out << "\\\""; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default: out << c; break;
        }
    }
    return out.str();
}

std::string JsonStringValue(const std::string& json, const std::string& key) {
    const std::string needle = "\"" + key + "\"";
    std::size_t pos = json.find(needle);
    if (pos == std::string::npos) {
        return "";
    }
    pos = json.find(':', pos + needle.size());
    if (pos == std::string::npos) {
        return "";
    }
    pos = json.find('"', pos + 1);
    if (pos == std::string::npos) {
        return "";
    }

    std::string out;
    bool escaped = false;
    for (++pos; pos < json.size(); ++pos) {
        const char c = json[pos];
        if (escaped) {
            switch (c) {
                case 'n': out.push_back('\n'); break;
                case 'r': out.push_back('\r'); break;
                case 't': out.push_back('\t'); break;
                default: out.push_back(c); break;
            }
            escaped = false;
            continue;
        }
        if (c == '\\') {
            escaped = true;
            continue;
        }
        if (c == '"') {
            break;
        }
        out.push_back(c);
    }
    return out;
}

bool JsonNumberValue(const std::string& json, const std::string& key, double& out) {
    const std::string needle = "\"" + key + "\"";
    std::size_t pos = json.find(needle);
    if (pos == std::string::npos) {
        return false;
    }
    pos = json.find(':', pos + needle.size());
    if (pos == std::string::npos) {
        return false;
    }
    ++pos;
    while (pos < json.size() && std::isspace(static_cast<unsigned char>(json[pos]))) {
        ++pos;
    }
    const std::size_t start = pos;
    while (pos < json.size()) {
        const char c = json[pos];
        if (!(std::isdigit(static_cast<unsigned char>(c)) || c == '-' || c == '+' ||
              c == '.' || c == 'e' || c == 'E')) {
            break;
        }
        ++pos;
    }
    if (pos == start) {
        return false;
    }
    char* end = nullptr;
    out = std::strtod(json.substr(start, pos - start).c_str(), &end);
    return end && *end == '\0';
}

std::string DirnameOf(const std::string& path) {
    const std::size_t slash = path.find_last_of("\\/");
    if (slash == std::string::npos) {
        return "";
    }
    return path.substr(0, slash);
}

void CreateDirectoriesForPath(const std::string& path) {
    std::string current;
    for (char c : path) {
        current.push_back(c);
        if (c != '\\' && c != '/') {
            continue;
        }
        if (current.size() <= 3 && current.size() >= 2 && current[1] == ':') {
            continue;
        }
#ifdef _WIN32
        CreateDirectoryA(current.c_str(), nullptr);
#else
        mkdir(current.c_str(), 0755);
#endif
    }
    if (!path.empty()) {
#ifdef _WIN32
        CreateDirectoryA(path.c_str(), nullptr);
#else
        mkdir(path.c_str(), 0755);
#endif
    }
}

void CreateParentDirs(const std::string& filePath) {
    const std::string dir = DirnameOf(filePath);
    if (!dir.empty()) {
        CreateDirectoriesForPath(dir);
    }
}

void WriteStatus(const RuntimeStatus& status, const codered_mp::ClientConfig& config) {
    if (status.path.empty()) {
        return;
    }
    CreateParentDirs(status.path);

    std::ofstream file(status.path.c_str(), std::ios::trunc);
    if (!file) {
        return;
    }

    const std::time_t now = std::time(nullptr);
    file << "{\n";
    file << "  \"source\": \"codered-mp-client\",\n";
    file << "  \"transport\": \"slikenet\",\n";
    file << "  \"host\": \"" << JsonEscape(config.host) << "\",\n";
    file << "  \"port\": " << config.port << ",\n";
    file << "  \"name\": \"" << JsonEscape(config.name) << "\",\n";
    file << "  \"state\": \"" << JsonEscape(status.state) << "\",\n";
    file << "  \"summary\": \"" << JsonEscape(status.summary) << "\",\n";
    file << "  \"last_event\": \"" << JsonEscape(status.lastEvent) << "\",\n";
    file << "  \"native_call\": \"" << JsonEscape(status.nativeCall) << "\",\n";
    if (status.playerId != codered_mp::kInvalidPlayerId) {
        file << "  \"player_id\": " << static_cast<unsigned int>(status.playerId) << ",\n";
    } else {
        file << "  \"player_id\": null,\n";
    }
    file << "  \"snapshot_players\": " << status.snapshotPlayers << ",\n";
    file << "  \"timestamp\": " << static_cast<long long>(now) << "\n";
    file << "}\n";
}

std::string ReadSmallTextFile(const std::string& path, std::size_t maxBytes = 32768) {
    std::ifstream file(path.c_str(), std::ios::binary);
    if (!file) {
        return "";
    }
    std::ostringstream out;
    char buffer[1024] = {};
    std::size_t total = 0;
    while (file && total < maxBytes) {
        const std::size_t remaining = maxBytes - total;
        const std::size_t want = remaining < sizeof(buffer) ? remaining : sizeof(buffer);
        file.read(buffer, static_cast<std::streamsize>(want));
        const std::streamsize got = file.gcount();
        if (got <= 0) {
            break;
        }
        out.write(buffer, got);
        total += static_cast<std::size_t>(got);
    }
    return out.str();
}

unsigned long long FileWriteTime(const std::string& path) {
#ifdef _WIN32
    WIN32_FILE_ATTRIBUTE_DATA data = {};
    if (!GetFileAttributesExA(path.c_str(), GetFileExInfoStandard, &data)) {
        return 0;
    }
    return (static_cast<unsigned long long>(data.ftLastWriteTime.dwHighDateTime) << 32) |
           static_cast<unsigned long long>(data.ftLastWriteTime.dwLowDateTime);
#else
    struct stat data = {};
    if (stat(path.c_str(), &data) != 0) {
        return 0;
    }
#if defined(__APPLE__)
    return static_cast<unsigned long long>(data.st_mtimespec.tv_sec) * 1000000000ULL +
           static_cast<unsigned long long>(data.st_mtimespec.tv_nsec);
#else
    return static_cast<unsigned long long>(data.st_mtim.tv_sec) * 1000000000ULL +
           static_cast<unsigned long long>(data.st_mtim.tv_nsec);
#endif
#endif
}

bool LoadBridgeInput(const std::string& path, BridgeInput& out) {
    const std::string json = ReadSmallTextFile(path);
    if (json.empty()) {
        return false;
    }

    BridgeInput parsed;
    double value = 0.0;
    if (JsonNumberValue(json, "state_seq", value)) {
        parsed.stateSeq = static_cast<std::uint32_t>(value);
        parsed.state.sequence = parsed.stateSeq;
    }
    if (JsonNumberValue(json, "chat_seq", value)) {
        parsed.chatSeq = static_cast<std::uint32_t>(value);
    }
    parsed.chat = JsonStringValue(json, "chat");

    if (JsonNumberValue(json, "x", value)) {
        parsed.state.x = static_cast<float>(value);
        parsed.hasState = true;
    }
    if (JsonNumberValue(json, "y", value)) {
        parsed.state.y = static_cast<float>(value);
        parsed.hasState = true;
    }
    if (JsonNumberValue(json, "z", value)) {
        parsed.state.z = static_cast<float>(value);
        parsed.hasState = true;
    }
    if (JsonNumberValue(json, "heading", value)) {
        parsed.state.heading = static_cast<float>(value);
        parsed.hasState = true;
    }
    if (JsonNumberValue(json, "health", value)) {
        parsed.state.health = static_cast<std::uint16_t>(value);
    }
    if (JsonNumberValue(json, "flags", value)) {
        parsed.state.flags = static_cast<std::uint16_t>(value);
    }
    if (JsonNumberValue(json, "actor_enum", value)) {
        parsed.state.actorEnum = static_cast<std::uint16_t>(value);
    }

    out = parsed;
    return true;
}

void WritePlayerStateJson(std::ofstream& file, const codered_mp::PlayerState& state) {
    file << "{\"player_id\":" << static_cast<unsigned int>(state.playerId)
         << ",\"x\":" << state.x
         << ",\"y\":" << state.y
         << ",\"z\":" << state.z
         << ",\"heading\":" << state.heading
         << ",\"health\":" << state.health
         << ",\"flags\":" << state.flags
         << ",\"actor_enum\":" << state.actorEnum
         << ",\"sequence\":" << state.sequence
         << "}";
}

void WriteBridgeOutput(const std::string& path,
                       const RuntimeStatus& status,
                       const codered_mp::ClientConfig& config,
                       const std::vector<codered_mp::PlayerState>& snapshot,
                       const codered_mp::PlayerState& spawnState,
                       bool hasSpawn,
                       const std::vector<std::string>& chatHistory,
                       const std::vector<std::string>& nativeCalls) {
    if (path.empty()) {
        return;
    }
    CreateParentDirs(path);

    std::ofstream file(path.c_str(), std::ios::trunc);
    if (!file) {
        return;
    }

    const std::time_t now = std::time(nullptr);
    file << "{\n";
    file << "  \"source\": \"codered-mp-client\",\n";
    file << "  \"transport\": \"slikenet\",\n";
    file << "  \"host\": \"" << JsonEscape(config.host) << "\",\n";
    file << "  \"port\": " << config.port << ",\n";
    file << "  \"name\": \"" << JsonEscape(config.name) << "\",\n";
    file << "  \"state\": \"" << JsonEscape(status.state) << "\",\n";
    file << "  \"summary\": \"" << JsonEscape(status.summary) << "\",\n";
    if (status.playerId != codered_mp::kInvalidPlayerId) {
        file << "  \"player_id\": " << static_cast<unsigned int>(status.playerId) << ",\n";
    } else {
        file << "  \"player_id\": null,\n";
    }
    file << "  \"spawn_valid\": " << (hasSpawn ? "true" : "false") << ",\n";
    file << "  \"spawn_x\": " << spawnState.x << ",\n";
    file << "  \"spawn_y\": " << spawnState.y << ",\n";
    file << "  \"spawn_z\": " << spawnState.z << ",\n";
    file << "  \"spawn_heading\": " << spawnState.heading << ",\n";
    file << "  \"spawn_actor_enum\": " << spawnState.actorEnum << ",\n";
    file << "  \"snapshot_players\": " << snapshot.size() << ",\n";
    file << "  \"players\": [\n";
    for (std::size_t i = 0; i < snapshot.size(); ++i) {
        file << "    ";
        WritePlayerStateJson(file, snapshot[i]);
        if (i + 1 < snapshot.size()) {
            file << ",";
        }
        file << "\n";
    }
    file << "  ],\n";
    file << "  \"chat\": [\n";
    for (std::size_t i = 0; i < chatHistory.size(); ++i) {
        file << "    \"" << JsonEscape(chatHistory[i]) << "\"";
        if (i + 1 < chatHistory.size()) {
            file << ",";
        }
        file << "\n";
    }
    file << "  ],\n";
    file << "  \"native_calls\": [\n";
    for (std::size_t i = 0; i < nativeCalls.size(); ++i) {
        file << "    \"" << JsonEscape(nativeCalls[i]) << "\"";
        if (i + 1 < nativeCalls.size()) {
            file << ",";
        }
        file << "\n";
    }
    file << "  ],\n";
    file << "  \"timestamp\": " << static_cast<long long>(now) << "\n";
    file << "}\n";
}

codered_mp::ClientConfig ParseArgs(int argc, char** argv, int& seconds, RuntimeStatus& status,
                                   std::string& bridgeIn, std::string& bridgeOut) {
    codered_mp::ClientConfig config;
    seconds = 15;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--host" && i + 1 < argc) {
            config.host = argv[++i];
        } else if (arg == "--port" && i + 1 < argc) {
            config.port = ParseU16(argv[++i], config.port);
        } else if (arg == "--local-port" && i + 1 < argc) {
            config.localPort = ParseU16(argv[++i], config.localPort);
        } else if (arg == "--name" && i + 1 < argc) {
            config.name = argv[++i];
        } else if (arg == "--seconds" && i + 1 < argc) {
            seconds = ParseInt(argv[++i], seconds);
        } else if (arg == "--status" && i + 1 < argc) {
            status.path = argv[++i];
        } else if (arg == "--bridge-in" && i + 1 < argc) {
            bridgeIn = argv[++i];
        } else if (arg == "--bridge-out" && i + 1 < argc) {
            bridgeOut = argv[++i];
        } else if (arg == "--help") {
            std::puts("Usage: codered-mp-client [--host 127.0.0.1] [--port 7777] [--name marston] [--seconds 15] [--status scratch/codered_mp_client_status.json] [--bridge-in scratch/codered_mp_local_state.json] [--bridge-out scratch/codered_mp_world_state.json]");
            std::exit(0);
        }
    }
    return config;
}

} // namespace

int main(int argc, char** argv) {
    int seconds = 0;
    RuntimeStatus status;
    std::string bridgeInPath;
    std::string bridgeOutPath;
    const codered_mp::ClientConfig config = ParseArgs(argc, argv, seconds, status, bridgeInPath, bridgeOutPath);
    status.summary = "starting SLikeNet client";
    WriteStatus(status, config);

    std::vector<codered_mp::PlayerState> lastSnapshot;
    std::vector<std::string> chatHistory;
    std::vector<std::string> nativeCalls;
    std::uint32_t nativeCallSeq = 0;
    codered_mp::PlayerState spawnState;
    bool hasSpawn = false;
    WriteBridgeOutput(bridgeOutPath, status, config, lastSnapshot, spawnState, hasSpawn, chatHistory, nativeCalls);

    codered_mp::ClientNetStack net;
    if (!net.Connect(config)) {
        std::fputs("[client] Connect failed\n", stderr);
        status.state = "connect_start_failed";
        status.summary = "SLikeNet Connect() could not start";
        WriteStatus(status, config);
        WriteBridgeOutput(bridgeOutPath, status, config, lastSnapshot, spawnState, hasSpawn, chatHistory, nativeCalls);
        return 1;
    }

    status.state = "connecting";
    status.summary = "connecting to " + config.host + ":" + std::to_string(config.port);
    WriteStatus(status, config);
    WriteBridgeOutput(bridgeOutPath, status, config, lastSnapshot, spawnState, hasSpawn, chatHistory, nativeCalls);

    const auto start = std::chrono::steady_clock::now();
    auto nextState = start;
    bool sentHelloChat = false;
    unsigned long long bridgeInputWriteTime = 0;
    BridgeInput bridgeInput;
    std::uint32_t sentStateSeq = 0;
    std::uint32_t sentChatSeq = 0;

    while (seconds <= 0 || std::chrono::steady_clock::now() - start < std::chrono::seconds(seconds)) {
        net.Pump();
        bool bridgeDirty = false;

        for (const codered_mp::ClientEvent& event : net.DrainEvents()) {
            status.lastEvent = event.text;
            if (event.type == codered_mp::ClientEvent::kJoinAccepted) {
                std::printf("[client] joined as playerid=%u: %s\n", event.playerId, event.text.c_str());
                status.state = "joined";
                status.playerId = event.playerId;
                status.summary = "joined playerid=" + std::to_string(event.playerId);
                if (!event.players.empty()) {
                    spawnState = event.players.front();
                    hasSpawn = true;
                }
            } else if (event.type == codered_mp::ClientEvent::kJoinRejected) {
                std::printf("[client] join rejected: %s\n", event.text.c_str());
                status.state = "join_rejected";
                status.summary = event.text;
                WriteStatus(status, config);
                WriteBridgeOutput(bridgeOutPath, status, config, lastSnapshot, spawnState, hasSpawn, chatHistory, nativeCalls);
                return 2;
            } else if (event.type == codered_mp::ClientEvent::kNativeCall) {
                std::printf("[client] native-call %s\n", event.text.c_str());
                status.state = "native_call";
                status.nativeCall = event.text;
                status.summary = event.text;
                nativeCalls.push_back(std::to_string(++nativeCallSeq) + "|" + event.text);
                if (nativeCalls.size() > 16) {
                    nativeCalls.erase(nativeCalls.begin(), nativeCalls.end() - 16);
                }
            } else if (event.type == codered_mp::ClientEvent::kSnapshot) {
                std::printf("[client] snapshot players=%zu\n", event.players.size());
                if (status.playerId != codered_mp::kInvalidPlayerId) {
                    status.state = "joined";
                }
                status.nativeCall.clear();
                status.snapshotPlayers = event.players.size();
                lastSnapshot = event.players;
            } else if (event.type == codered_mp::ClientEvent::kChat) {
                std::printf("[client] chat %s\n", event.text.c_str());
                if (status.playerId != codered_mp::kInvalidPlayerId) {
                    status.state = "joined";
                }
                status.nativeCall.clear();
                status.summary = event.text;
                chatHistory.push_back(event.text);
                if (chatHistory.size() > 16) {
                    chatHistory.erase(chatHistory.begin(), chatHistory.end() - 16);
                }
            } else {
                std::printf("[client] %s\n", event.text.c_str());
                if (event.type == codered_mp::ClientEvent::kConnected) {
                    status.state = "connected";
                    status.summary = event.text;
                } else if (event.type == codered_mp::ClientEvent::kDisconnected) {
                    status.state = "disconnected";
                    status.summary = event.text;
                }
            }
            WriteStatus(status, config);
            bridgeDirty = true;
        }

        if (net.IsConnected() && net.LocalPlayerId() != codered_mp::kInvalidPlayerId) {
            const unsigned long long writeTime = bridgeInPath.empty() ? 0 : FileWriteTime(bridgeInPath);
            if (writeTime != 0 && writeTime != bridgeInputWriteTime) {
                bridgeInputWriteTime = writeTime;
                if (LoadBridgeInput(bridgeInPath, bridgeInput)) {
                    if (!bridgeInput.chat.empty() && bridgeInput.chatSeq != 0 && bridgeInput.chatSeq != sentChatSeq) {
                        net.SendChat(bridgeInput.chat);
                        sentChatSeq = bridgeInput.chatSeq;
                    }
                }
            }

            if (bridgeInPath.empty() && !sentHelloChat) {
                net.SendChat("hello from Code RED SLikeNet client");
                sentHelloChat = true;
            }

            const auto now = std::chrono::steady_clock::now();
            if (now >= nextState) {
                if (bridgeInput.hasState) {
                    codered_mp::PlayerState state = bridgeInput.state;
                    state.playerId = net.LocalPlayerId();
                    if (state.actorEnum == 0) {
                        state.actorEnum = hasSpawn ? spawnState.actorEnum : codered_mp::kDefaultActorEnum;
                    }
                    net.SendPlayerState(state);
                    sentStateSeq = state.sequence;
                } else if (bridgeInPath.empty()) {
                    const float t = std::chrono::duration<float>(now - start).count();
                    codered_mp::PlayerState state;
                    state.x = std::cos(t) * 5.0f;
                    state.y = std::sin(t) * 5.0f;
                    state.z = 0.0f;
                    state.heading = std::fmod(t * 45.0f, 360.0f);
                    state.health = 100;
                    state.actorEnum = hasSpawn ? spawnState.actorEnum : codered_mp::kDefaultActorEnum;
                    state.sequence = ++sentStateSeq;
                    net.SendPlayerState(state);
                }
                nextState = now + std::chrono::milliseconds(100);
            }
        }

        if (bridgeDirty) {
            WriteBridgeOutput(bridgeOutPath, status, config, lastSnapshot, spawnState, hasSpawn, chatHistory, nativeCalls);
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    net.Disconnect();
    if (seconds > 0) {
        status.state = "stopped";
        status.summary = "client stopped after timed run";
        WriteStatus(status, config);
        WriteBridgeOutput(bridgeOutPath, status, config, lastSnapshot, spawnState, hasSpawn, chatHistory, nativeCalls);
    }
    return 0;
}
