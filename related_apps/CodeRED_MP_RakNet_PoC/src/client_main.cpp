#include "codered_mp/client_net_stack.h"

#include <chrono>
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

codered_mp::ClientConfig ParseArgs(int argc, char** argv, int& seconds, RuntimeStatus& status) {
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
        } else if (arg == "--help") {
            std::puts("Usage: codered-mp-client [--host 127.0.0.1] [--port 7777] [--name marston] [--seconds 15] [--status scratch/codered_mp_client_status.json]");
            std::exit(0);
        }
    }
    return config;
}

} // namespace

int main(int argc, char** argv) {
    int seconds = 0;
    RuntimeStatus status;
    const codered_mp::ClientConfig config = ParseArgs(argc, argv, seconds, status);
    status.summary = "starting SLikeNet client";
    WriteStatus(status, config);

    codered_mp::ClientNetStack net;
    if (!net.Connect(config)) {
        std::fputs("[client] Connect failed\n", stderr);
        status.state = "connect_start_failed";
        status.summary = "SLikeNet Connect() could not start";
        WriteStatus(status, config);
        return 1;
    }

    status.state = "connecting";
    status.summary = "connecting to " + config.host + ":" + std::to_string(config.port);
    WriteStatus(status, config);

    const auto start = std::chrono::steady_clock::now();
    auto nextState = start;
    bool sentHelloChat = false;

    while (seconds <= 0 || std::chrono::steady_clock::now() - start < std::chrono::seconds(seconds)) {
        net.Pump();

        for (const codered_mp::ClientEvent& event : net.DrainEvents()) {
            status.lastEvent = event.text;
            if (event.type == codered_mp::ClientEvent::kJoinAccepted) {
                std::printf("[client] joined as playerid=%u: %s\n", event.playerId, event.text.c_str());
                status.state = "joined";
                status.playerId = event.playerId;
                status.summary = "joined playerid=" + std::to_string(event.playerId);
            } else if (event.type == codered_mp::ClientEvent::kJoinRejected) {
                std::printf("[client] join rejected: %s\n", event.text.c_str());
                status.state = "join_rejected";
                status.summary = event.text;
                WriteStatus(status, config);
                return 2;
            } else if (event.type == codered_mp::ClientEvent::kNativeCall) {
                std::printf("[client] native-call %s\n", event.text.c_str());
                status.state = "native_call";
                status.nativeCall = event.text;
                status.summary = event.text;
            } else if (event.type == codered_mp::ClientEvent::kSnapshot) {
                std::printf("[client] snapshot players=%zu\n", event.players.size());
                status.snapshotPlayers = event.players.size();
            } else if (event.type == codered_mp::ClientEvent::kChat) {
                std::printf("[client] chat %s\n", event.text.c_str());
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
        }

        if (net.IsConnected() && net.LocalPlayerId() != codered_mp::kInvalidPlayerId) {
            if (!sentHelloChat) {
                net.SendChat("hello from Code RED SLikeNet client");
                sentHelloChat = true;
            }

            const auto now = std::chrono::steady_clock::now();
            if (now >= nextState) {
                const float t = std::chrono::duration<float>(now - start).count();
                codered_mp::PlayerState state;
                state.x = std::cos(t) * 5.0f;
                state.y = std::sin(t) * 5.0f;
                state.z = 0.0f;
                state.heading = std::fmod(t * 45.0f, 360.0f);
                state.health = 100;
                net.SendPlayerState(state);
                nextState = now + std::chrono::milliseconds(100);
            }
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    net.Disconnect();
    if (seconds > 0) {
        status.state = "stopped";
        status.summary = "client stopped after timed run";
        WriteStatus(status, config);
    }
    return 0;
}
