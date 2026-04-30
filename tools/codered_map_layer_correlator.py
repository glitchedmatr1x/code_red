#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from codered_wsi_explorer import RPF6, rdr_hash


WTB_RE = re.compile(r"(?P<x>[0-9a-fA-F]{4})(?P<y>[0-9a-fA-F]{4})_bnd\.wtb$")
TERRAIN_WVD_RE = re.compile(r"resource_(?P<lod>\d+)[/\\]tile_(?P<x>-?\d+)_(?P<y>-?\d+)\.wvd$", re.I)


def signed16(hex_text: str) -> int:
    value = int(hex_text, 16)
    return value - 0x10000 if value & 0x8000 else value


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fields)
        if fields:
            writer.writeheader()
        writer.writerows(rows)


def collect_rpfs(paths: list[str]) -> list[Path]:
    output: list[Path] = []
    for item in paths:
        path = Path(item)
        if path.is_dir():
            output.extend(sorted(path.rglob("*.rpf")))
        elif path.exists() and path.suffix.lower() == ".rpf":
            output.append(path)
    return output


def layer_of(path: str) -> str:
    low = path.lower()
    if low.endswith(".wsi"):
        return "sector_info_wsi"
    if low.endswith(".wvd"):
        return "drawable_wvd"
    if low.endswith(".wbd"):
        return "bounds_wbd"
    if low.endswith(".wtb"):
        return "terrain_bounds_wtb"
    if low.endswith(".wtl"):
        return "terrain_lod_world_wtl"
    if low.endswith(".wtd"):
        return "texture_dictionary_wtd"
    if low.endswith(".wtx"):
        return "texture_wtx"
    if low.endswith(".xlist"):
        return "texture_xlist"
    if low.endswith(".dlc"):
        return "dlc_bounding_box"
    if low.endswith(".txt"):
        return "plain_text"
    return "other"


def inventory_archive(path: Path) -> tuple[dict, list[dict]]:
    rpf = RPF6(str(path))
    summary = rpf.summary()
    rows: list[dict] = []
    for entry in rpf.files():
        base_name = entry.name.rsplit(".", 1)[0] if "." in entry.name else entry.name
        rows.append(
            {
                "archive": path.name,
                "archive_path": str(path),
                "entry_path": entry.path,
                "name": entry.name,
                "extension": entry.ext,
                "layer": layer_of(entry.path),
                "size": entry.size,
                "offset": entry.offset,
                "is_resource": entry.resource,
                "resource_type": entry.resource_type,
                "base_name": base_name,
                "name_hash": f"0x{rdr_hash(base_name):08X}" if base_name and not base_name.startswith("0x") else "",
            }
        )
    return summary, rows


def terrainbound_rows(rows: list[dict], cell_size: int = 0x40) -> list[dict]:
    output: list[dict] = []
    for row in rows:
        if row.get("extension") != ".wtb":
            continue
        match = WTB_RE.search(row["name"])
        if not match:
            continue
        x_hex = match.group("x")
        y_hex = match.group("y")
        x_u16 = int(x_hex, 16)
        y_u16 = int(y_hex, 16)
        x_s16 = signed16(x_hex)
        y_s16 = signed16(y_hex)
        output.append(
            {
                **row,
                "grid_x_hex": x_hex,
                "grid_y_hex": y_hex,
                "grid_x_u16": x_u16,
                "grid_y_u16": y_u16,
                "grid_x_s16": x_s16,
                "grid_y_s16": y_s16,
                "bounds_grid_cell_size_guess": cell_size,
                "world_min_x_guess": x_s16,
                "world_min_y_guess": y_s16,
                "world_max_x_guess": x_s16 + cell_size,
                "world_max_y_guess": y_s16 + cell_size,
            }
        )
    return output


def terrainlod_rows(rows: list[dict]) -> list[dict]:
    output: list[dict] = []
    for row in rows:
        if row.get("extension") not in (".wvd", ".wtl"):
            continue
        entry_path = row["entry_path"].replace("\\", "/")
        match = TERRAIN_WVD_RE.search(entry_path)
        if match:
            x = int(match.group("x"))
            y = int(match.group("y"))
            lod = int(match.group("lod"))
            output.append(
                {
                    **row,
                    "terrain_lod": lod,
                    "tile_x": x,
                    "tile_y": y,
                    "tile_name": f"tile_{x}_{y}",
                    "terrain_role": "terrain_visual_tile",
                }
            )
        elif row.get("extension") == ".wtl":
            output.append(
                {
                    **row,
                    "terrain_lod": "",
                    "tile_x": "",
                    "tile_y": "",
                    "tile_name": row["base_name"],
                    "terrain_role": "terrain_lod_world",
                }
            )
    return output


