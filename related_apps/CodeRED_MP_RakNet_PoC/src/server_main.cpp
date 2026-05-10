#include "codered_mp/pawn_host.h"
#include "codered_mp/protocol.h"

#include <array>
#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <thread>

#include <slikenet/peerinterface.h>

namespace {

std::atomic<bool> g_stopRequested{false};

struct PeerSlot {
    bool active = false;
    SLNet::SystemAddress address = SLNet::UNASSIGNED_SYSTEM_ADDRESS;
    std::string name;
    codered_mp::PlayerState state;
};

void OnSignal(int) {
    g_stopRequested = true;
}

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

struct ServerConfig {
    std::uint16_t port = codered_mp::kDefaultPort;
    std::uint16_t maxPlayers = 16;
    const char* bind = nullptr;
    std::string gamemode = "gamemodes/codered_hello.amx";
    std::string spawnPreset = "escalera-mptransport";
    float spawnX = -4265.4355f;
    float spawnY = 4475.8091f;
    float spawnZ = 19.1414f;
    float spawnHeading = 31.9f;
    float spawnSpacing = 2.5f;
};

bool ApplySpawnPreset(ServerConfig& config, const std::string& preset) {
    if (preset == "origin") {
        config.spawnPreset = preset;
        config.spawnX = 0.0f;
        config.spawnY = 0.0f;
        config.spawnZ = 0.0f;
        config.spawnHeading = 0.0f;
        return true;
    }
    if (preset == "escalera" || preset == "escalera-mptransport" ||
        preset == "escalera-market") {
        config.spawnPreset = "escalera-mptransport";
        config.spawnX = -4265.4355f;
        config.spawnY = 4475.8091f;
        config.spawnZ = 19.1414f;
        config.spawnHeading = 31.9f;
        return true;
    }
    if (preset == "escalera-trainer") {
        config.spawnPreset = "escalera-trainer";
        config.spawnX = -4279.04f;
        config.spawnY = 4447.64f;
        config.spawnZ = 18.07f;
        config.spawnHeading = 90.0f;
        return true;
    }
    if (preset == "escalera-legacy" || preset == "escalera-market-legacy") {
        config.spawnPreset = "escalera-legacy";
        config.spawnX = -4285.0f;
        config.spawnY = -3475.0f;
        config.spawnZ = 45.0f;
        config.spawnHeading = 90.0f;
        return true;
    }
    return false;
}

ServerConfig ParseArgs(int argc, char** argv) {
    ServerConfig config;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--port" && i + 1 < argc) {
            config.port = ParseU16(argv[++i], config.port);
        } else if (arg == "--maxplayers" && i + 1 < argc) {
            config.maxPlayers = ParseU16(argv[++i], config.maxPlayers);
        } else if (arg == "--bind" && i + 1 < argc) {
            config.bind = argv[++i];
        } else if ((arg == "--gamemode" || arg == "--amx") && i + 1 < argc) {
            config.gamemode = argv[++i];
        } else if (arg == "--spawn-preset" && i + 1 < argc) {
            const std::string preset = argv[++i];
            if (!ApplySpawnPreset(config, preset)) {
                std::fprintf(stderr, "[server] unknown spawn preset '%s' (known: escalera, escalera-mptransport, escalera-trainer, escalera-legacy, origin)\n",
                             preset.c_str());
                std::exit(2);
            }
        } else if (arg == "--spawn-x" && i + 1 < argc) {
            config.spawnX = static_cast<float>(std::strtod(argv[++i], nullptr));
            config.spawnPreset = "custom";
        } else if (arg == "--spawn-y" && i + 1 < argc) {
            config.spawnY = static_cast<float>(std::strtod(argv[++i], nullptr));
            config.spawnPreset = "custom";
        } else if (arg == "--spawn-z" && i + 1 < argc) {
            config.spawnZ = static_cast<float>(std::strtod(argv[++i], nullptr));
            config.spawnPreset = "custom";
        } else if (arg == "--spawn-heading" && i + 1 < argc) {
            config.spawnHeading = static_cast<float>(std::strtod(argv[++i], nullptr));
            config.spawnPreset = "custom";
        } else if (arg == "--spawn-spacing" && i + 1 < argc) {
            config.spawnSpacing = static_cast<float>(std::strtod(argv[++i], nullptr));
            config.spawnPreset = "custom";
        } else if (arg == "--help") {
            std::puts("Usage: codered-mp-server [--bind 0.0.0.0] [--port 7777] [--maxplayers 16] [--gamemode gamemodes/codered_hello.amx] [--spawn-preset escalera-mptransport|escalera-trainer|escalera-legacy|origin] [--spawn-x -4265.4355] [--spawn-y 4475.8091] [--spawn-z 19.1414] [--spawn-heading 31.9] [--spawn-spacing 2.5]");
            std::exit(0);
        }
    }
    return config;
}

