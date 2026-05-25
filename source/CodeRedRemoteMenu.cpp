#include "CodeRedRemoteMenu.h"
#include <algorithm>
#include <sstream>

namespace codered {

CodeRedRemoteMenu::CodeRedRemoteMenu(SoulStealerRuntime& runtime, SectorCatalog& sectors, SectorPatchQueue& patchQueue)
    : runtime_(runtime), sectors_(sectors), patchQueue_(patchQueue) {}

void CodeRedRemoteMenu::open() { open_ = true; setPage(RemoteMenuPage::Main); }
void CodeRedRemoteMenu::close() { open_ = false; }

void CodeRedRemoteMenu::setPage(RemoteMenuPage page) {
    page_ = page;
    selected_ = 0;
}

void CodeRedRemoteMenu::back() {
    switch (page_) {
    case RemoteMenuPage::Main: close(); break;
    case RemoteMenuPage::SectorChildren: setPage(RemoteMenuPage::SectorParents); break;
    case RemoteMenuPage::SectorActions: setPage(RemoteMenuPage::SectorChildren); break;
    default: setPage(RemoteMenuPage::Main); break;
    }
}

void CodeRedRemoteMenu::moveSelection(int delta) {
    auto lines = currentLines();
    if (lines.empty()) { selected_ = 0; return; }
    int next = static_cast<int>(selected_) + delta;
    if (next < 0) next = static_cast<int>(lines.size()) - 1;
    if (next >= static_cast<int>(lines.size())) next = 0;
    selected_ = static_cast<std::size_t>(next);
}

void CodeRedRemoteMenu::activateSelected() {
    auto lines = currentLines();
    if (lines.empty() || selected_ >= lines.size()) return;

    if (page_ == RemoteMenuPage::Main) {
        switch (selected_) {
        case 0: setPage(RemoteMenuPage::SoulStealer); break;
        case 1: setPage(RemoteMenuPage::Teleport); break;
        case 2: setPage(RemoteMenuPage::RemotePuppet); break;
        case 3: setPage(RemoteMenuPage::SectorParents); break;
        case 4: setPage(RemoteMenuPage::Debug); break;
        default: close(); break;
        }
        return;
    }

    if (page_ == RemoteMenuPage::SoulStealer) {
        if (selected_ == 0) runtime_.module().toggleArmed();
        else if (selected_ == 1) runtime_.module().captureBestTarget();
        else if (selected_ == 2) runtime_.module().cancel();
        return;
    }

    if (page_ == RemoteMenuPage::Teleport) {
        if (selected_ == 0) runtime_.teleports().savePlayerSlot(0, "Remote Menu Slot 0");
        else if (selected_ == 1) runtime_.teleports().teleportPlayerToSlot(0);
        else if (selected_ == 2) runtime_.remotePuppet().teleportActorToPlayer();
        return;
    }

    if (page_ == RemoteMenuPage::SectorParents) {
        auto parents = sectors_.parents();
        if (selected_ < parents.size()) {
            selectedParent_ = parents[selected_];
            setPage(RemoteMenuPage::SectorChildren);
        }
        return;
    }

    if (page_ == RemoteMenuPage::SectorChildren) {
        auto children = sectors_.byParent(selectedParent_);
        if (selected_ < children.size()) {
            selectedSector_ = children[selected_].name;
            setPage(RemoteMenuPage::SectorActions);
        }
        return;
    }

    if (page_ == RemoteMenuPage::SectorActions) {
        if (selected_ == 0) queueSectorAction(SectorPatchAction::Enable);
        else if (selected_ == 1) queueSectorAction(SectorPatchAction::Disable);
        else if (selected_ == 2) queueSectorAction(SectorPatchAction::ConvertToWorld, SectorKind::World);
        else if (selected_ == 3) queueSectorAction(SectorPatchAction::ConvertToChild, SectorKind::Child);
        return;
    }
}

void CodeRedRemoteMenu::queueSectorAction(SectorPatchAction action, SectorKind desiredKind, const std::string& replacement) {
    auto matches = sectors_.findByName(selectedSector_);
    SectorKind currentKind = matches.empty() ? SectorKind::Unknown : matches.front().kind;
    SectorPatchRequest req{};
    req.action = action;
    req.parent = selectedParent_;
    req.sectorName = selectedSector_;
    req.replacementName = replacement;
    req.currentKind = currentKind;
    req.desiredKind = desiredKind;
    req.targetWscPath = "medium_update_thread.wsc";
    patchQueue_.enqueue(req);
    runtime_.logger().log("Queued sector patch: " + selectedSector_ + " -> " + toString(action));
}

std::vector<MenuLine> CodeRedRemoteMenu::currentLines() const {
    std::vector<MenuLine> lines;
    switch (page_) {
    case RemoteMenuPage::Main:
        return {{"Soul Stealer", "capture/control actors", true}, {"Teleport", "save and jump slots", true}, {"Remote Puppet", "blip/sync/debug", true}, {"Sector Toggle", "world/child sectors", true}, {"Debug", "status/logs", true}, {"Close", "return to game", true}};
    case RemoteMenuPage::SoulStealer:
        return {{"Toggle Armed", runtime_.module().state() == SoulStealerModule::State::Armed ? "currently armed" : "currently off", true}, {"Capture Target", "reticle/last damaged/nearest", true}, {"Cancel/Restore", "emergency restore", true}};
    case RemoteMenuPage::Teleport:
        return {{"Save Slot 0", "stores player position", true}, {"Load Slot 0", "teleport player", true}, {"Remote Puppet To Player", "bring controlled actor back", true}};
    case RemoteMenuPage::RemotePuppet:
        return {{"Remote Blip", "handled by RemotePuppetController", false}, {"Bind Actor", "Codex wires to selected actor", false}, {"Sync Mode", "soft/snap future setting", false}};
    case RemoteMenuPage::SectorParents: {
        auto parents = sectors_.parents();
        if (parents.empty()) return {{"No sector catalog loaded", "run territory_sector_catalog_builder.py", false}};
        for (const auto& p : parents) lines.push_back({p, "parent/territory", true});
        return lines;
    }
    case RemoteMenuPage::SectorChildren: {
        auto entries = sectors_.byParent(selectedParent_);
        if (entries.empty()) return {{"No sectors under parent", selectedParent_, false}};
        for (const auto& e : entries) {
            lines.push_back({e.name, toString(e.kind) + ", " + toString(e.state), true});
        }
        return lines;
    }
    case RemoteMenuPage::SectorActions:
        return {{"Enable", selectedSector_, true}, {"Disable", selectedSector_, true}, {"Convert to WORLD", selectedSector_, true}, {"Convert to CHILD", selectedSector_, true}};
    case RemoteMenuPage::Debug:
        return {{"Runtime", runtime_.module().debugStatus(), false}, {"Queued Sector Patches", std::to_string(patchQueue_.size()), false}};
    }
    return lines;
}

RemoteMenuView CodeRedRemoteMenu::view() const {
    RemoteMenuView v{};
    switch (page_) {
    case RemoteMenuPage::Main: v.title = "Code RED Remote Menu"; break;
    case RemoteMenuPage::SoulStealer: v.title = "Soul Stealer"; break;
    case RemoteMenuPage::Teleport: v.title = "Teleport Options"; break;
    case RemoteMenuPage::RemotePuppet: v.title = "Remote Puppet"; break;
    case RemoteMenuPage::SectorParents: v.title = "Sector Toggle: Parents"; break;
    case RemoteMenuPage::SectorChildren: v.title = "Sector Toggle: " + selectedParent_; break;
    case RemoteMenuPage::SectorActions: v.title = "Sector Actions: " + selectedSector_; break;
    case RemoteMenuPage::Debug: v.title = "Debug"; break;
    }
    v.lines = currentLines();
    v.selected = selected_;
    return v;
}

} // namespace codered
