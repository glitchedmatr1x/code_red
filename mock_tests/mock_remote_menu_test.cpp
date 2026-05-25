#include "CodeRedRemoteMenu.h"
#include "MockInputBridge.h"
#include "MockNativeBridge.h"
#include <cassert>
#include <iostream>

using namespace codered;

int main() {
    MockNativeBridge bridge;
    MockInputBridge input;
    SoulStealerConfig config{};
    SoulStealerRuntime runtime(bridge, input, config);
    SectorCatalog catalog;
    SectorPatchQueue queue;

    catalog.addOrUpdate({"blackwater", "blk_zombieFire01x", SectorKind::Child, SectorState::Disabled, "territory_swall", 0});
    catalog.addOrUpdate({"dlc02x", "dlc02x", SectorKind::World, SectorState::Disabled, "territory_swall", 0});
    catalog.addOrUpdate({"escalera", "esc_villaWall04x", SectorKind::Child, SectorState::Disabled, "medium_update_thread", 0x96C8});

    CodeRedRemoteMenu menu(runtime, catalog, queue);
    menu.open();
    auto view = menu.view();
    assert(view.title == "Code RED Remote Menu");
    assert(view.lines.size() >= 4);

    // Move to Sector Toggle and open it.
    menu.moveSelection(3);
    menu.activateSelected();
    assert(menu.page() == RemoteMenuPage::SectorParents);
    view = menu.view();
    assert(!view.lines.empty());

    // Choose first parent, first child, queue enable.
    menu.activateSelected();
    assert(menu.page() == RemoteMenuPage::SectorChildren);
    menu.activateSelected();
    assert(menu.page() == RemoteMenuPage::SectorActions);
    menu.activateSelected();
    assert(queue.size() == 1);

    std::string json = queue.exportJson();
    assert(json.find("sector_name") != std::string::npos);
    assert(json.find("enable") != std::string::npos);
    std::cout << "remote menu sector queue mock: passed\n";
    return 0;
}
