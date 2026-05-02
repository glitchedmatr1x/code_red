# Code RED — WSI ↔ WGD Gringo Correlator Pass

Date: 2026-04-30

This pass adds:

```text
tools/codered_wsi_gringo_correlator.py
```

## Purpose

The previous Blackwater WSI test proved a static prop replacement was not enough:

```text
p_gen_carblocked01x -> car01
```

The original broken-car placement disappeared, but `car01` did not appear. That means WSI editing affected the world, but a real vehicle probably requires a gringo/script vehicle setup instead of a raw model-name replacement.

This correlator connects two existing research lanes:

```text
WSI sector/placement context
WGD gringo dictionary components
```

## What the tool does

The tool is read-only. It exports evidence tables before any patch is attempted.

It can scan WSI data from:

```text
--wsi-archive <rpf containing .wsi files>
--wsi-path <specific WSI path inside the archive>
--wsi-decoded <already decoded WSI payloads>
```

It can scan gringo dictionary data from:

```text
--wgd <decoded .wgd or raw RSC/zstd WGD slots>
--wgd-components <CSV/JSON from codered_gringo_wgd_export.py>
```

## Outputs

Default output folder:

```text
exports/wsi_gringo_correlation
```

Generated files:

```text
wsi_sector_context.csv
wsi_keyword_string_hits.csv
wsi_hash_matches_to_wgd.csv
wgd_keyword_components.csv
wsi_wgd_correlations.csv
safe_candidate_gringo_hosts.csv
wsi_gringo_correlation_master.json
```

## Correlation strategy

The tool searches WSI payloads for keyword strings and 32-bit hash values matching WGD gringo data.

Default keyword set:

```text
gringo|has_gringo|gringo_available|vehicle|car|wagon|coach|cart|train|turret|gatling|maxim|horse
```

WGD fields resolved:

```text
QueryName
ScriptName
GringoName
HashCode
HashedName
ActivationRadius
Child count
Use-context count
Instanced item count
Critical
MaintainState
PlayerUsable
GringoHandlesMovement
RequiresPhysicsCheck
AllowAiShoot
AllowNavigateTo
```

WSI context exported:

```text
WSI source
hit offset
hit kind
hit string/hash
sector offset
sector name/scope
resolved sector names when possible
sector bounds guess
resident/disabled/district context
```

## Why it matters

This is the safest next step before testing `Vehicle_Generator`, `PlayerCar`, or `car_gringo` in Blackwater.

The correlator should help identify one visible, non-critical gringo host/reference in Blackwater and show whether its WSI lane connects to the WGD dictionary path.

## Next recommended experiment

1. Run `codered_gringo_wgd_export.py` on `commongringos.wgd` if no component export exists yet.
2. Run this correlator against Blackwater WSI and the WGD component export.
3. Inspect `safe_candidate_gringo_hosts.csv`.
4. Pick one visible non-critical host.
5. Only then create a copied-RPF patch test, one changed placement at a time.

## Do not do yet

Do not bulk-patch WSI/WGD/WVD/WBD.

Do not retry `car01` as a raw WSI prop replacement.

Do not test `Vehicle_Generator` until the correlation table proves the WSI-to-WGD reference path well enough to pick a safe host.
