#pragma once
#include "SectorCatalog.h"
#include <string>
#include <vector>

namespace codered {

enum class SectorPatchAction {
    Enable,
    Disable,
    ConvertToWorld,
    ConvertToChild,
    ReplaceName
};

struct SectorPatchRequest {
    SectorPatchAction action = SectorPatchAction::Enable;
    std::string parent;
    std::string sectorName;
    std::string replacementName;
    SectorKind currentKind = SectorKind::Unknown;
    SectorKind desiredKind = SectorKind::Unknown;
    std::string targetWscPath;
};

std::string toString(SectorPatchAction action);

class SectorPatchQueue {
public:
    void enqueue(const SectorPatchRequest& request);
    void clear();
    std::vector<SectorPatchRequest> requests() const { return requests_; }
    std::size_t size() const { return requests_.size(); }
    std::string exportJson() const;
    std::string exportWorkbenchCommands(const std::string& workbenchPy) const;

private:
    std::vector<SectorPatchRequest> requests_;
};

} // namespace codered
