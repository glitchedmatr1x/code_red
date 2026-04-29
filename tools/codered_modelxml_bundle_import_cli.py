#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path
import xml.etree.ElementTree as ET

# The export CLI already contains the RPF6 parser, resource parser, resource payload reader,
# string/reference scanner, and Model XML bundle writer. Reuse it so import/export stay paired.
THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import codered_modelxml_bundle_cli as modelxml_export  # noqa: E402

MODEL_EXTS = modelxml_export.MODEL_EXTS


def sha1_hex(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def copy_file_streamed(src: Path, dst: Path, chunk_size: int = 16 * 1024 * 1024) -> None:
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + '.tmp_copying')
    if tmp.exists():
        tmp.unlink()
    with src.open('rb') as fsrc, tmp.open('wb') as fdst:
        while True:
            chunk = fsrc.read(chunk_size)
            if not chunk:
                break
            fdst.write(chunk)
        fdst.flush()
    try:
        shutil.copystat(src, tmp)
    except Exception:
        pass
    if dst.exists():
        dst.unlink()
    tmp.replace(dst)


def safe_filename(value: str, default: str = 'asset') -> str:
    value = str(value or default).replace('\\', '/')
    value = Path(value).name
    value = re.sub(r'[^A-Za-z0-9_.-]+', '_', value).strip('._')
    return (value or default)[:140]


def load_bundle_manifest(bundle: Path) -> dict:
    manifest_path = bundle / 'manifest.json'
    if not manifest_path.exists():
        raise FileNotFoundError(f'Missing manifest.json in bundle: {bundle}')
    return json.loads(manifest_path.read_text(encoding='utf-8'))


def find_bundle_raw_file(bundle: Path, manifest: dict) -> Path:
    asset_name = manifest.get('asset_name') or ''
    candidates: list[Path] = []
    if asset_name:
        candidates.append(bundle / safe_filename(asset_name))
        candidates.append(bundle / Path(asset_name).name)
    for ext in MODEL_EXTS:
        candidates.extend(sorted(bundle.glob(f'*{ext}')))
    for candidate in candidates:
        if candidate.exists() and candidate.is_file() and candidate.suffix.lower() in MODEL_EXTS:
            return candidate
    raise FileNotFoundError(f'No raw model/resource file found in bundle: {bundle}')


def find_payload_sidecar(bundle: Path, manifest: dict, raw_file: Path) -> Path | None:
    # Prefer XML/manifest hints, then fall back to the conventional sidecar path.
    sidecars = bundle / 'sidecars'
    xml_value = manifest.get('xml') or ''
    xml_path = Path(xml_value)
    if not xml_path.is_absolute():
        xml_path = bundle / xml_path.name
    if xml_path.exists():
        try:
            root = ET.parse(xml_path).getroot()
            payload = root.find('Payload')
            if payload is not None:
                sidecar = payload.get('sidecar') or ''
                if sidecar:
                    p = bundle / sidecar
                    if p.exists():
                        return p
        except Exception:
            pass
    expected = sidecars / f'{raw_file.name}.payload.bin'
    if expected.exists():
        return expected
    payloads = sorted(sidecars.glob('*.payload.bin')) if sidecars.exists() else []
    return payloads[0] if payloads else None




def find_bundle_xml(bundle: Path, manifest: dict) -> Path | None:
    candidates: list[Path] = []
    for key in ('edit_xml', 'xml'):
        value = manifest.get(key) or ''
        if value:
            xp = Path(value)
            candidates.append(xp if xp.is_absolute() else bundle / xp.name)
    candidates.extend(sorted(bundle.glob('*.modelxml.xml')))
    candidates.extend(sorted(bundle.glob('*.xml')))
    for xp in candidates:
        if xp.exists() and xp.is_file():
            return xp
    return None


def _decode_xml_text(value: str) -> bytes:
    return (value or '').encode('latin-1')


