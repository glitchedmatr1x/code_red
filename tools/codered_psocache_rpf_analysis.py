#!/usr/bin/env python3
"""Analyze psocache.rpf Pipeline State Object XML entries for Code RED research.

This is read-only against the game archive. It decodes compressed XML entries,
parses shader/state metadata, and writes AI-readable research outputs under
``research - Scan`` plus a short IMPORTANT log note.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
import sys
import zlib
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    import zstandard as zstd
except Exception:  # pragma: no cover - reported in output
    zstd = None  # type: ignore


CODE_RED_ROOT = Path(__file__).resolve().parents[1]
RED_DEAD_ROOT = CODE_RED_ROOT.parent
GAME_ROOT = RED_DEAD_ROOT / "game"
ARCHIVE_PATH = GAME_ROOT / "psocache.rpf"
TEMP_ROOT = GAME_ROOT / "_CodeRED_Temp_Later_RPF_Extract_20260502" / "live_psocache"
OUT_DIR = CODE_RED_ROOT / "research - Scan" / "IMPORTANT_psocache_rpf_analysis_2026-05-02"
LOG_NOTE = CODE_RED_ROOT / "logs" / "IMPORTANT_CodeRED_Psocache_RPF_Analysis_2026-05-02.md"
LOG_INDEX = CODE_RED_ROOT / "logs" / "CodeRED_LOG_INDEX.md"
RESEARCH_MANIFEST = CODE_RED_ROOT / "research - Scan" / "CodeRED_RESEARCH_MANIFEST.csv"

SEARCH_TERMS = (
    "vehicle", "car", "truck", "wagon", "horse", "ped", "npc", "law",
    "gang", "gringo", "cutscene", "camera", "terrain", "water", "decal",
    "shadow", "skin", "hair", "cloth", "foliage", "grass", "weapon",
    "blood", "fire", "smoke", "particle", "ui", "text", "impostor",
)


@dataclass
class EntryRow:
    entry_index: int
    internal_path: str
    filename_hash: str
    xml_hash: str
    payload_size: int
    compressed_size: int
    payload_sha1: str
    shader_filename: str
    technique_name: str
    pass_index: str
    blend_hash: str
    depth_stencil_hash: str
    framebuffer_hash: str
    raster_hash: str
    vertex_decl_hash: str
    vertex_shader_hash: str
    pixel_shader_hash: str
    root_signature_hash: str
    blend_enable_targets: str
    alpha_to_coverage: str
    independent_blend: str
    depth_enable: str
    depth_write_mask: str
    depth_func: str
    stencil_enable: str
    cull_mode: str
    fill_mode: str
    primitive_topology_type: str
    num_render_targets: str
    rtv_formats: str
    dsv_format: str
    input_semantics: str
    input_element_count: str
    matched_terms: str
    parse_error: str = ""


def load_rpf_utils():
    path = CODE_RED_ROOT / "tools - Implement" / "rpf_patch_utils.py"
    spec = importlib.util.spec_from_file_location("codered_rpf_patch_utils", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["codered_rpf_patch_utils"] = module
    spec.loader.exec_module(module)
    return module


RPF = load_rpf_utils()


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(CODE_RED_ROOT)).replace("\\", "/")
    except ValueError:
        try:
            return str(path.relative_to(RED_DEAD_ROOT)).replace("\\", "/")
        except ValueError:
            return str(path)


def decompress_slot(raw: bytes, ent: dict) -> bytes:
    if ent.get("is_resource"):
        return raw
    if not ent.get("is_compressed"):
        return raw
    if raw.startswith(b"\x28\xB5\x2F\xFD"):
        if zstd is None:
            raise RuntimeError("zstandard module unavailable")
        max_size = int(ent.get("total_size") or 0) or 64 * 1024 * 1024
        return zstd.ZstdDecompressor().decompress(raw, max_output_size=max_size)
    for wb in (-15, 15, 31):
        try:
            return zlib.decompress(raw, wb)
        except Exception:
            pass
    raise RuntimeError("unsupported compressed slot")


def text_of(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", "replace")


def attr(node: ET.Element | None, name: str) -> str:
    if node is None:
        return ""
    return node.attrib.get(name, "")


def child_attrs(root: ET.Element, tag: str) -> dict[str, str]:
    node = root.find(tag)
    return dict(node.attrib) if node is not None else {}


def render_target_blend_summary(root: ET.Element) -> str:
    node = root.find("BlendState")
    if node is None:
        return ""
    enabled: list[str] = []
    for child in list(node):
        if child.tag.startswith("RenderTarget_") and child.attrib.get("BlendEnable") == "1":
            enabled.append(child.tag.replace("RenderTarget_", "RT"))
    return "|".join(enabled)


def input_layout_summary(root: ET.Element) -> tuple[str, str]:
    layout = root.find("InputLayout")
    if layout is None:
        return "", ""
    semantics: list[str] = []
    for child in list(layout):
        if child.tag.startswith("Element_"):
            sem = child.attrib.get("SemanticName", "")
            fmt = child.attrib.get("Format", "")
            slot = child.attrib.get("InputSlot", "")
            offset = child.attrib.get("AlignedByteOffset", "")
            if sem:
                semantics.append(f"{sem}:fmt{fmt}:slot{slot}:off{offset}")
    return "|".join(semantics), layout.attrib.get("NumElements", str(len(semantics)))


def rtv_formats(root: ET.Element) -> str:
    formats: list[str] = []
    for child in list(root):
        if child.tag.startswith("RTVFormat_"):
            formats.append(child.attrib.get("RTVFormats", ""))
    return "|".join(formats)


def matched_terms(text: str) -> str:
    haystack = text.lower()
    found = [term for term in SEARCH_TERMS if term in haystack]
    return "|".join(found)


def parse_entry(ent: dict, payload: bytes) -> EntryRow:
    internal_path = ent.get("path", "")
    guessed_name = ent.get("name", "")
    filename_hash = guessed_name.rsplit(".", 1)[0] if guessed_name.endswith(".xml") else guessed_name
    xml_text = text_of(payload)
    xml_hash = ""
    payload_sha1 = sha1_bytes(payload)
    try:
        if not xml_text.lstrip().startswith("<"):
            return EntryRow(
                entry_index=int(ent.get("index", -1)),
                internal_path=internal_path,
                filename_hash=filename_hash,
                xml_hash="",
                payload_size=len(payload),
                compressed_size=int(ent.get("size_in_archive", 0)),
                payload_sha1=payload_sha1,
                shader_filename="",
                technique_name="",
                pass_index="",
                blend_hash="",
                depth_stencil_hash="",
                framebuffer_hash="",
                raster_hash="",
                vertex_decl_hash="",
                vertex_shader_hash="",
                pixel_shader_hash="",
                root_signature_hash="",
                blend_enable_targets="",
                alpha_to_coverage="",
                independent_blend="",
                depth_enable="",
                depth_write_mask="",
                depth_func="",
                stencil_enable="",
                cull_mode="",
                fill_mode="",
                primitive_topology_type="",
                num_render_targets="",
                rtv_formats="",
                dsv_format="",
                input_semantics="",
                input_element_count="",
                matched_terms=matched_terms(xml_text[:4096]),
                parse_error="non_xml_preload_list",
            )
        root = ET.fromstring(xml_text)
        xml_hash = root.attrib.get("hash", "")
        table = child_attrs(root, "PipelineStateHashTable")
        shader = child_attrs(root, "ShaderProgram")
        blend = child_attrs(root, "BlendState")
        depth = child_attrs(root, "DepthStencilState")
        raster = child_attrs(root, "RasterizerState")
        primitive = child_attrs(root, "PrimitiveTopologyType")
        targets = child_attrs(root, "NumRenderTargets")
        dsv = child_attrs(root, "DSVFormat")
        input_semantics, input_count = input_layout_summary(root)
        search_blob = " ".join([
            internal_path, xml_text[:4096], shader.get("filename", ""),
            shader.get("techniqueName", ""), input_semantics,
        ])
        return EntryRow(
            entry_index=int(ent.get("index", -1)),
            internal_path=internal_path,
            filename_hash=filename_hash,
            xml_hash=xml_hash,
            payload_size=len(payload),
            compressed_size=int(ent.get("size_in_archive", 0)),
            payload_sha1=payload_sha1,
            shader_filename=shader.get("filename", ""),
            technique_name=shader.get("techniqueName", ""),
            pass_index=shader.get("pass", ""),
            blend_hash=table.get("BlendStateHash", ""),
            depth_stencil_hash=table.get("DepthStencilHash", ""),
            framebuffer_hash=table.get("FramebufferHash", ""),
            raster_hash=table.get("RasterStateHash", ""),
            vertex_decl_hash=table.get("VertexDeclarationHash", ""),
            vertex_shader_hash=table.get("VertexShaderHash", ""),
            pixel_shader_hash=table.get("PixelShaderHash", ""),
            root_signature_hash=table.get("RootSignatureHash", ""),
            blend_enable_targets=render_target_blend_summary(root),
            alpha_to_coverage=blend.get("AlphaToCoverageEnable", ""),
            independent_blend=blend.get("IndependentBlendEnable", ""),
            depth_enable=depth.get("DepthEnable", ""),
            depth_write_mask=depth.get("DepthWriteMask", ""),
            depth_func=depth.get("DepthFunc", ""),
            stencil_enable=depth.get("StencilEnable", ""),
            cull_mode=raster.get("CullMode", ""),
            fill_mode=raster.get("FillMode", ""),
            primitive_topology_type=primitive.get("PrimitiveTopologyType", ""),
            num_render_targets=targets.get("NumRenderTargets", ""),
            rtv_formats=rtv_formats(root),
            dsv_format=dsv.get("DSVFormat", ""),
            input_semantics=input_semantics,
            input_element_count=input_count,
            matched_terms=matched_terms(search_blob),
        )
    except Exception as exc:
        return EntryRow(
            entry_index=int(ent.get("index", -1)),
            internal_path=internal_path,
            filename_hash=filename_hash,
            xml_hash=xml_hash,
            payload_size=len(payload),
            compressed_size=int(ent.get("size_in_archive", 0)),
            payload_sha1=payload_sha1,
            shader_filename="",
            technique_name="",
            pass_index="",
            blend_hash="",
            depth_stencil_hash="",
            framebuffer_hash="",
            raster_hash="",
            vertex_decl_hash="",
            vertex_shader_hash="",
            pixel_shader_hash="",
            root_signature_hash="",
            blend_enable_targets="",
            alpha_to_coverage="",
            independent_blend="",
            depth_enable="",
            depth_write_mask="",
            depth_func="",
            stencil_enable="",
            cull_mode="",
            fill_mode="",
            primitive_topology_type="",
            num_render_targets="",
            rtv_formats="",
            dsv_format="",
            input_semantics="",
            input_element_count="",
            matched_terms=matched_terms(xml_text[:4096]),
            parse_error=str(exc),
        )


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def counter_rows(counter: Counter, key_name: str, extra: dict[str, str] | None = None) -> list[dict]:
    base = extra or {}
    return [
        {**base, key_name: key, "count": count}
        for key, count in counter.most_common()
    ]


def short_counter(counter: Counter, limit: int = 12) -> str:
    return ", ".join(f"{k}={v}" for k, v in counter.most_common(limit))


def hash_to_u32(value: str) -> int | None:
    try:
        return int(value) & 0xFFFFFFFF
    except (TypeError, ValueError):
        return None


def append_once(path: Path, marker: str, text: str) -> None:
    existing = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    if marker in existing:
        return
    path.write_text(existing.rstrip() + "\n\n" + text.strip() + "\n", encoding="utf-8")


def update_log_index() -> None:
    if not LOG_INDEX.exists():
        return
    text = LOG_INDEX.read_text(encoding="utf-8", errors="replace")
    primary = "| IMPORTANT psocache RPF analysis | `../research - Scan/IMPORTANT_psocache_rpf_analysis_2026-05-02/psocache_analysis.md` | Dedicated parsed PSO/shader-state cache inventory for `psocache.rpf`; confirms render-only relevance. |"
    read_step = "| 8 | `../research - Scan/IMPORTANT_psocache_rpf_analysis_2026-05-02/psocache_analysis.md` | Dedicated psocache shader/PSO metadata inventory and modding relevance warning. |"
    source = "| `../research - Scan/IMPORTANT_psocache_rpf_analysis_2026-05-02/psocache_analysis.md` | Important PSO/shader-state cache analysis for `psocache.rpf`. |"
    generated = "| `../research - Scan/IMPORTANT_psocache_rpf_analysis_2026-05-02/` | `psocache_analysis.md`, `psocache_analysis.json`, `psocache_entries.csv`, `psocache_shader_programs.csv`, `psocache_techniques.csv`, `psocache_state_hashes.csv`, `psocache_duplicates.csv`, `psocache_interesting_terms.csv`, `psocache_preload_list.csv` |"
    if primary not in text:
        text = text.replace(
            "| IMPORTANT later RPF compare | `../research - Scan/IMPORTANT_later_rpf_compare_2026-05-02/later_rpf_compare.md` | Temporary extraction and comparison of later/live game-folder RPF readable entries for remapping. |",
            "| IMPORTANT later RPF compare | `../research - Scan/IMPORTANT_later_rpf_compare_2026-05-02/later_rpf_compare.md` | Temporary extraction and comparison of later/live game-folder RPF readable entries for remapping. |\n" + primary,
        )
    if read_step not in text:
        text = text.replace(
            "| 7 | `../research - Scan/IMPORTANT_later_rpf_compare_2026-05-02/later_rpf_compare.md` | Important later/live RPF extraction compare, old-root matching, and version-diff matrix. |",
            "| 7 | `../research - Scan/IMPORTANT_later_rpf_compare_2026-05-02/later_rpf_compare.md` | Important later/live RPF extraction compare, old-root matching, and version-diff matrix. |\n" + read_step,
        )
    if source not in text:
        text = text.replace(
            "| `../research - Scan/IMPORTANT_later_rpf_compare_2026-05-02/later_rpf_compare.md` | Important comparison/remap index for later/live RPF readable entries. |",
            "| `../research - Scan/IMPORTANT_later_rpf_compare_2026-05-02/later_rpf_compare.md` | Important comparison/remap index for later/live RPF readable entries. |\n" + source,
        )
    if generated not in text:
        text = text.replace(
            "| `../research - Scan/IMPORTANT_later_rpf_compare_2026-05-02/` | `later_rpf_compare.md`, `later_rpf_extract_manifest.csv`, `later_rpf_remap_candidates.csv`, `later_rpf_version_diffs.csv`, `later_rpf_changed_between_versions.csv` |",
            "| `../research - Scan/IMPORTANT_later_rpf_compare_2026-05-02/` | `later_rpf_compare.md`, `later_rpf_extract_manifest.csv`, `later_rpf_remap_candidates.csv`, `later_rpf_version_diffs.csv`, `later_rpf_changed_between_versions.csv` |\n" + generated,
        )
    LOG_INDEX.write_text(text, encoding="utf-8")


def update_manifest() -> None:
    rows = [
        ("important", "IMPORTANT Psocache RPF Analysis Summary", "IMPORTANT_psocache_rpf_analysis_2026-05-02/psocache_analysis.md", "md", "Dedicated parsed PSO shader-state cache analysis for psocache.rpf"),
        ("important", "IMPORTANT Psocache RPF Structured Data", "IMPORTANT_psocache_rpf_analysis_2026-05-02/psocache_analysis.json", "json", "Structured psocache archive entries counters duplicates and conclusions"),
        ("render", "Psocache Parsed Entries", "IMPORTANT_psocache_rpf_analysis_2026-05-02/psocache_entries.csv", "csv", "Every psocache PSO XML entry parsed into shader state fields"),
        ("render", "Psocache Shader Programs", "IMPORTANT_psocache_rpf_analysis_2026-05-02/psocache_shader_programs.csv", "csv", "Shader filename technique pass counts"),
        ("render", "Psocache Techniques", "IMPORTANT_psocache_rpf_analysis_2026-05-02/psocache_techniques.csv", "csv", "Technique frequency counts across psocache"),
        ("render", "Psocache State Hashes", "IMPORTANT_psocache_rpf_analysis_2026-05-02/psocache_state_hashes.csv", "csv", "Pipeline hash component frequency counts"),
        ("render", "Psocache Duplicate Payloads", "IMPORTANT_psocache_rpf_analysis_2026-05-02/psocache_duplicates.csv", "csv", "Duplicate payload/state groups if present"),
        ("render", "Psocache Interesting Terms", "IMPORTANT_psocache_rpf_analysis_2026-05-02/psocache_interesting_terms.csv", "csv", "Term hits showing shader-only references such as vehicle or terrain"),
        ("render", "Psocache Preload Hash List", "IMPORTANT_psocache_rpf_analysis_2026-05-02/psocache_preload_list.csv", "csv", "Preload hash list and whether each hash has matching PSO XML"),
    ]
    existing = RESEARCH_MANIFEST.read_text(encoding="utf-8", errors="replace") if RESEARCH_MANIFEST.exists() else "topic,title,path,format,notes\n"
    lines = existing.rstrip().splitlines()
    present = {line.split(",", 3)[2] for line in lines[1:] if "," in line}
    with RESEARCH_MANIFEST.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if not lines:
            writer.writerow(["topic", "title", "path", "format", "notes"])
        for row in rows:
            if row[2] not in present:
                writer.writerow(row)


def analyze() -> dict:
    if not ARCHIVE_PATH.exists():
        raise FileNotFoundError(ARCHIVE_PATH)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_NOTE.parent.mkdir(parents=True, exist_ok=True)

    info = RPF.parse(ARCHIVE_PATH, with_debug=True)
    rows: list[EntryRow] = []
    errors: list[dict] = []
    for ent in info["entries"]:
        if ent.get("type") != "file":
            continue
        try:
            raw = RPF.read_slot(ARCHIVE_PATH, ent)
            payload = decompress_slot(raw, ent)
            rows.append(parse_entry(ent, payload))
        except Exception as exc:
            errors.append({
                "entry_index": ent.get("index", ""),
                "internal_path": ent.get("path", ""),
                "error": str(exc),
            })

    entry_dicts = [asdict(row) for row in sorted(rows, key=lambda r: r.entry_index)]
    write_csv(OUT_DIR / "psocache_entries.csv", entry_dicts)
    if errors:
        write_csv(OUT_DIR / "psocache_errors.csv", errors)

    pso_rows = [row for row in rows if not row.parse_error]
    preload_rows = [row for row in rows if row.parse_error == "non_xml_preload_list"]
    xml_parse_error_rows = [
        row for row in rows
        if row.parse_error and row.parse_error != "non_xml_preload_list"
    ]

    preload_hashes: list[str] = []
    for preload_row in preload_rows:
        preload_ent = next((ent for ent in info["entries"] if ent.get("index") == preload_row.entry_index), None)
        if preload_ent is None:
            continue
        try:
            payload = decompress_slot(RPF.read_slot(ARCHIVE_PATH, preload_ent), preload_ent)
        except Exception:
            continue
        preload_hashes.extend(
            line.strip()
            for line in text_of(payload).splitlines()
            if line.strip() and re.fullmatch(r"-?\d+", line.strip())
        )
    pso_xml_hashes_u32 = {
        normalized
        for row in pso_rows
        for normalized in [hash_to_u32(row.xml_hash)]
        if normalized is not None
    }
    preload_list_rows = [
        {
            "preload_hash": value,
            "normalized_u32": "" if hash_to_u32(value) is None else str(hash_to_u32(value)),
            "has_matching_pso_xml": "yes" if hash_to_u32(value) in pso_xml_hashes_u32 else "no",
        }
        for value in preload_hashes
    ]
    write_csv(OUT_DIR / "psocache_preload_list.csv", preload_list_rows, ["preload_hash", "normalized_u32", "has_matching_pso_xml"])

    shader_program_counter = Counter((r.shader_filename, r.technique_name, r.pass_index) for r in pso_rows)
    shader_rows = [
        {"shader_filename": shader, "technique_name": tech, "pass_index": p, "count": count}
        for (shader, tech, p), count in shader_program_counter.most_common()
    ]
    write_csv(OUT_DIR / "psocache_shader_programs.csv", shader_rows)

    technique_counter = Counter(r.technique_name for r in pso_rows if r.technique_name)
    write_csv(OUT_DIR / "psocache_techniques.csv", counter_rows(technique_counter, "technique_name"))

    state_rows: list[dict] = []
    for field in (
        "blend_hash", "depth_stencil_hash", "framebuffer_hash", "raster_hash",
        "vertex_decl_hash", "vertex_shader_hash", "pixel_shader_hash",
        "root_signature_hash", "rtv_formats", "dsv_format", "input_semantics",
        "cull_mode", "depth_enable", "stencil_enable",
    ):
        counter = Counter(getattr(row, field) for row in pso_rows if getattr(row, field))
        state_rows.extend(counter_rows(counter, "value", {"field": field}))
    write_csv(OUT_DIR / "psocache_state_hashes.csv", state_rows, ["field", "value", "count"])

    by_sha1: dict[str, list[EntryRow]] = defaultdict(list)
    by_state_signature: dict[str, list[EntryRow]] = defaultdict(list)
    for row in pso_rows:
        by_sha1[row.payload_sha1].append(row)
        sig = "|".join([
            row.shader_filename, row.technique_name, row.pass_index, row.blend_hash,
            row.depth_stencil_hash, row.framebuffer_hash, row.raster_hash,
            row.vertex_decl_hash, row.vertex_shader_hash, row.pixel_shader_hash,
            row.root_signature_hash, row.input_semantics, row.rtv_formats, row.dsv_format,
        ])
        by_state_signature[sig].append(row)
    duplicate_rows: list[dict] = []
    for kind, groups in (("payload_sha1", by_sha1), ("state_signature", by_state_signature)):
        for key, group in groups.items():
            if len(group) <= 1:
                continue
            duplicate_rows.append({
                "duplicate_kind": kind,
                "key": key,
                "count": len(group),
                "entry_indexes": "|".join(str(r.entry_index) for r in group),
                "internal_paths": "|".join(r.internal_path for r in group),
                "shader_programs": "|".join(sorted({f"{r.shader_filename}:{r.technique_name}:pass{r.pass_index}" for r in group})),
            })
    write_csv(OUT_DIR / "psocache_duplicates.csv", duplicate_rows, ["duplicate_kind", "key", "count", "entry_indexes", "internal_paths", "shader_programs"])

    interesting_rows: list[dict] = []
    for row in pso_rows:
        if not row.matched_terms:
            continue
        interesting_rows.append({
            "entry_index": row.entry_index,
            "internal_path": row.internal_path,
            "shader_filename": row.shader_filename,
            "technique_name": row.technique_name,
            "pass_index": row.pass_index,
            "matched_terms": row.matched_terms,
            "input_semantics": row.input_semantics,
        })
    write_csv(OUT_DIR / "psocache_interesting_terms.csv", interesting_rows, ["entry_index", "internal_path", "shader_filename", "technique_name", "pass_index", "matched_terms", "input_semantics"])

    shader_counter = Counter(r.shader_filename for r in pso_rows if r.shader_filename)
    pass_counter = Counter(r.pass_index for r in pso_rows if r.pass_index != "")
    input_count_counter = Counter(r.input_element_count for r in pso_rows if r.input_element_count)
    topology_counter = Counter(r.primitive_topology_type for r in pso_rows if r.primitive_topology_type)
    rtv_counter = Counter(r.rtv_formats for r in pso_rows if r.rtv_formats)
    dsv_counter = Counter(r.dsv_format for r in pso_rows if r.dsv_format)
    parse_error_count = len(xml_parse_error_rows)
    xml_hash_mismatch = [
        r for r in rows
        if r.filename_hash
        and r.xml_hash
        and hash_to_u32(r.filename_hash) != hash_to_u32(r.xml_hash)
    ]
    compression_total = sum(r.compressed_size for r in rows)
    payload_total = sum(r.payload_size for r in rows)

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "archive_path": str(ARCHIVE_PATH),
        "archive_size": ARCHIVE_PATH.stat().st_size,
        "entry_count": info["entry_count"],
        "file_count": info["file_count"],
        "dir_count": info["dir_count"],
        "resolved_count": info["resolved_count"],
        "decoded_entries": len(rows),
        "pso_xml_entries": len(pso_rows),
        "preload_list_entries": len(preload_rows),
        "preload_hash_count": len(preload_hashes),
        "preload_hashes_with_matching_pso_xml": sum(1 for value in preload_hashes if hash_to_u32(value) in pso_xml_hashes_u32),
        "preload_hashes_missing_pso_xml": sum(1 for value in preload_hashes if hash_to_u32(value) not in pso_xml_hashes_u32),
        "decode_errors": len(errors),
        "parse_error_count": parse_error_count,
        "xml_hash_mismatch_count": len(xml_hash_mismatch),
        "compressed_payload_total": compression_total,
        "decoded_payload_total": payload_total,
        "compression_ratio_decoded_to_archive_payload": round(payload_total / compression_total, 3) if compression_total else 0,
        "unique_shader_filenames": len(shader_counter),
        "unique_shader_programs": len(shader_program_counter),
        "unique_techniques": len(technique_counter),
        "unique_payload_sha1": len(by_sha1),
        "duplicate_payload_groups": sum(1 for group in by_sha1.values() if len(group) > 1),
        "duplicate_state_signature_groups": sum(1 for group in by_state_signature.values() if len(group) > 1),
        "interesting_term_rows": len(interesting_rows),
        "top_shader_filenames": shader_counter.most_common(30),
        "top_shader_programs": [
            {"shader_filename": shader, "technique_name": tech, "pass_index": p, "count": count}
            for (shader, tech, p), count in shader_program_counter.most_common(30)
        ],
        "top_techniques": technique_counter.most_common(40),
        "pass_counts": pass_counter.most_common(),
        "input_element_counts": input_count_counter.most_common(),
        "topologies": topology_counter.most_common(),
        "rtv_formats": rtv_counter.most_common(20),
        "dsv_formats": dsv_counter.most_common(20),
        "outputs": {
            "summary_md": rel(OUT_DIR / "psocache_analysis.md"),
            "summary_json": rel(OUT_DIR / "psocache_analysis.json"),
            "entries_csv": rel(OUT_DIR / "psocache_entries.csv"),
            "shader_programs_csv": rel(OUT_DIR / "psocache_shader_programs.csv"),
            "techniques_csv": rel(OUT_DIR / "psocache_techniques.csv"),
            "state_hashes_csv": rel(OUT_DIR / "psocache_state_hashes.csv"),
            "duplicates_csv": rel(OUT_DIR / "psocache_duplicates.csv"),
            "interesting_terms_csv": rel(OUT_DIR / "psocache_interesting_terms.csv"),
            "preload_list_csv": rel(OUT_DIR / "psocache_preload_list.csv"),
            "log_note": rel(LOG_NOTE),
        },
    }

    (OUT_DIR / "psocache_analysis.json").write_text(json.dumps({
        "summary": summary,
        "entries": entry_dicts,
        "errors": errors,
        "duplicates": duplicate_rows,
        "interesting_terms": interesting_rows,
    }, indent=2), encoding="utf-8")

    md = f"""# IMPORTANT Psocache RPF Analysis - 2026-05-02

