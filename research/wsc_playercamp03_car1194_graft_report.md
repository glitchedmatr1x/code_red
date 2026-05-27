# WSC PlayerCamp03 Car1194 Graft

## Goal

Create a modified copied RPF experiment for:

`root/content/release64/scripting/gringo/commonscripts/playercamp03_gringo.wsc`

The intended behavior is to test car-at-camp behavior using the existing `car_gringo.wsc` payload associated with actor enum `1194`.

## Important Boundary

This is not a bytecode merge into the original `playercamp03_gringo.wsc` function graph. Code RED still cannot rebuild existing WSC source/functions.

This experiment is a full WSC slot graft:

- Preserve original `playercamp03_gringo.wsc` in the workspace.
- Copy `imports\car_gringo.wsc` as the graft payload.
- Pack that graft payload into the `playercamp03_gringo.wsc` archive slot in a copied RPF.

## Workspace

`build\wsc_playercamp03_car1194_graft\`

Original camp WSC:

`build\wsc_playercamp03_car1194_graft\original\content\release64\scripting\gringo\commonscripts\playercamp03_gringo.wsc`

Graft payload:

`build\wsc_playercamp03_car1194_graft\edited\playercamp03_gringo_car1194_graft.wsc`

Copied RPF output:

`build\wsc_playercamp03_car1194_graft\packed\content.rpf`

## Hashes

- Original `playercamp03_gringo.wsc`: `075669E6727ABEC04F4C158EA2472C660CAF081D`
- Donor `car_gringo.wsc`: `1751BD2B912039048FD480B43DA6EA2B9386FFA9`
- Packed/extracted `playercamp03_gringo.wsc`: `1751BD2B912039048FD480B43DA6EA2B9386FFA9`

The packed/extracted hash matches the donor payload, so the copied RPF contains the graft in the intended archive slot.

## Verification

- Packed archive inventory passed.
- Extracting `root/content/release64/scripting/gringo/commonscripts/playercamp03_gringo.wsc` from the copied RPF passed.
- The extracted WSC hash matched the graft payload hash.

Reports:

- `logs\wsc_playercamp03_car_graft\playercamp03_inspect.json`
- `logs\wsc_playercamp03_car_graft\car_gringo_inspect.json`
- `logs\wsc_edit\playercamp03_car1194_graft\manual_wsc_playercamp03_car1194_graft_overlay_report.json`
- `logs\wsc_playercamp03_car1194_graft\packed_inventory\rpf_inventory.json`

## Runtime Risk

This may fail or behave differently from a true source-level edit because it replaces the whole camp03 script with the car gringo script. If it boots and changes behavior at camp, it proves the slot can load/run the car gringo payload. If it does not, the next step needs either a real WSC source rebuild path or a smaller proven binary patch point inside the original camp script.