def apply_xml_edit_plan(data: bytes, bundle: Path, manifest: dict) -> tuple[bytes, list[dict]]:
    xml_path = find_bundle_xml(bundle, manifest)
    if not xml_path:
        return data, []
    root = ET.parse(xml_path).getroot()
    out = bytearray(data)
    report: list[dict] = []

    strings = root.find('EditableStrings')
    if strings is not None:
        for node in strings.findall('String'):
            sid = node.get('id') or ''
            original = node.get('original') or ''
            value = node.get('value') if node.get('value') is not None else original
            try:
                offset = int(node.get('offset') or '0', 0)
                length = int(node.get('length') or '0', 0)
            except Exception as exc:
                raise ValueError(f'Bad EditableStrings offset/length on {sid}: {exc}') from exc
            if value == original:
                continue
            old_b = _decode_xml_text(original)
            new_b = _decode_xml_text(value)
            if len(new_b) > length:
                raise ValueError(f'XML edit {sid} is too long: {len(new_b)} bytes > slot length {length}.')
            if offset < 0 or offset + length > len(out):
                raise ValueError(f'XML edit {sid} points outside the imported file: offset={offset}, length={length}, file={len(out)}.')
            current = bytes(out[offset:offset + len(old_b)])
            if old_b and current != old_b:
                raise ValueError(f'XML edit {sid} original bytes do not match at offset {offset}. Refusing unsafe patch.')
            padded = new_b + (b'\x00' * (length - len(new_b)))
            out[offset:offset + length] = padded
            report.append({'kind': 'xml-string', 'id': sid, 'offset': offset, 'length': length, 'old': original, 'new': value, 'null_padded': len(new_b) < length})

    patches = root.find('EditableBytePatches')
    if patches is not None:
        for node in patches.findall('Patch'):
            enabled = (node.get('enabled') or 'false').strip().lower() in {'1', 'true', 'yes', 'on'}
            if not enabled:
                continue
            pid = node.get('id') or ''
            try:
                offset = int(node.get('offset') or '0', 0)
                length = int(node.get('length') or '0', 0)
                raw = bytes.fromhex((node.get('hex') or '').replace(' ', ''))
            except Exception as exc:
                raise ValueError(f'Bad byte patch {pid}: {exc}') from exc
            if length and len(raw) != length:
                raise ValueError(f'Byte patch {pid} length mismatch: declared {length}, hex gives {len(raw)} bytes.')
            if offset < 0 or offset + len(raw) > len(out):
                raise ValueError(f'Byte patch {pid} points outside the imported file.')
            out[offset:offset + len(raw)] = raw
            report.append({'kind': 'xml-byte-patch', 'id': pid, 'offset': offset, 'length': len(raw)})
    return bytes(out), report


def parse_bundle_text_replacements(bundle: Path, manifest: dict) -> list[tuple[str, str]]:
    candidates: list[Path] = []
    value = manifest.get('edit_text') or ''
    if value:
        tp = Path(value)
        candidates.append(tp if tp.is_absolute() else bundle / tp.name)
    candidates.extend(sorted(bundle.glob('*.model_edits.txt')))
    replacements: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for path in candidates:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            if line.lower().startswith('replace '):
                line = line[8:].strip()
            if '=>' not in line:
                continue
            old, new = [part.strip() for part in line.split('=>', 1)]
            if len(old) >= 2 and old[0] == old[-1] == '"':
                old = old[1:-1]
            if len(new) >= 2 and new[0] == new[-1] == '"':
                new = new[1:-1]
            pair = (old, new)
            if old and pair not in seen and old != new:
                seen.add(pair)
                replacements.append(pair)
    return replacements

def rebuild_from_payload_sidecar(raw_bytes: bytes, payload_bytes: bytes) -> bytes:
    resource = modelxml_export.parse_resource_header(raw_bytes)
    if not resource:
        # No wrapper to rebuild; for plain files the payload is the file.
        return payload_bytes
    header_size = modelxml_export.resource_header_size(resource)
    if len(raw_bytes) < header_size:
        raise ValueError('Raw resource header is shorter than expected.')
    return raw_bytes[:header_size] + payload_bytes


