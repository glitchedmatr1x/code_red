# Code RED WSC / SCO / XSC Classification Proof — 2026-05-04

## Commands run

```powershell
py -3 tools\codered_classify_script_artifacts.py --root "C:\Users\glitc\OneDrive\Desktop\CodeRED_RPF_Extracts"
py -3 tools\codered_classify_script_artifacts.py --root script_compiling\sccl\output --out logs\sccl_output_script_artifact_classification
```

## Extracted workspace counts

```text
.sco: 197
.wsc: 303
```

## Code RED SC-CL output counts

```text
.sco: 3
.xsc: 6
```

## Important byte-header evidence

Extracted `.sco` files begin with:

```text
53 43 52 02 ...
ASCII: SCR.
```

Code RED compiled `camp_car_probe.sco` begins with:

```text
53 43 52 02 34 9D 01 8A ...
ASCII: SCR.
```

Code RED compiled `camp_car_probe.xsc` begins with:

```text
85 43 53 52 ...
ASCII: .CSR
```

## Interpretation

The compiled `.sco` is in the same broad header family as extracted `.sco` scripts.

The compiled `.xsc` is a distinct header family from `.sco`.

`.wsc` still needs a focused header sample before it can be treated as equivalent to either `.sco` or `.xsc`.

## Current rule

Do not rename `.xsc` or `.sco` to `.wsc` yet.

Do not replace `playercamp01_gringo.wsc` yet.

Next proof step: inspect `.wsc` heads directly, especially:

```text
content/release64/scripting/gringo/commonscripts/playercamp01_gringo.wsc
content/release64/scripting/gringo/commonscripts/vehicle_generator.wsc
content/release64/scripting/gringo/commonscripts/car_gringo.wsc
content/release64/scripting/gringo/commonscripts/playercar.wsc
```