Source archive: `{ARCHIVE_PATH}`

## Summary

- RPF entries: `{info["entry_count"]}` total, `{info["file_count"]}` files, `{info["dir_count"]}` dirs.
- Debug names resolved: `{info["resolved_count"]}` / `{info["entry_count"]}`.
- Decoded entries: `{len(rows)}`.
- Parsed PSO XML entries: `{len(pso_rows)}`.
- Preload list entries: `{len(preload_rows)}`.
- Preload hash count: `{len(preload_hashes)}`.
- Preload hashes with matching PSO XML: `{summary["preload_hashes_with_matching_pso_xml"]}`.
- Preload hashes missing PSO XML in archive: `{summary["preload_hashes_missing_pso_xml"]}`.
- Decode errors: `{len(errors)}`.
- XML parse errors: `{parse_error_count}`.
- Filename hash mismatches vs XML root hash: `{len(xml_hash_mismatch)}`.
- Compressed archive payload bytes: `{compression_total}`.
- Decoded XML payload bytes: `{payload_total}`.
- Decoded/compressed payload ratio: `{summary["compression_ratio_decoded_to_archive_payload"]}`.
- Unique shader filenames: `{len(shader_counter)}`.
- Unique shader filename + technique + pass combinations: `{len(shader_program_counter)}`.
- Unique techniques: `{len(technique_counter)}`.
- Duplicate exact XML payload groups: `{summary["duplicate_payload_groups"]}`.
- Duplicate full state-signature groups: `{summary["duplicate_state_signature_groups"]}`.