def apply_same_length_text_replacements(data: bytes, replacements: list[tuple[str, str]]) -> tuple[bytes, list[dict]]:
    out = bytearray(data)
    report: list[dict] = []
    for old, new in replacements:
        old_b = old.encode('latin-1')
        new_b = new.encode('latin-1')
        if len(new_b) > len(old_b):
            raise ValueError(f'Replacement must keep the same byte length or shorter: {old!r} ({len(old_b)}) vs {new!r} ({len(new_b)})')
        patched = new_b + (b'\x00' * (len(old_b) - len(new_b)))
        hits = []
        start = 0
        while True:
            pos = bytes(out).find(old_b, start)
            if pos < 0:
                break
            out[pos:pos + len(old_b)] = patched
            hits.append(pos)
            start = pos + len(old_b)
        report.append({'kind': 'text-replace', 'old': old, 'new': new, 'old_length': len(old_b), 'new_length': len(new_b), 'null_padded': len(new_b) < len(old_b), 'hits': hits, 'hit_count': len(hits)})
    return bytes(out), report


def validate_model_resource(data: bytes) -> dict:
    resource = modelxml_export.parse_resource_header(data)
    payload_info = modelxml_export.extract_resource_payload(data, resource)
    payload = payload_info.get('payload') or b''
    refs, bone_hints = modelxml_export.scan_refs(payload)
    streams = modelxml_export.model_candidates(payload, limit=3)
    return {
        'read_ok': True,
        'size': len(data),
        'sha1': sha1_hex(data),
        'resource': resource,
        'payload_bytes': len(payload),
        'payload_notes': payload_info.get('notes', []),
        'texture_ref_count': sum(len(v) for v in refs.values()),
        'texture_refs': refs,
        'bone_hint_count': len(bone_hints),
        'heuristic_stream_count': len(streams),
        'heuristic_streams': [{k: v for k, v in row.items() if k != 'points'} for row in streams],
    }


