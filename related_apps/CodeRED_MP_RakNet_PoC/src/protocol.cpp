#include "codered_mp/protocol.h"

#include <algorithm>
#include <cstring>

#include <slikenet/time.h>

namespace codered_mp {

std::uint8_t GetPacketId(const SLNet::Packet* packet) {
    if (!packet || !packet->data || packet->length == 0) {
        return 0xFF;
    }

    const auto first = static_cast<std::uint8_t>(packet->data[0]);
    if (first == ID_TIMESTAMP) {
        const std::size_t offset = sizeof(unsigned char) + sizeof(SLNet::Time);
        if (packet->length > offset) {
            return static_cast<std::uint8_t>(packet->data[offset]);
        }
        return 0xFF;
    }
    return first;
}

const char* PacketIdName(std::uint8_t packetId) {
    switch (packetId) {
        case ID_CONNECTION_REQUEST_ACCEPTED: return "ID_CONNECTION_REQUEST_ACCEPTED";
        case ID_NEW_INCOMING_CONNECTION: return "ID_NEW_INCOMING_CONNECTION";
        case ID_NO_FREE_INCOMING_CONNECTIONS: return "ID_NO_FREE_INCOMING_CONNECTIONS";
        case ID_DISCONNECTION_NOTIFICATION: return "ID_DISCONNECTION_NOTIFICATION";
        case ID_CONNECTION_LOST: return "ID_CONNECTION_LOST";
        case ID_CONNECTION_ATTEMPT_FAILED: return "ID_CONNECTION_ATTEMPT_FAILED";
        case ID_INVALID_PASSWORD: return "ID_INVALID_PASSWORD";
        default: return "UNKNOWN";
    }
}

const char* MessageName(std::uint8_t messageId) {
    switch (messageId) {
        case kMsgJoinRequest: return "join_request";
        case kMsgJoinAccepted: return "join_accepted";
        case kMsgJoinRejected: return "join_rejected";
        case kMsgPlayerState: return "player_state";
        case kMsgWorldSnapshot: return "world_snapshot";
        case kMsgChat: return "chat";
        case kMsgServerNotice: return "server_notice";
        case kMsgNativeCall: return "native_call";
        default: return "unknown_user_message";
    }
}

void WriteString(SLNet::BitStream& stream, const std::string& value, std::size_t maxLength) {
    const auto length = static_cast<std::uint8_t>(std::min(value.size(), maxLength));
    stream.Write(length);
    if (length > 0) {
        stream.Write(value.data(), length);
    }
}

bool ReadString(SLNet::BitStream& stream, std::string& value, std::size_t maxLength) {
    std::uint8_t length = 0;
    if (!stream.Read(length)) {
        return false;
    }
    if (length > maxLength) {
        return false;
    }
    value.assign(length, '\0');
    if (length == 0) {
        return true;
    }
    return stream.Read(value.data(), length);
}

void WritePlayerState(SLNet::BitStream& stream, const PlayerState& state) {
    stream.Write(state.playerId);
    stream.Write(state.x);
    stream.Write(state.y);
    stream.Write(state.z);
    stream.Write(state.heading);
    stream.Write(state.health);
    stream.Write(state.flags);
    stream.Write(state.actorEnum);
    stream.Write(state.sequence);
}

bool ReadPlayerState(SLNet::BitStream& stream, PlayerState& state) {
    return stream.Read(state.playerId) &&
           stream.Read(state.x) &&
           stream.Read(state.y) &&
           stream.Read(state.z) &&
           stream.Read(state.heading) &&
           stream.Read(state.health) &&
           stream.Read(state.flags) &&
           stream.Read(state.actorEnum) &&
           stream.Read(state.sequence);
}

} // namespace codered_mp