## Research Conclusion

`psocache.rpf` is a render Pipeline State Object cache. It contains one `preload.list` plus numeric XML files named by PSO hash. Each PSO XML contains shader program/technique/pass metadata plus blend, rasterizer, depth/stencil, input-layout, render-target, and shader hash fields.

This archive is not a vehicle spawning, gringo, cutscene script, faction, AI behavior, navmesh, or stringtable source. It can matter for rendering/performance diagnostics and shader-state remapping, but it should not be patched for Code RED spawn or AI behavior work unless the goal is specifically render pipeline experimentation.

## Top Shader Filenames

{chr(10).join(f"- `{name}`: {count}" for name, count in shader_counter.most_common(20))}

## Top Shader Program / Technique / Pass Combos

{chr(10).join(f"- `{shader}` / `{tech}` / pass `{p}`: {count}" for (shader, tech, p), count in shader_program_counter.most_common(25))}

## Top Techniques

{chr(10).join(f"- `{name}`: {count}" for name, count in technique_counter.most_common(30))}

## State Shape Quick Counts

- Passes: `{short_counter(pass_counter)}`
- Input element counts: `{short_counter(input_count_counter)}`
- Primitive topology types: `{short_counter(topology_counter)}`
- RTV formats: `{short_counter(rtv_counter)}`
- DSV formats: `{short_counter(dsv_counter)}`

