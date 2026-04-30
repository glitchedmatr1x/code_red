# Code RED — WFT/WEDT Full Extract + Roundtrip Research Pass 7

Date: 2026-04-30

## Purpose

This pass starts the model-resource path cleanly and read-only. It does not claim full model recompilation yet. It builds a reusable extractor for WFT/WEDT-adjacent RSC6 resources and proves enough of the resource lane to move toward future no-op rebuilds.

## Added

```text
tools/codered_model_resource_extractor.py
```

The extractor can:

```text
- Open RPF6 archives or ZIP files containing RPFs.
- Decode RSC/zstd resource payloads.
- Inventory model/resource candidates by extension, resource type, and decoded root VFT.
- Export decoded payloads for controlled analysis.
- Export virtual pointer maps.
- Export ASCII/UTF-16 string samples.
- Export VFT/class-pointer histograms.
- Optionally run compression roundtrip checks.
```

## Current resource-type evidence

`fragments2.rpf` is hash-named, so the tool labels candidates conservatively by resource type and decoded root VFT.

Observed in the sample run:

```text
resource_type 11
root VFT 0x00D0E590
hint: WEDT / edit-data candidate

resource_type 1
root VFT 0x00DDC0A0
hint: WFT / fragment-or-drawable candidate
```

This is intentionally cautious. The pass proves extraction and layout clues, not final semantic class names.

## Sample run

Input:

```text
fragments2.rpf
```

Outputs:

```text
reports/model_resource_extract_outputs/model_inventory.csv
reports/model_resource_extract_outputs/virtual_pointer_map.csv
reports/model_resource_extract_outputs/strings.csv
reports/model_resource_extract_outputs/vft_histogram.csv
reports/model_resource_extract_outputs/roundtrip_results.csv
reports/model_resource_extract_outputs/model_resource_extract_master.json
reports/model_resource_extract_outputs/model_extract_report.md
reports/model_resource_extract_outputs/decoded_payloads/*.decoded.bin
```

Sample result:

```text
candidate resources scanned: 3
resource_type 11 candidates: 2
resource_type 1 candidates: 1
compression roundtrip checks: 1/1 passed
```

## Safety boundary

This is not a mutating pass.

```text
No RPF patching.
No WFT/WEDT semantic rebuild.
No model edits.
No fake compiler claims.
```

The next pass should be a byte-preserving decoded-payload rebuilder or a same-size/same-format texture replacement proof in a copied RPF only.
