#include "codered_mp/client_net_stack.h"

#include <cstdio>
#include <sstream>

#include <slikenet/peerinterface.h>

namespace codered_mp {

ClientNetStack::ClientNetStack() = default;

ClientNetStack::~ClientNetStack() {
    Disconnect();
}

bool ClientNetStack::Connect(const ClientConfig& config) {
    Disconnect();
    config_ = config;
    client_ = SLNet::RakPeerInterface::GetInstance();
    if (!client_) {
        PushLog("SLikeNet returned null client peer");
        return false;
    }

    SLNet::SocketDescriptor descriptor(config_.localPort, nullptr);
    const SLNet::StartupResult startup = client_->Startup(1, &descriptor, 1);
    if (startup != SLNet::RAKNET_STARTED) {
        std::ostringstream out;
        out << "SLikeNet Startup() failed result=" << static_cast<int>(startup);
        PushLog(out.str());
        SLNet::RakPeerInterface::DestroyInstance(client_);
        client_ = nullptr;
        return false;
    }

    const SLNet::ConnectionAttemptResult attempt =
        client_->Connect(config_.host.c_str(), config_.port, nullptr, 0);
    if (attempt != SLNet::CONNECTION_ATTEMPT_STARTED) {
        std::ostringstream out;
        out << "SLikeNet Connect() initiation failed result=" << static_cast<int>(attempt);
        PushLog(out.str());
        client_->Shutdown(100);
        SLNet::RakPeerInterface::DestroyInstance(client_);
        client_ = nullptr;
        return false;
    }

    std::ostringstream out;
    out << "SLikeNet connect initiated host=" << config_.host << " port=" << config_.port;
    PushLog(out.str());
    return true;
}

void ClientNetStack::Disconnect() {
    if (client_) {
        client_->Shutdown(100);
        SLNet::RakPeerInterface::DestroyInstance(client_);
        client_ = nullptr;
    }
    connected_ = false;
    localPlayerId_ = kInvalidPlayerId;
}

void ClientNetStack::Pump() {
    if (!client_) {
        return;
    }

    for (SLNet::Packet* packet = client_->Receive(); packet; packet = client_->Receive()) {
        HandlePacket(packet);
        client_->DeallocatePacket(packet);
    }
}

bool ClientNetStack::SendPlayerState(const PlayerState& state) {
    if (!client_ || !connected_ || localPlayerId_ == kInvalidPlayerId) {
        return false;
    }

    PlayerState outbound = state;
    outbound.playerId = localPlayerId_;

    SLNet::BitStream stream;
    stream.Write(static_cast<unsigned char>(kMsgPlayerState));
    WritePlayerState(stream, outbound);
    return client_->Send(&stream, HIGH_PRIORITY, UNRELIABLE_SEQUENCED, 0,
                         SLNet::UNASSIGNED_SYSTEM_ADDRESS, true) != 0;
}

bool ClientNetStack::SendChat(const std::string& text) {
    if (!client_ || !connected_) {
        return false;
    }

    SLNet::BitStream stream;
    stream.Write(static_cast<unsigned char>(kMsgChat));
    WriteString(stream, text, kMaxChatLength);
    return client_->Send(&stream, HIGH_PRIORITY, RELIABLE_ORDERED, 0,
                         SLNet::UNASSIGNED_SYSTEM_ADDRESS, true) != 0;
}

bool ClientNetStack::IsConnected() const {
    return connected_;
}

std::uint8_t ClientNetStack::LocalPlayerId() const {
    return localPlayerId_;
}

std::vector<ClientEvent> ClientNetStack::DrainEvents() {
    std::vector<ClientEvent> out;
    out.swap(events_);
    return out;
}

void ClientNetStack::PushLog(const std::string& text) {
    ClientEvent event;
    event.type = ClientEvent::kLog;
    event.text = text;
    events_.push_back(event);
}

void ClientNetStack::HandlePacket(SLNet::Packet* packet) {
    const std::uint8_t packetId = GetPacketId(packet);
    switch (packetId) {
        case ID_CONNECTION_REQUEST_ACCEPTED:
            connected_ = true;
            events_.push_back({ClientEvent::kConnected, "SLikeNet connection accepted", kInvalidPlayerId, {}});
            SendJoinRequest();
            return;
        case ID_DISCONNECTION_NOTIFICATION:
        case ID_CONNECTION_LOST:
            connected_ = false;
            events_.push_back({ClientEvent::kDisconnected, PacketIdName(packetId), localPlayerId_, {}});
            return;
        case ID_CONNECTION_ATTEMPT_FAILED:
        case ID_NO_FREE_INCOMING_CONNECTIONS:
        case ID_INVALID_PASSWORD:
            connected_ = false;
            events_.push_back({ClientEvent::kDisconnected, PacketIdName(packetId), kInvalidPlayerId, {}});
            return;
        default:
            break;
    }

    if (packetId < kMsgJoinRequest) {
        std::ostringstream out;
        out << "ignored SLikeNet packet id=" << static_cast<int>(packetId) << " " << PacketIdName(packetId);
        PushLog(out.str());
        return;
    }

    SLNet::BitStream stream(packet->data, packet->length, false);
    unsigned char messageId = 0;
    if (!stream.Read(messageId)) {
        return;
    }

    if (messageId == kMsgJoinAccepted) {
        std::uint8_t assignedId = kInvalidPlayerId;
        PlayerState spawnState;
        std::string notice;
        if (stream.Read(assignedId) &&
            ReadPlayerState(stream, spawnState) &&
            ReadString(stream, notice, kMaxChatLength)) {
            localPlayerId_ = assignedId;
            ClientEvent event;
            event.type = ClientEvent::kJoinAccepted;
            event.text = notice;
            event.playerId = assignedId;
            event.players.push_back(spawnState);
            events_.push_back(event);
        }
    } else if (messageId == kMsgJoinRejected) {
        std::string reason;
        ReadString(stream, reason, kMaxChatLength);
        events_.push_back({ClientEvent::kJoinRejected, reason, kInvalidPlayerId, {}});
    } else if (messageId == kMsgWorldSnapshot) {
        std::uint8_t count = 0;
        ClientEvent event;
        event.type = ClientEvent::kSnapshot;
        event.playerId = localPlayerId_;
        if (stream.Read(count)) {
            for (std::uint8_t i = 0; i < count; ++i) {
                PlayerState state;
                if (ReadPlayerState(stream, state)) {
                    event.players.push_back(state);
                }
            }
        }
        events_.push_back(event);
    } else if (messageId == kMsgChat || messageId == kMsgServerNotice) {
        std::string text;
        ReadString(stream, text, kMaxChatLength);
        events_.push_back({messageId == kMsgChat ? ClientEvent::kChat : ClientEvent::kLog, text, localPlayerId_, {}});
    } else if (messageId == kMsgNativeCall) {
        std::string callName;
        std::string payload;
        if (ReadString(stream, callName, kMaxNativeCallLength) &&
            ReadString(stream, payload, kMaxChatLength)) {
            events_.push_back({ClientEvent::kNativeCall, callName + ": " + payload, localPlayerId_, {}});
        }
    } else {
        std::ostringstream out;
        out << "ignored user message id=" << static_cast<int>(messageId) << " " << MessageName(messageId);
        PushLog(out.str());
    }
}

void ClientNetStack::SendJoinRequest() {
    SLNet::BitStream stream;
    stream.Write(static_cast<unsigned char>(kMsgJoinRequest));
    stream.Write(kProtocolVersion);
    WriteString(stream, config_.name, kMaxNameLength);
    client_->Send(&stream, HIGH_PRIORITY, RELIABLE_ORDERED, 0,
                  SLNet::UNASSIGNED_SYSTEM_ADDRESS, true);
}

} // namespace codered_mp
