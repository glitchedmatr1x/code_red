#include "SectorCatalog.h"
#include <algorithm>
#include <set>

namespace codered {

std::string toString(SectorKind kind) {
    switch (kind) {
    case SectorKind::World: return "world";
    case SectorKind::Child: return "child";
    default: return "unknown";
    }
}

std::string toString(SectorState state) {
    switch (state) {
    case SectorState::Enabled: return "enabled";
    case SectorState::Disabled: return "disabled";
    default: return "unknown";
    }
}

void SectorCatalog::clear() {
    entries_.clear();
}

bool SectorCatalog::addOrUpdate(const SectorEntry& entry) {
    auto it = std::find_if(entries_.begin(), entries_.end(), [&](const SectorEntry& e) {
        return e.parent == entry.parent && e.name == entry.name && e.kind == entry.kind;
    });
    if (it == entries_.end()) {
        entries_.push_back(entry);
        return true;
    }
    if (entry.state != SectorState::Unknown) it->state = entry.state;
    if (!entry.source.empty()) it->source = entry.source;
    if (entry.decodedOffset != 0) it->decodedOffset = entry.decodedOffset;
    return false;
}

std::vector<SectorEntry> SectorCatalog::all() const {
    return entries_;
}

std::vector<SectorEntry> SectorCatalog::byParent(const std::string& parent) const {
    std::vector<SectorEntry> out;
    for (const auto& e : entries_) {
        if (e.parent == parent) out.push_back(e);
    }
    return out;
}

std::vector<SectorEntry> SectorCatalog::findByName(const std::string& name) const {
    std::vector<SectorEntry> out;
    for (const auto& e : entries_) {
        if (e.name == name) out.push_back(e);
    }
    return out;
}

std::vector<std::string> SectorCatalog::parents() const {
    std::set<std::string> seen;
    for (const auto& e : entries_) seen.insert(e.parent);
    return {seen.begin(), seen.end()};
}

} // namespace codered