codered_mp::PlayerState MakeSpawnState(const ServerConfig& config, std::uint8_t slot) {
    codered_mp::PlayerState state;
    state.playerId = slot;
    state.x = config.spawnX + static_cast<float>(slot % 4) * config.spawnSpacing;
    state.y = config.spawnY + static_cast<float>(slot / 4) * config.spawnSpacing;
    state.z = config.spawnZ;
    state.heading = config.spawnHeading;
    state.health = 100;
    state.flags = 0;
    state.actorEnum = static_cast<std::uint16_t>(codered_mp::kDefaultActorEnum + (slot % 8));
    state.sequence = 0;
    return state;
}

std::uint8_t AllocateSlot(std::array<PeerSlot, 32>& peers, SLNet::SystemAddress address, const ServerConfig& config) {
    for (std::uint8_t i = 0; i < peers.size(); ++i) {
        if (!peers[i].active) {
            peers[i].active = true;
            peers[i].address = address;
            peers[i].state = MakeSpawnState(config, i);
            return i;
        }
    }
    return codered_mp::kInvalidPlayerId;
}

std::uint8_t FindSlot(const std::array<PeerSlot, 32>& peers, SLNet::SystemAddress address) {
    for (std::uint8_t i = 0; i < peers.size(); ++i) {
        if (peers[i].active && peers[i].address == address) {
            return i;
        }
    }
    return codered_mp::kInvalidPlayerId;
}

void SendJoinAccepted(SLNet::RakPeerInterface* server, const PeerSlot& peer) {
    SLNet::BitStream out;
    out.Write(static_cast<unsigned char>(codered_mp::kMsgJoinAccepted));
    out.Write(peer.state.playerId);
    codered_mp::WritePlayerState(out, peer.state);
    codered_mp::WriteString(out, "Code RED MP PoC accepted", codered_mp::kMaxChatLength);
    server->Send(&out, HIGH_PRIORITY, RELIABLE_ORDERED, 0, peer.address, false);
}

void SendJoinRejected(SLNet::RakPeerInterface* server, SLNet::SystemAddress target, const std::string& reason) {
    SLNet::BitStream out;
    out.Write(static_cast<unsigned char>(codered_mp::kMsgJoinRejected));
    codered_mp::WriteString(out, reason, codered_mp::kMaxChatLength);
    server->Send(&out, HIGH_PRIORITY, RELIABLE_ORDERED, 0, target, false);
}

void SendNativeCall(SLNet::RakPeerInterface* server, const PeerSlot& peer,
                    const std::string& callName, const std::string& payload) {
    SLNet::BitStream out;
    out.Write(static_cast<unsigned char>(codered_mp::kMsgNativeCall));
    codered_mp::WriteString(out, callName, codered_mp::kMaxNativeCallLength);
    codered_mp::WriteString(out, payload, codered_mp::kMaxChatLength);
    server->Send(&out, HIGH_PRIORITY, RELIABLE_ORDERED, 0, peer.address, false);
}

