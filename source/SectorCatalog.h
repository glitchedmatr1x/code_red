#pragma once
#include <cstddef>
#include <string>
#include <vector>

namespace codered {

enum class SectorKind {
    Unknown,
    World,
    Child
};

enum class SectorState {
    Unknown,
    Enabled,
    Disabled
};

struct SectorEntry {
    std::string parent;      // Territory RPF or owner group, e.g. blackwater / dlc02x.
    std::string name;        // Sector token, e.g. dlc02x or esc_villaWall04x.
    SectorKind kind = SectorKind::Unknown;
    SectorState state = SectorState::Unknown;
    std::string source;      // territory_swall, medium_update_thread, manual preset, etc.
    std::size_t decodedOffset = 0;
};

std::string toString(SectorKind kind);
std::string toString(SectorState state);

class SectorCatalog {
public:
    void clear();
    bool addOrUpdate(const SectorEntry& entry);
    std::vector<SectorEntry> all() const;
    std::vector<SectorEntry> byParent(const std::string& parent) const;
    std::vector<SectorEntry> findByName(const std::string& name) const;
    std::vector<std::string> parents() const;
    std::size_t size() const { return entries_.size(); }

private:
    std::vector<SectorEntry> entries_;
};

} // namespace codered
