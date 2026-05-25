"""RDR script resource opening and conservative RSC85 repacking."""
from __future__ import annotations

import hashlib
import io
import os
import struct
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


CODEX_AES_KEY_SHA1 = bytes.fromhex("87862497EE46855372B51C7A324A2BB5CD66F4AF")
CODEX_AES_KEY_OFFSETS = (0x22A2300, 0x2293500)
RSC85 = b"RSC\x85"
XSC_SWAPPED_RSC85 = b"\x85CSR"


class ResourceError(RuntimeError):
    """Raised when a resource cannot be opened or rebuilt safely."""


@dataclass
class KeyOptions:
    aes_key_hex: str = ""
    aes_key_file: str = ""
    rdr_exe: str = ""


@dataclass
class ResourceHeader:
    family: str
    normalized_from_xsc: bool
    magic_hex: str
    resource_type: int | None
    flag1: int | None
    flag2: int | None
    header_size: int
    stored_size: int
    payload_size: int
    expected_unpacked_size: int | None
    compression: str
    encryption: str


@dataclass
class ScriptResource:
    path: Path
    original: bytes
    normalized: bytes
    decoded: bytes
    header: ResourceHeader
    key: bytes | None = field(repr=False, default=None)
    key_attempts: list[dict[str, Any]] = field(default_factory=list)
    decode_error: str = ""

    def header_dict(self) -> dict[str, Any]:
        report = asdict(self.header)
        report.update(
            {
                "path": str(self.path),
                "source_sha256": sha256(self.original),
                "normalized_sha256": sha256(self.normalized),
                "decoded_sha256": sha256(self.decoded),
                "decoded_size": len(self.decoded),
                "key_attempts": self.key_attempts,
                "decode_error": self.decode_error,
            }
        )
        return report


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha1(data: bytes) -> bytes:
    return hashlib.sha1(data).digest()


def swap32(data: bytes) -> bytes:
    """Swap complete 32-bit words."""
    full = len(data) // 4
    out = bytearray()
    for index in range(full):
        word = data[index * 4 : index * 4 + 4]
        out.extend(word[::-1])
    out.extend(data[full * 4 :])
    return bytes(out)


def normalize_xsc_resource(data: bytes) -> bytes:
    """Normalize XENON XSC to RSC85 without corrupting the encrypted payload.

    The XENON resource header is 32-bit word-swapped, but the encrypted script
    payload is byte-for-byte AES data. Swapping the whole file destroys the LZX
    wrapper after decrypt.
    """
    return swap32(data[:16]) + data[16:]


def denormalize_xsc_resource(data: bytes) -> bytes:
    """Return normalized RSC85 bytes to XENON XSC header order."""
    return swap32(data[:16]) + data[16:]


def normalize_resource(data: bytes) -> tuple[bytes, bool]:
    if data.startswith(XSC_SWAPPED_RSC85):
        return normalize_xsc_resource(data), True
    return data, False


def parse_header(data: bytes, normalized_from_xsc: bool = False) -> ResourceHeader:
    if data.startswith(RSC85) and len(data) >= 16:
        resource_type, flag1, flag2 = struct.unpack_from("<III", data, 4)
        # The RSC85 extended flags observed here encode total virtual/physical
        # resource sizes in Flag2 compact 4 KiB page fields.
        virtual_size = (flag2 & 0x3FFF) << 12
        physical_size = ((flag2 >> 14) & 0x3FFF) << 12
        return ResourceHeader(
            family="RSC85",
            normalized_from_xsc=normalized_from_xsc,
            magic_hex=data[:4].hex(" ").upper(),
            resource_type=resource_type,
            flag1=flag1,
            flag2=flag2,
            header_size=16,
            stored_size=len(data),
            payload_size=len(data) - 16,
            expected_unpacked_size=virtual_size + physical_size,
            compression="zstandard-candidate",
            encryption="aes-256-ecb-16-pass",
        )
    return ResourceHeader(
        family="raw",
        normalized_from_xsc=normalized_from_xsc,
        magic_hex=data[:4].hex(" ").upper(),
        resource_type=None,
        flag1=None,
        flag2=None,
        header_size=0,
        stored_size=len(data),
        payload_size=len(data),
        expected_unpacked_size=len(data),
        compression="none",
        encryption="none",
    )


def candidate_rdr_exes(explicit: str, cwd: Path) -> list[Path]:
    raw = [explicit, os.environ.get("CODERED_RDR_EXE", ""), str(cwd / "rdr.exe"), str(cwd.parent / "rdr.exe")]
    seen: set[str] = set()
    paths: list[Path] = []
    for value in raw:
        if not value:
            continue
        path = Path(value)
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            paths.append(path)
    return paths


