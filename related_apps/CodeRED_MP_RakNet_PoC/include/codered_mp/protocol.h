#pragma once

#include <cstdint>
#include <string>

#include <slikenet/BitStream.h>
#include <slikenet/MessageIdentifiers.h>
#include <slikenet/types.h>

namespace codered_mp {

constexpr std::uint32_t kProtocolVersion = 2;
constexpr std::uint16_t kDefaultPort = 7777;
constexpr std::uint8_t kInvalidPlayerId = 0xFF;
constexpr std::uint16_t kDefaultActorEnum = 837; // ACTOR_mpplayer01.
constexpr std::size_t kMaxNameLength = 24;
constexpr std::size_t kMaxChatLength = 96;
constexpr std::size_t kMaxNativeCallLength = 96;

enum MessageId : std::uint8_t {
    kMsgJoinRequest = ID_USER_PACKET_ENUM,
    kMsgJoinAccepted,
    kMsgJoinRejected,
    kMsgPlayerState,
    kMsgWorldSnapshot,
    kMsgChat,
    kMsgServerNotice,
    kMsgNativeCall,
};

struct PlayerState {
    std::uint8_t playerId = kInvalidPlayerId;
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
    float heading = 0.0f;
    std::uint16_t health = 100;
    std::uint16_t flags = 0;
    std::uint16_t actorEnum = kDefaultActorEnum;
    std::uint32_t sequence = 0;
};

std::uint8_t GetPacketId(const SLNet::Packet* packet);
const char* PacketIdName(std::uint8_t packetId);
const char* MessageName(std::uint8_t messageId);

void WriteString(SLNet::BitStream& stream, const std::string& value, std::size_t maxLength);
bool ReadString(SLNet::BitStream& stream, std::string& value, std::size_t maxLength);

void WritePlayerState(SLNet::BitStream& stream, const PlayerState& state);
bool ReadPlayerState(SLNet::BitStream& stream, PlayerState& state);

} // namespace codered_mp
