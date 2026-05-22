"""Repeated data-table candidates, including known population pool blocks."""
from __future__ import annotations

from typing import Any


def population_table_map(data: bytes):
    # Import lazily so generic analysis can exist without population patching.
    from ..pools import scan_population_pools

    return scan_population_pools(data)


def table_patch_candidates(data: bytes) -> list[dict[str, Any]]:
    pool_map = population_table_map(data)
    output: list[dict[str, Any]] = []
    for candidate in pool_map.candidates:
        safe = bool(candidate["safe_same_width_replace"])
        if candidate["likely_enum_category"] == "vehicle_actor":
            patch_type = "population_vehicle_pool_replace"
        elif candidate["likely_enum_category"] == "human_actor":
            patch_type = "population_actor_pool_replace"
        else:
            patch_type = ""
        output.append(
            {
                **candidate,
                "candidate_kind": "table",
                "table_kind": "population_pool",
                "patchability": "SAME_SIZE_SAFE" if safe else "READ_ONLY",
                "safe_patch_type": patch_type if safe else "",
                "reason": candidate["confidence_reason"] if safe else f"{candidate['confidence_reason']}; not safe for same-width pool replacement",
            }
        )
    return output


def table_rows(data: bytes) -> list[dict[str, Any]]:
    pool_map = population_table_map(data)
    return [{**pool, "table_kind": "population_pool"} for pool in pool_map.pools]