def parse_key_file(path: Path) -> bytes:
    payload = path.read_bytes()
    if len(payload) == 32:
        return payload
    text = payload.decode("ascii", errors="ignore").strip().replace(" ", "").replace("\n", "")
    try:
        key = bytes.fromhex(text.removeprefix("0x"))
    except ValueError as exc:
        raise ResourceError(f"AES key file is neither 32 raw bytes nor hex: {path}") from exc
    if len(key) != 32:
        raise ResourceError(f"AES key must be 32 bytes, got {len(key)} from {path}")
    return key


def resolve_aes_key(options: KeyOptions, cwd: Path | None = None) -> tuple[bytes | None, list[dict[str, Any]]]:
    cwd = cwd or Path.cwd()
    attempts: list[dict[str, Any]] = []
    key_hex = options.aes_key_hex or os.environ.get("CODERED_RDR_AES_KEY_HEX", "")
    if key_hex:
        try:
            key = bytes.fromhex(key_hex.removeprefix("0x"))
        except ValueError as exc:
            raise ResourceError("AES key hex is not valid hexadecimal") from exc
        if len(key) != 32:
            raise ResourceError(f"AES key hex must decode to 32 bytes, got {len(key)}")
        attempts.append({"method": "hex", "key_sha1": sha1(key).hex().upper()})
        return key, attempts
    key_file = options.aes_key_file or os.environ.get("CODERED_RDR_AES_KEY_FILE", "")
    if key_file:
        key = parse_key_file(Path(key_file))
        attempts.append({"method": "file", "path": key_file, "key_sha1": sha1(key).hex().upper()})
        return key, attempts
    for exe in candidate_rdr_exes(options.rdr_exe, cwd):
        item: dict[str, Any] = {"method": "rdr_exe", "path": str(exe), "exists": exe.exists()}
        if not exe.exists():
            attempts.append(item)
            continue
        blob = exe.read_bytes()
        for offset in CODEX_AES_KEY_OFFSETS:
            if offset + 32 <= len(blob):
                key = blob[offset : offset + 32]
                if sha1(key) == CODEX_AES_KEY_SHA1:
                    item.update({"offset": f"0x{offset:X}", "key_sha1": sha1(key).hex().upper()})
                    attempts.append(item)
                    return key, attempts
        item["error"] = "known key offsets did not match"
        attempts.append(item)
    return None, attempts


def aes_crypt_16_passes(data: bytes, key: bytes, decrypt: bool) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError as exc:  # pragma: no cover - environment failure
        raise ResourceError("RSC85 AES requires the Python package 'cryptography'") from exc
    if len(key) != 32:
        raise ResourceError("RSC85 AES key is not 32 bytes")
    aligned = len(data) & ~15
    out = bytearray(data)
    for _ in range(16):
        cipher = Cipher(algorithms.AES(key), modes.ECB())
        transform = cipher.decryptor() if decrypt else cipher.encryptor()
        out[:aligned] = transform.update(bytes(out[:aligned])) + transform.finalize()
    return bytes(out)


def zstd_decompress(data: bytes) -> bytes:
    try:
        import zstandard as zstd
    except ImportError as exc:  # pragma: no cover - environment failure
        raise ResourceError("RSC85 Zstandard decode requires the Python package 'zstandard'") from exc
    buffer = io.BytesIO()
    with zstd.ZstdDecompressor().stream_reader(io.BytesIO(data)) as reader:
        while chunk := reader.read(1024 * 1024):
            buffer.write(chunk)
    return buffer.getvalue()


def zlib_decompress(data: bytes) -> bytes:
    import zlib

    return zlib.decompress(data)


def zstd_compress_variants(data: bytes) -> list[tuple[int, str, bytes]]:
    try:
        import zstandard as zstd
    except ImportError as exc:  # pragma: no cover - environment failure
        raise ResourceError("RSC85 Zstandard encode requires the Python package 'zstandard'") from exc
    variants: list[tuple[int, str, bytes]] = []
    for level in range(22, 0, -1):
        for content_size in (False, True):
            name = f"zstd-level-{level}-{'content-size' if content_size else 'no-content-size'}"
            compressed = zstd.ZstdCompressor(level=level, write_content_size=content_size).compress(data)
            variants.append((len(compressed), name, compressed))
    variants.sort(key=lambda row: row[0])
    return variants


def zstd_skippable_padding(size: int) -> bytes:
    if size == 0:
        return b""
    if size < 8:
        raise ResourceError(f"RSC85 exact-fit padding needs 0 or at least 8 bytes, got {size}")
    return struct.pack("<II", 0x184D2A50, size - 8) + (b"\0" * (size - 8))


