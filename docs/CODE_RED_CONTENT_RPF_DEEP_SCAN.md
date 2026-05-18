# Code RED Content RPF Deep Scanner v1

Read-only deep scan for `content.rpf`.

Targets the current Code RED questions:

- which WSC/CSC scripts reference vehicle actor IDs 1156-1202
- where 1193 Truck01 and 1194 Car01 show up
- where mounted gun strings show up: `MaximShootTruck`, `GatlingShootTruck`, `gattling_attach`, `stagegat_attach`
- where train car enums 1156-1176 and train seat gates show up
- candidate scripts for seat disabling / gringo availability / mission car setup

The scanner parses RPF6, decrypts the TOC with the RDR1 AES key from `rdr.exe`, extracts resources, decodes RSC85 type-2 WSC payloads when possible, and writes CSV/JSON reports.

It does not patch files.