void BroadcastSnapshot(SLNet::RakPeerInterface* server, const std::array<PeerSlot, 32>& peers) {
    SLNet::BitStream out;
    out.Write(static_cast<unsigned char>(codered_mp::kMsgWorldSnapshot));

    std::uint8_t count = 0;
    for (const PeerSlot& peer : peers) {
        if (peer.active) {
            ++count;
        }
    }
    out.Write(count);
    for (const PeerSlot& peer : peers) {
        if (peer.active) {
            codered_mp::WritePlayerState(out, peer.state);
        }
    }

    server->Send(&out, MEDIUM_PRIORITY, UNRELIABLE_SEQUENCED, 0, SLNet::UNASSIGNED_SYSTEM_ADDRESS, true);
}

void BroadcastChat(SLNet::RakPeerInterface* server, std::uint8_t playerId, const std::string& text) {
    SLNet::BitStream out;
    out.Write(static_cast<unsigned char>(codered_mp::kMsgChat));
    codered_mp::WriteString(out, "[" + std::to_string(playerId) + "] " + text, codered_mp::kMaxChatLength);
    server->Send(&out, HIGH_PRIORITY, RELIABLE_ORDERED, 0, SLNet::UNASSIGNED_SYSTEM_ADDRESS, true);
}

} // namespace

