#include "codered_mp/protocol.h"

#include <array>
#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <thread>

#include <raknet/RakNetworkFactory.h>
#include <raknet/RakServerInterface.h>

namespace {

std::atomic<bool> g_stopRequested{false};

struct PeerSlot {
    bool active = false;
    RakNet::PlayerID address = RakNet::UNASSIGNED_PLAYER_ID;
    std::string name;
    codered_mp::PlayerState state;
};

class ScriptHostStub {
public:
    void OnGameModeInit() {
        std::puts("[script] OnGameModeInit()");
    }

    void OnPlayerConnect(std::uint8_t playerId, const std::string& name) {
        std::printf("[script] OnPlayerConnect(playerid=%u, name=%s)\n", playerId, name.c_str());
    }

    void OnPlayerDisconnect(std::uint8_t playerId) {
        std::printf("[script] OnPlayerDisconnect(playerid=%u)\n", playerId);
    }

    void OnPlayerUpdate(const codered_mp::PlayerState& state) {
        std::printf("[script] OnPlayerUpdate(playerid=%u, pos=%.2f %.2f %.2f)\n",
                    state.playerId, state.x, state.y, state.z);
    }

    void OnPlayerText(std::uint8_t playerId, const std::string& text) {
        std::printf("[script] OnPlayerText(playerid=%u, text=%s)\n", playerId, text.c_str());
    }
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
};

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
        } else if (arg == "--help") {
            std::puts("Usage: codered-mp-server [--bind 0.0.0.0] [--port 7777] [--maxplayers 16]");
            std::exit(0);
        }
    }
    return config;
}

std::uint8_t AllocateSlot(std::array<PeerSlot, 32>& peers, RakNet::PlayerID address) {
    for (std::uint8_t i = 0; i < peers.size(); ++i) {
        if (!peers[i].active) {
            peers[i].active = true;
            peers[i].address = address;
            peers[i].state.playerId = i;
            peers[i].state.health = 100;
            return i;
        }
    }
    return codered_mp::kInvalidPlayerId;
}

std::uint8_t FindSlot(const std::array<PeerSlot, 32>& peers, RakNet::PlayerID address) {
    for (std::uint8_t i = 0; i < peers.size(); ++i) {
        if (peers[i].active && peers[i].address == address) {
            return i;
        }
    }
    return codered_mp::kInvalidPlayerId;
}

void SendJoinAccepted(RakNet::RakServerInterface* server, const PeerSlot& peer) {
    RakNet::BitStream out;
    out.Write(static_cast<unsigned char>(codered_mp::kMsgJoinAccepted));
    out.Write(peer.state.playerId);
    codered_mp::WriteString(out, "Code RED MP PoC accepted", codered_mp::kMaxChatLength);
    server->Send(&out, RakNet::HIGH_PRIORITY, RakNet::RELIABLE_ORDERED, 0, peer.address, false);
}

void SendJoinRejected(RakNet::RakServerInterface* server, RakNet::PlayerID target, const std::string& reason) {
    RakNet::BitStream out;
    out.Write(static_cast<unsigned char>(codered_mp::kMsgJoinRejected));
    codered_mp::WriteString(out, reason, codered_mp::kMaxChatLength);
    server->Send(&out, RakNet::HIGH_PRIORITY, RakNet::RELIABLE_ORDERED, 0, target, false);
}

void BroadcastSnapshot(RakNet::RakServerInterface* server, const std::array<PeerSlot, 32>& peers) {
    RakNet::BitStream out;
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

    server->Send(&out, RakNet::MEDIUM_PRIORITY, RakNet::UNRELIABLE_SEQUENCED, 0, RakNet::UNASSIGNED_PLAYER_ID, true);
}

void BroadcastChat(RakNet::RakServerInterface* server, std::uint8_t playerId, const std::string& text) {
    RakNet::BitStream out;
    out.Write(static_cast<unsigned char>(codered_mp::kMsgChat));
    codered_mp::WriteString(out, "[" + std::to_string(playerId) + "] " + text, codered_mp::kMaxChatLength);
    server->Send(&out, RakNet::HIGH_PRIORITY, RakNet::RELIABLE_ORDERED, 0, RakNet::UNASSIGNED_PLAYER_ID, true);
}

} // namespace

