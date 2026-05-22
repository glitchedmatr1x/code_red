"""Width-preserving decoded-byte patch primitives."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class DecodedEdit:
    patch_type: str
    offset: int
    before: bytes
    after: bytes
    note: str
    pool: str = ""
    enum_category: str = ""
    old_enum: int | None = None
    new_enum: int | None = None

    def csv_row(self) -> dict[str, Any]:
        return {
            "type": self.patch_type,
            "offset": self.offset,
            "offset_hex": f"0x{self.offset:X}",
            "size": len(self.before),
            "before_hex": self.before.hex(" ").upper(),
            "after_hex": self.after.hex(" ").upper(),
            "note": self.note,
            "pool": self.pool,
            "enum_category": self.enum_category,
            "old_enum": self.old_enum if self.old_enum is not None else "",
            "new_enum": self.new_enum if self.new_enum is not None else "",
        }


def parse_int(value: Any, label: str, error_factory: Callable[[str], Exception]) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise error_factory(f"{label} is not an integer: {value}") from exc
    raise error_factory(f"{label} is not an integer: {value!r}")


def parse_hex(value: Any, label: str, error_factory: Callable[[str], Exception]) -> bytes:
    if not isinstance(value, str):
        raise error_factory(f"{label} must be hex text")
    try:
        return bytes.fromhex(value.replace(",", " "))
    except ValueError as exc:
        raise error_factory(f"{label} is not valid hex: {value}") from exc


def replace_at(
    data: bytearray,
    offset: int,
    before: bytes,
    after: bytes,
    patch_type: str,
    note: str,
    error_factory: Callable[[str], Exception],
) -> DecodedEdit:
    if len(before) != len(after):
        raise error_factory(f"{patch_type} would change decoded length at 0x{offset:X}")
    if offset < 0 or offset + len(before) > len(data):
        raise error_factory(f"{patch_type} range 0x{offset:X}..0x{offset + len(before):X} is outside decoded bytes")
    actual = bytes(data[offset : offset + len(before)])
    if actual != before:
        raise error_factory(f"{patch_type} expected {before.hex(' ')} at 0x{offset:X}, found {actual.hex(' ')}")
    data[offset : offset + len(after)] = after
    return DecodedEdit(patch_type, offset, before, after, note)


def integer_bytes(value: int, width: int, endian: str, error_factory: Callable[[str], Exception], label: str = "Integer") -> bytes:
    if width not in (1, 2, 4):
        raise error_factory(f"{label} width {width} is not safe")
    if value < 0 or value >= 1 << (width * 8):
        raise error_factory(f"{label} value {value} does not fit {width} bytes")
    order = "big" if endian in ("big", "be") else "little" if endian in ("little", "le") else ""
    if not order:
        raise error_factory(f"{label} endian must be big/be or little/le, got {endian}")
    return value.to_bytes(width, order)
