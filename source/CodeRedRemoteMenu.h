#pragma once
#include "RemotePuppetController.h"
#include "SectorCatalog.h"
#include "SectorPatchQueue.h"
#include "SoulStealerRuntime.h"
#include <string>
#include <vector>

namespace codered {

enum class RemoteMenuPage {
    Main,
    SoulStealer,
    Teleport,
    RemotePuppet,
    SectorParents,
    SectorChildren,
    SectorActions,
    Debug
};

struct MenuLine {
    std::string label;
    std::string detail;
    bool selectable = true;
};

struct RemoteMenuView {
    std::string title;
    std::vector<MenuLine> lines;
    std::size_t selected = 0;
};

class CodeRedRemoteMenu {
public:
    CodeRedRemoteMenu(SoulStealerRuntime& runtime, SectorCatalog& sectors, SectorPatchQueue& patchQueue);

    void open();
    void close();
    bool isOpen() const { return open_; }
    void back();
    void moveSelection(int delta);
    void activateSelected();
    RemoteMenuView view() const;

    RemoteMenuPage page() const { return page_; }
    std::string selectedParent() const { return selectedParent_; }
    std::string selectedSector() const { return selectedSector_; }

private:
    SoulStealerRuntime& runtime_;
    SectorCatalog& sectors_;
    SectorPatchQueue& patchQueue_;
    bool open_ = false;
    RemoteMenuPage page_ = RemoteMenuPage::Main;
    std::size_t selected_ = 0;
    std::string selectedParent_;
    std::string selectedSector_;

    void setPage(RemoteMenuPage page);
    void queueSectorAction(SectorPatchAction action, SectorKind desiredKind = SectorKind::Unknown, const std::string& replacement = "");
    std::vector<MenuLine> currentLines() const;
};

} // namespace codered
