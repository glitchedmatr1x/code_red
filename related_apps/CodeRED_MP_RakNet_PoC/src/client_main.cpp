#include "codered_mp/client_net_stack.h"

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <thread>

namespace {

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

codered_mp::ClientConfig ParseArgs(int argc, char** argv, int& seconds) {
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
        } else if (arg == "--help") {
            std::puts("Usage: codered-mp-client [--host 127.0.0.1] [--port 7777] [--name marston] [--seconds 15]");
            std::exit(0);
        }
    }
    return config;
}

} // namespace

int main(int argc, char** argv) {
    int seconds = 0;
    const codered_mp::ClientConfig config = ParseArgs(argc, argv, seconds);

    codered_mp::ClientNetStack net;
    if (!net.Connect(config)) {
        std::fputs("[client] Connect failed\n", stderr);
        return 1;
    }

    const auto start = std::chrono::steady_clock::now();
    auto nextState = start;
    bool sentHelloChat = false;

    while (seconds <= 0 || std::chrono::steady_clock::now() - start < std::chrono::seconds(seconds)) {
        net.Pump();

        for (const codered_mp::ClientEvent& event : net.DrainEvents()) {
            if (event.type == codered_mp::ClientEvent::kJoinAccepted) {
                std::printf("[client] joined as playerid=%u: %s\n", event.playerId, event.text.c_str());
            } else if (event.type == codered_mp::ClientEvent::kJoinRejected) {
                std::printf("[client] join rejected: %s\n", event.text.c_str());
                return 2;
            } else if (event.type == codered_mp::ClientEvent::kSnapshot) {
                std::printf("[client] snapshot players=%zu\n", event.players.size());
            } else if (event.type == codered_mp::ClientEvent::kChat) {
                std::printf("[client] chat %s\n", event.text.c_str());
            } else {
                std::printf("[client] %s\n", event.text.c_str());
            }
        }

        if (net.IsConnected() && net.LocalPlayerId() != codered_mp::kInvalidPlayerId) {
            if (!sentHelloChat) {
                net.SendChat("hello from Code RED RakNet client");
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
    return 0;
}
