# Xbox Layer Resolver

Code RED now includes a read-only Xbox/Xenia layer resolver for older Red Dead Redemption research layouts where content is split across Disc/base files, `layer_0.rpf`, update layers, and DLC/content layers.

The purpose is to answer one question before patching:

```text
Which copy of this file does the game actually see?
```

This matters because Xbox-style packages can contain the same path in multiple places. Editing the lower layer may do nothing if a higher layer overrides that path.

## Public-safety rule

Do not commit extracted game content, RPFs, XSC/SCO/WSC files, profile packages, or private reports to the public repo. The resolver is a local/private research tool that exports path-level reports only.

## GUI workflow

Run:

```bat
python python_workbench.py
```

Open the **Xbox Layers** tab.

Add layers in priority order:

```text
1. base/disc folder or base RPF
2. layer_0 / install layer
3. update layer
4. DLC/content layer
```

Then press **Build Effective Tree**.

The table shows:

```text
Status       single-layer, duplicated-same, overridden-by-higher-layer
Winner       which layer owns the effective path
Kind         Script/Text/Archive/etc.
In Layers    every layer where that path appears
Tags         profile/avatar/network, init/pop/zombie, script, xbox-script
Path         normalized effective game path
```

Double-click a row to copy its effective path.

## CLI workflow

```bat
python tools\codered_xbox_layer_resolver.py ^
  --layer base=D:\RDR\disc_base_extract ^
  --layer layer0=D:\RDR\layer_0_extract ^
  --layer update=D:\RDR\title_update_extract ^
  --out reports\xbox_layer_resolver
```

Outputs:

```text
xbox_layer_report.json
xbox_layer_effective_tree.csv
xbox_layer_focus_files.csv
xbox_layer_gpt_packet.json
```

## XSC/SCO detector

The resolver can also inspect one script-like file without patching it:

```bat
python tools\codered_xbox_layer_resolver.py --inspect-script private_input\main.xsc
python tools\codered_xbox_layer_resolver.py --inspect-script private_input\mission.sco
```

The detector reports:

```text
extension/family guess
header bytes
SHA-256
readable strings preview
profile/avatar/network keyword hits
init/pop/zombie keyword hits
```

It does not decrypt, compile, or rewrite files.

## Code RED rule for Xbox research

Use this pass before modifying any script:

```text
resolve layers first
open the effective script second
compare normal/zombie/profile/lobby paths third
patch only after the winning layer is known
```

This should reduce false negatives where a patch appears to fail because the wrong layer was edited.