def open_script(path: Path, options: KeyOptions | None = None) -> ScriptResource:
    options = options or KeyOptions()
    original = path.read_bytes()
    normalized, from_xsc = normalize_resource(original)
    header = parse_header(normalized, from_xsc)
    if header.family == "raw":
        return ScriptResource(path, original, normalized, normalized, header)
    if header.resource_type != 2:
        raise ResourceError(f"Refusing RSC85 resource type {header.resource_type}; scripts observed here are type 2")
    key, attempts = resolve_aes_key(options)
    if key is None:
        raise ResourceError("No RDR AES key found. Use --rdr-exe, --aes-key-file, or --aes-key-hex.")
    decrypted = aes_crypt_16_passes(normalized[16:], key, decrypt=True)
    try:
        decoded = zstd_decompress(decrypted)
        header.compression = "zstandard"
        return ScriptResource(path, original, normalized, decoded, header, key, attempts)
    except Exception:
        pass
    try:
        decoded = zlib_decompress(decrypted)
        header.compression = "zlib-deflate"
        return ScriptResource(path, original, normalized, decoded, header, key, attempts)
    except Exception:
        pass
    if len(decrypted) >= 8:
        xbox_magic, xbox_size = struct.unpack_from(">II", decrypted, 0)
        if xbox_magic == 267719409 and 0 < xbox_size <= len(decrypted) - 8:
            header.compression = "xbox-lzx-xcompress-required"
            return ScriptResource(
                path,
                original,
                normalized,
                b"",
                header,
                key,
                attempts,
                "AES decrypt succeeded and the payload has the Xbox LZX wrapper. LZX decode/repack needs an explicit xcompress bridge.",
            )
    header.compression = "unsupported-or-key-mismatch"
    return ScriptResource(
        path,
        original,
        normalized,
        b"",
        header,
        key,
        attempts,
        "AES decrypt was attempted, but the payload did not match the implemented Zstandard/zlib lanes or the simple Xbox LZX wrapper probe.",
    )


def repack_script(resource: ScriptResource, decoded: bytes, allow_growth: bool = False) -> tuple[bytes, dict[str, Any]]:
    if resource.decode_error:
        raise ResourceError(resource.decode_error)
    if resource.header.family == "raw":
        if decoded != resource.decoded:
            raise ResourceError("Raw script byte changes need a container-specific writer; RSC85 writer was not used")
        return resource.original, {"fit_mode": "raw-copy", "validate_ok": True, "output_sha256": sha256(resource.original)}
    if resource.key is None:
        raise ResourceError("RSC85 resource was opened without an AES key")
    payload_capacity = len(resource.normalized) - 16
    candidates = zstd_compress_variants(decoded)
    size, codec, compressed = candidates[0]
    fit = next(
        (
            candidate
            for candidate in candidates
            if candidate[0] <= payload_capacity and (payload_capacity - candidate[0] == 0 or payload_capacity - candidate[0] >= 8)
        ),
        None,
    )
    if fit is None and not allow_growth:
        raise ResourceError(f"Smallest rebuilt payload is {size} bytes for {payload_capacity}-byte slot")
    if fit is None:
        payload = compressed
        fit_mode = "variable-size"
        pad = 0
    else:
        size, codec, compressed = fit
        pad = payload_capacity - size
        payload = compressed + zstd_skippable_padding(pad)
        fit_mode = "exact" if pad == 0 else "zstd-skippable-padding"
    normalized = resource.normalized[:16] + aes_crypt_16_passes(payload, resource.key, decrypt=False)
    output = denormalize_xsc_resource(normalized) if resource.header.normalized_from_xsc else normalized
    reopened = open_script_from_bytes(output, resource.path, resource.key, resource.header.normalized_from_xsc)
    report = {
        "fit_mode": fit_mode,
        "codec": codec,
        "compressed_size": size,
        "payload_capacity": payload_capacity,
        "padding_size": pad,
        "output_size": len(output),
        "output_sha256": sha256(output),
        "validate_ok": reopened.decoded == decoded,
        "decoded_sha256": sha256(decoded),
    }
    if not report["validate_ok"]:
        raise ResourceError("Rebuilt RSC85 did not decode to the requested bytes")
    return output, report


def open_script_from_bytes(data: bytes, path: Path, key: bytes, originally_xsc: bool = False) -> ScriptResource:
    normalized, from_xsc = normalize_resource(data)
    header = parse_header(normalized, from_xsc or originally_xsc)
    if header.family != "RSC85":
        raise ResourceError("Reopen validation expected an RSC85 script")
    decoded = zstd_decompress(aes_crypt_16_passes(normalized[16:], key, decrypt=True))
    return ScriptResource(path, data, normalized, decoded, header, key, [{"method": "reopen-validation"}])
