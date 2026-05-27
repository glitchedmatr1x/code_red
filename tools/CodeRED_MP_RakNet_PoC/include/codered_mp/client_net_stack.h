#pragma once

#include <chrono>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "codered_mp/protocol.h"

namespace SLNet {
class RakPeerInterface;
struct Packet;
}

namespace codered_mp {

struct ClientConfig {
    std::string host = "127.0.0.1";
    std::uint16_t port = kDefaultPort;
    std::uint16_t localPort = 0;
    std::string name = "rdr_player";
};

struct ClientEvent {
    enum Type {
        kLog,
        kConnected,
        kDisconnected,
        kJoinAccepted,
        kJoinRejected,
        kSnapshot,
        kChat,
        kNativeCall,
    };

    Type type = kLog;
    std::string text;
    std::uint8_t playerId = kInvalidPlayerId;
    std::vector<PlayerState> players;
};

class ClientNetStack {
public:
    ClientNetStack();
    ~ClientNetStack();

    ClientNetStack(const ClientNetStack&) = delete;
    ClientNetStack& operator=(const ClientNetStack&) = delete;

    bool Connect(const ClientConfig& config);
    void Disconnect();
    void Pump();

    bool SendPlayerState(const PlayerState& state);
    bool SendChat(const std::string& text);

    bool IsConnected() const;
    std::uint8_t LocalPlayerId() const;
    std::vector<ClientEvent> DrainEvents();

private:
    void PushLog(const std::string& text);
    void HandlePacket(SLNet::Packet* packet);
    void SendJoinRequest();

    SLNet::RakPeerInterface* client_ = nullptr;
    ClientConfig config_;
    bool connected_ = false;
    std::uint8_t localPlayerId_ = kInvalidPlayerId;
    std::vector<ClientEvent> events_;
};

} // namespace codered_mp