int main(int argc, char** argv) {
    const ServerConfig config = ParseArgs(argc, argv);
    std::signal(SIGINT, OnSignal);
    std::signal(SIGTERM, OnSignal);

    SLNet::RakPeerInterface* server = SLNet::RakPeerInterface::GetInstance();
    if (!server) {
        std::fputs("[server] failed to create SLikeNet RakPeerInterface\n", stderr);
        return 1;
    }

    server->DisableSecurity();
    SLNet::SocketDescriptor descriptor(config.port, config.bind);
    const SLNet::StartupResult startup = server->Startup(config.maxPlayers, &descriptor, 1);
    if (startup != SLNet::RAKNET_STARTED) {
        std::fprintf(stderr, "[server] unable to start on %s:%u\n",
                     config.bind ? config.bind : "0.0.0.0", config.port);
        std::fprintf(stderr, "[server] SLikeNet Startup() result=%d\n", static_cast<int>(startup));
        SLNet::RakPeerInterface::DestroyInstance(server);
        return 1;
    }
    server->SetMaximumIncomingConnections(config.maxPlayers);

    std::array<PeerSlot, 32> peers;
    codered_mp::PawnHost script;
    if (!script.Load(config.gamemode, [&](std::uint8_t playerId, const std::string& callName, const std::string& payload) {
            if (playerId >= peers.size() || !peers[playerId].active) {
                std::printf("[server] native-call target is not active: playerid=%u call=%s\n",
                            playerId, callName.c_str());
                return;
            }
            SendNativeCall(server, peers[playerId], callName, payload);
        },
        [&](std::uint8_t playerId, codered_mp::PlayerState& outState) {
            if (playerId >= peers.size() || !peers[playerId].active) {
                return false;
            }
            outState = peers[playerId].state;
            return true;
        },
        [&](std::uint8_t playerId, std::uint16_t actorEnum) {
            if (playerId >= peers.size() || !peers[playerId].active || actorEnum == 0) {
                return false;
            }
            peers[playerId].state.actorEnum = actorEnum;
            return true;
        })) {
        std::fprintf(stderr, "[server] Pawn gamemode failed: %s\n", script.LastError().c_str());
        server->Shutdown(100);
        SLNet::RakPeerInterface::DestroyInstance(server);
        return 1;
    }
    script.OnGameModeInit();
    std::printf("[server] Code RED MP SLikeNet PoC listening on %s:%u maxplayers=%u\n",
                config.bind ? config.bind : "0.0.0.0", config.port, config.maxPlayers);
    std::printf("[server] gamemode=%s text=%s\n", config.gamemode.c_str(), script.GameModeText().c_str());
    std::printf("[server] spawn preset=%s pos=(%.2f, %.2f, %.2f) heading=%.2f spacing=%.2f\n",
                config.spawnPreset.c_str(), config.spawnX, config.spawnY, config.spawnZ,
                config.spawnHeading, config.spawnSpacing);

    auto nextSnapshot = std::chrono::steady_clock::now();

    while (!g_stopRequested) {
        for (SLNet::Packet* packet = server->Receive(); packet; packet = server->Receive()) {
            const std::uint8_t packetId = codered_mp::GetPacketId(packet);
            if (packetId == ID_NEW_INCOMING_CONNECTION) {
                std::printf("[server] SLikeNet incoming connection from %s\n",
                            packet->systemAddress.ToString(true));
            } else if (packetId == ID_DISCONNECTION_NOTIFICATION || packetId == ID_CONNECTION_LOST) {
                const std::uint8_t slot = FindSlot(peers, packet->systemAddress);
                if (slot != codered_mp::kInvalidPlayerId) {
                    peers[slot] = PeerSlot{};
                    script.OnPlayerDisconnect(slot);
                }
            } else if (packetId >= codered_mp::kMsgJoinRequest) {
                SLNet::BitStream in(packet->data, packet->length, false);
                unsigned char messageId = 0;
                if (in.Read(messageId)) {
                    if (messageId == codered_mp::kMsgJoinRequest) {
                        std::uint32_t version = 0;
                        std::string name;
                        if (!in.Read(version) || !codered_mp::ReadString(in, name, codered_mp::kMaxNameLength)) {
                            SendJoinRejected(server, packet->systemAddress, "malformed join");
                        } else if (version != codered_mp::kProtocolVersion) {
                            SendJoinRejected(server, packet->systemAddress, "protocol mismatch");
                        } else {
                            std::uint8_t slot = FindSlot(peers, packet->systemAddress);
                            if (slot == codered_mp::kInvalidPlayerId) {
                                slot = AllocateSlot(peers, packet->systemAddress, config);
                            }
                            if (slot == codered_mp::kInvalidPlayerId) {
                                SendJoinRejected(server, packet->systemAddress, "server full");
                            } else {
                                peers[slot].name = name;
                                SendJoinAccepted(server, peers[slot]);
                                script.OnPlayerConnect(slot);
                            }
                        }
                    } else if (messageId == codered_mp::kMsgPlayerState) {
                        codered_mp::PlayerState state;
                        const std::uint8_t slot = FindSlot(peers, packet->systemAddress);
                        if (slot != codered_mp::kInvalidPlayerId && codered_mp::ReadPlayerState(in, state)) {
                            const std::uint16_t actorEnum = peers[slot].state.actorEnum;
                            state.playerId = slot;
                            state.actorEnum = actorEnum;
                            peers[slot].state = state;
                        }
                    } else if (messageId == codered_mp::kMsgChat) {
                        std::string text;
                        const std::uint8_t slot = FindSlot(peers, packet->systemAddress);
                        if (slot != codered_mp::kInvalidPlayerId && codered_mp::ReadString(in, text, codered_mp::kMaxChatLength)) {
                            if (script.OnPlayerText(slot, text)) {
                                BroadcastChat(server, slot, text);
                            }
                        }
                    }
                }
            }

            server->DeallocatePacket(packet);
        }

        const auto now = std::chrono::steady_clock::now();
        if (now >= nextSnapshot) {
            BroadcastSnapshot(server, peers);
            nextSnapshot = now + std::chrono::milliseconds(100);
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
    }

    std::puts("[server] shutting down");
    server->Shutdown(100);
    SLNet::RakPeerInterface::DestroyInstance(server);
    return 0;
}