def build_imported_file(bundle: Path, out_root: Path, mode: str, replacements: list[tuple[str, str]], apply_xml_edits: bool = True, apply_text_sheet: bool = True) -> dict:
    bundle = Path(bundle)
    manifest = load_bundle_manifest(bundle)
    raw_file = find_bundle_raw_file(bundle, manifest)
    raw_bytes = raw_file.read_bytes()
    sidecar = find_payload_sidecar(bundle, manifest, raw_file)

    if mode == 'raw-clone':
        imported = raw_bytes
        import_mode_note = 'Copied the exported raw resource file from the bundle.'
    elif mode == 'payload-sidecar':
        if sidecar is None:
            raise FileNotFoundError('payload-sidecar mode needs a sidecars/*.payload.bin file.')
        imported = rebuild_from_payload_sidecar(raw_bytes, sidecar.read_bytes())
        import_mode_note = 'Rebuilt the resource stream from the original resource header plus exported payload sidecar.'
    else:
        raise ValueError(f'Unknown import mode: {mode}')

    replacement_report: list[dict] = []
    xml_edit_report: list[dict] = []
    text_sheet_report: list[dict] = []
    if apply_xml_edits:
        imported, xml_edit_report = apply_xml_edit_plan(imported, bundle, manifest)
        if xml_edit_report:
            import_mode_note += ' Applied XML editable field patch(es).'
    text_sheet_replacements = parse_bundle_text_replacements(bundle, manifest) if apply_text_sheet else []
    if text_sheet_replacements:
        imported, text_sheet_report = apply_same_length_text_replacements(imported, text_sheet_replacements)
        import_mode_note += ' Applied TXT edit-sheet replacement(s).'
    if replacements:
        imported, replacement_report = apply_same_length_text_replacements(imported, replacements)
        import_mode_note += ' Applied command-line text/reference replacement(s).'

    out_root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    suffix = raw_file.suffix or Path(manifest.get('asset_name', 'asset.wvd')).suffix or '.bin'
    name = f'{safe_filename(Path(raw_file.name).stem)}_imported_{stamp}{suffix}'
    imported_path = out_root / name
    imported_path.write_bytes(imported)

    raw_payload_info = modelxml_export.extract_resource_payload(raw_bytes, modelxml_export.parse_resource_header(raw_bytes))
    imported_payload_info = modelxml_export.extract_resource_payload(imported, modelxml_export.parse_resource_header(imported))
    validation = validate_model_resource(imported)
    result = {
        'status': 'import_file_written',
        'bundle': str(bundle),
        'source_raw_file': str(raw_file),
        'source_payload_sidecar': str(sidecar) if sidecar else '',
        'import_mode': mode,
        'note': import_mode_note,
        'imported_file': str(imported_path),
        'raw_bytes': len(raw_bytes),
        'imported_bytes': len(imported),
        'byte_identical_to_bundle_raw': imported == raw_bytes,
        'payload_identical_to_bundle_payload': (raw_payload_info.get('payload') == imported_payload_info.get('payload')),
        'source_sha1': sha1_hex(raw_bytes),
        'imported_sha1': sha1_hex(imported),
        'replacements': replacement_report,
        'xml_edits': xml_edit_report,
        'text_sheet_edits': text_sheet_report,
        'validation': validation,
    }
    (imported_path.with_suffix(imported_path.suffix + '.import_report.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def find_archive_entry(archive_info: dict, entry_query: str, imported_path: Path | None = None) -> dict:
    q = (entry_query or '').lower().strip()
    candidates = []
    for entry in archive_info.get('entries', []):
        if entry.get('type') != 'file':
            continue
        hay = f"{entry.get('path', '')} {entry.get('name', '')}".lower()
        if q and q in hay:
            candidates.append(entry)
    if not candidates and imported_path is not None:
        name = imported_path.name.lower().replace('_imported', '')
        stem = imported_path.stem.lower().split('_imported')[0]
        for entry in archive_info.get('entries', []):
            if entry.get('type') == 'file' and (entry.get('name', '').lower() == name or entry.get('name', '').lower().startswith(stem)):
                candidates.append(entry)
    if not candidates:
        raise ValueError(f'No archive entry matched query: {entry_query}')
    candidates.sort(key=lambda e: (Path(e.get('name', '')).suffix.lower() not in MODEL_EXTS, -int(e.get('size_in_archive') or 0)))
    return candidates[0]


def direct_slot_patch_archive_copy(archive_path: Path, entry_query: str, imported_file: Path, out_archive: Path | None = None, reexport_proof: bool = True) -> dict:
    archive_path = Path(archive_path)
    imported_file = Path(imported_file)
    imported_bytes = imported_file.read_bytes()
    archive_info = modelxml_export.parse_rpf6(archive_path)
    if not archive_info:
        raise ValueError(f'Could not parse RPF6 archive: {archive_path}')
    entry = find_archive_entry(archive_info, entry_query, imported_path=imported_file)
    entry_suffix = Path(entry.get('name', '')).suffix.lower()
    if imported_file.suffix.lower() != entry_suffix:
        raise ValueError(f'Replacement suffix must match archive entry suffix: {imported_file.suffix} vs {entry_suffix}')
    slot_size = int(entry.get('size_in_archive') or 0)
    if len(imported_bytes) != slot_size:
        raise ValueError(f'Direct safe import requires exact slot size: imported={len(imported_bytes):,}, archive slot={slot_size:,}.')

    original_extract = modelxml_export.extract_rpf_entry(archive_path, entry)
    original_resource = modelxml_export.parse_resource_header(original_extract)
    imported_resource = modelxml_export.parse_resource_header(imported_bytes)
    if bool(original_resource) != bool(imported_resource):
        raise ValueError('Imported file resource-header presence does not match the archive entry.')
    if original_resource and imported_resource:
        if original_resource.get('ident_name') != imported_resource.get('ident_name') or original_resource.get('resource_type') != imported_resource.get('resource_type'):
            raise ValueError('Imported file resource identity/type does not match the archive entry.')

    if out_archive is None:
        out_archive = imported_file.with_name(f'{archive_path.stem}__{imported_file.stem}_direct_import_copy{archive_path.suffix}')
    else:
        out_archive = Path(out_archive)
    out_archive.parent.mkdir(parents=True, exist_ok=True)
    copy_file_streamed(archive_path, out_archive)

    with out_archive.open('r+b') as f:
        f.seek(int(entry.get('offset') or 0))
        f.write(imported_bytes)

    copied_entry = dict(entry)
    # Read the patched slot back directly by the already-validated TOC offset/slot size.
    # This avoids an expensive full archive reparse immediately after writing large archives.
    with out_archive.open('rb') as f:
        f.seek(int(copied_entry.get('offset') or 0))
        reread = f.read(slot_size)
    reread_validation = validate_model_resource(reread)
    result = {
        'status': 'archive_copy_direct_import_verified' if reread == imported_bytes else 'archive_copy_direct_import_failed',
        'archive_source': str(archive_path),
        'archive_copy': str(out_archive),
        'internal_path': copied_entry.get('path', ''),
        'offset': int(copied_entry.get('offset') or 0),
        'slot_size': slot_size,
        'imported_file': str(imported_file),
        'imported_sha1': sha1_hex(imported_bytes),
        'reread_sha1': sha1_hex(reread),
        'reread_matches_imported': reread == imported_bytes,
        'resource_header_ok_after_reread': bool(reread_validation.get('resource')),
        'archive_reparse_skipped_for_speed': True,
        'reread_validation': reread_validation,
    }

    if reexport_proof:
        proof_root = imported_file.parent / 'reexport_proof_from_imported_archive'
        proof_bundle, proof_manifest = modelxml_export.create_bundle(
            copied_entry.get('name') or imported_file.name,
            reread,
            proof_root,
            archive_path=out_archive,
            archive_entry=copied_entry,
            archive_info=None,
        )
        result['reexport_proof_bundle'] = str(proof_bundle)
        result['reexport_proof_manifest'] = str(proof_bundle / 'manifest.json')
        result['reexport_texture_ref_count'] = sum(len(v) for v in proof_manifest.get('texture_refs', {}).values())
        result['reexport_heuristic_stream_count'] = len(proof_manifest.get('heuristic_streams', []))

    report_path = imported_file.with_suffix(imported_file.suffix + '.archive_import_report.json')
    report_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    result['report_path'] = str(report_path)
    return result


def parse_replace_args(items: list[str] | None) -> list[tuple[str, str]]:
    replacements: list[tuple[str, str]] = []
    for item in items or []:
        if '=' not in item:
            raise ValueError(f'--replace-text value must use old=new format: {item}')
        old, new = item.split('=', 1)
        replacements.append((old, new))
    return replacements


def main() -> int:
    parser = argparse.ArgumentParser(description='Code RED Model XML bundle import / archive-copy verification tool.')
    parser.add_argument('--bundle', type=Path, required=True, help='Code RED Model XML export bundle folder containing manifest.json.')
    parser.add_argument('--out', type=Path, default=Path('imports/modelxml_roundtrip'), help='Output folder for imported files/reports.')
    parser.add_argument('--mode', choices=['raw-clone', 'payload-sidecar'], default='payload-sidecar', help='How to rebuild the imported model/resource file.')
    parser.add_argument('--replace-text', action='append', default=[], help='Optional same-size-safe reference edit, old=new. Example: old.dds=new.dds')
    parser.add_argument('--ignore-xml-edits', action='store_true', help='Ignore edits made in the exported .modelxml.xml file.')
    parser.add_argument('--ignore-text-sheet', action='store_true', help='Ignore replace lines in the exported .model_edits.txt file.')
    parser.add_argument('--archive', type=Path, help='Optional RPF6 archive to patch into a copied archive for readback proof.')
    parser.add_argument('--entry', help='Archive entry substring to patch/read back when --archive is used.')
    parser.add_argument('--out-archive', type=Path, help='Optional path for the patched archive copy.')
    parser.add_argument('--no-reexport-proof', action='store_true', help='Skip re-exporting the patched entry as an extra readback proof.')
    args = parser.parse_args()

    replacements = parse_replace_args(args.replace_text)
    import_result = build_imported_file(args.bundle, args.out, args.mode, replacements, apply_xml_edits=not args.ignore_xml_edits, apply_text_sheet=not args.ignore_text_sheet)
    final = {'import_result': import_result}

    if args.archive:
        entry_query = args.entry or Path(import_result['source_raw_file']).name
        archive_result = direct_slot_patch_archive_copy(
            args.archive,
            entry_query,
            Path(import_result['imported_file']),
            out_archive=args.out_archive,
            reexport_proof=not args.no_reexport_proof,
        )
        final['archive_import_result'] = archive_result

    print(json.dumps(final, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
