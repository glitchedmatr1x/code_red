#pragma once

#include <cstdint>
#include <string>

#include <raknet/BitStream.h>
#include <raknet/NetworkTypes.h>
#include <raknet/PacketEnumerations.h>

namespace codered_mp {

constexpr std::uint32_t kProtocolVersion = 1;
constexpr std::uint16_t kDefaultPort = 7777;
constexpr std::uint8_t kInvalidPlayerId = 0xFF;
constexpr std::size_t kMaxNameLength = 24;
constexpr std::size_t kMaxChatLength = 96;

enum MessageId : std::uint8_t {
    kMsgJoinRequest = RakNet::ID_USER_PACKET_ENUM,
    kMsgJoinAccepted,
    kMsgJoinRejected,
    kMsgPlayerState,
    kMsgWorldSnapshot,
    kMsgChat,
    kMsgServerNotice,
};

struct PlayerState {
    std::uint8_t playerId = kInvalidPlayerId;
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
    float heading = 0.0f;
    std::uint16_t health = 100;
    std::uint16_t flags = 0;
};

std::uint8_t GetPacketId(const RakNet::Packet* packet);
const char* PacketIdName(std::uint8_t packetId);
const char* MessageName(std::uint8_t messageId);

void WriteString(RakNet::BitStream& stream, const std::string& value, std::size_t maxLength);
bool ReadString(RakNet::BitStream& stream, std::string& value, std::size_t maxLength);

void WritePlayerState(RakNet::BitStream& stream, const PlayerState& state);
bool ReadPlayerState(RakNet::BitStream& stream, PlayerState& state);

} // namespace codered_mp