## Files Generated

- `psocache_analysis.json` - full structured data.
- `psocache_entries.csv` - one row per PSO XML entry.
- `psocache_shader_programs.csv` - shader filename / technique / pass counts.
- `psocache_techniques.csv` - technique counts.
- `psocache_state_hashes.csv` - individual hash/state value counts.
- `psocache_duplicates.csv` - duplicate payload and full state-signature groups.
- `psocache_interesting_terms.csv` - shader-only keyword hits for quick filtering.
- `psocache_preload_list.csv` - preload hash list and whether each hash has a matching PSO XML entry.

## AI Index Notes

- For spawn/AI/faction work, prefer `content.rpf`, `tune_d11generic.rpf`, extracted `root` XML/scripts, WSI, gringo, and navres reports.
- For render/performance research, use `psocache_shader_programs.csv`, `psocache_techniques.csv`, and `psocache_state_hashes.csv`.
- Keyword hits in this report are shader-name or technique-name matches only; they are not gameplay metadata references.
"""
    (OUT_DIR / "psocache_analysis.md").write_text(md, encoding="utf-8")

    log_md = f"""# IMPORTANT Code RED Psocache RPF Analysis - 2026-05-02

Dedicated analysis added for `psocache.rpf`.

Primary report:
- `{rel(OUT_DIR / "psocache_analysis.md")}`

