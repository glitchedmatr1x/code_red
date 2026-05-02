from __future__ import annotations
import json, platform, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def first_existing(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None

def main() -> int:
    panda = {"available": False, "version": None, "error": None}
    try:
        from panda3d.core import PandaSystem  # type: ignore
        panda["available"] = True
        panda["version"] = PandaSystem.getVersionString()
    except Exception as exc:
        panda["error"] = repr(exc)
    companion = first_existing([
        ROOT / "related_apps" / "Code_RED_MP_Companion_v19" / "mp_companion.py",
        ROOT / "data" / "Code_RED_MP_Companion_v19" / "mp_companion.py",
        ROOT / "Code_RED_MP_Companion_v19" / "mp_companion.py",
    ])
    world = ROOT / "related_apps" / "code_red_cleanroom_world_v32.py"
    tuner_dir = ROOT / "related_apps" / "CodeRED_Tuner"
    tuner = tuner_dir / "codered_tuner.py"
    builtins = tuner_dir / "builtin_mod_presets.py"
    arcade = tuner_dir / "code_red_arcade.py"
    arcade_settings = tuner_dir / "runtime" / "arcade_settings.json"
    arcade_bat = tuner_dir / "run_CodeRed_Arcade.bat"
    arcade_vehicle_asset = tuner_dir / "assets" / "vehicles" / "concept_vehicle_baked_wire.json"
    arcade_vehicle_manifest = tuner_dir / "assets" / "vehicles" / "concept_vehicle_baked_wire.json"
    mods_dir = tuner_dir / "Mods"
    mod_packs = []
    builtin_mod_packs = []
    if builtins.exists():
        try:
            sys.path.insert(0, str(tuner_dir))
            from builtin_mod_presets import list_builtin_mod_packs  # type: ignore
            builtin_mod_packs = [p.get("name", "") for p in list_builtin_mod_packs()]
        except Exception as exc:
            builtin_mod_packs = [f"error: {exc!r}"]
    if mods_dir.exists():
        mod_packs = sorted([p.name for p in mods_dir.iterdir() if p.is_dir()])
    probe = {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "root": str(ROOT),
        "panda3d": panda,
        "paths": {
            "main_py": str(ROOT / "main.py"),
            "main_exists": (ROOT / "main.py").exists(),
            "python_workbench_exists": (ROOT / "python_workbench.py").exists(),
            "mp_companion": str(companion) if companion else None,
            "mp_companion_exists": companion is not None,
            "world_app": str(world),
            "world_app_exists": world.exists(),
            "tuner_app": str(tuner),
            "tuner_app_exists": tuner.exists(),
            "tuner_builtin_presets_file": str(builtins),
            "tuner_builtin_presets_exists": builtins.exists(),
            "tuner_builtin_presets": builtin_mod_packs,
            "code_red_arcade": str(arcade),
            "code_red_arcade_exists": arcade.exists(),
            "code_red_arcade_bat": str(arcade_bat),
            "code_red_arcade_bat_exists": arcade_bat.exists(),
            "code_red_arcade_renderer": "Panda3D preferred, baked concept vehicle wire/design data, Tk fallback",
            "code_red_arcade_settings": str(arcade_settings),
            "code_red_arcade_settings_exists": arcade_settings.exists(),
            "code_red_arcade_vehicle_asset": str(arcade_vehicle_asset),
            "code_red_arcade_vehicle_asset_exists": arcade_vehicle_asset.exists(),
            "code_red_arcade_vehicle_baked_data": str(arcade_vehicle_manifest),
            "code_red_arcade_vehicle_baked_data_exists": arcade_vehicle_manifest.exists(),
            "tuner_optional_mods_dir": str(mods_dir),
            "tuner_optional_mod_packs": mod_packs,
            "requirements": str(ROOT / "requirements.txt"),
            "requirements_exists": (ROOT / "requirements.txt").exists(),
        },
    }
    print(json.dumps(probe, indent=2))
    core_ok = probe["paths"]["python_workbench_exists"] and probe["paths"]["tuner_app_exists"] and probe["paths"]["code_red_arcade_exists"]
    return 0 if core_ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