int main(int argc, char** argv) {
    const ServerConfig config = ParseArgs(argc, argv);
    std::signal(SIGINT, OnSignal);
    std::signal(SIGTERM, OnSignal);

    RakNet::RakServerInterface* server = RakNet::RakNetworkFactory::GetRakServerInterface();
    if (!server) {
        std::fputs("[server] failed to create RakServerInterface\n", stderr);
        return 1;
    }

    server->DisableSecurity();
    if (!server->Start(config.maxPlayers, 0, 10, config.port, config.bind)) {
        std::fprintf(stderr, "[server] unable to start on %s:%u\n",
                     config.bind ? config.bind : "0.0.0.0", config.port);
        RakNet::RakNetworkFactory::DestroyRakServerInterface(server);
        return 1;
    }
    server->StartOccasionalPing();

    ScriptHostStub script;
    script.OnGameModeInit();
    std::printf("[server] Code RED MP RakNet PoC listening on %s:%u maxplayers=%u\n",
                config.bind ? config.bind : "0.0.0.0", config.port, config.maxPlayers);

    std::array<PeerSlot, 32> peers;
    auto nextSnapshot = std::chrono::steady_clock::now();

    while (!g_stopRequested) {
        for (RakNet::Packet* packet = server->Receive(); packet; packet = server->Receive()) {
            const std::uint8_t packetId = codered_mp::GetPacketId(packet);
            if (packetId == RakNet::ID_NEW_INCOMING_CONNECTION) {
                std::printf("[server] raknet incoming connection\n");
            } else if (packetId == RakNet::ID_DISCONNECTION_NOTIFICATION || packetId == RakNet::ID_CONNECTION_LOST) {
                const std::uint8_t slot = FindSlot(peers, packet->playerId);
                if (slot != codered_mp::kInvalidPlayerId) {
                    peers[slot] = PeerSlot{};
                    script.OnPlayerDisconnect(slot);
                }
            } else if (packetId >= codered_mp::kMsgJoinRequest) {
                RakNet::BitStream in(packet->data, packet->length, false);
                unsigned char messageId = 0;
                if (in.Read(messageId)) {
                    if (messageId == codered_mp::kMsgJoinRequest) {
                        std::uint32_t version = 0;
                        std::string name;
                        if (!in.Read(version) || !codered_mp::ReadString(in, name, codered_mp::kMaxNameLength)) {
                            SendJoinRejected(server, packet->playerId, "malformed join");
                        } else if (version != codered_mp::kProtocolVersion) {
                            SendJoinRejected(server, packet->playerId, "protocol mismatch");
                        } else {
                            std::uint8_t slot = FindSlot(peers, packet->playerId);
                            if (slot == codered_mp::kInvalidPlayerId) {
                                slot = AllocateSlot(peers, packet->playerId);
                            }
                            if (slot == codered_mp::kInvalidPlayerId) {
                                SendJoinRejected(server, packet->playerId, "server full");
                            } else {
                                peers[slot].name = name;
                                SendJoinAccepted(server, peers[slot]);
                                script.OnPlayerConnect(slot, name);
                            }
                        }
                    } else if (messageId == codered_mp::kMsgPlayerState) {
                        codered_mp::PlayerState state;
                        const std::uint8_t slot = FindSlot(peers, packet->playerId);
                        if (slot != codered_mp::kInvalidPlayerId && codered_mp::ReadPlayerState(in, state)) {
                            state.playerId = slot;
                            peers[slot].state = state;
                            script.OnPlayerUpdate(state);
                        }
                    } else if (messageId == codered_mp::kMsgChat) {
                        std::string text;
                        const std::uint8_t slot = FindSlot(peers, packet->playerId);
                        if (slot != codered_mp::kInvalidPlayerId && codered_mp::ReadString(in, text, codered_mp::kMaxChatLength)) {
                            script.OnPlayerText(slot, text);
                            BroadcastChat(server, slot, text);
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
    server->Disconnect(100);
    RakNet::RakNetworkFactory::DestroyRakServerInterface(server);
    return 0;
}