Generated data:
- `{rel(OUT_DIR / "psocache_entries.csv")}`
- `{rel(OUT_DIR / "psocache_shader_programs.csv")}`
- `{rel(OUT_DIR / "psocache_techniques.csv")}`
- `{rel(OUT_DIR / "psocache_state_hashes.csv")}`
- `{rel(OUT_DIR / "psocache_duplicates.csv")}`
- `{rel(OUT_DIR / "psocache_interesting_terms.csv")}`
- `{rel(OUT_DIR / "psocache_preload_list.csv")}`

Key results:
- Decoded entries: `{len(rows)}`
- Parsed PSO XML entries: `{len(pso_rows)}`
- Preload hash count: `{len(preload_hashes)}`
- Unique shader filenames: `{len(shader_counter)}`
- Unique shader/technique/pass combos: `{len(shader_program_counter)}`
- Unique techniques: `{len(technique_counter)}`
- Decode errors: `{len(errors)}`
- Parse errors: `{parse_error_count}`

Conclusion:
- `psocache.rpf` is render Pipeline State Object cache data.
- It is important for shader/render-state/performance research.
- It is not a direct source for vehicle spawning, gringo behavior, cutscene scripting, factions, AI commands, navmesh, or strings.
"""
    LOG_NOTE.write_text(log_md, encoding="utf-8")

    update_log_index()
    update_manifest()
    return summary


def main() -> int:
    summary = analyze()
    print(json.dumps({
        "archive": summary["archive_path"],
        "decoded_entries": summary["decoded_entries"],
        "decode_errors": summary["decode_errors"],
        "parse_error_count": summary["parse_error_count"],
        "output": str(OUT_DIR),
        "log_note": str(LOG_NOTE),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