def territory_asset_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row.get("extension") in (".wsi", ".wvd", ".wbd", ".dlc")]


def map_texture_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row.get("extension") in (".wtd", ".wtx", ".xlist")]


def layer_summary(rows: list[dict]) -> list[dict]:
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row.get("archive", ""), row.get("layer", ""))
        counts[key] = counts.get(key, 0) + 1
    return [
        {"archive": archive, "layer": layer, "count": count}
        for (archive, layer), count in sorted(counts.items())
    ]


def correlate(args: argparse.Namespace) -> None:
    rpfs = collect_rpfs(args.inputs)
    if not rpfs:
        raise SystemExit("No RPF files found. Pass extracted .rpf files or folders containing .rpf files.")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    summaries: list[dict] = []
    all_rows: list[dict] = []
    errors: list[dict] = []

    for rpf_path in rpfs:
        try:
            summary, rows = inventory_archive(rpf_path)
            summaries.append(summary)
            all_rows.extend(rows)
            print(f"Indexed {rpf_path.name}: {summary.get('file_count')} files")
        except Exception as exc:
            errors.append({"archive_path": str(rpf_path), "error": repr(exc)})
            print(f"Skipped {rpf_path}: {exc}")

    archive_rows = [
        {
            "archive": Path(summary["archive"]).name,
            "archive_path": summary["archive"],
            "entry_count": summary["entry_count"],
            "file_count": summary["file_count"],
            "dir_count": summary["dir_count"],
            "encrypted_toc": summary["encrypted_toc"],
            "extensions_json": json.dumps(summary.get("extensions", {}), sort_keys=True),
        }
        for summary in summaries
    ]

    territory_rows = territory_asset_rows(all_rows)
    terrainbound = terrainbound_rows(all_rows, args.bounds_cell_size)
    terrainlod = terrainlod_rows(all_rows)
    map_textures = map_texture_rows(all_rows)
    summaries_by_layer = layer_summary(all_rows)

    write_csv(outdir / "archive_layers.csv", archive_rows)
    write_csv(outdir / "layer_summary.csv", summaries_by_layer)
    write_csv(outdir / "all_resource_entries.csv", all_rows)
    write_csv(outdir / "territory_assets_wsi_wvd_wbd.csv", territory_rows)
    write_csv(outdir / "terrainbound_tiles_wtb.csv", terrainbound)
    write_csv(outdir / "terrainlod_tiles_wtl_wvd.csv", terrainlod)
    write_csv(outdir / "map_texture_resources.csv", map_textures)

    master = {
        "input_count": len(args.inputs),
        "archives_indexed": len(summaries),
        "errors": errors,
        "counts": {
            "all_entries": len(all_rows),
            "territory_assets": len(territory_rows),
            "terrainbound_tiles": len(terrainbound),
            "terrainlod_rows": len(terrainlod),
            "map_texture_rows": len(map_textures),
            "layer_summary_rows": len(summaries_by_layer),
        },
        "outputs": {
            "archive_layers": "archive_layers.csv",
            "layer_summary": "layer_summary.csv",
            "all_resource_entries": "all_resource_entries.csv",
            "territory_assets": "territory_assets_wsi_wvd_wbd.csv",
            "terrainbound_tiles": "terrainbound_tiles_wtb.csv",
            "terrainlod_tiles": "terrainlod_tiles_wtl_wvd.csv",
            "map_texture_resources": "map_texture_resources.csv",
        },
    }
    (outdir / "map_layer_correlation_master.json").write_text(json.dumps(master, indent=2), encoding="utf-8")
    print("Wrote", outdir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Code RED map layer correlator for territory / terrainbound / terrainlod / mapres RPFs")
    parser.add_argument("inputs", nargs="+", help="RPF files or folders containing RPF files")
    parser.add_argument("--outdir", default="exports/map_layer_correlation")
    parser.add_argument("--bounds-cell-size", type=int, default=0x40, help="CodeX BoundsGrid cell size guess. Default: 0x40.")
    args = parser.parse_args()
    correlate(args)


if __name__ == "__main__":
    main()
