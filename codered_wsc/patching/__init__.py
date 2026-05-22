"""Safe patch recipe and report surfaces for decoded RDR scripts."""
from .primitives import DecodedEdit
from .recipes import (
    PatchError,
    PatchResult,
    apply_recipe,
    apply_recipe_detailed,
    load_recipe,
    validate_recipe,
    write_patch_bundle,
)

__all__ = [
    "DecodedEdit",
    "PatchError",
    "PatchResult",
    "apply_recipe",
    "apply_recipe_detailed",
    "load_recipe",
    "validate_recipe",
    "write_patch_bundle",
]
