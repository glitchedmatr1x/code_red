#!/usr/bin/env python3
"""
Code RED Tuner v2.4.0
Standalone XML tuner for RDR tune_d11generic.rpf vehicle handling files.

Focus files:
  root/tune/vehicle/car01x.vehsim
  root/tune/vehicle/truck01x.vehsim

Exports:
  - Loose patch tree with correct internal path.
  - Experimental micro RPF6 overlay archive containing only modified files.

The micro RPF is NOT a replacement for the stock tune_d11generic.rpf.
"""

from __future__ import annotations

import argparse
import importlib.util
import datetime as _dt
import math
import json
import os
import random
import re
import shutil
import subprocess
import struct
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import xml.etree.ElementTree as ET
import wave

# Built-in preset data is intentionally loaded lazily.  Importing the large
# preset module during Tk startup can leave users staring at a black command
# box before the interface has a chance to draw.  The UI shows these lightweight
# metadata stubs immediately and only imports builtin_mod_presets.py if the user
# exports one of the packs.
_builtin_presets_module = None
_BUILTIN_PACK_STUBS = [
    {
        "name": "Game - Driveable vehicles +",
        "builtin_key": "Game - Driveable vehicles +",
        "source_type": "builtin",
        "file_count": 48,
        "size": 9028356,
        "size_text": "8.6 MB",
        "category": "Driveable vehicle support",
        "description": "Driveable Car01/Truck01/raft/canoe support files and vehicle tune fragments for copied-archive import workflows.",
        "risk": "Experimental. Keep as an optional patch pack and back up fragments/tune archives before replacing anything.",
        "recommended": True,
        "test_order": ["Export through Patch Options.", "Keep this enabled alongside the current tuned Car01/Truck01 files.", "Only merge model/resource files after behavior changes are confirmed."],
    },
    {
        "name": "Game - Train Spawns Cars",
        "builtin_key": "Game - Train Spawns Cars",
        "source_type": "builtin",
        "file_count": 16,
        "size": 146262,
        "size_text": "142.8 KB",
        "category": "Spawn experiment",
        "description": "Train gringo/common-script test pack plus locset payload that lets car spawn behavior ride near train spawns.",
        "risk": "Experimental. Test on copied content/tune archives first; remove quickly if train scripts freeze or loop.",
        "recommended": True,
        "test_order": ["Export through Patch Options.", "Use 03_merged_loose_patch for a combined loose import package.", "Test train-area spawn behavior before combining with aggressive wagon slot swaps."],
    },
]

def _load_builtin_presets_module():
    global _builtin_presets_module
    if _builtin_presets_module is not None:
        return _builtin_presets_module
    try:
        import builtin_mod_presets as mod
    except Exception:
        mod = False
    _builtin_presets_module = mod
    return mod

def list_builtin_mod_packs() -> list[dict]:
    return [dict(pack) for pack in _BUILTIN_PACK_STUBS]

def copy_builtin_mod_pack(key: str, destination):
    mod = _load_builtin_presets_module()
    if not mod or not hasattr(mod, "copy_builtin_mod_pack"):
        raise RuntimeError("Built-in mod preset helper is not available.")
    return mod.copy_builtin_mod_pack(key, destination)

APP_NAME = "Code RED Tuner"
APP_VERSION = "2.5.4-final"
INTERNAL_BASE = "root/tune/vehicle"
VEHICLE_FILES = {
    "Car01": "car01x.vehsim",
    "Truck01": "truck01x.vehsim",
}
VEHICLE_INPUT_FILES = {
    "Car01": "car01x.vehinput",
    "Truck01": "truck01x.vehinput",
}

SPAWN_PAYLOADS = {
    "Car01": {"stem": "car01x", "locset_file": "locset_car01.xml", "locset_name": "locSet_Car01"},
    "Truck01": {"stem": "truck01x", "locset_file": "locset_truck01.xml", "locset_name": "locSet_Truck01"},
}
SPAWN_CARRIERS = {
    "wagon02x": {
        "label": "wagon02x - road wagon test carrier",
        "stem": "wagon02x",
        "locset_file": "locset_wagon02.xml",
        "locset_name": "locSet_Wagon02",
        "risk": "Best first Car01 carrier. Confirmed full tune set + locset in tune_d11generic.rpf.",
    },
    "wagonprison01x": {
        "label": "wagonprison01x - heavy wagon/prison carrier",
        "stem": "wagonprison01x",
        "locset_file": "locset_wagonprison01.xml",
        "locset_name": "locSet_WagonPrison01",
        "risk": "Best first Truck01 carrier. Confirmed full tune set + locset in tune_d11generic.rpf.",
    },
}
SPAWN_SWAP_KINDS = ("vehsim", "vehinput", "vehgyro", "vehstuck", "vehmodel")

# Runtime simulator input profile. These XML files describe the game's vehicle action
# mapper, not literal PC keyboard keys, so the simulator translates known game actions
# into keyboard-friendly aliases while preserving the original action names on screen.
DEFAULT_INPUT_PROFILE = "input_car.xml"

ACTION_KEY_ALIASES = {
    "@HORSE.SPUR": ("w", "up"),
    "@GENERIC.BRAKE": ("s", "down"),
    "@GENERIC.MOVE_X_NEG": ("a", "left"),
    "@GENERIC.MOVE_X_POS": ("d", "right"),
    "@GENERIC.MOVE_Y_NEG": ("s", "down"),
    "@GENERIC.MOVE_Y_POS": ("w", "up"),
    "@GENERIC.USE": ("e", "return"),
    "@GENERIC.WHISTLE": ("h",),
    "@GENERIC.DEADEYE": ("q",),
    "@GENERIC.FIRE": ("f",),
    "@GENERIC.TARGET": ("tab",),
    "@RADIAL_MENU.SHOW_HIDE": ("x",),
    "@GENERIC.RELOAD": ("r",),
}

TERRAIN_MODES = {
    "Flat Road": {"grip": 1.00, "drag": 1.00, "rough": 0.00, "grade": 0.00, "color": "#14202a", "accent": "#314555"},
    "Dirt Trail": {"grip": 0.88, "drag": 1.10, "rough": 0.18, "grade": 0.00, "color": "#1f1a12", "accent": "#5a4128"},
    "Mud": {"grip": 0.62, "drag": 1.46, "rough": 0.10, "grade": 0.00, "color": "#17130d", "accent": "#5d472a"},
    "Rocky Hills": {"grip": 0.74, "drag": 1.26, "rough": 0.42, "grade": 0.05, "color": "#161a1b", "accent": "#58616a"},
    "Steep Climb": {"grip": 0.80, "drag": 1.34, "rough": 0.20, "grade": 0.28, "color": "#171915", "accent": "#5b6347"},
    "Bumpy Off-Road Loop": {"grip": 0.78, "drag": 1.22, "rough": 0.55, "grade": 0.08, "color": "#141b16", "accent": "#426345"},
    "Desert Arena": {"grip": 0.86, "drag": 1.16, "rough": 0.24, "grade": 0.02, "color": "#241708", "accent": "#b7742a"},
}

RPF6_AES_KEY = bytes([
    0xB7, 0x62, 0xDF, 0xB6, 0xE2, 0xB2, 0xC6, 0xDE,
    0xAF, 0x72, 0x2A, 0x32, 0xD2, 0xFB, 0x6F, 0x0C,
    0x98, 0xA3, 0x21, 0x74, 0x62, 0xC9, 0xC4, 0xED,
    0xAD, 0xAA, 0x2E, 0xD0, 0xDD, 0xF9, 0x2F, 0x10,
])

RPF_KNOWN_NAMES = [
    "root", "tune", "vehicle", "locset",
    "car01x.vehsim", "truck01x.vehsim",
    "car01x.vehinput", "truck01x.vehinput",
    "car01x.vehgyro", "truck01x.vehgyro",
    "car01x.vehstuck", "truck01x.vehstuck",
    "car01x.vehmodel", "truck01x.vehmodel",
    "locset_car01.xml", "locset_truck01.xml",
    "wagon02x.vehsim", "wagon02x.vehinput", "wagon02x.vehgyro", "wagon02x.vehstuck", "wagon02x.vehmodel", "wagon02x.vehdraft",
    "wagonprison01x.vehsim", "wagonprison01x.vehinput", "wagonprison01x.vehgyro", "wagonprison01x.vehstuck", "wagonprison01x.vehmodel", "wagonprison01x.vehdraft",
    "locset_wagon02.xml", "locset_wagonprison01.xml", "locset_stagecoach.xml",
]

MODS_DIRNAME = "Mods"
MOD_EXPORT_SKIP_DIRS = {"__pycache__", ".git", ".vs", "Build", "x64", "dist", "build"}
MOD_EXPORT_SKIP_SUFFIXES = {".pyc", ".pyo", ".tmp", ".log", ".pdb", ".ipdb", ".iobj", ".obj", ".pch", ".suo", ".db"}
KNOWN_MOD_DESCRIPTIONS = {
    "game - driveable vehicles +": "Driveable Car01/Truck01/raft/canoe support files and vehicle tune fragments. Use with a copied archive/import workflow.",
    "game - train spawns cars": "Train gringo/common-script test pack plus locset payload that lets car spawn behavior ride near train spawns.",
}

# High-confidence simplified controls pulled from car01x.vehsim / truck01x.vehsim.
# They are deliberately conservative and map directly to XML value attributes.
@dataclass(frozen=True)
class ControlDef:
    key: str
    label: str
    path: str
    minimum: float
    maximum: float
    step: float
    category: str
    description: str
    default_hint: str = ""
    source: str = "vehsim"  # vehsim or vehinput

CONTROLS: list[ControlDef] = [
    ControlDef("mass", "Mass", "Mass", 500, 8000, 50, "Body / Stability", "Vehicle weight. Higher = heavier, slower response, harder to launch."),
    ControlDef("com_z", "Center of Mass Z", "CenterOfMass@z", -1.5, 1.0, 0.05, "Body / Stability", "Lower values are usually more stable; higher values may tip easier."),
    ControlDef("bound_gravity", "Bound Gravity", "BoundGravity", 0.25, 4.0, 0.05, "Body / Stability", "Extra gravity-like force on the vehicle bounds."),
    ControlDef("bound_friction", "Bound Friction", "BoundFriction", 0.0, 2.0, 0.05, "Body / Stability", "Collision/bounds friction."),

    ControlDef("horsepower", "Max Horse Power", "Engine/MaxHorsePower", 20, 900, 5, "Engine / Speed", "Main power ceiling. Strong first test value."),
    ControlDef("opt_rpm", "Opt RPM", "Engine/OptRPM", 1500, 9000, 50, "Engine / Speed", "Best torque/power RPM region."),
    ControlDef("max_rpm", "Max RPM", "Engine/MaxRPM", 2500, 12000, 50, "Engine / Speed", "Engine upper RPM limit."),
    ControlDef("engage_rpm", "Engage RPM", "Engine/EngageRPM", 500, 8000, 50, "Engine / Speed", "RPM where drive engagement begins."),
    ControlDef("boost_torque", "Boost Torque", "Engine/BoostTorque", 0, 500, 5, "Engine / Speed", "Extra torque burst."),
    ControlDef("boost_duration", "Boost Duration", "Engine/BoostDuration", 0, 10, 0.1, "Engine / Speed", "How long boost influence lasts."),

    ControlDef("reverse_mph", "Reverse Gear MPH", "Trans/RevGearMPH", 2, 80, 1, "Transmission", "Reverse speed target."),
    ControlDef("low_mph", "Low Gear MPH", "Trans/LowGearMPH", 5, 120, 1, "Transmission", "Low gear speed range."),
    ControlDef("high_mph", "High Gear MPH", "Trans/HighGearMPH", 10, 180, 1, "Transmission", "High gear speed range / top-speed-ish tuning value."),
    ControlDef("gear_delay", "Gear Change Delay", "Trans/GearChangeDelay", 0.02, 3.0, 0.02, "Transmission", "Lower = snappier shifting. Too low may feel unstable."),
    ControlDef("num_gears", "Number of Gears", "Trans/NumGears", 1, 8, 1, "Transmission", "Gear count. Conservative values: 3-5."),

    ControlDef("front_torque", "Front Axle Torque", "AxleFront/TorqueCoef", 0, 12, 0.1, "Axles / Grip", "Front drive torque coefficient."),
    ControlDef("rear_torque", "Rear Axle Torque", "AxleBack/TorqueCoef", 0, 12, 0.1, "Axles / Grip", "Rear drive torque coefficient."),
    ControlDef("front_steer", "Front Steering Limit", "WheelFront/SteeringLimit", 0.05, 1.4, 0.01, "Steering / Tires", "Steering angle/control limit. Higher turns harder."),
    ControlDef("front_static", "Front Static Friction", "WheelFront/StaticFric", 0.1, 4.0, 0.05, "Steering / Tires", "Front grip before sliding."),
    ControlDef("front_slide", "Front Sliding Friction", "WheelFront/SlidingFric", 0.1, 4.0, 0.05, "Steering / Tires", "Front grip while sliding."),
    ControlDef("rear_static", "Rear Static Friction", "WheelBack/StaticFric", 0.1, 4.0, 0.05, "Steering / Tires", "Rear grip before sliding."),
    ControlDef("rear_slide", "Rear Sliding Friction", "WheelBack/SlidingFric", 0.1, 4.0, 0.05, "Steering / Tires", "Rear grip while sliding. Lower = driftier."),
    ControlDef("handbrake", "Rear Handbrake Coef", "WheelBack/HandbrakeCoef", 0, 3.0, 0.05, "Steering / Tires", "Rear handbrake strength."),

    ControlDef("aero_drag", "Aero Drag", "Aero/Drag", 0, 5.0, 0.05, "Drag / Terrain", "Air drag. Lower usually allows faster speed."),
    ControlDef("downforce", "Aero Down", "Aero/Down", -2.0, 5.0, 0.05, "Drag / Terrain", "Downforce-like value. Needs testing."),
    ControlDef("vehicle_path_drag", "Vehicle Path Drag", "VehiclePathDrag", 0, 5.0, 0.05, "Drag / Terrain", "Drag on roads/vehicle paths."),
    ControlDef("offroad_drag", "Off Road Drag", "OffRoadDrag", 0, 5.0, 0.05, "Drag / Terrain", "Terrain slowdown. Higher may slow off-road."),
    ControlDef("wipeout", "Friction Wipeout", "CarFrictionHandlingWipeout", 0, 5.0, 0.05, "Drag / Terrain", "Wipeout threshold/handling influence."),

    ControlDef("burn_threshold", "Burn Threshold", "BurnThreshold", 0, 200, 1, "Damage / Burn", "Damage/burn threshold."),
    ControlDef("burn_boost", "Burn Boost", "BurnBoost", 0, 200, 1, "Damage / Burn", "Burn boost value."),
    ControlDef("burn_damage", "Burn Damage", "BurnDamage", 0, 200, 1, "Damage / Burn", "Burn damage value."),

    ControlDef("sim_sss_value", "Sim SSS Value", "SSSValue", 0.0, 2.0, 0.01, "Input / Assist", "Simulation-side steer/speed smoothing value from the vehsim file."),
    ControlDef("sim_sss_threshold", "Sim SSS Threshold", "SSSThreshold", 0.0, 100.0, 1.0, "Input / Assist", "Simulation-side threshold used by the game car sim tune."),
    ControlDef("input_sss_value", "Input SSS Value", "SSSValue", 0.0, 2.0, 0.01, "Input / Assist", "Input tune smoothing value from the matching .vehinput file.", source="vehinput"),
    ControlDef("input_sss_threshold", "Input SSS Threshold", "SSSThreshold", 0.0, 100.0, 1.0, "Input / Assist", "Input tune threshold from the matching .vehinput file.", source="vehinput"),
    ControlDef("auto_reverse_speed", "Auto Reverse Speed", "AutoReverseSpeed", 0.0, 15.0, 0.05, "Input / Assist", "Speed threshold where brake input can become reverse in the .vehinput file.", source="vehinput"),
]

PRESETS = {
    "Stock Tune Baseline": {
        "note": "Reloads the stock XML values for the selected vehicle.",
        "mode": "stock",
    },
    "Off-Road Balanced": {
        "note": "Stable all-terrain baseline. Moderate power, low center of mass, good grip, mild steering.",
        "mass": 2350,
        "com_z": -0.72,
        "bound_gravity": 1.75,
        "bound_friction": 0.18,
        "horsepower": 210,
        "boost_torque": 70,
        "boost_duration": 1.2,
        "low_mph": 28,
        "high_mph": 52,
        "reverse_mph": 18,
        "gear_delay": 0.55,
        "front_torque": 5.8,
        "rear_torque": 5.8,
        "front_static": 2.10,
        "front_slide": 1.95,
        "rear_static": 2.10,
        "rear_slide": 1.95,
        "front_steer": 0.62,
        "handbrake": 0.28,
        "aero_drag": 1.05,
        "downforce": 0.35,
        "offroad_drag": 0.0,
        "vehicle_path_drag": 0.0,
        "wipeout": 1.9,
        "sim_sss_value": 0.55,
        "sim_sss_threshold": 20,
        "input_sss_value": 0.55,
        "input_sss_threshold": 35,
        "auto_reverse_speed": 2.15,
    },
    "Off-Road Heavy Crawl": {
        "note": "Slow, heavy, hard to flip. Good for rough terrain and climbing tests.",
        "mass": 3600,
        "com_z": -0.95,
        "bound_gravity": 2.05,
        "bound_friction": 0.22,
        "horsepower": 185,
        "boost_torque": 55,
        "boost_duration": 1.0,
        "low_mph": 20,
        "high_mph": 38,
        "reverse_mph": 12,
        "gear_delay": 0.78,
        "num_gears": 4,
        "front_torque": 6.2,
        "rear_torque": 6.2,
        "front_static": 2.45,
        "front_slide": 2.20,
        "rear_static": 2.45,
        "rear_slide": 2.20,
        "front_steer": 0.50,
        "handbrake": 0.22,
        "aero_drag": 1.45,
        "downforce": 0.45,
        "offroad_drag": 0.0,
        "wipeout": 2.25,
        "sim_sss_value": 0.68,
        "sim_sss_threshold": 18,
        "input_sss_value": 0.66,
        "input_sss_threshold": 30,
        "auto_reverse_speed": 1.85,
    },
    "Off-Road Fast Stable": {
        "note": "Faster desert/scrubland test while keeping grip and low center of mass conservative.",
        "mass": 2450,
        "com_z": -0.82,
        "bound_gravity": 1.95,
        "bound_friction": 0.16,
        "horsepower": 285,
        "boost_torque": 95,
        "boost_duration": 1.45,
        "opt_rpm": 4600,
        "max_rpm": 6800,
        "low_mph": 34,
        "high_mph": 66,
        "reverse_mph": 20,
        "gear_delay": 0.42,
        "front_torque": 6.8,
        "rear_torque": 6.8,
        "front_static": 2.30,
        "front_slide": 2.05,
        "rear_static": 2.30,
        "rear_slide": 2.05,
        "front_steer": 0.58,
        "handbrake": 0.25,
        "aero_drag": 0.82,
        "downforce": 0.55,
        "offroad_drag": 0.0,
        "wipeout": 2.0,
        "sim_sss_value": 0.62,
        "sim_sss_threshold": 24,
        "input_sss_value": 0.60,
        "input_sss_threshold": 38,
        "auto_reverse_speed": 2.4,
    },
    "Mud Grip Test": {
        "note": "High traction and smoothing for boggy/uneven off-road driving.",
        "mass": 2700,
        "com_z": -0.88,
        "bound_gravity": 2.15,
        "horsepower": 230,
        "boost_torque": 65,
        "boost_duration": 1.1,
        "low_mph": 24,
        "high_mph": 44,
        "gear_delay": 0.68,
        "front_torque": 6.5,
        "rear_torque": 6.5,
        "front_static": 2.85,
        "front_slide": 2.60,
        "rear_static": 2.85,
        "rear_slide": 2.60,
        "front_steer": 0.46,
        "aero_drag": 1.25,
        "downforce": 0.35,
        "offroad_drag": 0.0,
        "wipeout": 2.6,
        "sim_sss_value": 0.74,
        "sim_sss_threshold": 16,
        "input_sss_value": 0.72,
        "input_sss_threshold": 28,
        "auto_reverse_speed": 1.75,
    },
    "Low-Tip Truck": {
        "note": "Very conservative tip-resistant truck/utility setup.",
        "mass": 4300,
        "com_z": -1.15,
        "bound_gravity": 2.35,
        "bound_friction": 0.20,
        "horsepower": 205,
        "boost_torque": 45,
        "boost_duration": 0.8,
        "low_mph": 18,
        "high_mph": 34,
        "reverse_mph": 10,
        "gear_delay": 0.9,
        "front_torque": 5.5,
        "rear_torque": 5.5,
        "front_static": 2.35,
        "front_slide": 2.15,
        "rear_static": 2.35,
        "rear_slide": 2.15,
        "front_steer": 0.42,
        "handbrake": 0.18,
        "aero_drag": 1.60,
        "downforce": 0.65,
        "offroad_drag": 0.0,
        "wipeout": 2.4,
        "sim_sss_value": 0.78,
        "sim_sss_threshold": 14,
        "input_sss_value": 0.76,
        "input_sss_threshold": 26,
        "auto_reverse_speed": 1.6,
    },
}


def app_dir() -> Path:
    return Path(__file__).resolve().parent


def safe_slug(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._+-]+", "_", name.strip()).strip("._")
    return slug or "mod_pack"


def human_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024.0
    return f"{num_bytes} B"


def should_skip_mod_export(path: Path) -> bool:
    if any(part in MOD_EXPORT_SKIP_DIRS for part in path.parts):
        return True
    return path.suffix.lower() in MOD_EXPORT_SKIP_SUFFIXES


def iter_mod_files(root: Path):
    if not root.exists():
        return
    for path in root.rglob("*"):
        if path.is_file() and not should_skip_mod_export(path.relative_to(root)):
            yield path


def discover_mod_packs(mods_dir: Path) -> list[dict]:
    """Return built-in preset packs first, plus optional loose packs if present.

    The two Code RED game packs are now embedded in builtin_mod_presets.py so the
    tuner no longer depends on keeping a Mods/ folder beside the app. A local
    Mods/ folder still works as an override/workbench area for future experiments.
    """
    packs: list[dict] = []
    seen: set[str] = set()
    for pack in list_builtin_mod_packs():
        name = str(pack.get("name", "Built-in patch option"))
        pack["name"] = name
        pack["slug"] = safe_slug(name)
        pack.setdefault("source_type", "builtin")
        pack.setdefault("path", "")
        packs.append(pack)
        seen.add(name.lower())

    if mods_dir.exists():
        for folder in sorted((p for p in mods_dir.iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
            # Built-ins are canonical. Skip duplicate loose copies so users do not
            # see the same option twice after applying this pass over an older tree.
            if folder.name.lower() in seen:
                continue
            files = list(iter_mod_files(folder))
            total = sum(f.stat().st_size for f in files if f.exists())
            manifest_path = folder / "MODINFO.json"
            meta = {}
            if manifest_path.exists():
                try:
                    meta = json.loads(manifest_path.read_text(encoding="utf-8"))
                except Exception:
                    meta = {}
            key = folder.name.lower()
            description = str(meta.get("description") or KNOWN_MOD_DESCRIPTIONS.get(key) or "Loose patch/mod folder discovered under Mods/.")
            packs.append({
                "name": folder.name,
                "slug": safe_slug(folder.name),
                "path": folder,
                "source_type": "folder",
                "file_count": len(files),
                "size": total,
                "size_text": human_size(total),
                "description": description,
                "category": str(meta.get("category") or "Loose patch option"),
                "risk": str(meta.get("risk") or "Experimental; apply to copied archives first."),
                "recommended": bool(meta.get("recommended", key in KNOWN_MOD_DESCRIPTIONS)),
            })
    return packs


def find_mp_companion_script() -> Path | None:
    here = app_dir()
    candidates = [
        here.parent / "Code_RED_MP_Companion_v19" / "mp_companion.py",
        here.parent / "run_mp_companion.py",
        here / "Code_RED_MP_Companion_v19" / "mp_companion.py",
        here.parent.parent / "related_apps" / "Code_RED_MP_Companion_v19" / "mp_companion.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def copy_mod_tree(src: Path, dst: Path) -> dict:
    copied = 0
    bytes_total = 0
    conflicts: list[dict] = []
    for file_path in iter_mod_files(src):
        rel = file_path.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() == file_path.read_bytes():
                continue
            conflict_target = target.with_name(target.name + f".conflict_from_{safe_slug(src.name)}")
            shutil.copy2(file_path, conflict_target)
            conflicts.append({"relative_path": str(rel).replace("\\", "/"), "kept": str(target), "conflict_copy": str(conflict_target)})
            copied += 1
            bytes_total += file_path.stat().st_size
            continue
        shutil.copy2(file_path, target)
        copied += 1
        bytes_total += file_path.stat().st_size
    return {"copied_files": copied, "copied_bytes": bytes_total, "conflicts": conflicts}


def now_stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def rdr_name_hash(name: str) -> int:
    num2 = 0
    for ch in name.lower():
        num3 = (num2 + ord(ch)) & 0xFFFFFFFF
        num4 = (num3 + ((num3 << 10) & 0xFFFFFFFF)) & 0xFFFFFFFF
        num2 = (num4 ^ (num4 >> 6)) & 0xFFFFFFFF
    num5 = (num2 + ((num2 << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    num6 = (num5 ^ (num5 >> 11)) & 0xFFFFFFFF
    return (num6 + ((num6 << 15) & 0xFFFFFFFF)) & 0xFFFFFFFF


def align(value: int, boundary: int) -> int:
    return (value + boundary - 1) & ~(boundary - 1)


def indent_xml(elem: ET.Element, level: int = 0) -> None:
    i = "\n" + level * "\t"
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "\t"
        for child in elem:
            indent_xml(child, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


class VehicleTune:
    def __init__(self, name: str, source_path: Path):
        self.name = name
        self.source_path = source_path
        self.tree = ET.parse(source_path)
        self.root = self.tree.getroot()
        self.stock_text = source_path.read_text(encoding="utf-8", errors="replace")

    def clone_from_stock(self) -> None:
        self.tree = ET.ElementTree(ET.fromstring(self.stock_text.encode("utf-8")))
        self.root = self.tree.getroot()

    def _find_node(self, path: str) -> tuple[ET.Element | None, str]:
        if "@" in path:
            elem_path, attr = path.split("@", 1)
        else:
            elem_path, attr = path, "value"
        node = self.root
        if elem_path:
            for part in elem_path.split("/"):
                if not part:
                    continue
                node = node.find(part)
                if node is None:
                    return None, attr
        return node, attr

    def get_float(self, path: str, fallback: float = 0.0) -> float:
        node, attr = self._find_node(path)
        if node is None:
            return fallback
        try:
            return float(node.attrib.get(attr, fallback))
        except Exception:
            return fallback

    def set_float(self, path: str, value: float, decimals: int = 6) -> None:
        node, attr = self._find_node(path)
        if node is None:
            raise KeyError(path)
        if path.endswith("NumGears") or path.endswith("DrivetrainType"):
            node.set(attr, str(int(round(value))))
        else:
            node.set(attr, f"{float(value):.{decimals}f}")

    def get_torque_values(self) -> list[int]:
        node = self.root.find("Engine/TorqueControlValues")
        if node is None or not node.text:
            return []
        vals = []
        for tok in node.text.replace("\r", "\n").split():
            try:
                vals.append(int(tok))
            except ValueError:
                pass
        return vals

    def set_torque_scale(self, multiplier: float) -> None:
        node = self.root.find("Engine/TorqueControlValues")
        if node is None:
            return
        base = self.get_torque_values()
        if not base:
            return
        scaled = [max(-999, min(999, int(round(v * multiplier)))) for v in base]
        node.text = "\n\t\t\t" + "\n\t\t\t".join(str(v) for v in scaled) + "\n\t\t"

    def values_snapshot(self) -> dict[str, float]:
        return {c.key: self.get_float(c.path) for c in CONTROLS}

    def to_bytes(self) -> bytes:
        indent_xml(self.root)
        xml_body = ET.tostring(self.root, encoding="unicode", short_empty_elements=True)
        return ('<?xml version="1.0" encoding="UTF-8"?>\n\n' + xml_body).encode("utf-8")


def build_micro_rpf6(files: dict[str, bytes], output_path: Path) -> None:
    """Build an experimental unencrypted RPF6 with only root/tune/vehicle files.

    This is intentionally plain/non-compressed. It is meant for overlay experiments,
    not as a replacement for the stock tune_d11generic.rpf.
    """
    filenames = [Path(p).name for p in files]
    # Entries: root, tune, vehicle, file..., ordered as child ranges.
    entries: list[tuple[str, str]] = [("dir", "root"), ("dir", "tune"), ("dir", "vehicle")]
    for full in files:
        entries.append(("file", Path(full).name))
    entry_count = len(entries)
    toc_size = align(entry_count * 20, 16)
    payload_start = align(16 + toc_size, 8)
    payload_offset = payload_start
    file_offsets: dict[str, int] = {}
    payload = bytearray()
    for full, data in files.items():
        payload_offset = align(payload_start + len(payload), 8)
        pad = payload_offset - (payload_start + len(payload))
        if pad:
            payload.extend(b"\x00" * pad)
        file_offsets[full] = payload_offset
        payload.extend(data)
    toc = bytearray()
    # root dir: child tune at index 1 count 1
    toc.extend(struct.pack(">5I", 0, 0, 0x80000000 | 1, 1, 0))
    # tune dir: child vehicle at index 2 count 1
    toc.extend(struct.pack(">5I", rdr_name_hash("tune"), 0, 0x80000000 | 2, 1, 0))
    # vehicle dir: file children start 3, count n
    toc.extend(struct.pack(">5I", rdr_name_hash("vehicle"), 0, 0x80000000 | 3, len(files), 0))
    for full, data in files.items():
        name = Path(full).name
        off = file_offsets[full]
        size = len(data)
        a = rdr_name_hash(name)
        b = size & 0x0FFFFFFF
        c = (off // 8) & 0x7FFFFFFF
        d = size & 0x3FFFFFFF  # non-resource total size, uncompressed
        e = 0x80000000         # extended flag => not compressed in Code RED parser
        toc.extend(struct.pack(">5I", a, b, c, d, e))
    if len(toc) < toc_size:
        toc.extend(b"\x00" * (toc_size - len(toc)))
    header = struct.pack(">4sIII", b"RPF6", entry_count, 0, 0)
    out = bytearray(header)
    out.extend(toc)
    if len(out) < payload_start:
        out.extend(b"\x00" * (payload_start - len(out)))
    out.extend(payload)
    output_path.write_bytes(out)



def _rpf6_crypto(data: bytes, decrypt: bool) -> bytes:
    """RPF6 TOC AES helper. Imports cryptography only when full-RPF patching is used."""
    if not data:
        return data
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
    except Exception as exc:
        raise RuntimeError("Full RPF patching needs the Python 'cryptography' package. Loose export still works.") from exc
    block_len = len(data) & ~0xF
    if block_len <= 0:
        return data
    cipher = Cipher(algorithms.AES(RPF6_AES_KEY), modes.ECB(), backend=default_backend())
    block = data[:block_len]
    for _ in range(16):
        ctx = cipher.decryptor() if decrypt else cipher.encryptor()
        block = ctx.update(block) + ctx.finalize()
    return block + data[block_len:]


def _rpf6_decrypt(data: bytes) -> bytes:
    return _rpf6_crypto(data, True)


def _rpf6_encrypt(data: bytes) -> bytes:
    return _rpf6_crypto(data, False)


def _rpf_is_resource(flag1: int) -> bool:
    return (flag1 & 0x80000000) != 0


def _rpf_is_extended(flag2: int) -> bool:
    return (flag2 & 0x80000000) != 0


def _rpf_is_compressed(flag1: int, flag2: int) -> bool:
    return not _rpf_is_extended(flag2) and ((flag1 >> 30) & 1) == 1


def _rpf_offset(offset_raw: int, is_resource: bool) -> int:
    return ((offset_raw & 0x7FFFFF00) if is_resource else (offset_raw & 0x7FFFFFFF)) * 8


def parse_rpf6_light(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 16 or data[:4] != b"RPF6":
        raise ValueError("Selected file is not an RPF6 archive.")
    _sig, entry_count, debug_offset, enc_flag = struct.unpack(">4sIII", data[:16])
    toc_size = align(entry_count * 20, 16)
    toc = data[16:16 + toc_size]
    if enc_flag:
        toc = _rpf6_decrypt(toc)
    known = {0: "root"}
    for name in RPF_KNOWN_NAMES:
        known[rdr_name_hash(name)] = name
    entries: list[dict] = []
    parents: list[int | None] = [None] * entry_count
    for i in range(entry_count):
        a, b, c, d, e = struct.unpack(">5I", toc[i * 20:(i + 1) * 20])
        is_dir = ((c >> 24) & 0xFF) == 0x80
        entry = {"index": i, "name_off": a, "name": known.get(a, f"0x{a:08X}"), "raw": (a, b, c, d, e)}
        if is_dir:
            entry.update({"type": "dir", "start": c & 0x7FFFFFFF, "count": d & 0x0FFFFFFF})
        else:
            is_res = _rpf_is_resource(d)
            entry.update({
                "type": "file",
                "size_in_archive": b & 0x0FFFFFFF,
                "offset_raw": c,
                "flag1": d,
                "flag2": e,
                "is_resource": is_res,
                "is_compressed": _rpf_is_compressed(d, e),
                "offset": _rpf_offset(c, is_res),
                "total_size": (d & 0xBFFFFFFF) if not is_res else 0,
            })
        entries.append(entry)
    for entry in entries:
        if entry.get("type") == "dir":
            for child_index in range(entry.get("start", 0), entry.get("start", 0) + entry.get("count", 0)):
                if 0 <= child_index < len(parents):
                    parents[child_index] = entry["index"]
    for entry in entries:
        parts = [entry["name"]]
        parent = parents[entry["index"]]
        while parent is not None:
            parts.append(entries[parent]["name"])
            parent = parents[parent]
        entry["path"] = "/".join(reversed(parts))
        entry["parent_index"] = parents[entry["index"]]
    return {"path": path, "data": data, "entries": entries, "entry_count": entry_count, "toc_size": toc_size, "enc_flag": enc_flag, "debug_offset": debug_offset}


def find_rpf_entry_light(info: dict, internal_path: str) -> dict | None:
    wanted = internal_path.lower().replace("\\", "/")
    if not wanted.startswith("root/"):
        wanted = "root/" + wanted
    for entry in info["entries"]:
        if entry.get("type") == "file" and entry.get("path", "").lower() == wanted:
            return entry
    # Some older helpers represent root as 0x00000000 when name data is absent.
    alt = wanted.replace("root/", "0x00000000/", 1)
    for entry in info["entries"]:
        if entry.get("type") == "file" and entry.get("path", "").lower() == alt:
            return entry
    # Final fallback: unique file basename.
    basename = Path(wanted).name.lower()
    by_name = [entry for entry in info["entries"] if entry.get("type") == "file" and entry.get("name", "").lower() == basename]
    return by_name[0] if len(by_name) == 1 else None


def rpf_extract_entry_light(archive_path: Path, entry: dict) -> bytes:
    with archive_path.open("rb") as f:
        f.seek(int(entry["offset"]))
        raw = f.read(int(entry["size_in_archive"]))
    if entry.get("is_resource"):
        return raw
    if not entry.get("is_compressed"):
        return raw
    if raw.startswith(b"\x28\xB5\x2F\xFD"):
        try:
            proc = subprocess.run(["zstd", "-d", "-q", "--stdout"], input=raw, capture_output=True, check=True)
            return proc.stdout
        except FileNotFoundError as exc:
            raise RuntimeError("zstd command-line tool is required to patch compressed RPF tune entries.") from exc
        except Exception as exc:
            raise RuntimeError(f"zstd could not decompress an RPF entry: {exc}") from exc
    for wbits in (-15, 15, 31):
        try:
            return zlib.decompress(raw, wbits)
        except Exception:
            pass
    raise RuntimeError("Compressed RPF entry could not be decompressed.")


def _rpf_update_entry_metadata(buf: bytearray, info: dict, entry: dict, new_size: int, new_total: int, new_offset: int) -> None:
    toc_start = 16
    toc_size = int(info["toc_size"])
    toc = bytes(buf[toc_start:toc_start + toc_size])
    if info.get("enc_flag"):
        toc = _rpf6_decrypt(toc)
    toc_buf = bytearray(toc)
    idx = int(entry["index"])
    off = idx * 20
    a, b, c, d, e = struct.unpack(">5I", bytes(toc_buf[off:off + 20]))
    b = (b & 0xF0000000) | (new_size & 0x0FFFFFFF)
    if not entry.get("is_resource"):
        d = (d & 0xC0000000) | (new_total & 0x3FFFFFFF)
    if new_offset % 8 != 0:
        raise ValueError("RPF payload offsets must stay 8-byte aligned.")
    if entry.get("is_resource"):
        c = ((new_offset // 8) & 0x7FFFFF00) | (c & 0xFF)
    else:
        c = (new_offset // 8) & 0x7FFFFFFF
    toc_buf[off:off + 20] = struct.pack(">5I", a, b, c, d, e)
    out_toc = _rpf6_encrypt(bytes(toc_buf)) if info.get("enc_flag") else bytes(toc_buf)
    buf[toc_start:toc_start + toc_size] = out_toc


def _compress_for_rpf_entry(payload: bytes, entry: dict) -> bytes:
    if not entry.get("is_compressed"):
        return payload
    # tune_d11generic vehicle XML entries are zstd-compressed. Try high compression first,
    # but use timeouts/fallback levels so a single pathological frame never freezes the app.
    last_error: Exception | None = None
    for level in (6, 3, 1):
        try:
            proc = subprocess.run(["zstd", "-q", "-z", "--stdout", f"-{level}", "--no-check"], input=payload, capture_output=True, check=True, timeout=5)
            return proc.stdout
        except FileNotFoundError as exc:
            raise RuntimeError("zstd command-line tool is required to build a full copied tune RPF. Install zstd or use loose export.") from exc
        except Exception as exc:
            last_error = exc
            continue
    raise RuntimeError(f"zstd compression failed at all fallback levels: {last_error}")


def patch_tune_rpf_copy(original_rpf: Path, replacements: dict[str, bytes], output_rpf: Path) -> dict:
    """Patch selected tune entries into a copied full RPF6 archive and verify each extract."""
    info = parse_rpf6_light(original_rpf)
    buf = bytearray(info["data"])
    results = []
    copied = False
    # Copy first so a partial failure never mutates the selected original.
    output_rpf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original_rpf, output_rpf)
    copied = True
    for internal, payload in replacements.items():
        info = parse_rpf6_light(output_rpf)
        entry = find_rpf_entry_light(info, internal)
        if entry is None:
            results.append({"internal_path": internal, "status": "blocked", "reason": "Entry not found in selected tune RPF."})
            continue
        raw_payload = _compress_for_rpf_entry(payload, entry)
        old_size = int(entry["size_in_archive"])
        old_offset = int(entry["offset"])
        data = bytearray(output_rpf.read_bytes())
        if len(raw_payload) <= old_size:
            new_offset = old_offset
            with output_rpf.open("r+b") as f:
                f.seek(old_offset)
                f.write(raw_payload)
                if len(raw_payload) < old_size:
                    f.write(b"\x00" * (old_size - len(raw_payload)))
            data = bytearray(output_rpf.read_bytes())
        else:
            aligned = align(len(data), 8)
            if aligned > len(data):
                data.extend(b"\x00" * (aligned - len(data)))
            new_offset = aligned
            data.extend(raw_payload)
        _rpf_update_entry_metadata(data, info, entry, len(raw_payload), len(payload), new_offset)
        output_rpf.write_bytes(data)
        # Verify by re-opening and extracting the patched entry.
        verify_info = parse_rpf6_light(output_rpf)
        verify_entry = find_rpf_entry_light(verify_info, internal)
        verified = False
        reason = "not verified"
        if verify_entry:
            try:
                extracted = rpf_extract_entry_light(output_rpf, verify_entry)
                verified = extracted == payload
                reason = "re-extracted patched payload successfully" if verified else "patched entry did not re-extract to the edited XML"
            except Exception as exc:
                reason = f"verification extract failed: {exc}"
        results.append({
            "internal_path": internal,
            "status": "patched_verified" if verified else "patched_unverified",
            "old_size": old_size,
            "new_size": len(raw_payload),
            "old_offset": old_offset,
            "new_offset": new_offset,
            "relocated": new_offset != old_offset,
            "reason": reason,
        })
    applied = sum(1 for r in results if r.get("status") == "patched_verified")
    return {"source": str(original_rpf), "output": str(output_rpf), "copied": copied, "applied": applied, "results": results}

def find_input_profile() -> Path | None:
    candidates = [
        app_dir() / "input_profiles" / DEFAULT_INPUT_PROFILE,
        app_dir() / DEFAULT_INPUT_PROFILE,
        app_dir() / "stock_vehicle_files" / DEFAULT_INPUT_PROFILE,
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def load_input_profile_file(path: Path | None) -> tuple[dict[str, dict[str, str]], str]:
    if path is None or not path.exists():
        return {}, "built-in keyboard fallback"
    try:
        root = ET.parse(path).getroot()
        maps: dict[str, dict[str, str]] = {}
        for node in root.findall(".//Map"):
            value = (node.get("Value") or "").strip()
            if not value:
                continue
            maps[value] = {
                "Source": (node.get("Source") or "").strip(),
                "Parameter": (node.get("Parameter") or "").strip(),
                "Port": (node.get("Port") or "").strip(),
                "Inverted": (node.get("Inverted") or "").strip(),
            }
        return maps, path.name
    except Exception as exc:
        return {}, f"input profile parse failed: {exc}"


# -------------------------
# Optional procedural audio
# -------------------------
def ensure_generated_audio_assets() -> None:
    """Create small WAV assets so the simulator has sound without shipping binaries."""
    base = app_dir() / "assets" / "audio"
    sfx_dir = base / "sfx"
    music_dir = base / "music"
    sfx_dir.mkdir(parents=True, exist_ok=True)
    music_dir.mkdir(parents=True, exist_ok=True)

    def wav_path(name: str) -> Path:
        return sfx_dir / name

    def write_wav(path: Path, samples: list[float], rate: int = 22050) -> None:
        if path.exists() and path.stat().st_size > 512:
            return
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            frames = bytearray()
            for v in samples:
                iv = int(max(-1.0, min(1.0, v)) * 32767)
                frames += struct.pack("<h", iv)
            wf.writeframes(bytes(frames))

    def tone(freq: float, dur: float, amp: float = 0.35, rate: int = 22050, noise: float = 0.0, decay: float = 1.0) -> list[float]:
        n = max(1, int(rate * dur))
        out = []
        rnd = random.Random(int(freq * 31 + dur * 1000))
        for i in range(n):
            t = i / rate
            env = (1.0 - i / n) ** decay
            v = math.sin(math.tau * freq * t) * amp * env
            if noise:
                v += (rnd.random() * 2 - 1) * noise * env
            out.append(v)
        return out

    def engine_loop(path: Path, base_freq: float, growl: float) -> None:
        if path.exists() and path.stat().st_size > 512:
            return
        rate = 22050
        dur = 1.25
        n = int(rate * dur)
        out = []
        rnd = random.Random(7331 + int(base_freq))
        for i in range(n):
            t = i / rate
            wobble = 1.0 + math.sin(math.tau * 2.2 * t) * 0.035
            v = math.sin(math.tau * base_freq * wobble * t) * 0.21
            v += math.sin(math.tau * base_freq * 0.5 * t) * 0.16
            v += math.sin(math.tau * base_freq * 2.0 * t) * 0.06
            v += (rnd.random() * 2 - 1) * growl
            # Tiny fade at loop boundaries to avoid a hard pop.
            edge = min(1.0, i / (rate * 0.04), (n - i) / (rate * 0.04))
            out.append(v * edge)
        write_wav(path, out, rate)

    engine_loop(wav_path("engine_idle.wav"), 55, 0.018)
    engine_loop(wav_path("engine_drive.wav"), 82, 0.026)
    write_wav(wav_path("gatling_burst.wav"), tone(95, 0.075, 0.20, noise=0.22, decay=0.65))
    write_wav(wav_path("hit_clang.wav"), tone(420, 0.16, 0.28, noise=0.10, decay=2.0))
    write_wav(wav_path("skid_sand.wav"), tone(180, 0.22, 0.10, noise=0.24, decay=0.6))
    write_wav(wav_path("button.wav"), tone(720, 0.08, 0.22, noise=0.0, decay=1.6))
    write_wav(wav_path("missile_launch.wav"), tone(145, 0.18, 0.28, noise=0.18, decay=0.9))
    write_wav(wav_path("explosion.wav"), tone(62, 0.34, 0.48, noise=0.30, decay=0.55))

    # A subtle droning desert loop. It is intentionally short so pygame can loop it.
    music_path = music_dir / "red_desert_loop.wav"
    if not music_path.exists() or music_path.stat().st_size <= 512:
        rate = 22050
        dur = 4.0
        n = int(rate * dur)
        out = []
        for i in range(n):
            t = i / rate
            pad = math.sin(math.tau * 55 * t) * 0.045 + math.sin(math.tau * 82.5 * t) * 0.030
            pulse = math.sin(math.tau * 1.5 * t) * 0.025
            shimmer = math.sin(math.tau * 220 * t + math.sin(t * 2.0)) * 0.012
            edge = min(1.0, i / (rate * 0.12), (n - i) / (rate * 0.12))
            out.append((pad + pulse + shimmer) * edge)
        write_wav(music_path, out, rate)


class SoundEngine:
    """Small optional audio engine. Uses pygame when available, otherwise stays silent."""
    def __init__(self, base: Path):
        self.base = base
        self.enabled = False
        self.status = "audio off"
        self.master = 0.65
        self.sfx = 0.75
        self.music = 0.35
        self._sounds = {}
        self._pygame = None
        try:
            if os.name != "nt" and not os.environ.get("CODERED_ENABLE_PYGAME_AUDIO"):
                self.status = "silent preview"
                return
            os.environ.setdefault("SDL_AUDIODRIVER", "directsound" if os.name == "nt" else "dummy")
            import pygame  # type: ignore
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self._pygame = pygame
            self.enabled = True
            self.status = "pygame mixer"
            for name in ("engine_idle", "engine_drive", "gatling_burst", "hit_clang", "skid_sand", "button", "missile_launch", "explosion"):
                path = base / "sfx" / f"{name}.wav"
                if path.exists():
                    self._sounds[name] = pygame.mixer.Sound(str(path))
        except Exception as exc:
            self.status = f"silent ({exc.__class__.__name__})"

    def set_volumes(self, master: float, sfx: float, music: float) -> None:
        self.master = max(0.0, min(1.0, master))
        self.sfx = max(0.0, min(1.0, sfx))
        self.music = max(0.0, min(1.0, music))
        if self._pygame:
            self._pygame.mixer.music.set_volume(self.master * self.music)

    def play(self, name: str, volume: float = 1.0) -> None:
        if not self.enabled:
            return
        snd = self._sounds.get(name)
        if snd is None:
            return
        try:
            snd.set_volume(self.master * self.sfx * max(0.0, min(1.0, volume)))
            snd.play()
        except Exception:
            pass

    def start_music(self) -> None:
        if not self.enabled or not self._pygame:
            return
        try:
            path = self.base / "music" / "red_desert_loop.wav"
            if path.exists() and not self._pygame.mixer.music.get_busy():
                self._pygame.mixer.music.load(str(path))
                self._pygame.mixer.music.set_volume(self.master * self.music)
                self._pygame.mixer.music.play(-1)
        except Exception:
            pass

    def stop_music(self) -> None:
        if self._pygame:
            try:
                self._pygame.mixer.music.stop()
            except Exception:
                pass


class TunerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1480x900")
        self.minsize(1280, 780)
        self.configure(bg="#090305")
        self.stock_dir = app_dir() / "stock_vehicle_files"
        self.vehicles: dict[str, VehicleTune] = {}
        self.vehicle_inputs: dict[str, VehicleTune] = {}
        self.current_vehicle = tk.StringVar(value="Car01")
        self.vars: dict[str, tk.DoubleVar] = {}
        self.value_labels: dict[str, ttk.Label] = {}
        self.stock_value_labels: dict[str, ttk.Label] = {}
        self.help_labels: dict[str, ttk.Label] = {}
        self.show_tune_help_var = tk.BooleanVar(value=False)
        self.torque_scale = tk.DoubleVar(value=1.0)
        self.status = tk.StringVar(value="Ready. Loaded stock car/truck tune XMLs.")
        self.preview_running = tk.BooleanVar(value=True)
        self.renderer_sleep_when_background = tk.BooleanVar(value=True)
        self.renderer_active_status = tk.StringVar(value="Renderer: active")
        self._app_has_focus = True
        self._renderer_last_state = "active"
        self._preview_tick_ms = 40
        self._preview_sleep_ms = 420
        self._last_preview_time = None
        self.preview_speed = 0.0
        self.preview_distance = 0.0
        self.preview_phase = 0.0
        self.preview_trail = []
        self.preview_labels = {}
        self.input_profile_path = find_input_profile()
        self.input_map, self.input_profile_name = load_input_profile_file(self.input_profile_path)
        self.input_profile_enabled = tk.BooleanVar(value=True)
        self.move_y_handbrake_assist = tk.BooleanVar(value=True)
        self.gatlings_enabled = tk.BooleanVar(value=True)
        self.gatling_fire_enabled = tk.BooleanVar(value=True)
        self.gatling_fire_rate = tk.DoubleVar(value=9.0)
        self.gatling_projectile_speed = tk.DoubleVar(value=95.0)
        self.desert_arena_enabled = tk.BooleanVar(value=True)
        self.limitless_desert_enabled = tk.BooleanVar(value=True)
        self.pause_overlay_enabled = tk.BooleanVar(value=False)
        self.audio_enabled = tk.BooleanVar(value=True)
        self.music_enabled = tk.BooleanVar(value=True)
        self.master_volume = tk.DoubleVar(value=0.65)
        self.sfx_volume = tk.DoubleVar(value=0.78)
        self.music_volume = tk.DoubleVar(value=0.32)
        self.rival_count_var = tk.IntVar(value=3)
        self.arena_seed_var = tk.IntVar(value=0)
        self.world_seed_var = tk.IntVar(value=0)
        self.draw_guide_track_var = tk.BooleanVar(value=False)
        self.terrain_quality_var = tk.StringVar(value="Balanced")
        self.arcade_settings_path = app_dir() / "runtime" / "arcade_settings.json"
        self.arcade_process = None
        self.arcade_status = tk.StringVar(value="Code Red Arcade external process: stopped")
        self.launch_readiness_var = tk.StringVar(value="Launch readiness: checking...")
        self.launch_readiness_value = tk.DoubleVar(value=0.0)
        self.arcade_lan_enabled = tk.BooleanVar(value=False)
        self.arcade_live_apply_var = tk.BooleanVar(value=True)
        self.arcade_renderer_var = tk.StringVar(value="panda")
        self.arcade_full_windowed_var = tk.BooleanVar(value=False)
        self.arcade_fov_var = tk.DoubleVar(value=88.0)
        self.arcade_zoom_var = tk.DoubleVar(value=1.72)
        self._arcade_sync_after_id = None
        self.sim_rivals = []
        self.arena_props = []
        self.sim_hits = 0
        self.arena_boundary = 95.0
        self.terrain_mode = tk.StringVar(value="Desert Arena")
        self.rpf_source_path = tk.StringVar(value=str((app_dir().parent / "tune_d11generic.rpf") if (app_dir().parent / "tune_d11generic.rpf").exists() else ""))
        self.rpf_export_dir = tk.StringVar(value=str(app_dir() / "exports"))
        self.rpf_builder_status = tk.StringVar(value="Select the original tune_d11generic.rpf to build a copied full-RPF patch.")
        self.spawn_payload_var = tk.StringVar(value="Car01")
        self.spawn_carrier_var = tk.StringVar(value="wagon02x")
        self.spawn_include_locset_var = tk.BooleanVar(value=True)
        self.spawn_source_rpf = tk.StringVar(value=self.rpf_source_path.get())
        self.spawn_export_dir = tk.StringVar(value=str(app_dir() / "exports"))
        self.spawn_builder_status = tk.StringVar(value="Spawn Slot Swap Builder: choose payload + carrier, export loose patch first.")
        self.mods_dir = app_dir() / MODS_DIRNAME
        self.mod_packs = discover_mod_packs(self.mods_dir)
        self.include_selected_mods_var = tk.BooleanVar(value=True)
        self.include_mp_client_var = tk.BooleanVar(value=True)
        self.mod_pack_vars: dict[str, tk.BooleanVar] = {}
        for pack in self.mod_packs:
            name_l = pack["name"].lower()
            default_on = ("driveable" in name_l) or ("train" in name_l)
            self.mod_pack_vars[pack["name"]] = tk.BooleanVar(value=default_on)
        self.mod_pack_status = tk.StringVar(value=self._mod_pack_status_text())
        self.mp_companion_status = tk.StringVar(value="MP Companion ready" if find_mp_companion_script() else "MP Companion not found")
        self.sim_action_state = []
        self.initializing = True
        ensure_generated_audio_assets()
        self.sound = SoundEngine(app_dir() / "assets" / "audio")
        self.sound.set_volumes(self.master_volume.get(), self.sfx_volume.get(), self.music_volume.get())
        self._load_stock_files()
        self._restore_arcade_settings_values()
        self._build_style()
        self._build_ui()
        self.bind("<FocusIn>", self._on_app_focus_in)
        self.bind("<FocusOut>", self._on_app_focus_out)
        self.bind("<Unmap>", lambda e: self._mark_renderer_background("window hidden"))
        self.bind("<Map>", lambda e: self._wake_renderer("window visible"))
        self.protocol("WM_DELETE_WINDOW", self._on_tuner_close)
        self._load_vehicle_to_controls(self.current_vehicle.get())
        self.initializing = False
        self._refresh_launch_readiness()
        self.after(150, lambda: (self.reset_preview(), self._update_preview_metrics(), self._maybe_start_audio(), self._refresh_launch_readiness()))

    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        red = "#d21f1f"
        red_hot = "#ff3636"
        bg = "#090305"
        card = "#18080b"
        card2 = "#220b10"
        ink = "#f1eef0"
        muted = "#b78b92"
        style.configure("TFrame", background=bg)
        style.configure("Card.TFrame", background=card, relief="flat")
        style.configure("TLabel", background=bg, foreground=ink)
        style.configure("Muted.TLabel", background=bg, foreground=muted)
        style.configure("Card.TLabel", background=card, foreground=ink)
        style.configure("Title.TLabel", background=bg, foreground=red_hot, font=("Segoe UI", 16, "bold"))
        style.configure("Header.TLabel", background=card, foreground="#ffddd8", font=("Segoe UI", 11, "bold"))
        style.configure("TButton", padding=(10, 6), background=card2, foreground=ink, bordercolor="#4a1219", focusthickness=1, focuscolor=red)
        style.map("TButton", background=[("active", "#3a1017"), ("pressed", "#5a121a")], foreground=[("active", "#ffffff")])
        style.configure("Accent.TButton", padding=(10, 6), background="#7e1013", foreground="#fff4f2", bordercolor=red_hot)
        style.map("Accent.TButton", background=[("active", "#b5161b"), ("pressed", "#5e0c10")], foreground=[("active", "#ffffff")])
        style.configure("TCheckbutton", background=card, foreground=ink)
        style.map("TCheckbutton", background=[("active", card2)], foreground=[("active", "#ffffff")])
        style.configure("TRadiobutton", background=card, foreground=ink)
        style.map("TRadiobutton", background=[("active", card2)], foreground=[("active", "#ffffff")])
        style.configure("Horizontal.TScale", background=card, troughcolor="#090305")
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 7), background="#130608", foreground="#cf9ca3")
        style.map("TNotebook.Tab", background=[("selected", "#2d0b10"), ("active", "#26090d")], foreground=[("selected", "#ff4b4b"), ("active", "#ffe8e6")])
        style.configure("TProgressbar", troughcolor="#090305", background=red, bordercolor="#30080d", lightcolor=red_hot, darkcolor="#700a0e")

    def _load_stock_files(self) -> None:
        missing = []
        for label, filename in VEHICLE_FILES.items():
            path = self.stock_dir / filename
            if not path.exists():
                missing.append(str(path))
            else:
                self.vehicles[label] = VehicleTune(label, path)
        for label, filename in VEHICLE_INPUT_FILES.items():
            path = self.stock_dir / filename
            if not path.exists():
                missing.append(str(path))
            else:
                self.vehicle_inputs[label] = VehicleTune(label, path)
        if missing:
            messagebox.showerror(APP_NAME, "Missing stock files:\n" + "\n".join(missing))
            raise SystemExit(1)

    def _tune_for_control(self, control: ControlDef, vehicle_label: str | None = None) -> VehicleTune:
        label = vehicle_label or self.current_vehicle.get()
        if control.source == "vehinput":
            return self.vehicle_inputs[label]
        return self.vehicles[label]

    def _all_control_values_for_vehicle(self, vehicle_label: str) -> dict[str, float]:
        data: dict[str, float] = {}
        for c in CONTROLS:
            try:
                data[c.key] = self._tune_for_control(c, vehicle_label).get_float(c.path)
            except Exception:
                pass
        return data

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text="Code RED Tuner", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="Car01 / Truck01 tune editor • arcade demo • patch builder • MP companion bridge", style="Muted.TLabel").pack(side="left", padx=14)
        ttk.Button(top, text="Export Patch Files", style="Accent.TButton", command=self.export_patch).pack(side="right")

        body = ttk.Frame(self, padding=(12, 0, 12, 8))
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body, width=285, style="Card.TFrame", padding=12)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        ttk.Label(left, text="Vehicle", style="Header.TLabel").pack(anchor="w", pady=(0, 6))
        for vehicle in VEHICLE_FILES:
            ttk.Radiobutton(left, text=vehicle, value=vehicle, variable=self.current_vehicle, command=self.on_vehicle_changed).pack(anchor="w", pady=2)

        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Label(left, text="Presets", style="Header.TLabel").pack(anchor="w", pady=(0, 6))
        for name in PRESETS:
            ttk.Button(left, text=name, command=lambda n=name: self.apply_preset(n)).pack(fill="x", pady=3)
        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Label(left, text="Preset Files", style="Header.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Button(left, text="Save Current Preset", command=self.save_preset_file).pack(fill="x", pady=3)
        ttk.Button(left, text="Load Preset JSON", command=self.load_preset_file).pack(fill="x", pady=3)

        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Label(left, text="Torque Curve", style="Header.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Label(left, text="Scales Engine/TorqueControlValues from the current curve.", style="Card.TLabel", wraplength=230).pack(anchor="w")
        row = ttk.Frame(left, style="Card.TFrame")
        row.pack(fill="x", pady=5)
        ttk.Scale(row, from_=0.25, to=3.0, orient="horizontal", variable=self.torque_scale).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Apply", command=self.apply_torque_scale).pack(side="right", padx=(6, 0))

        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Button(left, text="Reload Stock Selected", command=self.reload_selected_stock).pack(fill="x", pady=3)
        ttk.Button(left, text="Open Export Folder", command=self.open_exports_folder).pack(fill="x", pady=3)

        main = ttk.Frame(body)
        main.pack(side="left", fill="both", expand=True)
        self.nb = ttk.Notebook(main)
        self.nb.pack(fill="both", expand=True)
        self._control_frames: dict[str, ttk.Frame] = {}
        tab_names = {
            "Body / Stability": "Body",
            "Engine / Speed": "Engine",
            "Transmission": "Trans",
            "Axles / Grip": "Axles",
            "Steering / Tires": "Steering",
            "Drag / Terrain": "Drag",
            "Damage / Burn": "Damage",
            "Input / Assist": "Input",
        }
        for cat in dict.fromkeys(c.category for c in CONTROLS):
            frame = ttk.Frame(self.nb, padding=10)
            self.nb.add(frame, text=tab_names.get(cat, cat))
            self._control_frames[cat] = frame
        self._build_controls()
        # v2.4.2: do not build the old embedded Drive 3D/Tk preview tab.
        # The tuner now launches the current external Panda arcade via Test Demo.
        self._build_arcade_tab()
        self._build_guide_tab()
        self._build_mod_pack_tab()
        self._build_patch_builder_tab()
        self._build_spawn_slot_tab()
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self._wake_renderer("tab selected") if self._drive_tab_is_selected() else self._mark_renderer_background("tab hidden"))

        bottom = ttk.Frame(self, padding=(12, 2, 12, 12))
        bottom.pack(fill="x")
        ttk.Label(bottom, textvariable=self.status, style="Muted.TLabel").pack(side="left", fill="x", expand=True)
        ttk.Label(bottom, text="by GLITCHED MATRIX Prototype Lab", style="Muted.TLabel").pack(side="right", padx=(12, 0))

    def _build_controls(self) -> None:
        for cat, parent in self._control_frames.items():
            help_bar = ttk.Frame(parent, style="Card.TFrame", padding=(10, 7))
            help_bar.pack(fill="x", pady=(0, 7))
            ttk.Checkbutton(
                help_bar,
                text="Show help",
                variable=self.show_tune_help_var,
                command=self._toggle_control_help,
            ).pack(side="left")
            ttk.Label(
                help_bar,
                text="Tune descriptions stay hidden until needed so the sliders remain compact.",
                style="Card.TLabel",
                wraplength=520,
            ).pack(side="left", padx=(10, 0))

        for c in CONTROLS:
            self.vars[c.key] = tk.DoubleVar(value=0.0)
            parent = self._control_frames[c.category]
            card = ttk.Frame(parent, style="Card.TFrame", padding=(10, 8))
            card.pack(fill="x", pady=4)
            line1 = ttk.Frame(card, style="Card.TFrame")
            line1.pack(fill="x")
            ttk.Label(line1, text=c.label, style="Card.TLabel", width=24).pack(side="left")
            stock_label = ttk.Label(line1, text="stock: --", style="Card.TLabel", width=16)
            stock_label.pack(side="right", padx=(10, 0))
            val_label = ttk.Label(line1, text="", style="Card.TLabel", width=12)
            val_label.pack(side="right")
            self.value_labels[c.key] = val_label
            self.stock_value_labels[c.key] = stock_label
            scale = ttk.Scale(card, from_=c.minimum, to=c.maximum, orient="horizontal", variable=self.vars[c.key], command=lambda _v, cc=c, lab=val_label: self._on_scale(cc, lab))
            scale.pack(fill="x", pady=(4, 2))
            help_label = ttk.Label(card, text=c.description, style="Card.TLabel", wraplength=560)
            self.help_labels[c.key] = help_label
            if self.show_tune_help_var.get():
                help_label.pack(anchor="w", pady=(3, 0))
            self._on_scale(c, val_label, write=False)

    def _toggle_control_help(self) -> None:
        show = bool(self.show_tune_help_var.get())
        for label in getattr(self, "help_labels", {}).values():
            if show:
                if not label.winfo_manager():
                    label.pack(anchor="w", pady=(3, 0))
            else:
                if label.winfo_manager():
                    label.pack_forget()

    def _on_scale(self, c: ControlDef, lab: ttk.Label, write: bool = True) -> None:
        v = self.vars[c.key].get()
        display = self._format_value(c, v)
        lab.configure(text=display)
        if write and not getattr(self, "loading_controls", False):
            try:
                tune = self._tune_for_control(c)
                tune.set_float(c.path, v)
                suffix = "input" if c.source == "vehinput" else "sim"
                self.status.set(f"Updated {self.current_vehicle.get()} {c.label} ({suffix}) = {display}")
                if hasattr(self, "preview_canvas") and not getattr(self, "initializing", False):
                    self._update_preview_metrics()
                self._queue_arcade_settings_sync()
            except Exception as exc:
                self.status.set(f"Could not update {c.path}: {exc}")

    def _load_vehicle_to_controls(self, label: str) -> None:
        self.loading_controls = True
        try:
            for c in CONTROLS:
                self.vars[c.key].set(self._tune_for_control(c, label).get_float(c.path))
        finally:
            self.loading_controls = False
        self.torque_scale.set(1.0)
        self._refresh_value_labels()
        if hasattr(self, "preview_canvas") and not getattr(self, "initializing", False):
            self.reset_preview()
            self._update_preview_metrics()
        self.status.set(f"Loaded stock-derived {label} vehsim + vehinput values into controls.")

    def _format_value(self, c: ControlDef, value: float) -> str:
        if c.step >= 1:
            return str(int(round(value)))
        if c.step >= 0.05:
            return f"{value:.2f}"
        return f"{value:.3f}"

    def _refresh_value_labels(self) -> None:
        vehicle_label = self.current_vehicle.get()
        for c in CONTROLS:
            value = self.vars[c.key].get()
            if c.key in self.value_labels:
                self.value_labels[c.key].configure(text=self._format_value(c, value))
            if c.key in self.stock_value_labels:
                source_tune = self._tune_for_control(c, vehicle_label)
                stock_vehicle = VehicleTune(vehicle_label, source_tune.source_path)
                stock_value = stock_vehicle.get_float(c.path)
                source_tag = "input" if c.source == "vehinput" else "sim"
                self.stock_value_labels[c.key].configure(text=f"{source_tag} stock: {self._format_value(c, stock_value)}")

    def on_vehicle_changed(self) -> None:
        self._load_vehicle_to_controls(self.current_vehicle.get())

    def save_preset_file(self) -> None:
        preset_dir = app_dir() / "presets_custom"
        preset_dir.mkdir(exist_ok=True)
        default_name = f"codered_{self.current_vehicle.get().lower()}_preset_{now_stamp()}.json"
        path = filedialog.asksaveasfilename(
            title="Save Code RED tune preset",
            initialdir=str(preset_dir),
            initialfile=default_name,
            defaultextension=".json",
            filetypes=[("Code RED preset", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        data = {
            "app": APP_NAME,
            "version": APP_VERSION,
            "created": _dt.datetime.now().isoformat(timespec="seconds"),
            "active_vehicle": self.current_vehicle.get(),
            "controls": [c.__dict__ for c in CONTROLS],
            "vehicles": {label: self._all_control_values_for_vehicle(label) for label in VEHICLE_FILES},
        }
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.status.set(f"Saved preset JSON: {path}")

    def load_preset_file(self) -> None:
        preset_dir = app_dir() / "presets_custom"
        preset_dir.mkdir(exist_ok=True)
        path = filedialog.askopenfilename(
            title="Load Code RED tune preset",
            initialdir=str(preset_dir),
            filetypes=[("Code RED preset", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            vehicles = data.get("vehicles")
            if isinstance(vehicles, dict):
                for label, values in vehicles.items():
                    if label not in VEHICLE_FILES or not isinstance(values, dict):
                        continue
                    for key, value in values.items():
                        c = next((x for x in CONTROLS if x.key == key), None)
                        if c is not None:
                            self._tune_for_control(c, label).set_float(c.path, float(value))
            elif isinstance(data.get("values"), dict):
                label = self.current_vehicle.get()
                for key, value in data["values"].items():
                    c = next((x for x in CONTROLS if x.key == key), None)
                    if c is not None:
                        self._tune_for_control(c, label).set_float(c.path, float(value))
            self._load_vehicle_to_controls(self.current_vehicle.get())
            self.status.set(f"Loaded preset JSON: {path}")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not load preset:\n{exc}")

    def apply_preset(self, name: str) -> None:
        vehicle_label = self.current_vehicle.get()
        preset = PRESETS[name]
        if preset.get("mode") == "stock":
            self.vehicles[vehicle_label].clone_from_stock()
            self.vehicle_inputs[vehicle_label].clone_from_stock()
        else:
            for key, value in preset.items():
                if key == "note":
                    continue
                c = next((x for x in CONTROLS if x.key == key), None)
                if c is not None:
                    self._tune_for_control(c, vehicle_label).set_float(c.path, float(value))
            # off-road presets use gentle torque scaling, not chaos scaling
            if name == "Off-Road Fast Stable":
                self.vehicles[vehicle_label].set_torque_scale(1.18)
            elif name in ("Off-Road Heavy Crawl", "Mud Grip Test", "Low-Tip Truck"):
                self.vehicles[vehicle_label].set_torque_scale(1.08)
        self._load_vehicle_to_controls(vehicle_label)
        self.status.set(f"Applied preset '{name}' to {vehicle_label}.")

    def apply_torque_scale(self) -> None:
        vehicle_label = self.current_vehicle.get()
        tune = self.vehicles[vehicle_label]
        mult = self.torque_scale.get()
        tune.set_torque_scale(mult)
        self.status.set(f"Scaled {vehicle_label} torque curve by {mult:.2f}.")

    def reload_selected_stock(self) -> None:
        label = self.current_vehicle.get()
        self.vehicles[label].clone_from_stock()
        self.vehicle_inputs[label].clone_from_stock()
        self._load_vehicle_to_controls(label)
        self.status.set(f"Reloaded stock {label} vehsim + vehinput.")

    def open_exports_folder(self) -> None:
        path = app_dir() / "exports"
        path.mkdir(exist_ok=True)
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception:
            messagebox.showinfo(APP_NAME, f"Exports folder:\n{path}")

    def _build_guide_tab(self) -> None:
        frame = ttk.Frame(self.nb, padding=12)
        self.nb.add(frame, text="Guide")
        ttk.Label(frame, text="Code RED final-pass guide", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "This tab mirrors README_CodeRED_Tuner.txt so the package stays usable after it is copied to another PC. "
                "All paths are portable and resolved from this folder at runtime."
            ),
            style="Muted.TLabel",
            wraplength=980,
        ).pack(anchor="w", pady=(4, 12))
        guide_card = ttk.Frame(frame, style="Card.TFrame", padding=12)
        guide_card.pack(fill="both", expand=True)
        sections = [
            ("Install", "Extract the full CodeRED_Tuner folder, keep the internal folders together, then run run_CodeRED_Tuner.bat. The launcher checks Python and installs panda3d, pygame, and cryptography from requirements.txt when needed."),
            ("Tune", "Choose Car01 or Truck01, apply a preset or move sliders, then export patch files. Save custom presets from the left panel when you find a stable setup."),
            ("Demo", "Open Code Red Arcade, press Save / Apply Arcade Settings, then Test Demo. The arcade reads runtime/arcade_settings.json and watches it while running."),
            ("Controls", "WASD/Arrows drive, Shift boost, mouse look, mouse wheel zoom/FOV, Space target-lock, LMB/Q/E right seeker, RMB/Ctrl left seeker, Esc settings, F fullscreen, F12 screenshot."),
            ("Safety", "Exports are written under exports/. The full-RPF builder copies the selected archive first and does not overwrite the original file."),
        ]
        for title, body in sections:
            row = ttk.Frame(guide_card, style="Card.TFrame", padding=(0, 6))
            row.pack(fill="x")
            ttk.Label(row, text=title, style="Header.TLabel", width=16).pack(side="left", anchor="n")
            ttk.Label(row, text=body, style="Card.TLabel", wraplength=820).pack(side="left", fill="x", expand=True)
        ttk.Label(guide_card, text="by GLITCHED MATRIX Prototype Lab", style="Card.TLabel").pack(anchor="e", pady=(18, 0))

    def _build_arcade_tab(self) -> None:
        frame = ttk.Frame(self.nb, padding=12)
        self.nb.add(frame, text="Code Red Arcade")

        ttk.Label(frame, text="Code Red Arcade", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "External open-world vehicle-combat testbed. The tuner writes a compact runtime settings file, "
                "then launches the arcade in a separate process so the embedded tuner renderer can stay asleep. "
                "Close the arcade from its own Close App button, or stop it here to prevent orphaned background processes."
            ),
            style="Muted.TLabel",
            wraplength=940,
        ).pack(anchor="w", pady=(4, 10))

        top_card = ttk.Frame(frame, style="Card.TFrame", padding=12)
        top_card.pack(fill="x", pady=(0, 10))
        ttk.Label(top_card, text="External Process Controls", style="Header.TLabel").pack(anchor="w", pady=(0, 8))
        row = ttk.Frame(top_card, style="Card.TFrame")
        row.pack(fill="x")
        ttk.Button(row, text="Save / Apply Arcade Settings", command=self._save_arcade_settings).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="Test Demo", style="Accent.TButton", command=self._launch_arcade).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="Launch Code Red Arcade", command=self._launch_arcade).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="Stop Arcade", command=self._stop_arcade_process).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="Open Arcade Folder", command=self._open_arcade_folder).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="Open Sound Folder", command=self._open_arcade_sound_folder).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(row, text="Live apply slider changes", variable=self.arcade_live_apply_var).pack(side="left", padx=(10, 0))
        ttk.Checkbutton(row, text="LAN ghost clients", variable=self.arcade_lan_enabled).pack(side="left", padx=(10, 0))
        ttk.Label(row, text="Renderer", style="Card.TLabel").pack(side="left", padx=(14, 4))
        renderer_box = ttk.Combobox(row, textvariable=self.arcade_renderer_var, values=("panda", "auto", "tk"), width=7, state="readonly")
        renderer_box.pack(side="left")
        ttk.Checkbutton(row, text="Start fullscreen", variable=self.arcade_full_windowed_var).pack(side="left", padx=(10, 0))
        ttk.Label(row, text="Base FOV", style="Card.TLabel").pack(side="left", padx=(10, 3))
        ttk.Spinbox(row, from_=68, to=106, increment=2, textvariable=self.arcade_fov_var, width=4).pack(side="left")
        ttk.Label(row, text="Zoom", style="Card.TLabel").pack(side="left", padx=(10, 3))
        ttk.Spinbox(row, from_=0.62, to=1.72, increment=0.10, textvariable=self.arcade_zoom_var, width=5).pack(side="left")
        ready_row = ttk.Frame(top_card, style="Card.TFrame")
        ready_row.pack(fill="x", pady=(10, 0))
        ttk.Label(ready_row, textvariable=self.launch_readiness_var, style="Card.TLabel", width=38).pack(side="left")
        self.launch_readiness_bar = ttk.Progressbar(ready_row, maximum=100, variable=self.launch_readiness_value)
        self.launch_readiness_bar.pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(ready_row, text="Refresh", command=self._refresh_launch_readiness).pack(side="left", padx=(0, 8))
        ttk.Button(ready_row, text="Smoke Test", command=self._smoke_test_arcade).pack(side="left")
        ttk.Label(top_card, textvariable=self.arcade_status, style="Card.TLabel", wraplength=980).pack(anchor="w", pady=(8, 0))
        ttk.Label(top_card, text=f"Settings file: {self.arcade_settings_path}", style="Card.TLabel", wraplength=980).pack(anchor="w", pady=(4, 0))

        info = ttk.Frame(frame, style="Card.TFrame", padding=12)
        info.pack(fill="both", expand=True)
        ttk.Label(info, text="What the arcade reads from the tuner", style="Header.TLabel").pack(anchor="w", pady=(0, 8))
        rows = [
            ("Vehicle selection", "Car01 / Truck01 chooses which tuned value block the arcade drives."),
            ("Engine sliders", "Horsepower, boost torque, boost duration, high gear MPH, and drag shape acceleration and top speed."),
            ("Grip and steering", "Front/rear friction, steering limit, downforce, handbrake, and center of mass shape drift and rollover feel."),
            ("Arena options", "Rival count, weapons, terrain quality, world seed, audio flags, rideable hills/ramps, and open-world procedural terrain are saved beside the tune."),
            ("Replaceable sounds", "Drop .wav/.ogg/.mp3 files into assets/sfx/arcade. Nearby sounds are stereo-panned and distance-faded; loud events like boosts/explosions carry farther."),
            ("External lifecycle", "The arcade is a normal child process. Stop Arcade terminates it, and closing the tuner also stops a child launched from here."),
            ("Renderer / display", "Panda is the default renderer. Auto/Tk are only fallbacks. The arcade now launches as a 1920x1080 resizable 16:9 window. F toggles fullscreen. Mouse wheel controls camera zoom and the FOV follows zoom automatically."),
            ("Multiplayer lane", "LAN ghost clients are optional. Separate machines launched with LAN enabled broadcast/receive visible peer cars without blocking offline play."),
        ]
        for title, desc in rows:
            r = ttk.Frame(info, style="Card.TFrame", padding=(0, 5))
            r.pack(fill="x")
            ttk.Label(r, text=title, style="Card.TLabel", width=20).pack(side="left", anchor="n")
            ttk.Label(r, text=desc, style="Card.TLabel", wraplength=760).pack(side="left", fill="x", expand=True)

        ttk.Separator(info).pack(fill="x", pady=12)
        ttk.Label(info, text="Arcade controls", style="Header.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Label(
            info,
            text="WASD/Arrows drive • Shift boosts while all other controls keep working • mouse looks around/up/down • mouse wheel zooms and auto-locks FOV • Space target-lock • RMB/Ctrl left seeker • LMB/Q/E right seeker • H/F1 help • Esc opens pause/settings • F fullscreen.",
            style="Card.TLabel",
            wraplength=900,
        ).pack(anchor="w")
        self.after(800, self._poll_arcade_process)

    def _compute_launch_readiness(self) -> tuple[int, list[str]]:
        checks: list[tuple[str, bool, int]] = []
        script = self._arcade_script_path()
        checks.append(("arcade script", script.exists(), 18))
        checks.append(("tuner stock files", all((self.stock_dir / name).exists() for name in list(VEHICLE_FILES.values()) + list(VEHICLE_INPUT_FILES.values())), 18))
        checks.append(("input profile", bool(self.input_profile_path and self.input_profile_path.exists()), 10))
        sfx_dir = app_dir() / "assets" / "sfx" / "arcade"
        checks.append(("arcade SFX folder", sfx_dir.exists() and len(list(sfx_dir.glob("*.wav"))) >= 5, 10))
        try:
            self.arcade_settings_path.parent.mkdir(parents=True, exist_ok=True)
            probe = self.arcade_settings_path.parent / ".settings_write_probe.tmp"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            writable = True
        except Exception:
            writable = False
        checks.append(("runtime settings writable", writable, 14))
        try:
            import ast as _ast
            _ast.parse(script.read_text(encoding="utf-8"))
            arcade_parse = True
        except Exception:
            arcade_parse = False
        checks.append(("arcade syntax", arcade_parse, 12))
        try:
            import tkinter as _tk  # noqa: F401
            tk_ready = True
        except Exception:
            tk_ready = False
        checks.append(("Tk fallback renderer", tk_ready, 8))
        panda_ready = importlib.util.find_spec("panda3d") is not None and importlib.util.find_spec("direct") is not None
        checks.append(("Panda3D preferred renderer or fallback accepted", True if panda_ready or tk_ready else False, 10))
        score = sum(weight for _name, ok, weight in checks if ok)
        missing = [name for name, ok, _weight in checks if not ok]
        return min(100, score), missing

    def _refresh_launch_readiness(self) -> None:
        try:
            score, missing = self._compute_launch_readiness()
            self.launch_readiness_value.set(float(score))
            if missing:
                self.launch_readiness_var.set(f"Launch readiness: {score}% • missing: {', '.join(missing[:2])}")
            else:
                self.launch_readiness_var.set(f"Launch readiness: {score}% • ready")
        except Exception as exc:
            self.launch_readiness_var.set(f"Launch readiness check failed: {exc}")

    def _smoke_test_arcade(self) -> None:
        script = self._arcade_script_path()
        if not script.exists():
            messagebox.showerror(APP_NAME, f"Code Red Arcade script not found:\n{script}")
            return
        try:
            self._save_arcade_settings()
            cmd = [sys.executable, str(script), "--selftest", "--settings", str(self.arcade_settings_path)]
            proc = subprocess.run(cmd, cwd=str(script.parent), capture_output=True, text=True, timeout=12, check=False)
            output = (proc.stdout or "").strip()
            errors = (proc.stderr or "").strip()
            detail = f"Exit code: {proc.returncode}"
            if output:
                detail += f"\n\nOutput:\n{output[-2000:]}"
            if errors:
                detail += f"\n\nErrors:\n{errors[-2000:]}"
            if proc.returncode == 0:
                self.arcade_status.set("Smoke Test passed. Arcade settings and launch file validated.")
                messagebox.showinfo(APP_NAME, detail)
            else:
                self.arcade_status.set("Smoke Test failed. Check details/logs before shipping.")
                messagebox.showerror(APP_NAME, detail)
        except Exception as exc:
            self.arcade_status.set(f"Smoke Test failed: {exc}")
            messagebox.showerror(APP_NAME, f"Smoke Test failed:\n{exc}")
        finally:
            self._refresh_launch_readiness()

    def _arcade_script_path(self) -> Path:
        return app_dir() / "code_red_arcade.py"

    def _arcade_settings_payload(self) -> dict:
        return {
            "app": APP_NAME,
            "version": APP_VERSION,
            "arcade_app": "Code Red Arcade",
            "created": _dt.datetime.now().isoformat(timespec="seconds"),
            "active_vehicle": self.current_vehicle.get(),
            "vehicles": {label: self._all_control_values_for_vehicle(label) for label in VEHICLE_FILES},
            "arcade": {
                "world_seed": int(self.world_seed_var.get() or 1),
                "arena_seed": int(self.arena_seed_var.get() or 0),
                "rival_count": int(self.rival_count_var.get()),
                "terrain_mode": self.terrain_mode.get(),
                "terrain_quality": self.terrain_quality_var.get(),
                "guide_track": bool(self.draw_guide_track_var.get()),
                "weapons_enabled": bool(self.gatlings_enabled.get()),
                "rivals_fire": bool(self.gatling_fire_enabled.get()),
                "desert_arena": bool(self.desert_arena_enabled.get()),
                "limitless_desert": bool(self.limitless_desert_enabled.get()),
                "input_profile_enabled": bool(self.input_profile_enabled.get()),
                "move_y_handbrake_assist": bool(self.move_y_handbrake_assist.get()),
                "audio_enabled": bool(self.audio_enabled.get()),
                "music_enabled": bool(self.music_enabled.get()),
                "master_volume": float(self.master_volume.get()),
                "sfx_volume": float(self.sfx_volume.get()),
                "music_volume": float(self.music_volume.get()),
                "lan_ghost_clients": bool(self.arcade_lan_enabled.get()),
                "renderer_preference": self.arcade_renderer_var.get(),
                "full_windowed": bool(self.arcade_full_windowed_var.get()),
                "camera_fov": float(self.arcade_fov_var.get()),
                "camera_zoom": float(self.arcade_zoom_var.get() or 1.72),
                "space_action": "target_lock",
                "f12_screenshots": True,
            },
        }

    def _restore_arcade_settings_values(self) -> None:
        """Restore the last saved arcade/tuner runtime values without requiring the UI to exist yet.

        v2.4.0 called this during startup but the method was missing, which made the
        tuner crash before the Tk window could draw. This loader is intentionally
        conservative: bad or partial JSON is ignored, UI widgets are not touched until
        they exist, and saved vehicle tune values are applied directly to the in-memory
        stock tune copies so _load_vehicle_to_controls() can populate the sliders later.
        """
        path = getattr(self, "arcade_settings_path", None)
        if not path:
            return
        try:
            path = Path(path)
            if not path.exists():
                return
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
        except Exception as exc:
            try:
                self.arcade_status.set(f"Saved arcade settings were ignored: {exc}")
            except Exception:
                pass
            return

        def _set_var(name: str, value, caster=None) -> None:
            var = getattr(self, name, None)
            if var is None or value is None:
                return
            try:
                var.set(caster(value) if caster else value)
            except Exception:
                pass

        active = data.get("active_vehicle")
        if active in VEHICLE_FILES:
            _set_var("current_vehicle", active)

        vehicles = data.get("vehicles")
        if isinstance(vehicles, dict):
            for label, values in vehicles.items():
                if label not in VEHICLE_FILES or not isinstance(values, dict):
                    continue
                for c in CONTROLS:
                    if c.key not in values:
                        continue
                    try:
                        self._tune_for_control(c, label).set_float(c.path, float(values[c.key]))
                    except Exception:
                        pass

        arcade = data.get("arcade")
        if not isinstance(arcade, dict):
            return
        _set_var("world_seed_var", arcade.get("world_seed"), int)
        _set_var("arena_seed_var", arcade.get("arena_seed"), int)
        _set_var("rival_count_var", arcade.get("rival_count"), int)
        _set_var("terrain_mode", arcade.get("terrain_mode"))
        _set_var("terrain_quality_var", arcade.get("terrain_quality"))
        _set_var("draw_guide_track_var", arcade.get("guide_track"), bool)
        _set_var("gatlings_enabled", arcade.get("weapons_enabled"), bool)
        _set_var("gatling_fire_enabled", arcade.get("rivals_fire"), bool)
        _set_var("desert_arena_enabled", arcade.get("desert_arena"), bool)
        _set_var("limitless_desert_enabled", arcade.get("limitless_desert"), bool)
        _set_var("input_profile_enabled", arcade.get("input_profile_enabled"), bool)
        _set_var("move_y_handbrake_assist", arcade.get("move_y_handbrake_assist"), bool)
        _set_var("audio_enabled", arcade.get("audio_enabled"), bool)
        _set_var("music_enabled", arcade.get("music_enabled"), bool)
        _set_var("master_volume", arcade.get("master_volume"), float)
        _set_var("sfx_volume", arcade.get("sfx_volume"), float)
        _set_var("music_volume", arcade.get("music_volume"), float)
        _set_var("arcade_lan_enabled", arcade.get("lan_ghost_clients"), bool)
        _set_var("arcade_renderer_var", arcade.get("renderer_preference") or "panda")
        _set_var("arcade_full_windowed_var", arcade.get("full_windowed"), bool)
        _set_var("arcade_fov_var", arcade.get("camera_fov"), float)
        zoom = arcade.get("camera_zoom", 1.72)
        try:
            zoom = max(0.62, min(1.72, float(zoom)))
        except Exception:
            zoom = 1.72
        _set_var("arcade_zoom_var", zoom, float)
        try:
            self.arcade_status.set(f"Restored arcade settings from {path.name}")
        except Exception:
            pass

    def _save_arcade_settings(self) -> Path:
        self.arcade_settings_path.parent.mkdir(parents=True, exist_ok=True)
        data = self._arcade_settings_payload()
        self.arcade_settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.arcade_status.set(f"Saved arcade settings for {data['active_vehicle']} at {self.arcade_settings_path}")
        self._refresh_launch_readiness()
        return self.arcade_settings_path

    def _queue_arcade_settings_sync(self) -> None:
        if getattr(self, "initializing", False):
            return
        if not hasattr(self, "arcade_live_apply_var") or not self.arcade_live_apply_var.get():
            return
        try:
            if self._arcade_sync_after_id is not None:
                self.after_cancel(self._arcade_sync_after_id)
        except Exception:
            pass
        self._arcade_sync_after_id = self.after(350, self._save_arcade_settings_quiet)

    def _save_arcade_settings_quiet(self) -> None:
        self._arcade_sync_after_id = None
        try:
            self._save_arcade_settings()
        except Exception as exc:
            self.arcade_status.set(f"Could not save arcade settings: {exc}")

    def _launch_arcade(self) -> None:
        script = self._arcade_script_path()
        if not script.exists():
            messagebox.showerror(APP_NAME, f"Code Red Arcade script not found:\n{script}")
            return
        self._save_arcade_settings()
        if self.arcade_process is not None and self.arcade_process.poll() is None:
            self.arcade_status.set("Code Red Arcade is already running from this tuner. Use Stop Arcade first if you need a clean relaunch.")
            return
        cmd = [sys.executable, str(script), "--settings", str(self.arcade_settings_path), "--renderer", self.arcade_renderer_var.get()]
        if self.arcade_lan_enabled.get():
            cmd.append("--lan")
        try:
            self.arcade_process = subprocess.Popen(cmd, cwd=str(script.parent))
            self.arcade_status.set(f"Launched Code Red Arcade PID {self.arcade_process.pid} using renderer={self.arcade_renderer_var.get()}")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not launch Code Red Arcade:\n{exc}")

    def _stop_arcade_process(self) -> None:
        proc = getattr(self, "arcade_process", None)
        if proc is None:
            self.arcade_status.set("Code Red Arcade is not running from this tuner.")
            return
        if proc.poll() is not None:
            self.arcade_status.set("Code Red Arcade had already exited.")
            self.arcade_process = None
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
            self.arcade_status.set("Stopped Code Red Arcade child process.")
        except Exception as exc:
            self.arcade_status.set(f"Could not stop Code Red Arcade: {exc}")
        finally:
            self.arcade_process = None

    def _poll_arcade_process(self) -> None:
        proc = getattr(self, "arcade_process", None)
        if proc is not None and proc.poll() is not None:
            self.arcade_status.set(f"Code Red Arcade exited with code {proc.returncode}.")
            self.arcade_process = None
        try:
            self.after(1200, self._poll_arcade_process)
        except Exception:
            pass

    def _open_arcade_folder(self) -> None:
        folder = app_dir()
        try:
            os.startfile(folder)  # type: ignore[attr-defined]
        except Exception:
            messagebox.showinfo(APP_NAME, f"Arcade folder:\n{folder}")

    def _open_arcade_sound_folder(self) -> None:
        folder = app_dir() / "assets" / "sfx" / "arcade"
        folder.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(folder)  # type: ignore[attr-defined]
        except Exception:
            messagebox.showinfo(APP_NAME, f"Arcade sound folder:\n{folder}")

    def _on_tuner_close(self) -> None:
        self._stop_arcade_process()
        self.destroy()

    def _build_preview_tab(self) -> None:
        frame = ttk.Frame(self.nb, padding=10)
        self.nb.add(frame, text="Drive 3D")
        left = ttk.Frame(frame)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(frame, style="Card.TFrame", padding=12, width=310)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)

        ttk.Label(left, text="Code Red Arcade Embedded Preview", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            left,
            text="Drive the current Car01/Truck01 tune in an open-world desert combat test. The old one-way guide track is off by default, the terrain streams around the car, and the active vehicle count stays capped for performance. The renderer sleeps when this tab/app is in the background.",
            style="Muted.TLabel",
            wraplength=860,
        ).pack(anchor="w", pady=(2, 8))

        self.preview_canvas = tk.Canvas(left, width=900, height=560, bg="#0b0f14", highlightthickness=1, highlightbackground="#4a2026")
        self.preview_canvas.pack(fill="both", expand=True)
        self.preview_canvas.bind("<ButtonPress-1>", self._sim_mouse_down)
        self.preview_canvas.bind("<ButtonRelease-1>", self._sim_mouse_up)
        self.preview_canvas.bind("<Motion>", self._sim_mouse_motion)
        self.preview_canvas.bind("<Leave>", self._sim_mouse_leave)
        self.preview_canvas.bind("<KeyPress>", self._sim_key_down)
        self.preview_canvas.bind("<KeyRelease>", self._sim_key_up)
        self.preview_canvas.bind("<MouseWheel>", self._sim_mousewheel)
        self.preview_canvas.focus_set()

        controls = ttk.Frame(left, padding=(0, 8, 0, 0))
        controls.pack(fill="x")
        ttk.Checkbutton(controls, text="Run sim", variable=self.preview_running).pack(side="left")
        ttk.Checkbutton(controls, text="Guide track", variable=self.draw_guide_track_var, command=self._draw_preview).pack(side="left", padx=(10, 4))
        ttk.Checkbutton(controls, text="Sleep renderer when background/tab hidden", variable=self.renderer_sleep_when_background).pack(side="left", padx=(10, 4))
        ttk.Label(controls, textvariable=self.renderer_active_status, style="Muted.TLabel").pack(side="left", padx=(4, 8))
        ttk.Button(controls, text="Reset Car", command=self.reset_preview).pack(side="left", padx=8)
        ttk.Button(controls, text="Load Manual Preview Mesh", command=self.load_preview_obj).pack(side="left", padx=4)
        ttk.Button(controls, text="Balanced", command=lambda: self.apply_preset("Off-Road Balanced")).pack(side="left", padx=4)
        ttk.Button(controls, text="Heavy Crawl", command=lambda: self.apply_preset("Off-Road Heavy Crawl")).pack(side="left", padx=4)
        ttk.Button(controls, text="Fast Stable", command=lambda: self.apply_preset("Off-Road Fast Stable")).pack(side="left", padx=4)
        ttk.Label(controls, text="Terrain:", style="Muted.TLabel").pack(side="left", padx=(14, 4))
        terrain_box = ttk.OptionMenu(controls, self.terrain_mode, self.terrain_mode.get(), *TERRAIN_MODES.keys(), command=lambda _v: self.reset_preview())
        terrain_box.pack(side="left")
        ttk.Label(controls, text="Quality:", style="Muted.TLabel").pack(side="left", padx=(10, 4))
        quality_box = ttk.OptionMenu(controls, self.terrain_quality_var, self.terrain_quality_var.get(), "Fast", "Balanced", "High", command=lambda _v: self._draw_preview())
        quality_box.pack(side="left")
        ttk.Button(controls, text="Randomize Arena", command=self.randomize_desert_arena).pack(side="left", padx=(10, 0))

        ttk.Label(right, text="Drive Controls", style="Header.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Label(
            right,
            text=self._input_control_help_text(),
            style="Card.TLabel",
            wraplength=270,
        ).pack(anchor="w", pady=(0, 6))
        ttk.Checkbutton(right, text="Use input_car.xml map", variable=self.input_profile_enabled).pack(anchor="w", pady=(0, 2))
        ttk.Checkbutton(right, text="MOVE_Y handbrake assist", variable=self.move_y_handbrake_assist).pack(anchor="w", pady=(0, 4))
        ttk.Checkbutton(right, text="Show side launchers", variable=self.gatlings_enabled, command=self._draw_preview).pack(anchor="w", pady=(0, 2))
        ttk.Checkbutton(right, text="LMB fires missiles", variable=self.gatling_fire_enabled).pack(anchor="w", pady=(0, 2))
        ttk.Checkbutton(right, text="Desert arena rivals", variable=self.desert_arena_enabled, command=self.randomize_desert_arena).pack(anchor="w", pady=(0, 2))
        ttk.Checkbutton(right, text="Limitless procedural desert", variable=self.limitless_desert_enabled, command=self._draw_preview).pack(anchor="w", pady=(0, 4))
        rival_row = ttk.Frame(right, style="Card.TFrame")
        rival_row.pack(fill="x", pady=(0, 6))
        ttk.Label(rival_row, text="Rivals (3 max)", style="Card.TLabel").pack(side="left")
        ttk.Button(rival_row, text="-", width=3, command=lambda: self._change_rival_count(-1)).pack(side="right", padx=(2, 0))
        ttk.Button(rival_row, text="+", width=3, command=lambda: self._change_rival_count(1)).pack(side="right")
        ttk.Label(rival_row, textvariable=self.rival_count_var, style="Card.TLabel", width=3).pack(side="right", padx=6)
        self.input_profile_label = ttk.Label(right, text=self._input_profile_summary(), style="Card.TLabel", wraplength=270)
        self.input_profile_label.pack(anchor="w", pady=(0, 8))

        seed_row = ttk.Frame(right, style="Card.TFrame")
        seed_row.pack(fill="x", pady=(0, 8))
        ttk.Label(seed_row, text="World seed", style="Card.TLabel").pack(side="left")
        ttk.Button(seed_row, text="New", command=self.randomize_world_seed).pack(side="right")
        ttk.Label(seed_row, textvariable=self.world_seed_var, style="Card.TLabel", width=7).pack(side="right", padx=4)

        ttk.Label(right, text="Pause / Audio", style="Header.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Checkbutton(right, text="P shows pause overlay", variable=self.pause_overlay_enabled, command=self._draw_preview).pack(anchor="w")
        ttk.Checkbutton(right, text="Enable SFX", variable=self.audio_enabled, command=self._on_audio_changed).pack(anchor="w")
        ttk.Checkbutton(right, text="Music loop", variable=self.music_enabled, command=self._on_audio_changed).pack(anchor="w", pady=(0, 3))
        for lbl, var in (("Master", self.master_volume), ("SFX", self.sfx_volume), ("Music", self.music_volume)):
            row = ttk.Frame(right, style="Card.TFrame")
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=lbl, style="Card.TLabel", width=7).pack(side="left")
            ttk.Scale(row, from_=0.0, to=1.0, orient="horizontal", variable=var, command=lambda _v: self._on_audio_changed()).pack(side="left", fill="x", expand=True)
        ttk.Button(right, text="Test Missile Sound", command=lambda: self.sound.play("missile_launch", 0.8)).pack(fill="x", pady=(4, 8))

        ttk.Label(right, text="Simulator Telemetry", style="Header.TLabel").pack(anchor="w", pady=(0, 8))
        for key, label in [
            ("speed", "Speed"),
            ("accel", "Acceleration"),
            ("top", "Estimated top"),
            ("grip", "Grip index"),
            ("drift", "Drift tendency"),
            ("stability", "Stability"),
            ("steer", "Steering"),
            ("drag", "Drag loss"),
            ("offroad", "Off-road score"),
            ("rollover", "Rollover risk"),
            ("climb", "Climb power"),
            ("terrain", "Terrain"),
            ("weapons", "Weapons"),
            ("rounds", "Missiles fired"),
            ("rivals", "Arena rivals"),
            ("hits", "Combat hits"),
            ("distance", "Distance out"),
            ("worldrough", "World roughness"),
            ("audio", "Audio"),
            ("mesh", "Mesh source"),
        ]:
            row = ttk.Frame(right, style="Card.TFrame")
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, style="Card.TLabel", width=17).pack(side="left")
            value = ttk.Label(row, text="--", style="Card.TLabel")
            value.pack(side="right")
            self.preview_labels[key] = value

        ttk.Separator(right).pack(fill="x", pady=10)
        ttk.Label(right, text="WFT / Model Viewer Lane", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            right,
            text="The Code RED resource viewer is a Blender/Sollumz RDR1 lane for CodeX-exported .wfd/.wvd XML, not direct raw WFT rendering inside this app. The visible final pass uses baked wire vehicle data in assets/vehicles and no longer depends on old shipped .obj/.glb/.fbx/.egg model paths. Optional manual OBJ loading remains only as a private preview fallback.",
            style="Card.TLabel",
            wraplength=270,
        ).pack(anchor="w", pady=(4, 0))

        self.sim_keys = set()
        self.sim_mouse_buttons = set()
        self.sim_projectiles = []
        self.sim_explosions = []
        self.sim_fire_cooldown = 0.0
        self.sim_missile_cooldown = 0.0
        self.player_health = 5
        self.player_respawn_timer = 0.0
        self.sim_rounds_fired = 0
        self.sim_mesh_cache = {}
        self.sim_mesh_source = "generated vehsim body"
        self.sim_camera_mode = tk.StringVar(value="chase")
        self.sim_camera_distance = 12.5
        self.sim_camera_height = 2.9
        self.sim_aim_offset = 0.0
        self.sim_aim_pitch = 0.0
        self.sim_mouse_x = 0
        self.sim_mouse_y = 0
        self.sim_missile_cooldown = 0.0
        self.sim_explosions = []
        self.player_health = 5
        self.player_respawn_timer = 0.0
        if self.world_seed_var.get() <= 0:
            self.world_seed_var.set(random.randint(10000, 999999))
        self.reset_preview()
        self._update_preview_metrics()
        self.after(50, self._preview_tick)

    def _on_app_focus_in(self, event=None) -> None:
        self._app_has_focus = True
        self._wake_renderer("focus")

    def _on_app_focus_out(self, event=None) -> None:
        # FocusOut also fires when moving between child widgets, so defer the real
        # check. If no widget in this Tk app owns focus after the delay, the app is
        # genuinely backgrounded and the renderer can sleep.
        self.after(120, self._verify_focus_state)

    def _verify_focus_state(self) -> None:
        try:
            self._app_has_focus = self.focus_displayof() is not None
        except Exception:
            self._app_has_focus = True
        if self._app_has_focus:
            self._wake_renderer("focus returned")
        else:
            self._mark_renderer_background("background")

    def _mark_renderer_background(self, reason: str = "background") -> None:
        self._renderer_last_state = reason
        if hasattr(self, "renderer_active_status"):
            self.renderer_active_status.set(f"Renderer: asleep ({reason})")
        # Release held inputs so the car does not keep driving/shooting while the
        # app is minimized, tabbed away, or not focused.
        if hasattr(self, "sim_mouse_buttons"):
            self.sim_mouse_buttons.clear()
        if hasattr(self, "sim_keys"):
            self.sim_keys.clear()

    def _wake_renderer(self, reason: str = "active") -> None:
        self._app_has_focus = True
        self._renderer_last_state = "active"
        if hasattr(self, "renderer_active_status"):
            self.renderer_active_status.set("Renderer: active")
        self._last_preview_time = None

    def _drive_tab_is_selected(self) -> bool:
        try:
            return self.nb.tab(self.nb.select(), "text") == "Drive 3D"
        except Exception:
            return True

    def _renderer_should_sleep(self) -> tuple[bool, str]:
        if not getattr(self, "renderer_sleep_when_background", tk.BooleanVar(value=True)).get():
            return False, "forced active"
        try:
            if self.state() == "iconic":
                return True, "minimized"
        except Exception:
            pass
        if not self._drive_tab_is_selected():
            return True, "tab hidden"
        if getattr(self, "_app_has_focus", True) is False:
            return True, "background"
        return False, "active"

    def _preview_snapshot(self) -> dict[str, float]:
        vals = {c.key: self.vars[c.key].get() for c in CONTROLS if c.key in self.vars}
        mass = max(vals.get("mass", 2000.0), 1.0)
        hp = vals.get("horsepower", 168.0)
        boost = vals.get("boost_torque", 0.0) * max(vals.get("boost_duration", 0.0), 0.0) * 0.06
        high = vals.get("high_mph", 45.0)
        low = vals.get("low_mph", 25.0)
        drag = max(vals.get("aero_drag", 1.0), 0.0) + max(vals.get("vehicle_path_drag", 0.0), 0.0) * 0.35 + max(vals.get("offroad_drag", 0.0), 0.0) * 0.20
        front_static = vals.get("front_static", 1.0)
        rear_static = vals.get("rear_static", 1.0)
        front_slide = vals.get("front_slide", 1.0)
        rear_slide = vals.get("rear_slide", 1.0)
        grip = max(0.05, (front_static + rear_static + front_slide + rear_slide) / 4.0)
        terrain_name = self.terrain_mode.get() if hasattr(self, "terrain_mode") else "Flat Road"
        terrain = TERRAIN_MODES.get(terrain_name, TERRAIN_MODES["Flat Road"])
        terrain_grip = float(terrain.get("grip", 1.0))
        terrain_drag = float(terrain.get("drag", 1.0))
        terrain_rough = float(terrain.get("rough", 0.0))
        terrain_grade = float(terrain.get("grade", 0.0))
        world_distance = math.hypot(getattr(self, "sim_x", 0.0), getattr(self, "sim_z", 0.0))
        progressive = 0.0
        local_grade = 0.0
        if getattr(self, "limitless_desert_enabled", tk.BooleanVar(value=True)).get() and terrain_name == "Desert Arena":
            seed = int(getattr(self, "world_seed_var", tk.IntVar(value=12345)).get() or 12345)
            wave_a = math.sin((getattr(self, "sim_x", 0.0) + seed * 0.01) * 0.055) * 0.5 + 0.5
            wave_b = math.cos((getattr(self, "sim_z", 0.0) - seed * 0.01) * 0.043) * 0.5 + 0.5
            progressive = min(0.58, world_distance / 520.0) + wave_a * wave_b * 0.12
            terrain_rough += progressive
            terrain_drag *= 1.0 + progressive * 0.32
            terrain_grip *= max(0.55, 1.0 - progressive * 0.22)
            local_grade = (wave_a - 0.5) * 0.08 + (wave_b - 0.5) * 0.07
            terrain_grade += max(0.0, local_grade)
        grip = max(0.05, grip * terrain_grip)
        rear_bias = vals.get("rear_torque", 1.0) - vals.get("front_torque", 1.0)
        handbrake = vals.get("handbrake", 0.0)
        drift = max(0.0, (front_slide - rear_slide) * 0.50 + rear_bias * 0.035 + handbrake * 0.05)
        steering = vals.get("front_steer", 0.5)
        com_z = vals.get("com_z", -0.5)
        bound_gravity = vals.get("bound_gravity", 1.0)
        input_smooth = max(0.0, vals.get("input_sss_value", 0.5))
        sim_smooth = max(0.0, vals.get("sim_sss_value", 0.45))
        auto_reverse = max(0.0, vals.get("auto_reverse_speed", 2.25))
        drag *= terrain_drag
        stability = max(0.05, min(3.0, 1.0 + (-com_z * 0.55) + (bound_gravity - 1.0) * 0.16 + (mass - 1800.0) / 7000.0 - drift * 0.10 + (input_smooth + sim_smooth - 0.9) * 0.18 - terrain_rough * 0.22))
        power_to_weight = (hp + boost) / mass
        climb_penalty = 1.0 + max(0.0, terrain_grade) * 1.65
        accel = max(0.02, power_to_weight * 7.0 / (1.0 + drag * 0.18) / climb_penalty)
        estimated_top = max(6.0, (high * 0.70 + low * 0.16 + hp * 0.038 + boost * 0.016) / (1.0 + drag * 0.12 + terrain_grade * 0.35))
        steer_response = steering / (1.0 + input_smooth * 0.28 + terrain_rough * 0.15)
        offroad_score = max(0, min(100, int(round((grip * 23) + (stability * 20) + (accel * 15) - (drift * 28) - (drag * 4) - (terrain_rough * 9)))))
        rollover_risk = max(0, min(100, int(round((1.75 - stability) * 36 + max(0, drift - 0.35) * 38 + terrain_rough * 26 + max(0, com_z + 0.55) * 25))))
        climb_power = max(0, min(100, int(round((accel * 34) + (grip * 18) + (hp / max(mass, 1)) * 260 - terrain_grade * 18))))
        return {"mass": mass, "hp": hp, "drag": drag, "grip": grip, "drift": drift, "steering": steer_response, "stability": stability, "accel": accel, "top": estimated_top, "input_smooth": input_smooth, "sim_smooth": sim_smooth, "auto_reverse": auto_reverse, "terrain": terrain_name, "terrain_grip": terrain_grip, "terrain_drag": terrain_drag, "terrain_rough": terrain_rough, "terrain_grade": terrain_grade, "world_distance": world_distance, "world_roughness": progressive, "local_grade": local_grade, "offroad_score": offroad_score, "rollover_risk": rollover_risk, "climb_power": climb_power}

    def _update_preview_metrics(self) -> None:
        if not hasattr(self, "preview_labels"):
            return
        s = self._preview_snapshot()
        values = {
            "speed": f"{getattr(self, 'preview_speed', 0.0):5.1f} mph",
            "accel": f"{s['accel']:.2f}x",
            "top": f"{s['top']:.1f} mph",
            "grip": f"{s['grip']:.2f}",
            "drift": f"{s['drift']:.2f}",
            "stability": f"{s['stability']:.2f}",
            "steer": f"{s['steering']:.2f}",
            "drag": f"{s['drag']:.2f}",
            "offroad": f"{s.get('offroad_score', 0)}/100",
            "rollover": f"{s.get('rollover_risk', 0)}/100",
            "climb": f"{s.get('climb_power', 0)}/100",
            "terrain": str(s.get('terrain', 'Flat Road')),
            "weapons": "missile launchers" if self.gatlings_enabled.get() else "hidden",
            "rounds": str(getattr(self, "sim_rounds_fired", 0)),
            "rivals": str(len(getattr(self, "sim_rivals", []))) if self.desert_arena_enabled.get() else "off",
            "hits": str(getattr(self, "sim_hits", 0)),
            "distance": f"{s.get('world_distance', 0.0):.0f} m",
            "worldrough": f"{s.get('world_roughness', 0.0):.2f}",
            "audio": getattr(getattr(self, "sound", None), "status", "off"),
            "mesh": getattr(self, "sim_mesh_source", "generated"),
        }
        for key, value in values.items():
            if key in self.preview_labels:
                self.preview_labels[key].configure(text=value)

    def reset_preview(self) -> None:
        self.sim_x = 0.0
        self.sim_z = 0.0
        self.sim_heading = 0.0
        self.sim_forward_speed = 0.0
        self.sim_lateral_speed = 0.0
        self.sim_steer = 0.0
        self.preview_speed = 0.0
        self.preview_distance = 0.0
        self.preview_phase = 0.0
        self.preview_trail = []
        self.sim_projectiles = []
        self.sim_explosions = []
        self.sim_fire_cooldown = 0.0
        self.sim_missile_cooldown = 0.0
        self.player_health = 5
        self.player_respawn_timer = 0.0
        self.sim_rounds_fired = 0
        self.sim_hits = 0
        self.sim_skid_cooldown = 0.0
        if not getattr(self, "sim_rivals", None):
            self.randomize_desert_arena(draw=False)
        if hasattr(self, "preview_canvas"):
            self.preview_canvas.focus_set()
            self._draw_preview()

    def _sim_mouse_down(self, event) -> None:
        self.preview_canvas.focus_set()
        self._sim_mouse_motion(event)
        if getattr(event, "num", 0) == 1:
            self.sim_mouse_buttons.add("mouse1")

    def _sim_mouse_up(self, event) -> None:
        if getattr(event, "num", 0) == 1:
            self.sim_mouse_buttons.discard("mouse1")


    def _sim_mouse_motion(self, event) -> None:
        """Mouse position controls aim/camera look in the Drive 3D combat view.
        Tk cannot lock the pointer like a real game, so this uses the mouse position
        inside the canvas as a stable aim offset. Center = straight ahead.
        """
        try:
            w = max(1, self.preview_canvas.winfo_width())
            h = max(1, self.preview_canvas.winfo_height())
            self.sim_mouse_x = int(getattr(event, "x", w // 2))
            self.sim_mouse_y = int(getattr(event, "y", h // 2))
            nx = max(-1.0, min(1.0, (self.sim_mouse_x - w * 0.5) / (w * 0.5)))
            ny = max(-1.0, min(1.0, (self.sim_mouse_y - h * 0.45) / (h * 0.45)))
            self.sim_aim_offset = nx * 0.78
            self.sim_aim_pitch = -ny * 0.28
        except Exception:
            self.sim_aim_offset = 0.0
            self.sim_aim_pitch = 0.0

    def _sim_mouse_leave(self, event) -> None:
        self.sim_mouse_buttons.discard("mouse1")

    def _sim_key_down(self, event) -> None:
        key = (event.keysym or "").lower()
        self.sim_keys.add(key)
        if key == "r":
            self.reset_preview()
        elif key == "c":
            self.sim_camera_mode.set("orbit" if self.sim_camera_mode.get() == "chase" else "chase")
        elif key == "p":
            self.pause_overlay_enabled.set(not self.pause_overlay_enabled.get())
            self._draw_preview()

    def _sim_key_up(self, event) -> None:
        self.sim_keys.discard((event.keysym or "").lower())

    def _sim_mousewheel(self, event) -> None:
        delta = -1 if event.delta > 0 else 1
        self.sim_camera_distance = max(7.5, min(24.0, self.sim_camera_distance + delta * 0.9))
        self.sim_camera_height = max(1.8, min(8.0, self.sim_camera_height + delta * 0.28))
        self._draw_preview()

    def _is_pressed(self, *names: str) -> bool:
        return any(n.lower() in self.sim_keys for n in names)

    def _input_parameter(self, value: str) -> str:
        return self.input_map.get(value, {}).get("Parameter", "")

    def _input_source(self, value: str) -> str:
        return self.input_map.get(value, {}).get("Source", "")

    def _input_aliases_for(self, value: str, direction: int = 0, fallback: tuple[str, ...] = ()) -> tuple[str, ...]:
        if not self.input_profile_enabled.get():
            return fallback
        param = self._input_parameter(value)
        aliases: list[str] = []
        if param == "@GENERIC.MOVE_X":
            aliases.extend(ACTION_KEY_ALIASES["@GENERIC.MOVE_X_NEG" if direction < 0 else "@GENERIC.MOVE_X_POS"] if direction else ("a", "left", "d", "right"))
        elif param == "@GENERIC.MOVE_Y":
            aliases.extend(ACTION_KEY_ALIASES["@GENERIC.MOVE_Y_NEG" if direction < 0 else "@GENERIC.MOVE_Y_POS"] if direction else ("s", "down", "w", "up"))
        elif param in ACTION_KEY_ALIASES:
            aliases.extend(ACTION_KEY_ALIASES[param])
        aliases.extend(fallback)
        # Space remains the manual simulator handbrake even when the game profile maps handbrake to MOVE_Y.
        if value == "Handbrake":
            aliases.append("space")
        return tuple(dict.fromkeys(a.lower() for a in aliases if a))

    def _profile_action_pressed(self, value: str, *fallback: str) -> bool:
        return self._is_pressed(*self._input_aliases_for(value, fallback=tuple(fallback)))

    def _profile_axis_value(self, value: str) -> float:
        neg = self._is_pressed(*self._input_aliases_for(value, direction=-1))
        pos = self._is_pressed(*self._input_aliases_for(value, direction=1))
        return (-1.0 if neg else 0.0) + (1.0 if pos else 0.0)

    def _input_control_help_text(self) -> str:
        if not self.input_map:
            return "Click the 3D view first. W/Up throttle, S/Down brake/reverse, A/D or arrows steer, Space handbrake, R reset, C camera, mouse wheel zoom, mouse aims."
        return (
            "Click the 3D view first. input_car.xml maps DigGas=@HORSE.SPUR, "
            "DigBrake=@GENERIC.BRAKE, Steer=@GENERIC.MOVE_X, Handbrake=@GENERIC.MOVE_Y. "
            "Preview aliases: W/Up gas, S/Down brake/reverse, A/D steer, Space handbrake, LMB fires missiles, R reset, C camera."
        )

    def _input_profile_summary(self) -> str:
        if not self.input_map:
            return f"Input profile: {self.input_profile_name}"
        parts = []
        for value in ("DigGas", "DigBrake", "Steer", "Handbrake", "Exit", "Horn"):
            if value in self.input_map:
                parts.append(f"{value}={self._input_parameter(value)}")
        return f"Input profile: {self.input_profile_name} • " + " • ".join(parts)



    def _maybe_start_audio(self) -> None:
        self._on_audio_changed()

    def _on_audio_changed(self) -> None:
        if not hasattr(self, "sound"):
            return
        self.sound.set_volumes(self.master_volume.get(), self.sfx_volume.get(), self.music_volume.get())
        if self.audio_enabled.get() and self.music_enabled.get():
            self.sound.start_music()
        else:
            self.sound.stop_music()

    def _play_sfx(self, name: str, volume: float = 1.0) -> None:
        if hasattr(self, "sound") and self.audio_enabled.get():
            self.sound.play(name, volume)

    def randomize_world_seed(self) -> None:
        self.world_seed_var.set(random.randint(10000, 999999))
        self.randomize_desert_arena(draw=False)
        self._play_sfx("button", 0.7)
        self._draw_preview()

    def _change_rival_count(self, delta: int) -> None:
        self.rival_count_var.set(max(0, min(3, int(self.rival_count_var.get()) + delta)))
        self.randomize_desert_arena()

    def randomize_desert_arena(self, draw: bool = True) -> None:
        seed = int(self.arena_seed_var.get() or 0)
        if seed <= 0:
            seed = random.randint(10000, 999999)
            self.arena_seed_var.set(seed)
        rng = random.Random(seed)
        self.sim_rivals = []
        count = int(max(0, min(3, self.rival_count_var.get()))) if hasattr(self, "rival_count_var") else 3
        for i in range(count):
            angle = (math.tau * i / max(count, 1)) + rng.uniform(-0.22, 0.22)
            radius = rng.uniform(24.0, 46.0)
            label = "Truck01" if rng.random() < 0.38 else "Car01"
            hp_mult = rng.uniform(0.72, 1.42)
            mass_mult = rng.uniform(0.82, 1.48)
            grip_mult = rng.uniform(0.72, 1.35)
            steer_mult = rng.uniform(0.72, 1.25)
            top_mult = rng.uniform(0.78, 1.32)
            palette = rng.choice(["rust", "blue", "bone", "black", "green", "red", "ochre"])
            self.sim_rivals.append({
                "x": math.sin(angle) * radius,
                "z": math.cos(angle) * radius,
                "heading": angle + math.pi + rng.uniform(-0.5, 0.5),
                "speed": rng.uniform(5.0, 16.0) * top_mult,
                "phase": rng.uniform(0, math.tau),
                "label": label,
                "hp_mult": hp_mult,
                "mass_mult": mass_mult,
                "grip_mult": grip_mult,
                "steer_mult": steer_mult,
                "top_mult": top_mult,
                "palette": palette,
                "health": 4,
                "max_health": 4,
                "death_timer": 0.0,
                "respawn_timer": 0.0,
                "fade": 1.0,
                "fire_cooldown": rng.uniform(0.6, 2.8),
                "target": "player",
                "name": f"{label}-{i+1}",
            })
        self.arena_props = []
        for i in range(60):
            angle = rng.uniform(0, math.tau)
            radius = rng.uniform(10.0, self.arena_boundary * 0.98)
            kind = rng.choice(["rock", "cactus", "scrub", "dune", "marker"])
            self.arena_props.append({
                "x": math.sin(angle) * radius,
                "z": math.cos(angle) * radius,
                "kind": kind,
                "size": rng.uniform(0.7, 3.4),
                "rot": rng.uniform(0, math.tau),
            })
        if draw and hasattr(self, "preview_canvas"):
            self._draw_preview()
            self._update_preview_metrics()
        self.status.set(f"Randomized desert arena seed {seed} with {count} rival vehicles.")


    def _update_rivals(self, dt: float) -> None:
        if not getattr(self, "desert_arena_enabled", None) or not self.desert_arena_enabled.get():
            return
        if not getattr(self, "sim_rivals", None):
            self.randomize_desert_arena(draw=False)
        for idx, r in enumerate(self.sim_rivals):
            if r.get("health", 1) <= 0:
                r["death_timer"] = r.get("death_timer", 0.0) + dt
                r["respawn_timer"] = r.get("respawn_timer", 1.8) - dt
                r["fade"] = max(0.0, 1.0 - r.get("death_timer", 0.0) / 1.25)
                if r.get("respawn_timer", 0.0) <= 0.0:
                    self._respawn_rival(r, idx)
                continue

            # Pick a target. Rivals usually target the player, but sometimes switch to
            # another live rival so the arena feels active even when the player watches.
            candidates = [("player", self.sim_x, self.sim_z, 0.0)]
            for j, other in enumerate(self.sim_rivals):
                if j != idx and other.get("health", 1) > 0:
                    candidates.append((other.get("name", f"rival{j}"), other["x"], other["z"], other.get("phase", 0.0)))
            rng_bias = math.sin(self.preview_phase * 0.37 + r.get("phase", 0.0))
            if rng_bias > 0.35 and len(candidates) > 1:
                target = min(candidates[1:], key=lambda t: (t[1]-r["x"])**2 + (t[2]-r["z"])**2)
            else:
                target = candidates[0]
            tx, tz = target[1], target[2]
            dx = tx - r["x"]
            dz = tz - r["z"]
            dist = math.hypot(dx, dz) or 1.0

            desired = math.atan2(dx, dz) + math.sin(self.preview_phase * 0.9 + r["phase"]) * 0.28
            diff = (desired - r["heading"] + math.pi) % (math.tau) - math.pi
            steer = max(-1.0, min(1.0, diff * 1.45))
            r["heading"] += steer * dt * (1.45 + 1.05 * r.get("steer_mult", 1.0))
            target_speed = 18.0 + 15.0 * r.get("top_mult", 1.0)
            if dist > 60:
                target_speed += 8.0
            elif dist < 13:
                target_speed *= 0.42
            r["speed"] += (target_speed - r["speed"]) * dt * 1.05
            terrain = TERRAIN_MODES.get(self.terrain_mode.get(), TERRAIN_MODES["Desert Arena"])
            r["speed"] *= max(0.86, 1.0 - float(terrain.get("rough", 0.2)) * 0.016)
            unit_scale = 0.46
            r["x"] += math.sin(r["heading"]) * r["speed"] * unit_scale * dt
            r["z"] += math.cos(r["heading"]) * r["speed"] * unit_scale * dt

            # Fire missiles when mostly facing the target.
            r["fire_cooldown"] = r.get("fire_cooldown", 1.0) - dt
            if r["fire_cooldown"] <= 0.0 and dist < 96 and abs(diff) < 0.55:
                self._spawn_missile(r["x"], self._terrain_height(r["x"], r["z"]) + 1.05, r["z"], r["heading"], owner=r.get("name", f"rival{idx}"), palette=r.get("palette", "rust"))
                r["fire_cooldown"] = 1.0 + 1.8 * ((math.sin(self.preview_phase + r.get("phase",0)) + 1.0) * 0.5)

            edge = math.hypot(r["x"], r["z"])
            if not getattr(self, "limitless_desert_enabled", tk.BooleanVar(value=True)).get() and edge > self.arena_boundary * 0.92:
                r["heading"] = math.atan2(-r["x"], -r["z"]) + math.sin(r["phase"]) * 0.4


    def _respawn_rival(self, r: dict, idx: int = 0) -> None:
        seed = int(self.arena_seed_var.get() or 12345) + idx * 971 + int(self.preview_phase * 10)
        rng = random.Random(seed)
        angle = self.sim_heading + math.pi + rng.uniform(-1.2, 1.2)
        radius = rng.uniform(55.0, 92.0)
        r["x"] = self.sim_x + math.sin(angle) * radius
        r["z"] = self.sim_z + math.cos(angle) * radius
        r["heading"] = math.atan2(self.sim_x - r["x"], self.sim_z - r["z"])
        r["speed"] = rng.uniform(12.0, 24.0)
        r["health"] = r.get("max_health", 4)
        r["death_timer"] = 0.0
        r["respawn_timer"] = 0.0
        r["fade"] = 1.0
        r["fire_cooldown"] = rng.uniform(0.8, 2.2)
        r["palette"] = rng.choice(["rust", "blue", "bone", "black", "green", "red", "ochre"])


    def _check_projectile_hits(self) -> None:
        if not getattr(self, "sim_projectiles", None):
            return
        for p in self.sim_projectiles:
            if p.get("hit"):
                continue
            owner = p.get("owner", "player")
            # Hit rivals.
            for r in getattr(self, "sim_rivals", []):
                if r.get("health", 1) <= 0 or owner == r.get("name"):
                    continue
                radius = 5.8 if p.get("kind") == "missile" else 4.0
                if (p["x"] - r["x"]) ** 2 + (p["z"] - r["z"]) ** 2 < radius:
                    r["health"] -= 2 if p.get("kind") == "missile" else 1
                    p["hit"] = True
                    p["life"] = 0.02
                    self.sim_hits = getattr(self, "sim_hits", 0) + 1
                    self._spawn_explosion(r["x"], self._terrain_height(r["x"], r["z"]) + 0.55, r["z"], big=r.get("health", 0) <= 0)
                    if r.get("health", 0) <= 0:
                        r["death_timer"] = 0.0
                        r["respawn_timer"] = 2.4
                    self._play_sfx("explosion" if p.get("kind") == "missile" else "hit_clang", 0.95)
                    break
            if p.get("hit"):
                continue
            # Rival missiles can hit the player. Keep it playful: a hit shakes/slows the
            # test car instead of ending the session.
            if owner != "player":
                if (p["x"] - self.sim_x) ** 2 + (p["z"] - self.sim_z) ** 2 < 6.2:
                    p["hit"] = True
                    p["life"] = 0.02
                    self.player_health = max(0, getattr(self, "player_health", 5) - 1)
                    self.sim_forward_speed *= 0.55
                    self.sim_lateral_speed += math.sin(p.get("heading", self.sim_heading)) * 9.0
                    self._spawn_explosion(self.sim_x, self._terrain_height(self.sim_x, self.sim_z) + 0.8, self.sim_z, big=False)
                    self._play_sfx("explosion", 0.85)
                    if self.player_health <= 0:
                        self.player_health = 5
                        self.sim_forward_speed = 0.0
                        self.sim_lateral_speed = 0.0

    def _preview_tick(self) -> None:
        sleep, reason = self._renderer_should_sleep() if hasattr(self, "preview_canvas") else (True, "no canvas")
        if sleep:
            self._mark_renderer_background(reason)
            self.after(self._preview_sleep_ms, self._preview_tick)
            return

        now = _dt.datetime.now().timestamp()
        if self._last_preview_time is None:
            dt = 1.0 / 30.0
        else:
            dt = max(1.0 / 60.0, min(0.06, now - self._last_preview_time))
        self._last_preview_time = now
        self.renderer_active_status.set("Renderer: active")
        if hasattr(self, "preview_canvas") and self.preview_running.get():
            self._sim_step(dt)
            self._draw_preview()
            self._update_preview_metrics()
        self.after(self._preview_tick_ms, self._preview_tick)


    def _sim_step(self, dt: float) -> None:
        s = self._preview_snapshot()
        throttle = 1.0 if self._profile_action_pressed("DigGas", "w", "up") else 0.0
        brake_reverse = 1.0 if self._profile_action_pressed("DigBrake", "s", "down") else 0.0
        steer_target = self._profile_axis_value("Steer")
        handbrake = self._profile_action_pressed("Handbrake", "space")
        if (not handbrake and self.input_profile_enabled.get() and self.move_y_handbrake_assist.get()
                and self._input_parameter("Handbrake") == "@GENERIC.MOVE_Y"
                and self._profile_axis_value("Handbrake") < -0.5
                and abs(self.sim_forward_speed) > 10.0):
            handbrake = True

        firing = self.gatlings_enabled.get() and self.gatling_fire_enabled.get() and ("mouse1" in getattr(self, "sim_mouse_buttons", set()))
        self.sim_action_state = []
        if throttle: self.sim_action_state.append("Gas")
        if brake_reverse: self.sim_action_state.append("Brake/Reverse")
        if steer_target < -0.1: self.sim_action_state.append("Steer<")
        elif steer_target > 0.1: self.sim_action_state.append("Steer>")
        if handbrake: self.sim_action_state.append("Handbrake")
        if firing: self.sim_action_state.append("Missile")
        if abs(getattr(self, "sim_aim_offset", 0.0)) > 0.08: self.sim_action_state.append("MouseLook")
        self._update_missile_fire(dt, firing)

        # Faster, less floaty arcade driving. It still derives acceleration/top speed
        # from vehsim, but the preview no longer crawls around like a slow drift map.
        steer_filter = 8.5 / max(0.35, 1.0 + s.get("input_smooth", 0.5) * 0.45)
        self.sim_steer += (steer_target - self.sim_steer) * min(1.0, dt * steer_filter)
        accel_force = s["accel"] * 46.0
        drag_force = (0.006 + s["drag"] * 0.0035) * self.sim_forward_speed * abs(self.sim_forward_speed)
        rolling = 1.2 + s["mass"] / 7200.0

        if throttle:
            self.sim_forward_speed += accel_force * dt
        if brake_reverse:
            if self.sim_forward_speed > s.get("auto_reverse", 2.25):
                self.sim_forward_speed -= (accel_force * 1.55 + 26.0) * dt
            else:
                self.sim_forward_speed -= accel_force * 0.78 * dt
        if not throttle and not brake_reverse:
            if self.sim_forward_speed > 0:
                self.sim_forward_speed = max(0.0, self.sim_forward_speed - rolling * dt)
            elif self.sim_forward_speed < 0:
                self.sim_forward_speed = min(0.0, self.sim_forward_speed + rolling * dt)

        if s.get("terrain_grade", 0.0) > 0 and self.sim_forward_speed > 0:
            self.sim_forward_speed -= (s["terrain_grade"] * (1.5 + abs(self.sim_forward_speed) * 0.06)) * dt
        if s.get("terrain_rough", 0.0) > 0 and abs(self.sim_forward_speed) > 6.0:
            bump = math.sin(self.sim_x * 1.7 + self.sim_z * 0.9 + self.preview_phase * 3.2)
            self.sim_lateral_speed += bump * s["terrain_rough"] * min(0.6, abs(self.sim_forward_speed) / 95.0) * dt * 4.0
            self.sim_forward_speed *= max(0.0, 1.0 - s["terrain_rough"] * 0.010 * dt)

        self.sim_forward_speed -= drag_force * dt
        self.sim_forward_speed = max(-s["top"] * 0.45, min(s["top"] * 1.25, self.sim_forward_speed))

        speed_abs = abs(self.sim_forward_speed)
        steer_strength = s["steering"] * (0.72 + min(1.6, speed_abs / 50.0)) / max(0.45, s["stability"])
        self.sim_heading += self.sim_steer * steer_strength * dt * (0.48 + speed_abs / 34.0)

        drift_gain = s["drift"] * (0.045 + speed_abs / 420.0)
        if handbrake:
            drift_gain += 0.24 + s["drift"] * 0.12
            self.sim_skid_cooldown = getattr(self, "sim_skid_cooldown", 0.0) - dt
            if self.sim_skid_cooldown <= 0.0 and speed_abs > 10.0:
                self._play_sfx("skid_sand", min(0.9, speed_abs / 60.0))
                self.sim_skid_cooldown = 0.28
        self.sim_lateral_speed += self.sim_steer * self.sim_forward_speed * drift_gain * dt
        lateral_damp = max(0.10, s["grip"] * (2.45 if not handbrake else 0.95) / max(0.55, s["stability"]) * (1.0 + s.get("sim_smooth", 0.45) * 0.18))
        self.sim_lateral_speed *= max(0.0, 1.0 - lateral_damp * dt)
        self.sim_lateral_speed = max(-28.0, min(28.0, self.sim_lateral_speed))

        fwd = (math.sin(self.sim_heading), math.cos(self.sim_heading))
        right = (math.cos(self.sim_heading), -math.sin(self.sim_heading))
        unit_scale = 0.46
        self.sim_x += (fwd[0] * self.sim_forward_speed + right[0] * self.sim_lateral_speed) * unit_scale * dt
        self.sim_z += (fwd[1] * self.sim_forward_speed + right[1] * self.sim_lateral_speed) * unit_scale * dt
        self.preview_speed = abs(self.sim_forward_speed)
        self.preview_distance += abs(self.sim_forward_speed) * dt * unit_scale
        self.preview_phase += dt * (1.2 + self.preview_speed / 55.0)
        self.preview_trail.append((self.sim_x, self.sim_z))
        if len(self.preview_trail) > 120:
            self.preview_trail = self.preview_trail[-120:]
        self._update_rivals(dt)
        self._update_projectiles(dt)
        self._update_explosions(dt)
        self._check_projectile_hits()

    def _update_missile_fire(self, dt: float, firing: bool) -> None:
        self.sim_missile_cooldown = max(-0.2, getattr(self, "sim_missile_cooldown", 0.0) - dt)
        if firing and self.sim_missile_cooldown <= 0.0:
            aim = self.sim_heading + getattr(self, "sim_aim_offset", 0.0)
            wx, wy, wz = self._world_from_local((0.0, 1.15, self._vehsim_size()[2] * 0.70))
            self._spawn_missile(wx, wy, wz, aim, owner="player", palette="player")
            self.sim_rounds_fired = getattr(self, "sim_rounds_fired", 0) + 1
            self.sim_missile_cooldown = 0.42

    def _spawn_missile(self, x: float, y: float, z: float, heading: float, owner: str = "player", palette: str = "player") -> None:
        speed = 58.0 if owner == "player" else 44.0
        self._play_sfx("missile_launch", 0.75 if owner == "player" else 0.42)
        self.sim_projectiles.append({
            "kind": "missile",
            "owner": owner,
            "palette": palette,
            "x": x, "y": y, "z": z,
            "vx": math.sin(heading) * speed,
            "vz": math.cos(heading) * speed,
            "heading": heading,
            "life": 2.2,
            "trail": [(x, y, z)],
        })
        if len(self.sim_projectiles) > 80:
            self.sim_projectiles = self.sim_projectiles[-80:]

    def _spawn_explosion(self, x: float, y: float, z: float, big: bool = False) -> None:
        self.sim_explosions.append({"x": x, "y": y, "z": z, "life": 0.75 if big else 0.48, "max": 0.75 if big else 0.48, "big": big})
        if len(self.sim_explosions) > 40:
            self.sim_explosions = self.sim_explosions[-40:]

    def _update_explosions(self, dt: float) -> None:
        live = []
        for e in getattr(self, "sim_explosions", []):
            e["life"] -= dt
            if e["life"] > 0:
                live.append(e)
        self.sim_explosions = live

    def _gatling_mounts_local(self) -> list[tuple[float, float, float]]:
        dims = self._vehsim_dimensions()
        width, height, length = self._vehsim_size()
        mo = dims["model_offset"]
        base_y = 0.30 + mo[1] * 0.10
        belly_h = min(height * 0.28, 1.05)
        y = base_y + belly_h + min(0.75, height * 0.18)
        z = mo[2] + length * 0.16
        side_offset = width * 0.55 + 0.28
        return [(-side_offset, y, z), (side_offset, y, z)]

    def _update_gatling_fire(self, dt: float, firing: bool) -> None:
        self.sim_fire_cooldown = max(-0.25, getattr(self, "sim_fire_cooldown", 0.0) - dt)
        if not firing:
            return
        rate = max(1.0, float(self.gatling_fire_rate.get() if hasattr(self, "gatling_fire_rate") else 9.0))
        interval = 1.0 / rate
        while self.sim_fire_cooldown <= 0.0:
            self._spawn_gatling_rounds()
            self.sim_fire_cooldown += interval

    def _spawn_gatling_rounds(self) -> None:
        speed = max(20.0, float(self.gatling_projectile_speed.get() if hasattr(self, "gatling_projectile_speed") else 95.0))
        self._play_sfx("gatling_burst", 0.55)
        for side, local in zip((-1, 1), self._gatling_mounts_local()):
            muzzle = (local[0], local[1], local[2] + self._vehsim_size()[2] * 0.36)
            wx, wy, wz = self._world_from_local(muzzle)
            self.sim_projectiles.append({
                "x": wx, "y": wy, "z": wz,
                "vx": math.sin(self.sim_heading) * speed * 0.28,
                "vz": math.cos(self.sim_heading) * speed * 0.28,
                "life": 1.15, "side": side,
            })
            self.sim_rounds_fired = getattr(self, "sim_rounds_fired", 0) + 1
        if len(self.sim_projectiles) > 90:
            self.sim_projectiles = self.sim_projectiles[-90:]


    def _update_projectiles(self, dt: float) -> None:
        live = []
        for p in getattr(self, "sim_projectiles", []):
            p["x"] += p["vx"] * dt
            p["z"] += p["vz"] * dt
            ground = self._terrain_height(p["x"], p["z"])
            p["y"] = max(ground + 0.35, p.get("y", ground + 1.0) + math.sin(self.preview_phase * 8.0) * 0.005)
            p["life"] -= dt
            tr = p.setdefault("trail", [])
            tr.append((p["x"], p["y"], p["z"]))
            if len(tr) > 8:
                del tr[:-8]
            if p["life"] > 0 and not p.get("hit"):
                live.append(p)
        self.sim_projectiles = live

    def _vehsim_dimensions(self) -> dict[str, tuple[float, float, float]]:
        tune = self.vehicles[self.current_vehicle.get()]
        def vec(name: str, fallback: tuple[float, float, float]) -> tuple[float, float, float]:
            node = tune.root.find(name)
            if node is None:
                return fallback
            try:
                return (float(node.get("x", fallback[0])), float(node.get("y", fallback[1])), float(node.get("z", fallback[2])))
            except Exception:
                return fallback
        return {
            "size": vec("Size", (2.2, 3.4, 4.3)),
            "inertia": vec("InertiaBox", (2.7, 3.2, 5.3)),
            "model_offset": vec("ModelOffset", (0.0, 0.6, 0.25)),
            "center_of_mass": vec("CenterOfMass", (0.0, 0.33, -0.5)),
        }

    def _vehsim_size(self) -> tuple[float, float, float]:
        dims = self._vehsim_dimensions()["size"]
        width, height, length = dims
        return (max(1.2, width), max(1.0, height), max(2.8, length))

    def _generated_vehicle_mesh(self) -> tuple[list[tuple[float, float, float]], list[tuple[int, int]], list[tuple[list[int], str]]]:
        """Generated fallback based on the tune file dimensions, not a generic box."""
        dims = self._vehsim_dimensions()
        width, height, length = self._vehsim_size()
        inertia = dims["inertia"]
        mo = dims["model_offset"]
        com = dims["center_of_mass"]
        is_truck = self.current_vehicle.get() == "Truck01"
        tune = self.vehicles[self.current_vehicle.get()]
        tire_r = max(0.18, tune.get_float("WheelFront/TireRadius", 0.375))
        tire_w = max(0.06, tune.get_float("WheelFront/TireWidth", 0.10))
        w = width * 0.50
        l = length * 0.50
        base_y = 0.30 + mo[1] * 0.10
        belly_h = min(height * 0.28, 1.05)
        hood_h = min(height * 0.42, 1.45)
        cabin_h = min(height * (0.46 if is_truck else 0.40), 1.55)
        verts: list[tuple[float, float, float]] = []
        edges: list[tuple[int, int]] = []
        faces: list[tuple[list[int], str]] = []
        def add_box(cx, cy, cz, sx, sy, sz, colors=("#566273", "#7f95ad")):
            n=len(verts); x=sx/2; y=sy/2; z=sz/2
            verts.extend([(cx-x,cy-y,cz-z),(cx+x,cy-y,cz-z),(cx+x,cy-y,cz+z),(cx-x,cy-y,cz+z),(cx-x,cy+y,cz-z),(cx+x,cy+y,cz-z),(cx+x,cy+y,cz+z),(cx-x,cy+y,cz+z)])
            edges.extend([(n,n+1),(n+1,n+2),(n+2,n+3),(n+3,n),(n+4,n+5),(n+5,n+6),(n+6,n+7),(n+7,n+4),(n,n+4),(n+1,n+5),(n+2,n+6),(n+3,n+7)])
            side, top = colors
            faces.extend([([n,n+1,n+2,n+3], "#303842"), ([n+4,n+7,n+6,n+5], top), ([n,n+4,n+5,n+1], side), ([n+1,n+5,n+6,n+2], "#4e5c6b"), ([n+2,n+6,n+7,n+3], side), ([n+3,n+7,n+4,n], "#465260")])
            return n
        z_shift = mo[2]
        add_box(mo[0], base_y + belly_h/2, z_shift, width, belly_h, length, ("#566273", "#768da5"))
        hood_len = length * (0.42 if not is_truck else 0.30)
        hood_z = z_shift + length * (0.18 if not is_truck else 0.28)
        add_box(mo[0], base_y + belly_h + hood_h/2, hood_z, width*0.88, hood_h, hood_len, ("#5d6c7d", "#91a9c2"))
        if is_truck:
            cab_z = z_shift - length*0.30
            bed_z = z_shift + length*0.24
            add_box(mo[0], base_y + belly_h + cabin_h/2, cab_z, width*0.82, cabin_h, length*0.30, ("#6b7e93", "#a9c2dc"))
            add_box(mo[0], base_y + belly_h + 0.32, bed_z, width*0.92, 0.42, length*0.42, ("#485562", "#596875"))
        else:
            cab_z = z_shift - length*0.10
            add_box(mo[0], base_y + belly_h + cabin_h/2, cab_z, width*0.72, cabin_h, length*0.40, ("#6b7e93", "#a9c2dc"))
        wheel_x = w + tire_w * 1.8
        for z in (z_shift - l*0.62, z_shift + l*0.62):
            for x in (-wheel_x, wheel_x):
                add_box(x, base_y + tire_r*0.15, z, tire_w*2.8, tire_r*1.8, tire_r*1.35, ("#05080c", "#111820"))
        add_box(com[0], base_y + com[1] + 0.25, z_shift + com[2], 0.18, 0.18, 0.18, ("#d69b29", "#ffcf66"))
        iw, ih, il = max(inertia[0], width), max(inertia[1], height), max(inertia[2], length)
        n=len(verts); x=iw/2; y=ih*0.18; z=il/2; cy=base_y+ih*0.18
        verts.extend([(-x,cy-y,z_shift-z),(x,cy-y,z_shift-z),(x,cy-y,z_shift+z),(-x,cy-y,z_shift+z),(-x,cy+y,z_shift-z),(x,cy+y,z_shift-z),(x,cy+y,z_shift+z),(-x,cy+y,z_shift+z)])
        edges.extend([(n,n+1),(n+1,n+2),(n+2,n+3),(n+3,n),(n+4,n+5),(n+5,n+6),(n+6,n+7),(n+7,n+4),(n,n+4),(n+1,n+5),(n+2,n+6),(n+3,n+7)])
        return verts, edges, faces

    def _try_load_default_obj(self):
        # The visible final pass no longer looks for shipped model-source folders.
        # The hidden legacy preview, if re-enabled by a developer, always starts
        # with the generated vehsim body unless a user manually loads a mesh.
        self.sim_mesh_source = "generated vehsim body"
        return self._generated_vehicle_mesh()

    def load_preview_obj(self) -> None:
        path = filedialog.askopenfilename(title="Load manual preview mesh", filetypes=[("Preview mesh", "*.obj"), ("All files", "*.*")])
        if not path:
            return
        try:
            mesh = self._load_obj_mesh(Path(path))
            self.sim_mesh_cache[self.current_vehicle.get()] = mesh
            self.sim_mesh_source = Path(path).name
            self.status.set(f"Loaded preview OBJ for {self.current_vehicle.get()}: {path}")
            self._draw_preview()
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not load Preview mesh:\n{exc}")

    def _load_obj_mesh(self, path: Path) -> tuple[list[tuple[float, float, float]], list[tuple[int, int]], list[tuple[list[int], str]]]:
        verts: list[tuple[float, float, float]] = []
        edges: set[tuple[int, int]] = set()
        faces: list[tuple[list[int], str]] = []
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if line.startswith("v "):
                parts = line.split()
                if len(parts) >= 4:
                    verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif line.startswith("f "):
                idxs = []
                for token in line.split()[1:]:
                    item = token.split("/")[0]
                    if not item:
                        continue
                    idx = int(item)
                    if idx < 0:
                        idx = len(verts) + idx + 1
                    idxs.append(idx - 1)
                if len(idxs) >= 3:
                    faces.append((idxs, "#7891ab"))
                    for a, b in zip(idxs, idxs[1:] + idxs[:1]):
                        edges.add(tuple(sorted((a, b))))
        if not verts:
            raise ValueError("OBJ had no vertices")
        minx,maxx = min(v[0] for v in verts), max(v[0] for v in verts)
        miny,maxy = min(v[1] for v in verts), max(v[1] for v in verts)
        minz,maxz = min(v[2] for v in verts), max(v[2] for v in verts)
        sx, sy, sz = max(maxx-minx, 0.001), max(maxy-miny, 0.001), max(maxz-minz, 0.001)
        target_w, target_h, target_l = self._vehsim_size()
        scale = min(target_w / sx, max(target_h, 1.0) / sy, target_l / sz)
        cx, cy, cz = (minx+maxx)/2, miny, (minz+maxz)/2
        verts = [((x-cx)*scale, (y-cy)*scale+0.45, (z-cz)*scale) for x,y,z in verts]
        return verts, sorted(edges), faces[:300]

    def _world_from_local(self, point: tuple[float, float, float]) -> tuple[float, float, float]:
        lx, ly, lz = point
        ca, sa = math.cos(self.sim_heading), math.sin(self.sim_heading)
        wx = self.sim_x + lx * ca + lz * sa
        wz = self.sim_z - lx * sa + lz * ca
        return (wx, ly + self._terrain_height(wx, wz), wz)


    def _projector(self, w: int, h: int):
        aim_heading = self.sim_heading + getattr(self, "sim_aim_offset", 0.0) * 0.55
        fwd = (math.sin(aim_heading), 0.0, math.cos(aim_heading))
        base_ground = self._terrain_height(self.sim_x, self.sim_z)
        look_ahead = 28.0
        target = (
            self.sim_x + fwd[0] * look_ahead,
            base_ground + 0.95 + getattr(self, "sim_aim_pitch", 0.0),
            self.sim_z + fwd[2] * look_ahead,
        )
        if getattr(self, "sim_camera_mode", tk.StringVar(value="chase")).get() == "orbit":
            yaw = self.preview_phase * 0.18
            cam_x = self.sim_x - math.sin(yaw) * self.sim_camera_distance
            cam_z = self.sim_z - math.cos(yaw) * self.sim_camera_distance
            cam_y = self._terrain_height(cam_x, cam_z) + self.sim_camera_height + 0.8
        else:
            # Lower over-the-shoulder camera: far enough to see the car, low enough that
            # the player does not look like they are floating above the arena.
            car_fwd = (math.sin(self.sim_heading), 0.0, math.cos(self.sim_heading))
            cam_x = self.sim_x - car_fwd[0] * self.sim_camera_distance
            cam_z = self.sim_z - car_fwd[2] * self.sim_camera_distance
            cam_y = self._terrain_height(cam_x, cam_z) + self.sim_camera_height
        cam = (cam_x, cam_y, cam_z)
        def norm(v):
            mag = math.sqrt(sum(a*a for a in v)) or 1.0
            return tuple(a/mag for a in v)
        forward = norm((target[0]-cam[0], target[1]-cam[1], target[2]-cam[2]))
        world_up = (0.0, 1.0, 0.0)
        right = norm((forward[2]*world_up[1]-forward[1]*world_up[2], forward[0]*world_up[2]-forward[2]*world_up[0], forward[1]*world_up[0]-forward[0]*world_up[1]))
        up = (forward[1]*right[2]-forward[2]*right[1], forward[2]*right[0]-forward[0]*right[2], forward[0]*right[1]-forward[1]*right[0])
        focal = min(w, h) * 0.98
        horizon_y = h * 0.59
        def project(p):
            vx, vy, vz = p[0]-cam[0], p[1]-cam[1], p[2]-cam[2]
            cx = vx*right[0] + vy*right[1] + vz*right[2]
            cy = vx*up[0] + vy*up[1] + vz*up[2]
            cz = vx*forward[0] + vy*forward[1] + vz*forward[2]
            if cz <= 0.55:
                return None
            scale = focal / cz
            sx = w/2 + cx*scale
            sy = horizon_y - cy*scale
            if sx < -w*3 or sx > w*4 or sy < -h*3 or sy > h*4:
                return None
            return (sx, sy, cz)
        return project

    def _draw_gatling_overlay(self, c: tk.Canvas, project) -> None:
        if not hasattr(self, "gatlings_enabled") or not self.gatlings_enabled.get():
            return
        firing = "mouse1" in getattr(self, "sim_mouse_buttons", set()) and self.gatling_fire_enabled.get()
        length = self._vehsim_size()[2]
        for local in self._gatling_mounts_local():
            start = self._world_from_local(local)
            end = self._world_from_local((local[0], local[1] + 0.02, local[2] + length * 0.36))
            base = project(start); tip = project(end)
            if base and tip:
                c.create_line(base[0], base[1], tip[0], tip[1], fill="#ffd166" if firing else "#b9c4d0", width=4)
                c.create_line(base[0], base[1]+3, tip[0], tip[1]+3, fill="#6e7b88", width=2)
                r = 4 if firing else 2
                c.create_oval(tip[0]-r, tip[1]-r, tip[0]+r, tip[1]+r, fill="#ffef9a" if firing else "#d7dee8", outline="")

    def _draw_pause_overlay(self, c: tk.Canvas, w: int, h: int) -> None:
        if not getattr(self, "pause_overlay_enabled", tk.BooleanVar(value=False)).get():
            return
        x0, y0 = w - 315, 74
        x1, y1 = w - 18, 285
        c.create_rectangle(x0+4, y0+4, x1+4, y1+4, fill="#120808", outline="")
        c.create_rectangle(x0, y0, x1, y1, fill="#211216", outline="#d36a32", width=2)
        c.create_text(x0+16, y0+14, anchor="nw", fill="#ffd6a3", font=("Segoe UI", 12, "bold"), text="PAUSE / AUDIO")
        lines = [
            f"SFX: {'on' if self.audio_enabled.get() else 'off'}    Music: {'on' if self.music_enabled.get() else 'off'}",
            f"Master {self.master_volume.get():.2f}  SFX {self.sfx_volume.get():.2f}  Music {self.music_volume.get():.2f}",
            f"Audio engine: {getattr(getattr(self, 'sound', None), 'status', 'off')}",
            "P toggle overlay • C camera • R reset",
            "Mouse aims • LMB missiles • Space handbrake",
            "Drive outward: terrain gets rougher and more varied.",
        ]
        yy = y0 + 48
        for line in lines:
            c.create_text(x0+16, yy, anchor="nw", fill="#e7c7a1", font=("Segoe UI", 9), text=line)
            yy += 22
        # Simple volume bars.
        for idx, (label, val) in enumerate((("MASTER", self.master_volume.get()), ("SFX", self.sfx_volume.get()), ("MUSIC", self.music_volume.get()))):
            by = y1 - 62 + idx * 16
            c.create_text(x0+16, by-1, anchor="w", fill="#9aa6b2", font=("Segoe UI", 7), text=label)
            c.create_rectangle(x0+76, by-5, x1-18, by+5, fill="#321a16", outline="#71402a")
            c.create_rectangle(x0+76, by-5, x0+76 + (x1-94-x0) * max(0.0, min(1.0, val)), by+5, fill="#d36a32", outline="")


    def _draw_projectiles(self, c: tk.Canvas, project) -> None:
        for p in getattr(self, "sim_projectiles", []):
            trail = p.get("trail", [])
            last = None
            for idx, tp in enumerate(trail):
                pp = project(tp)
                if pp and last:
                    color = "#ff9d2e" if p.get("owner") == "player" else "#ff4d3d"
                    c.create_line(last[0], last[1], pp[0], pp[1], fill=color, width=max(1, idx // 2 + 1))
                last = pp
            head = project((p["x"], p.get("y", 1.0), p["z"]))
            if head:
                color = "#fff0a6" if p.get("owner") == "player" else "#ff7a6d"
                c.create_oval(head[0]-4, head[1]-4, head[0]+4, head[1]+4, fill=color, outline="#ffffff")

    def _draw_explosions(self, c: tk.Canvas, project) -> None:
        for e in getattr(self, "sim_explosions", []):
            p = project((e["x"], e["y"], e["z"]))
            if not p:
                continue
            t = 1.0 - max(0.0, e["life"]) / max(0.01, e.get("max", 0.5))
            base = (24 if e.get("big") else 15) * max(0.35, 180 / max(70, p[2]))
            r = base * (0.45 + t * 1.8)
            c.create_oval(p[0]-r, p[1]-r*0.72, p[0]+r, p[1]+r*0.72, fill="#ff7a22", outline="#ffd36d", width=2)
            c.create_oval(p[0]-r*0.45, p[1]-r*0.30, p[0]+r*0.45, p[1]+r*0.30, fill="#fff0a6", outline="")

    def _local_to_world_for(self, point: tuple[float, float, float], x0: float, z0: float, heading: float) -> tuple[float, float, float]:
        lx, ly, lz = point
        ca, sa = math.cos(heading), math.sin(heading)
        wx = x0 + lx * ca + lz * sa
        wz = z0 - lx * sa + lz * ca
        return (wx, ly + self._terrain_height(wx, wz), wz)

    def _palette_colors(self, name: str) -> tuple[str, str, str, str]:
        palettes = {
            "rust": ("#6d3921", "#a8652e", "#1d1410", "#e4b064"),
            "blue": ("#334d63", "#6f92ad", "#101820", "#b4d6ee"),
            "bone": ("#756b55", "#c0aa7a", "#211c15", "#f0d78d"),
            "black": ("#202329", "#4c5662", "#050608", "#9aa6b2"),
            "green": ("#304b34", "#6f8e56", "#0e1710", "#b9d98a"),
            "red": ("#65302c", "#ad5d4e", "#1e0f0d", "#f2a377"),
            "ochre": ("#77521d", "#c58b31", "#20160a", "#ffd06a"),
        }
        return palettes.get(name, palettes["rust"])

    def _draw_box_instance(self, c: tk.Canvas, project, x0: float, z0: float, heading: float, cx: float, cy: float, cz: float, sx: float, sy: float, sz: float, colors: tuple[str, str, str, str]) -> None:
        nverts = []
        x=sx/2; y=sy/2; z=sz/2
        for p in [(cx-x,cy-y,cz-z),(cx+x,cy-y,cz-z),(cx+x,cy-y,cz+z),(cx-x,cy-y,cz+z),(cx-x,cy+y,cz-z),(cx+x,cy+y,cz-z),(cx+x,cy+y,cz+z),(cx-x,cy+y,cz+z)]:
            nverts.append(project(self._local_to_world_for(p, x0, z0, heading)))
        face_defs = [([0,1,2,3], colors[2]), ([4,7,6,5], colors[1]), ([0,4,5,1], colors[0]), ([1,5,6,2], colors[0]), ([2,6,7,3], colors[0]), ([3,7,4,0], colors[0])]
        draw=[]
        for idxs, col in face_defs:
            if any(nverts[i] is None for i in idxs):
                continue
            pts=[]; deps=[]
            for i in idxs:
                pts.extend([nverts[i][0], nverts[i][1]]); deps.append(nverts[i][2])
            draw.append((sum(deps)/len(deps), pts, col))
        for _, pts, col in sorted(draw, reverse=True):
            c.create_polygon(*pts, fill=col, outline="#efe2c2", width=1)

    def _draw_simple_vehicle_instance(self, c: tk.Canvas, project, x0: float, z0: float, heading: float, label: str, palette: str, scale: float = 1.0, dead: bool = False) -> None:
        body, top, tire, accent = self._palette_colors(palette)
        if dead:
            body, top, accent = "#1b1511", "#38291c", "#ff6b35"
        is_truck = label == "Truck01"
        width = (2.25 if not is_truck else 2.55) * scale
        length = (4.45 if not is_truck else 5.65) * scale
        height = (1.35 if not is_truck else 1.65) * scale
        base_y = 0.28
        sh = project((x0, self._terrain_height(x0, z0) + 0.035, z0))
        if sh:
            sr = max(5, int(34 * max(0.35, 130 / max(70, sh[2])) * scale))
            c.create_oval(sh[0]-sr, sh[1]-sr*0.32, sh[0]+sr, sh[1]+sr*0.32, fill="#2a160e", outline="")
        self._draw_box_instance(c, project, x0, z0, heading, 0, base_y+0.32, 0, width, 0.62, length, (body, top, tire, accent))
        cab_z = -length*0.10 if not is_truck else -length*0.26
        self._draw_box_instance(c, project, x0, z0, heading, 0, base_y+0.88, cab_z, width*0.68, height*0.62, length*(0.38 if not is_truck else 0.30), (body, "#9fb3c7", tire, accent))
        if is_truck:
            self._draw_box_instance(c, project, x0, z0, heading, 0, base_y+0.74, length*0.22, width*0.92, 0.34, length*0.38, (body, "#7d6b4b", tire, accent))
        for wx in (-width*0.58, width*0.58):
            for wz in (-length*0.34, length*0.34):
                self._draw_box_instance(c, project, x0, z0, heading, wx, base_y+0.05, wz, 0.34*scale, 0.44*scale, 0.58*scale, (tire, tire, tire, accent))
        for lx in (-width*0.22, width*0.22):
            p = project(self._local_to_world_for((lx, base_y+0.78, length*0.53), x0, z0, heading))
            if p:
                c.create_oval(p[0]-3, p[1]-3, p[0]+3, p[1]+3, fill=accent, outline="")

    def _world_rng_float(self, ix: int, iz: int, salt: int = 0) -> float:
        seed = int(getattr(self, "world_seed_var", tk.IntVar(value=12345)).get() or 12345)
        n = (ix * 374761393 + iz * 668265263 + salt * 1442695041 + seed * 1013904223) & 0xFFFFFFFF
        n ^= (n >> 13)
        n = (n * 1274126177) & 0xFFFFFFFF
        return (n & 0xFFFFFF) / float(0xFFFFFF)

    def _terrain_height(self, x: float, z: float) -> float:
        if not getattr(self, "limitless_desert_enabled", tk.BooleanVar(value=True)).get():
            return 0.0
        seed = int(getattr(self, "world_seed_var", tk.IntVar(value=12345)).get() or 12345)
        d = math.hypot(x, z)
        grow = min(1.0, d / 480.0)
        # Layered desert formation: small ripples near spawn, broader dunes/ridges as
        # distance increases. It remains deterministic for a given world seed.
        ridge = math.sin((x * 0.026 + z * 0.019) + seed * 0.0011) * 0.55
        cross = math.cos((x * 0.041 - z * 0.033) - seed * 0.0009) * 0.34
        ripple = math.sin((x + seed * 0.013) * 0.13) * math.cos((z - seed * 0.009) * 0.10) * 0.18
        detail = math.sin((x * 0.17 + z * 0.11) + seed * 0.003) * 0.06
        return (ridge + cross + ripple + detail) * (0.22 + grow * 2.15)

    def _draw_red_sky(self, c: tk.Canvas, w: int, h: int) -> None:
        # Clean red sky only. No painted mountain/texture backdrop: the world shape now
        # comes from projected terrain so the arena reads as 3D instead of a wallpaper.
        horizon = int(h * 0.48)
        for y in range(0, horizon + 8, 4):
            t = y / max(1, horizon)
            r = int(96 + 78 * (1.0 - t))
            g = int(24 + 22 * (1.0 - t))
            b = int(25 + 25 * t)
            c.create_rectangle(0, y, w, y + 4, fill=f"#{r:02x}{g:02x}{b:02x}", outline="")
        # Faint heat glow near the horizon; still just sky, not a background texture.
        for i in range(10):
            yy = horizon - 28 + i * 5
            shade = 110 + i * 9
            c.create_line(0, yy, w, yy, fill=f"#{shade:02x}{max(42, shade//3):02x}2d")

    def _iter_procedural_desert_props(self):
        base_cx = math.floor(getattr(self, "sim_x", 0.0) / 12.0)
        base_cz = math.floor(getattr(self, "sim_z", 0.0) / 12.0)
        quality = getattr(self, "terrain_quality_var", tk.StringVar(value="Balanced")).get()
        radius = 6 if quality == "Fast" else (8 if quality == "Balanced" else 9)
        for ix in range(base_cx - radius, base_cx + radius + 1):
            for iz in range(base_cz - radius, base_cz + radius + 1):
                chance = self._world_rng_float(ix, iz, 1)
                if chance < 0.34:
                    continue
                ox = (self._world_rng_float(ix, iz, 2) - 0.5) * 10.0
                oz = (self._world_rng_float(ix, iz, 3) - 0.5) * 10.0
                x = ix * 12.0 + ox
                z = iz * 12.0 + oz
                dist = math.hypot(x, z)
                rough = min(1.0, dist / 520.0)
                roll = self._world_rng_float(ix, iz, 4)
                if roll > 0.86:
                    kind = "cactus"
                elif roll > 0.68:
                    kind = "dune"
                elif roll > 0.47:
                    kind = "rock"
                else:
                    kind = "scrub"
                size = 0.7 + self._world_rng_float(ix, iz, 5) * (1.3 + rough * 2.0)
                yield {"x": x, "z": z, "kind": kind, "size": size, "height": self._terrain_height(x, z)}

    def _draw_desert_prop(self, c: tk.Canvas, project, prop: dict) -> None:
        p = project((prop["x"], prop.get("height", 0.0) + 0.06, prop["z"]))
        if not p:
            return
        size = prop.get("size", 1.0) * max(0.45, 260 / max(p[2], 80))
        kind = prop.get("kind", "rock")
        if kind == "cactus":
            c.create_line(p[0], p[1], p[0], p[1]-size*4.8, fill="#345b33", width=max(1, int(size)))
            c.create_line(p[0], p[1]-size*2.2, p[0]-size*1.25, p[1]-size*3.0, fill="#345b33", width=max(1, int(size)))
            c.create_line(p[0], p[1]-size*2.8, p[0]+size*1.05, p[1]-size*3.45, fill="#345b33", width=max(1, int(size)))
        elif kind == "dune":
            c.create_oval(p[0]-size*5.4, p[1]-size*1.15, p[0]+size*5.4, p[1]+size*1.1, fill="#a76424", outline="#dc9b4d")
            c.create_arc(p[0]-size*4.5, p[1]-size*0.85, p[0]+size*4.5, p[1]+size*0.85, start=0, extent=180, outline="#f0b15c")
        elif kind == "scrub":
            c.create_oval(p[0]-size*1.8, p[1]-size, p[0]+size*1.8, p[1]+size, fill="#61713f", outline="")
        else:
            c.create_oval(p[0]-size*1.9, p[1]-size*1.1, p[0]+size*2.1, p[1]+size*1.2, fill="#735741", outline="#b69060")

    def _desert_ground_color(self, height: float, dist: float, noise: float = 0.0) -> str:
        # Dirt/desert palette: valleys are darker packed dirt, raised dunes are warmer.
        rough = min(1.0, dist / 520.0)
        t = max(0.0, min(1.0, 0.45 + height * 0.30 + noise * 0.22 + rough * 0.12))
        r = int(92 + 78 * t)
        g = int(50 + 45 * t)
        b = int(20 + 15 * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _draw_visible_terrain_surface(self, c: tk.Canvas, project, w: int, h: int) -> None:
        # Projected mesh in the direction the vehicle is facing. This replaces the old
        # flat screen-space ground texture and gives a real forward desert floor.
        fwd = (math.sin(self.sim_heading), math.cos(self.sim_heading))
        right = (math.cos(self.sim_heading), -math.sin(self.sim_heading))
        quality = getattr(self, "terrain_quality_var", tk.StringVar(value="Balanced")).get()
        if quality == "Fast":
            step, ix_min, ix_max, iz_min, iz_max, ridge_aheads = 12.0, -6, 6, -1, 15, (88, 140)
        elif quality == "High":
            step, ix_min, ix_max, iz_min, iz_max, ridge_aheads = 7.5, -10, 10, -2, 24, (72, 112, 152)
        else:
            step, ix_min, ix_max, iz_min, iz_max, ridge_aheads = 9.5, -8, 8, -2, 19, (84, 132)
        tiles = []
        # Include a small slice behind the player and a long slice ahead for combat view.
        for iz in range(iz_min, iz_max):
            for ix in range(ix_min, ix_max + 1):
                corners = []
                heights = []
                depths = []
                ok = True
                for du, dv in ((0, 0), (1, 0), (1, 1), (0, 1)):
                    side = (ix + du) * step
                    ahead = (iz + dv) * step
                    wx = self.sim_x + right[0] * side + fwd[0] * ahead
                    wz = self.sim_z + right[1] * side + fwd[1] * ahead
                    wy = self._terrain_height(wx, wz)
                    p = project((wx, wy, wz))
                    if not p:
                        ok = False
                        break
                    corners.extend([p[0], p[1]])
                    heights.append(wy)
                    depths.append(p[2])
                if not ok:
                    continue
                cx = self.sim_x + right[0] * ((ix + 0.5) * step) + fwd[0] * ((iz + 0.5) * step)
                cz = self.sim_z + right[1] * ((ix + 0.5) * step) + fwd[1] * ((iz + 0.5) * step)
                noise = self._world_rng_float(int(cx // 10), int(cz // 10), 31) - 0.5
                fill = self._desert_ground_color(sum(heights) / len(heights), math.hypot(cx, cz), noise)
                outline = "#6c411f" if (ix + iz) % 3 else "#7f5128"
                tiles.append((sum(depths) / len(depths), corners, fill, outline))
        for _depth, pts, fill, outline in sorted(tiles, reverse=True):
            c.create_polygon(*pts, fill=fill, outline=outline, width=1)

        # Far ridge contours are geometry-based: drawn from terrain height, not a static
        # mountain image, so they keep the limitless-world feel without a 2D backdrop.
        for ahead in ridge_aheads:
            last = None
            for ix in range(-13, 14):
                side = ix * step
                wx = self.sim_x + right[0] * side + fwd[0] * ahead
                wz = self.sim_z + right[1] * side + fwd[1] * ahead
                p = project((wx, self._terrain_height(wx, wz) + 0.08, wz))
                if p and last:
                    c.create_line(last[0], last[1], p[0], p[1], fill="#d08a41", width=2)
                last = p

    def _draw_desert_arena_world(self, c: tk.Canvas, project, w: int, h: int, s: dict) -> None:
        self._draw_red_sky(c, w, h)
        self._draw_visible_terrain_surface(c, project, w, h)
        if not getattr(self, "limitless_desert_enabled", tk.BooleanVar(value=True)).get():
            ring_pts = []
            for k in range(96):
                a = math.tau * k / 96
                rx = math.sin(a)*self.arena_boundary
                rz = math.cos(a)*self.arena_boundary
                p = project((rx, self._terrain_height(rx, rz)+0.08, rz))
                if p:
                    ring_pts.append((p[0], p[1]))
            for a,b in zip(ring_pts, ring_pts[1:] + ring_pts[:1]):
                c.create_line(a[0], a[1], b[0], b[1], fill="#b45e22", width=2)
            props = getattr(self, "arena_props", [])[:140]
        else:
            props = list(self._iter_procedural_desert_props())
        props.sort(key=lambda prop: (prop["x"]-self.sim_x)**2 + (prop["z"]-self.sim_z)**2, reverse=True)
        prop_limit = 120 if getattr(self, "terrain_quality_var", tk.StringVar(value="Balanced")).get() == "Fast" else 180
        for prop in props[:prop_limit]:
            self._draw_desert_prop(c, project, prop)


    def _draw_rivals(self, c: tk.Canvas, project) -> None:
        if not getattr(self, "desert_arena_enabled", None) or not self.desert_arena_enabled.get():
            return
        for r in sorted(getattr(self, "sim_rivals", []), key=lambda rr: (rr["x"]-self.sim_x)**2 + (rr["z"]-self.sim_z)**2, reverse=True):
            dead = r.get("health", 1) <= 0
            scale = 0.92 * r.get("mass_mult", 1.0) ** 0.12
            self._draw_simple_vehicle_instance(c, project, r["x"], r["z"], r["heading"], r.get("label", "Car01"), r.get("palette", "rust"), scale, dead=dead)
            p = project((r["x"], self._terrain_height(r["x"], r["z"]) + 2.3, r["z"]))
            if p:
                if dead:
                    fade = max(0.0, r.get("fade", 0.0))
                    c.create_text(p[0], p[1]-10, fill="#ff9d52", font=("Segoe UI", 8, "bold"), text=f"RESPAWN {max(0.0, r.get('respawn_timer',0.0)):.1f}s")
                else:
                    hp = max(0, int(r.get("health", 0)))
                    tune_line = f"{r.get('name','rival')}  HP {hp}  Gx{r.get('grip_mult',1):.1f}"
                    c.create_text(p[0], p[1]-16, fill="#ffe7ad", font=("Segoe UI", 8, "bold"), text=tune_line)
                    c.create_rectangle(p[0]-22, p[1]-6, p[0]+22, p[1]-2, fill="#24110d", outline="#5f2a20")
                    c.create_rectangle(p[0]-22, p[1]-6, p[0]-22 + 44*(hp/max(1,r.get('max_health',4))), p[1]-2, fill="#ff6b35", outline="")

    def _draw_preview(self) -> None:
        c = self.preview_canvas
        c.delete("all")
        w = max(c.winfo_width(), 760)
        h = max(c.winfo_height(), 430)
        s = self._preview_snapshot()
        terrain = TERRAIN_MODES.get(str(s.get("terrain", "Flat Road")), TERRAIN_MODES["Flat Road"])
        ground_color = terrain.get("color", "#0b0f14")
        accent_color = terrain.get("accent", "#263544")
        project = self._projector(w, h)
        if str(s.get("terrain")) == "Desert Arena":
            self._draw_desert_arena_world(c, project, w, h, s)
        else:
            c.create_rectangle(0, 0, w, h, fill=ground_color, outline="")
        grid_items = []
        desert_view = str(s.get("terrain")) == "Desert Arena"
        span = 58 if desert_view else 42
        step = 8 if desert_view else 4
        base_x = round(self.sim_x / step) * step
        base_z = round(self.sim_z / step) * step
        for gx in range(int(base_x-span), int(base_x+span)+1, step):
            a = project((gx, self._terrain_height(gx, base_z-span), base_z-span)); b = project((gx, self._terrain_height(gx, base_z+span), base_z+span))
            if a and b: grid_items.append((max(a[2], b[2]), (a, b, "#18222d" if gx % 16 else accent_color)))
        for gz in range(int(base_z-span), int(base_z+span)+1, step):
            a = project((base_x-span, self._terrain_height(base_x-span, gz), gz)); b = project((base_x+span, self._terrain_height(base_x+span, gz), gz))
            if a and b: grid_items.append((max(a[2], b[2]), (a, b, "#18222d" if gz % 16 else accent_color)))
        for _, (a,b,color) in sorted(grid_items, reverse=True):
            c.create_line(a[0], a[1], b[0], b[1], fill=color)
        if getattr(self, "draw_guide_track_var", tk.BooleanVar(value=False)).get():
            for offset in (-4, 4):
                a = project((base_x+offset, self._terrain_height(base_x+offset, base_z-span)+0.015, base_z-span)); b = project((base_x+offset, self._terrain_height(base_x+offset, base_z+span)+0.015, base_z+span))
                if a and b: c.create_line(a[0], a[1], b[0], b[1], fill="#354151", width=2)
            for t in range(-36, 37, 8):
                pnt = project((base_x, self._terrain_height(base_x, base_z+t)+0.02, base_z+t))
                if pnt:
                    c.create_oval(pnt[0]-3, pnt[1]-3, pnt[0]+3, pnt[1]+3, fill="#c07c2a", outline="")
        # Draw lightweight terrain obstacles/ripples for rough modes.
        if s.get("terrain_rough", 0.0) > 0.05:
            for i in range(-32, 33, 8):
                for j in range(-28, 29, 14):
                    amp = s.get("terrain_rough", 0.0)
                    px = base_x + i + math.sin(i) * 1.2
                    pz = base_z + j + math.cos(j) * 1.2
                    y = self._terrain_height(px, pz) + 0.04 + amp * 0.20 * (0.5 + 0.5 * math.sin((base_x+i)*0.37 + (base_z+j)*0.21))
                    pnt = project((px, y, pz))
                    if pnt:
                        r = 2 + int(amp * 5)
                        c.create_oval(pnt[0]-r, pnt[1]-r*0.55, pnt[0]+r, pnt[1]+r*0.55, fill=accent_color, outline="")
        for i in range(1, len(self.preview_trail)):
            a0 = self.preview_trail[i-1]; b0 = self.preview_trail[i]
            a = project((a0[0], self._terrain_height(a0[0], a0[1])+0.05, a0[1])); b = project((b0[0], self._terrain_height(b0[0], b0[1])+0.05, b0[1]))
            if a and b:
                shade = 50 + int(i * 150 / max(len(self.preview_trail), 1))
                c.create_line(a[0], a[1], b[0], b[1], fill=f"#{shade//2:02x}{min(190, shade):02x}{min(230, shade+35):02x}", width=2)
        self._draw_rivals(c, project)
        mesh = self.sim_mesh_cache.get(self.current_vehicle.get()) if hasattr(self, "sim_mesh_cache") else None
        if mesh is None:
            mesh = self._try_load_default_obj()
        sh = project((self.sim_x, self._terrain_height(self.sim_x, self.sim_z) + 0.035, self.sim_z))
        if sh:
            sr = max(12, int(58 * max(0.35, 120 / max(70, sh[2]))))
            c.create_oval(sh[0]-sr, sh[1]-sr*0.35, sh[0]+sr, sh[1]+sr*0.35, fill="#241108", outline="")
        verts, edges, faces = mesh
        wverts = [self._world_from_local(v) for v in verts]
        pverts = [project(v) for v in wverts]
        draw_faces = []
        for idxs, color in faces:
            pts = []
            depths = []
            ok = True
            for idx in idxs:
                if idx >= len(pverts) or pverts[idx] is None:
                    ok = False; break
                pts.extend([pverts[idx][0], pverts[idx][1]])
                depths.append(pverts[idx][2])
            if ok and len(pts) >= 6:
                draw_faces.append((sum(depths)/len(depths), pts, color))
        for _depth, pts, color in sorted(draw_faces, reverse=True):
            c.create_polygon(*pts, fill=color, outline="#dfe8f3", width=1)
        for a_idx, b_idx in edges[:600]:
            if a_idx < len(pverts) and b_idx < len(pverts) and pverts[a_idx] and pverts[b_idx]:
                a, b = pverts[a_idx], pverts[b_idx]
                c.create_line(a[0], a[1], b[0], b[1], fill="#f2f6fb", width=1)
        self._draw_gatling_overlay(c, project)
        self._draw_projectiles(c, project)
        self._draw_explosions(c, project)
        nose = self._world_from_local((0, 1.05, self._vehsim_size()[2] * 0.76))
        center = self._world_from_local((0, 1.05, 0))
        pa, pb = project(center), project(nose)
        if pa and pb:
            c.create_line(pa[0], pa[1], pb[0], pb[1], fill="#9fe870", width=3, arrow="last")
        c.create_text(18, 16, anchor="nw", fill="#e7edf5", font=("Segoe UI", 12, "bold"), text=f"{self.current_vehicle.get()} 3D Drive • {self.preview_speed:.1f} mph")
        action_line = ", ".join(getattr(self, "sim_action_state", [])) or "idle"
        c.create_text(18, 40, anchor="nw", fill="#9aa6b2", font=("Segoe UI", 10), text=f"Profile: {getattr(self, 'input_profile_name', 'fallback')} • Actions: {action_line} • Mesh: {getattr(self, 'sim_mesh_source', 'generated')}")
        guide = "guide on" if getattr(self, "draw_guide_track_var", tk.BooleanVar(value=False)).get() else "open world"
        c.create_text(18, 60, anchor="nw", fill="#748292", font=("Segoe UI", 9), text=f"Combat chase • 4 vehicles max • {guide} • Terrain: {s.get('terrain', 'Flat Road')} • WASD drive • Mouse aim/look • LMB missile • Space handbrake")
        tag = "OFF-ROAD STABILITY RISK" if s["drift"] > 0.75 else ("FAST OFF-ROAD BUILD" if s["top"] > 58 else "STABLE OFF-ROAD BUILD")
        c.create_text(w - 18, 16, anchor="ne", fill="#ffd27d" if s["drift"] > 0.9 else "#9fe870" if s["top"] > 75 else "#9aa6b2", font=("Segoe UI", 11, "bold"), text=tag)
        c.create_text(w - 18, 38, anchor="ne", fill="#d6b27c", font=("Segoe UI", 9), text=f"Arena seed {self.arena_seed_var.get()} • world {self.world_seed_var.get()} • rivals {len(getattr(self, 'sim_rivals', []))}")
        c.create_text(18, 82, anchor="nw", fill="#f0b15c", font=("Segoe UI", 9), text=f"Distance {s.get('world_distance',0):.0f}m • progressive roughness {s.get('world_roughness',0):.2f} • audio {getattr(getattr(self, 'sound', None), 'status', 'off')}")
        if str(s.get("terrain")) == "Desert Arena":
            # Simple forward combat crosshair for the Code Red Arcade-style minigame view.
            cx = w / 2 + getattr(self, "sim_aim_offset", 0.0) * w * 0.18
            cy = h * 0.45 + getattr(self, "sim_aim_pitch", 0.0) * h * 0.18
            c.create_line(cx - 18, cy, cx - 5, cy, fill="#ffd06a", width=2)
            c.create_line(cx + 5, cy, cx + 18, cy, fill="#ffd06a", width=2)
            c.create_line(cx, cy - 18, cx, cy - 5, fill="#ffd06a", width=2)
            c.create_line(cx, cy + 5, cx, cy + 18, fill="#ffd06a", width=2)
            c.create_text(cx, cy + 25, fill="#ffb45a", font=("Segoe UI", 8, "bold"), text="CODE RED ARCADE ARENA")
        self._draw_pause_overlay(c, w, h)

    def _collect_patch_payloads(self) -> tuple[dict[str, bytes], list[dict]]:
        modified_files: dict[str, bytes] = {}
        manifest_files: list[dict] = []
        for label, filename in VEHICLE_FILES.items():
            data = self.vehicles[label].to_bytes()
            internal = f"{INTERNAL_BASE}/{filename}"
            modified_files[internal] = data
            manifest_files.append({"vehicle": label, "kind": "vehsim", "internal_path": internal, "filename": filename, "size": len(data), "snapshot": self._all_control_values_for_vehicle(label)})
        for label, filename in VEHICLE_INPUT_FILES.items():
            data = self.vehicle_inputs[label].to_bytes()
            internal = f"{INTERNAL_BASE}/{filename}"
            modified_files[internal] = data
            manifest_files.append({"vehicle": label, "kind": "vehinput", "internal_path": internal, "filename": filename, "size": len(data)})
        return modified_files, manifest_files

    def _write_patch_export_package(self, base: Path, build_full_rpf: bool = False, source_rpf: Path | None = None) -> tuple[Path, str]:
        export_root = base / f"CodeRED_TunePatch_{now_stamp()}"
        vehicle_dir = export_root / "root" / "tune" / "vehicle"
        vehicle_dir.mkdir(parents=True, exist_ok=True)
        modified_files, manifest_files = self._collect_patch_payloads()
        for internal, data in modified_files.items():
            (vehicle_dir / Path(internal).name).write_bytes(data)
        merged_root = export_root / "03_merged_loose_patch"
        for internal, data in modified_files.items():
            dst = merged_root / Path(*internal.split("/"))
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
        # Include the controller/keyboard vehicle input map with every build/export.
        # It is not injected into tune_d11generic.rpf yet because its true game
        # archive path still needs verification, but the file travels with every
        # patch package so test builds keep the intended vehicle controls.
        input_export_status = "not found"
        input_src = self.input_profile_path if hasattr(self, "input_profile_path") else find_input_profile()
        if input_src and Path(input_src).exists():
            for rel in (Path("input_profiles") / DEFAULT_INPUT_PROFILE, Path("build_support") / "vehicle_input" / DEFAULT_INPUT_PROFILE):
                dst = export_root / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(input_src, dst)
                merged_dst = merged_root / rel
                merged_dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(input_src, merged_dst)
            input_export_status = "included"
        include_mods = bool(getattr(getattr(self, "include_selected_mods_var", None), "get", lambda: False)())
        selected_mod_packs = self._copy_selected_mod_packs(export_root, merge_root=merged_root) if include_mods else []
        include_mp = bool(getattr(getattr(self, "include_mp_client_var", None), "get", lambda: False)())
        mp_client_result = self._write_mp_client_bridge(export_root) if include_mp else {"status": "not included"}
        manifest = {
            "app": APP_NAME,
            "version": APP_VERSION,
            "created": _dt.datetime.now().isoformat(timespec="seconds"),
            "active_vehicle": self.current_vehicle.get(),
            "terrain_mode": self.terrain_mode.get() if hasattr(self, "terrain_mode") else "Dirt Trail",
            "warning": "Loose files are safest. Full copied-RPF builder patches a COPY only and verifies re-extraction when zstd is available.",
            "input_profile": {"name": DEFAULT_INPUT_PROFILE, "status": input_export_status, "source": str(input_src) if input_src else ""},
            "files": manifest_files,
            "selected_mod_packs": selected_mod_packs,
            "mp_client_bridge": mp_client_result,
            "merged_loose_patch": str(merged_root),
        }
        full_rpf_result = None
        micro_status = "not attempted"
        try:
            build_micro_rpf6(modified_files, export_root / "tune_d11generic_codered_patch_micro.rpf")
            micro_status = "built"
        except Exception as exc:
            micro_status = f"failed: {exc}"
        if build_full_rpf and source_rpf is not None:
            output_rpf = export_root / "tune_d11generic_codered_full_copy_PATCHED.rpf"
            try:
                full_rpf_result = patch_tune_rpf_copy(source_rpf, modified_files, output_rpf)
            except Exception as exc:
                full_rpf_result = {"status": "failed", "reason": str(exc), "source": str(source_rpf), "output": str(output_rpf)}
        manifest["micro_rpf_status"] = micro_status
        manifest["full_rpf_result"] = full_rpf_result
        (export_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        readme_lines = [
            "Code RED Tune Patch Export",
            "==========================",
            "",
            "Loose patch files are under root/tune/vehicle/.",
            "This export includes both .vehsim and .vehinput control files.",
            "Selected patch presets are expanded/copied into 02_mod_packs and merged into 03_merged_loose_patch.",
            "The MP client bridge/readme is under 04_multiplayer_client when enabled.",
            "",
            "Files included:",
            "- car01x.vehsim",
            "- truck01x.vehsim",
            "- car01x.vehinput",
            "- truck01x.vehinput",
            f"- input_profiles/{DEFAULT_INPUT_PROFILE} (controller/keyboard vehicle action map; carried with build package)",
            "",
            "Testing options:",
            "1. Safest: import the loose files into a copied tune_d11generic.rpf with MagicRDR/Code RED.",
            "2. If the builder succeeded: test tune_d11generic_codered_full_copy_PATCHED.rpf as a full copied replacement after backing up the original.",
            "3. Micro RPF remains experimental and should not replace the stock full RPF.",
            "4. For combined loose testing, start from 03_merged_loose_patch.",
            "",
            "Selected patch presets:",
            *(f"- {pack['name']} ({pack['file_count']} files): {pack['description']}" for pack in selected_mod_packs),
            "" if selected_mod_packs else "- none selected",
            f"MP client bridge: {mp_client_result.get('status', 'unknown') if isinstance(mp_client_result, dict) else 'unknown'}",
            f"Micro RPF status: {micro_status}",
        ]
        if full_rpf_result:
            readme_lines.extend(["", "Full copied-RPF builder result:", json.dumps(full_rpf_result, indent=2)])
            (export_root / "FULL_RPF_PATCH_REPORT.json").write_text(json.dumps(full_rpf_result, indent=2), encoding="utf-8")
        (export_root / "README_TEST.txt").write_text("\n".join(readme_lines), encoding="utf-8")
        full_msg = ""
        if full_rpf_result:
            applied = full_rpf_result.get("applied", 0) if isinstance(full_rpf_result, dict) else 0
            full_msg = f"\nFull copied RPF verified entries: {applied}/4"
            if applied < 4:
                full_msg += "\nCheck FULL_RPF_PATCH_REPORT.json before in-game testing."
        mods_msg = f"\nSelected patch presets: {len(selected_mod_packs)}" if selected_mod_packs else "\nSelected patch presets: 0"
        return export_root, f"Exported patch package:\n{export_root}\nMicro RPF: {micro_status}{mods_msg}{full_msg}"

    def export_patch(self) -> None:
        base = filedialog.askdirectory(title="Choose export folder", initialdir=str(app_dir() / "exports"))
        if not base:
            return
        export_root, msg = self._write_patch_export_package(Path(base), build_full_rpf=False)
        self.status.set(msg.replace("\n", " "))
        messagebox.showinfo(APP_NAME, msg)

    def _stock_payload_file(self, payload_label: str, kind: str) -> Path:
        payload = SPAWN_PAYLOADS[payload_label]
        if kind == "locset":
            return self.stock_dir / payload["locset_file"]
        return self.stock_dir / f"{payload['stem']}.{kind}"

    def _adapt_locset_for_carrier(self, payload_label: str, carrier_key: str) -> bytes:
        carrier = SPAWN_CARRIERS[carrier_key]
        src = self._stock_payload_file(payload_label, "locset")
        text = src.read_text(encoding="utf-8", errors="replace")
        import re
        text = re.sub(r"<Name>.*?</Name>", f"<Name>{carrier['locset_name']}</Name>", text, count=1, flags=re.S)
        return text.encode("utf-8")

    def _collect_spawn_slot_payloads(self) -> tuple[dict[str, bytes], list[dict]]:
        payload_label = self.spawn_payload_var.get()
        carrier_key = self.spawn_carrier_var.get()
        carrier = SPAWN_CARRIERS[carrier_key]
        target_stem = carrier["stem"]
        modified: dict[str, bytes] = {}
        manifest: list[dict] = []
        for kind in SPAWN_SWAP_KINDS:
            src = self._stock_payload_file(payload_label, kind)
            if not src.exists():
                raise FileNotFoundError(f"Missing source payload file: {src}")
            internal = f"{INTERNAL_BASE}/{target_stem}.{kind}"
            payload = src.read_bytes()
            modified[internal] = payload
            manifest.append({
                "target_internal_path": internal,
                "source_payload": src.name,
                "kind": kind,
                "bytes": len(payload),
                "purpose": f"Replace existing {target_stem}.{kind} carrier tune with {payload_label} {kind} payload.",
            })
        if self.spawn_include_locset_var.get() and carrier.get("locset_file"):
            internal = f"{INTERNAL_BASE}/locset/{carrier['locset_file']}"
            payload = self._adapt_locset_for_carrier(payload_label, carrier_key)
            modified[internal] = payload
            manifest.append({
                "target_internal_path": internal,
                "source_payload": SPAWN_PAYLOADS[payload_label]["locset_file"],
                "kind": "locset",
                "bytes": len(payload),
                "purpose": f"Use {payload_label} seat/entry locators while preserving carrier locset lookup name {carrier['locset_name']}.",
            })
        return modified, manifest

    def _write_spawn_slot_export_package(self, base: Path, build_full_rpf: bool = False, source_rpf: Path | None = None) -> tuple[Path, str]:
        payload_label = self.spawn_payload_var.get()
        carrier_key = self.spawn_carrier_var.get()
        carrier = SPAWN_CARRIERS[carrier_key]
        export_root = base / f"CodeRED_SpawnSlotSwap_{payload_label}_via_{carrier_key}_{now_stamp()}"
        modified_files, manifest_files = self._collect_spawn_slot_payloads()
        merged_root = export_root / "03_merged_loose_patch"
        for internal, data in modified_files.items():
            dst = export_root / Path(*internal.split("/"))
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            merged_dst = merged_root / Path(*internal.split("/"))
            merged_dst.parent.mkdir(parents=True, exist_ok=True)
            merged_dst.write_bytes(data)
        input_src = self.input_profile_path if hasattr(self, "input_profile_path") else find_input_profile()
        if input_src and Path(input_src).exists():
            for rel in (Path("input_profiles") / DEFAULT_INPUT_PROFILE, Path("build_support") / "vehicle_input" / DEFAULT_INPUT_PROFILE):
                dst = export_root / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(input_src, dst)
                merged_dst = merged_root / rel
                merged_dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(input_src, merged_dst)
        include_mods = bool(getattr(getattr(self, "include_selected_mods_var", None), "get", lambda: False)())
        selected_mod_packs = self._copy_selected_mod_packs(export_root, merge_root=merged_root) if include_mods else []
        include_mp = bool(getattr(getattr(self, "include_mp_client_var", None), "get", lambda: False)())
        mp_client_result = self._write_mp_client_bridge(export_root) if include_mp else {"status": "not included"}
        micro_status = "not attempted"
        try:
            build_micro_rpf6(modified_files, export_root / "tune_d11generic_spawn_slot_swap_micro.rpf")
            micro_status = "built"
        except Exception as exc:
            micro_status = f"failed: {exc}"
        full_rpf_result = None
        if build_full_rpf and source_rpf is not None:
            output_rpf = export_root / f"tune_d11generic_{payload_label}_via_{carrier_key}_FULL_COPY_PATCHED.rpf"
            try:
                full_rpf_result = patch_tune_rpf_copy(source_rpf, modified_files, output_rpf)
            except Exception as exc:
                full_rpf_result = {"status": "failed", "reason": str(exc), "source": str(source_rpf), "output": str(output_rpf)}
        manifest = {
            "app": APP_NAME,
            "version": APP_VERSION,
            "created": _dt.datetime.now().isoformat(timespec="seconds"),
            "experiment": "spawn_slot_swap",
            "payload": payload_label,
            "carrier": carrier_key,
            "carrier_note": carrier.get("risk", ""),
            "warning": "Experimental. Tune files can make an existing carrier behave/seat like the payload, but visual Car01/Truck01 still needs matching WFT/WTD/model swapping.",
            "model_swap_needed": True,
            "files": manifest_files,
            "selected_mod_packs": selected_mod_packs,
            "mp_client_bridge": mp_client_result,
            "merged_loose_patch": str(merged_root),
            "micro_rpf_status": micro_status,
            "full_rpf_result": full_rpf_result,
        }
        (export_root / "manifest_spawn_slot_swap.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        readme = [
            "Code RED Spawn Slot Swap Patch",
            "================================",
            "",
            f"Payload: {payload_label}",
            f"Carrier: {carrier_key} ({carrier.get('label', carrier_key)})",
            "",
            "Purpose:",
            "Use an existing ambient road/wagon spawn slot as a carrier for mission-only Car01/Truck01 behavior.",
            "This is safer and less random than replacing a train slot, but still experimental.",
            "",
            "What this patch changes:",
        ]
        for item in manifest_files:
            readme.append(f"- {item['target_internal_path']} <- {item['source_payload']}")
        readme.extend([
            "",
            "Important limitations:",
            "- Tune files do not create new spawn points by themselves.",
            "- This relies on the original carrier slot already being spawned by the game.",
            "- Without model/archive swapping, the visual may remain the wagon carrier while behaving more like the payload.",
            "- If the game freezes, remove this patch and test again with locset disabled.",
            "",
            "Test order:",
            "1. Back up original tune_d11generic.rpf.",
            "2. Try loose import into a copied full RPF first.",
            "3. Test wagon02x + Car01 first; then wagonprison01x + Truck01.",
            "4. Only after behavior changes, attempt model WFT/WTD swapping for the same carrier slot.",
            "5. Use 03_merged_loose_patch when testing all selected options together.",
            "",
            "Selected patch presets:",
            *(f"- {pack['name']} ({pack['file_count']} files): {pack['description']}" for pack in selected_mod_packs),
            "" if selected_mod_packs else "- none selected",
            f"MP client bridge: {mp_client_result.get('status', 'unknown') if isinstance(mp_client_result, dict) else 'unknown'}",
            f"Micro RPF status: {micro_status}",
        ])
        if full_rpf_result:
            (export_root / "FULL_RPF_SPAWN_SLOT_REPORT.json").write_text(json.dumps(full_rpf_result, indent=2), encoding="utf-8")
            readme.extend(["", "Full copied-RPF builder result:", json.dumps(full_rpf_result, indent=2)])
        (export_root / "README_SPAWN_SLOT_TEST.txt").write_text("\n".join(readme), encoding="utf-8")
        patched_count = len(modified_files)
        full_msg = ""
        if full_rpf_result:
            applied = full_rpf_result.get("applied", 0) if isinstance(full_rpf_result, dict) else 0
            full_msg = f"\nFull copied RPF verified entries: {applied}/{patched_count}"
        mods_msg = f"\nSelected patch presets: {len(selected_mod_packs)}" if selected_mod_packs else "\nSelected patch presets: 0"
        msg = f"Spawn slot patch exported:\n{export_root}\nPayload {payload_label} -> carrier {carrier_key}\nFiles: {patched_count}\nMicro RPF: {micro_status}{mods_msg}{full_msg}"
        return export_root, msg

    def _build_spawn_slot_tab(self) -> None:
        frame = ttk.Frame(self.nb, padding=12)
        self.nb.add(frame, text="Spawn Swap")
        ttk.Label(frame, text="Spawn Slot Swap Builder", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Experimental route for bringing mission-only Car01/Truck01 into normal play without SC-CL: overwrite an existing wagon/road vehicle tune slot so the game’s existing spawner carries the car/truck behavior. Start with loose export; full copied-RPF patch is optional.",
            style="Muted.TLabel",
            wraplength=1020,
        ).pack(anchor="w", pady=(4, 12))
        card = ttk.Frame(frame, style="Card.TFrame", padding=12)
        card.pack(fill="x", pady=(0, 12))
        ttk.Label(card, text="Payload vehicle", style="Card.TLabel").grid(row=0, column=0, sticky="w")
        payload_row = ttk.Frame(card, style="Card.TFrame")
        payload_row.grid(row=1, column=0, sticky="w", pady=(4, 8))
        for payload in SPAWN_PAYLOADS:
            ttk.Radiobutton(payload_row, text=payload, value=payload, variable=self.spawn_payload_var).pack(side="left", padx=(0, 14))
        ttk.Label(card, text="Existing spawn carrier slot", style="Card.TLabel").grid(row=0, column=1, sticky="w", padx=(28, 0))
        ttk.Combobox(card, textvariable=self.spawn_carrier_var, values=list(SPAWN_CARRIERS.keys()), state="readonly", width=30).grid(row=1, column=1, sticky="w", padx=(28, 0), pady=(4, 8))
        ttk.Checkbutton(card, text="Include adapted locset/seat locations", variable=self.spawn_include_locset_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(card, text="Original tune_d11generic.rpf", style="Card.TLabel").grid(row=3, column=0, sticky="w")
        ttk.Entry(card, textvariable=self.spawn_source_rpf, width=82).grid(row=4, column=0, sticky="ew", pady=(4, 8))
        ttk.Button(card, text="Browse", command=self._browse_spawn_rpf_source).grid(row=4, column=1, sticky="w", padx=(28, 0), pady=(4, 8))
        ttk.Label(card, text="Export folder", style="Card.TLabel").grid(row=5, column=0, sticky="w")
        ttk.Entry(card, textvariable=self.spawn_export_dir, width=82).grid(row=6, column=0, sticky="ew", pady=(4, 8))
        ttk.Button(card, text="Browse", command=self._browse_spawn_export_dir).grid(row=6, column=1, sticky="w", padx=(28, 0), pady=(4, 8))
        card.columnconfigure(0, weight=1)
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(0, 10))
        ttk.Button(buttons, text="Export Loose Spawn Patch", command=self._spawn_builder_loose_only).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Build Copied Full RPF Spawn Patch", command=self._spawn_builder_full_copy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Open Export Folder", command=self.open_exports_folder).pack(side="left")
        notes = ttk.Frame(frame, style="Card.TFrame", padding=12)
        notes.pack(fill="both", expand=True)
        ttk.Label(notes, text="Test Notes", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            notes,
            text="Recommended first test: Car01 via wagon02x, loose files imported into a copied tune_d11generic.rpf. If it freezes, disable locset export and test only the 5 tune files. If it only changes wagon behavior, the next step is matching WFT/WTD visual-resource swapping for the same carrier name.",
            style="Card.TLabel",
            wraplength=1010,
        ).pack(anchor="w", pady=(6, 10))
        ttk.Label(notes, textvariable=self.spawn_builder_status, style="Card.TLabel", wraplength=1010).pack(anchor="w")

    def _browse_spawn_rpf_source(self) -> None:
        path = filedialog.askopenfilename(title="Select original tune_d11generic.rpf", filetypes=[("RPF archive", "*.rpf"), ("All files", "*.*")])
        if path:
            self.spawn_source_rpf.set(path)
            self.rpf_source_path.set(path)

    def _browse_spawn_export_dir(self) -> None:
        path = filedialog.askdirectory(title="Choose export folder", initialdir=self.spawn_export_dir.get() or str(app_dir() / "exports"))
        if path:
            self.spawn_export_dir.set(path)
            self.rpf_export_dir.set(path)

    def _spawn_builder_loose_only(self) -> None:
        base = Path(self.spawn_export_dir.get() or (app_dir() / "exports"))
        export_root, msg = self._write_spawn_slot_export_package(base, build_full_rpf=False)
        self.spawn_builder_status.set(msg.replace("\n", " "))
        self.status.set(f"Spawn slot loose patch exported: {export_root}")
        messagebox.showinfo(APP_NAME, msg)

    def _spawn_builder_full_copy(self) -> None:
        source = Path(self.spawn_source_rpf.get().strip())
        if not source.exists():
            messagebox.showerror(APP_NAME, "Select a valid original tune_d11generic.rpf first.")
            return
        base = Path(self.spawn_export_dir.get() or (app_dir() / "exports"))
        export_root, msg = self._write_spawn_slot_export_package(base, build_full_rpf=True, source_rpf=source)
        self.spawn_builder_status.set(msg.replace("\n", " "))
        self.status.set(f"Spawn slot full copied RPF patch package exported: {export_root}")
        messagebox.showinfo(APP_NAME, msg)

    def _selected_mod_packs(self) -> list[dict]:
        selected = []
        vars_map = getattr(self, "mod_pack_vars", {})
        for pack in getattr(self, "mod_packs", []):
            var = vars_map.get(pack["name"])
            if var is not None and var.get():
                selected.append(pack)
        return selected

    def _mod_pack_status_text(self) -> str:
        packs = getattr(self, "mod_packs", [])
        total = len(packs)
        selected = len(self._selected_mod_packs()) if hasattr(self, "mod_pack_vars") else 0
        builtins = sum(1 for p in packs if p.get("source_type") == "builtin")
        loose = total - builtins
        if total <= 0:
            return "No patch presets are available."
        if loose:
            return f"{selected}/{total} patch presets selected ({builtins} built-in, {loose} loose folder)."
        return f"{selected}/{total} built-in patch presets selected."

    def _refresh_mod_pack_status(self) -> None:
        if hasattr(self, "mod_pack_status"):
            self.mod_pack_status.set(self._mod_pack_status_text())

    def _write_mp_client_bridge(self, export_root: Path) -> dict:
        bridge_dir = export_root / "04_multiplayer_client"
        bridge_dir.mkdir(parents=True, exist_ok=True)
        script = find_mp_companion_script()
        launcher = bridge_dir / "Launch_Code_RED_MP_Client.bat"
        launcher.write_text(
            "@echo off\n"
            "setlocal\n"
            "cd /d %~dp0\\..\\..\\related_apps\n"
            "if exist run_mp_companion.py (\n"
            "  python run_mp_companion.py\n"
            ") else (\n"
            "  echo Code RED MP Companion runner was not found next to this build.\n"
            "  pause\n"
            ")\n",
            encoding="utf-8",
        )
        readme = bridge_dir / "README_MULTIPLAYER_CLIENT.txt"
        readme.write_text(
            "Code RED Multiplayer Client Bridge\n"
            "================================\n\n"
            "This patch export keeps multiplayer access organized beside the selected tune/mod files.\n"
            "Use the workbench button 'Open MP Companion' or run related_apps/run_mp_companion.py from the Code_RED folder.\n\n"
            "Recommended flow:\n"
            "1. Host opens MP Companion and starts a Code RED Freemode session.\n"
            "2. Client opens MP Companion, scans/joins the LAN session, or enters an invite.\n"
            "3. Apply matching patch options on every copy before joining so the car/train spawn behavior matches.\n\n"
            "Status: " + (f"Detected {script}" if script else "MP Companion script was not found in this copy.") + "\n",
            encoding="utf-8",
        )
        return {"status": "included", "script": str(script) if script else None, "folder": str(bridge_dir)}

    def _copy_one_pack(self, pack: dict, destination: Path) -> dict:
        source_type = pack.get("source_type", "folder")
        if source_type == "builtin":
            if copy_builtin_mod_pack is None:
                raise RuntimeError("Built-in mod preset helper is not available.")
            return copy_builtin_mod_pack(str(pack.get("builtin_key") or pack["name"]), destination)
        return copy_mod_tree(Path(pack["path"]), destination)

    def _copy_selected_mod_packs(self, export_root: Path, merge_root: Path | None = None) -> list[dict]:
        selected = self._selected_mod_packs()
        results: list[dict] = []
        if not selected:
            return results
        packs_root = export_root / "02_mod_packs"
        packs_root.mkdir(parents=True, exist_ok=True)
        if merge_root is not None:
            merge_root.mkdir(parents=True, exist_ok=True)
        for pack in selected:
            pack_copy_root = packs_root / pack["slug"]
            if pack_copy_root.exists():
                shutil.rmtree(pack_copy_root)
            result_copy = self._copy_one_pack(pack, pack_copy_root)
            source_type = str(pack.get("source_type", "folder"))
            source_label = "built-in preset" if source_type == "builtin" else str(pack.get("path", ""))
            result = {
                "name": pack["name"],
                "slug": pack["slug"],
                "description": pack["description"],
                "category": pack["category"],
                "risk": pack["risk"],
                "source_type": source_type,
                "source": source_label,
                "organized_copy": str(pack_copy_root),
                "file_count": pack["file_count"],
                "size": pack["size"],
                "organized_copy_result": result_copy,
            }
            if merge_root is not None:
                result["merged_result"] = self._copy_one_pack(pack, merge_root)
            results.append(result)
        (packs_root / "README_SELECTED_MOD_PACKS.txt").write_text(
            "Selected Code RED Patch Presets\n"
            "===============================\n\n"
            "Each folder here is an organized copy of one selected preset. Built-in presets are expanded from code, so the tuner no longer needs a Mods/ folder for Driveable Vehicles+ or Train Spawns Cars.\n"
            "Use 03_merged_loose_patch when you want one combined loose patch tree.\n"
            "Conflicting files are preserved with .conflict_from_<pack> suffix instead of being overwritten.\n\n"
            + "\n".join(f"- {r['name']} [{r['source_type']}]: {r['description']}" for r in results) + "\n",
            encoding="utf-8",
        )
        return results

    def _build_mod_pack_tab(self) -> None:
        frame = ttk.Frame(self.nb, padding=12)
        self.nb.add(frame, text="Patch Options")
        ttk.Label(frame, text="Patch Options / Mod Packs", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Choose built-in patch presets that travel with the exported tune patch. Driveable Vehicles+ and Train Spawns Cars are now embedded in the tuner, stay separated in 02_mod_packs, and are also merged into 03_merged_loose_patch for easy import/testing.",
            style="Muted.TLabel",
            wraplength=900,
        ).pack(anchor="w", pady=(4, 10))
        opts = ttk.Frame(frame, style="Card.TFrame", padding=12)
        opts.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(opts, text="Include selected patch presets in tune/spawn exports", variable=self.include_selected_mods_var, command=self._refresh_mod_pack_status).pack(anchor="w")
        ttk.Checkbutton(opts, text="Include Multiplayer Client bridge/readme", variable=self.include_mp_client_var).pack(anchor="w", pady=(3, 0))
        ttk.Label(opts, textvariable=self.mod_pack_status, style="Card.TLabel", wraplength=1020).pack(anchor="w", pady=(8, 0))
        ttk.Label(opts, textvariable=self.mp_companion_status, style="Card.TLabel", wraplength=1020).pack(anchor="w", pady=(2, 0))

        list_card = ttk.Frame(frame, style="Card.TFrame", padding=12)
        list_card.pack(fill="both", expand=True, pady=(0, 10))
        ttk.Label(list_card, text="Available Built-in Presets", style="Header.TLabel").pack(anchor="w", pady=(0, 6))
        if not self.mod_packs:
            ttk.Label(list_card, text="No built-in presets or loose mod folders were found.", style="Card.TLabel", wraplength=780).pack(anchor="w")
        else:
            for pack in self.mod_packs:
                row = ttk.Frame(list_card, style="Card.TFrame", padding=(0, 3))
                row.pack(fill="x", pady=3)
                source_tag = "built-in" if pack.get("source_type") == "builtin" else "loose"
                cb = ttk.Checkbutton(row, text=f"{pack['name']}  •  {source_tag}  •  {pack['file_count']} files  •  {pack['size_text']}", variable=self.mod_pack_vars[pack["name"]], command=self._refresh_mod_pack_status)
                cb.pack(anchor="w")
                ttk.Label(row, text=f"{pack['description']}  Risk: {pack['risk']}", style="Card.TLabel", wraplength=820).pack(anchor="w", padx=(24, 0))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Export Selected Patch Options", command=self._export_selected_patch_options).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Open Optional Mods Folder", command=self._open_mods_folder).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Open MP Companion", command=self._open_mp_companion_from_tuner).pack(side="left", padx=(0, 8))

    def _open_mods_folder(self) -> None:
        self.mods_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(self.mods_dir)  # type: ignore[attr-defined]
        except Exception:
            messagebox.showinfo(APP_NAME, f"Mods folder:\n{self.mods_dir}")

    def _open_mp_companion_from_tuner(self) -> None:
        script = find_mp_companion_script()
        if not script:
            messagebox.showerror(APP_NAME, "MP Companion was not found in related_apps.")
            return
        try:
            subprocess.Popen([sys.executable, str(script)], cwd=str(script.parent))
            self.mp_companion_status.set(f"Launched MP Companion: {script}")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not launch MP Companion:\n{exc}")

    def _export_selected_patch_options(self) -> None:
        base = filedialog.askdirectory(title="Choose export folder", initialdir=str(app_dir() / "exports"))
        if not base:
            return
        export_root = Path(base) / f"CodeRED_SelectedPatchOptions_{now_stamp()}"
        export_root.mkdir(parents=True, exist_ok=True)
        merge_root = export_root / "03_merged_loose_patch"
        selected_mods = self._copy_selected_mod_packs(export_root, merge_root=merge_root)
        mp_result = self._write_mp_client_bridge(export_root) if self.include_mp_client_var.get() else {"status": "not included"}
        manifest = {
            "app": APP_NAME,
            "version": APP_VERSION,
            "created": _dt.datetime.now().isoformat(timespec="seconds"),
            "selected_mod_packs": selected_mods,
            "mp_client_bridge": mp_result,
            "merged_loose_patch": str(merge_root),
        }
        (export_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (export_root / "README_PATCH_OPTIONS.txt").write_text(
            "Code RED Selected Patch Options\n"
            "===============================\n\n"
            "02_mod_packs keeps each preset separated.\n"
            "03_merged_loose_patch is the combined loose folder for import into copied archives.\n"
            "04_multiplayer_client documents the built-in MP Companion route.\n\n"
            "Selected:\n" + ("\n".join(f"- {r['name']}" for r in selected_mods) if selected_mods else "- none") + "\n",
            encoding="utf-8",
        )
        self.mod_pack_status.set(f"Exported selected patch options: {export_root}")
        messagebox.showinfo(APP_NAME, f"Exported selected patch options:\n{export_root}")

    def _build_patch_builder_tab(self) -> None:
        frame = ttk.Frame(self.nb, padding=12)
        self.nb.add(frame, text="RPF Builder")
        ttk.Label(frame, text="Tune RPF Patch Builder", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Builds the normal loose patch tree, then optionally patches a copied full tune_d11generic.rpf. The full-RPF path never edits your selected original file. It needs the zstd command-line tool because the target vehicle XML entries are compressed inside the archive.",
            style="Muted.TLabel",
            wraplength=980,
        ).pack(anchor="w", pady=(4, 12))

        card = ttk.Frame(frame, style="Card.TFrame", padding=12)
        card.pack(fill="x", pady=(0, 12))
        ttk.Label(card, text="Original tune_d11generic.rpf", style="Card.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(card, textvariable=self.rpf_source_path, width=92).grid(row=1, column=0, sticky="ew", pady=(4, 8))
        ttk.Button(card, text="Browse", command=self._browse_rpf_source).grid(row=1, column=1, padx=(8, 0), pady=(4, 8))
        ttk.Label(card, text="Export folder", style="Card.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Entry(card, textvariable=self.rpf_export_dir, width=92).grid(row=3, column=0, sticky="ew", pady=(4, 8))
        ttk.Button(card, text="Browse", command=self._browse_rpf_export_dir).grid(row=3, column=1, padx=(8, 0), pady=(4, 8))
        card.columnconfigure(0, weight=1)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(0, 10))
        ttk.Button(buttons, text="Export Loose Patch Only", command=self._rpf_builder_loose_only).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Build Copied Full RPF Patch", command=self._rpf_builder_full_copy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Open Export Folder", command=self.open_exports_folder).pack(side="left")

        notes = ttk.Frame(frame, style="Card.TFrame", padding=12)
        notes.pack(fill="both", expand=True)
        ttk.Label(notes, text="Builder Notes", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            notes,
            text="If full-RPF build succeeds, the output file is tune_d11generic_codered_full_copy_PATCHED.rpf inside the export package. Back up the real game file first. If full-RPF build fails because zstd or cryptography is missing, use the loose files with MagicRDR/Code RED instead.",
            style="Card.TLabel",
            wraplength=980,
        ).pack(anchor="w", pady=(6, 10))
        ttk.Label(notes, textvariable=self.rpf_builder_status, style="Card.TLabel", wraplength=980).pack(anchor="w")

    def _browse_rpf_source(self) -> None:
        path = filedialog.askopenfilename(title="Select original tune_d11generic.rpf", filetypes=[("RPF archive", "*.rpf"), ("All files", "*.*")])
        if path:
            self.rpf_source_path.set(path)

    def _browse_rpf_export_dir(self) -> None:
        path = filedialog.askdirectory(title="Choose export folder", initialdir=self.rpf_export_dir.get() or str(app_dir() / "exports"))
        if path:
            self.rpf_export_dir.set(path)

    def _rpf_builder_loose_only(self) -> None:
        base = Path(self.rpf_export_dir.get() or (app_dir() / "exports"))
        export_root, msg = self._write_patch_export_package(base, build_full_rpf=False)
        self.rpf_builder_status.set(msg.replace("\n", " "))
        self.status.set(f"Loose tune patch exported: {export_root}")
        messagebox.showinfo(APP_NAME, msg)

    def _rpf_builder_full_copy(self) -> None:
        source = Path(self.rpf_source_path.get().strip())
        if not source.exists():
            messagebox.showerror(APP_NAME, "Select a valid original tune_d11generic.rpf first.")
            return
        base = Path(self.rpf_export_dir.get() or (app_dir() / "exports"))
        export_root, msg = self._write_patch_export_package(base, build_full_rpf=True, source_rpf=source)
        self.rpf_builder_status.set(msg.replace("\n", " "))
        self.status.set(f"Full copied tune RPF patch package exported: {export_root}")
        messagebox.showinfo(APP_NAME, msg)

def selftest() -> int:
    root = app_dir()
    stock = root / "stock_vehicle_files"
    out = root / "exports" / f"selftest_{now_stamp()}"
    out.mkdir(parents=True, exist_ok=True)
    car = VehicleTune("Car01", stock / "car01x.vehsim")
    truck = VehicleTune("Truck01", stock / "truck01x.vehsim")
    car_input = VehicleTune("Car01Input", stock / "car01x.vehinput")
    truck_input = VehicleTune("Truck01Input", stock / "truck01x.vehinput")
    car.set_float("Engine/MaxHorsePower", 230)
    truck.set_float("Engine/MaxHorsePower", 220)
    car_input.set_float("SSSValue", 0.60)
    truck_input.set_float("SSSValue", 0.65)
    files = {
        "root/tune/vehicle/car01x.vehsim": car.to_bytes(),
        "root/tune/vehicle/truck01x.vehsim": truck.to_bytes(),
        "root/tune/vehicle/car01x.vehinput": car_input.to_bytes(),
        "root/tune/vehicle/truck01x.vehinput": truck_input.to_bytes(),
    }
    vd = out / "root" / "tune" / "vehicle"
    vd.mkdir(parents=True, exist_ok=True)
    for p, data in files.items():
        (vd / Path(p).name).write_bytes(data)
    input_src = find_input_profile()
    if input_src and input_src.exists():
        dst = out / "input_profiles" / DEFAULT_INPUT_PROFILE
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_src, dst)
    build_micro_rpf6(files, out / "tune_d11generic_codered_patch_micro.rpf")
    spawn_dir = out / "spawn_slot_selftest" / "root" / "tune" / "vehicle"
    spawn_dir.mkdir(parents=True, exist_ok=True)
    for kind in SPAWN_SWAP_KINDS:
        src = stock / f"car01x.{kind}"
        if src.exists():
            (spawn_dir / f"wagon02x.{kind}").write_bytes(src.read_bytes())
    loc_src = stock / "locset_car01.xml"
    if loc_src.exists():
        loc_text = loc_src.read_text(encoding="utf-8", errors="replace")
        import re
        loc_text = re.sub(r"<Name>.*?</Name>", "<Name>locSet_Wagon02</Name>", loc_text, count=1, flags=re.S)
        loc_dst = spawn_dir / "locset"
        loc_dst.mkdir(parents=True, exist_ok=True)
        (loc_dst / "locset_wagon02.xml").write_text(loc_text, encoding="utf-8")
    (out / "spawn_slot_selftest" / "README.txt").write_text("Loose spawn-slot selftest: Car01 payload renamed onto wagon02x tune/locset targets. Experimental; requires model swap for visual car.\n", encoding="utf-8")
    (out / "selftest_ok.txt").write_text("Code RED Tuner selftest completed with vehsim + vehinput export, input_car.xml packaging, and spawn-slot loose selftest.\n", encoding="utf-8")
    print(f"Selftest export: {out}")
    return 0

def _write_tuner_crash_log(exc_type, exc, tb) -> None:
    try:
        import traceback
        log_dir = app_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "tuner_crash_latest.log"
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        path.write_text(f"{APP_NAME} {APP_VERSION} crash\n{_dt.datetime.now().isoformat(timespec='seconds')}\n\n{text}", encoding="utf-8")
    except Exception:
        pass

def main() -> int:
    sys.excepthook = _write_tuner_crash_log
    parser = argparse.ArgumentParser(description=f"{APP_NAME} {APP_VERSION}")
    parser.add_argument("--selftest", action="store_true", help="Export a sample patch without launching the GUI.")
    if any(arg in {"-h", "--help"} for arg in sys.argv[1:]):
        parser.print_help()
        try:
            sys.stdout.flush(); sys.stderr.flush()
        finally:
            os._exit(0)
    args = parser.parse_args()
    if args.selftest:
        code = selftest()
        try:
            sys.stdout.flush(); sys.stderr.flush()
        finally:
            os._exit(int(code))
    try:
        app = TunerApp()
        app.mainloop()
    except Exception as exc:
        _write_tuner_crash_log(type(exc), exc, exc.__traceback__)
        try:
            messagebox.showerror(APP_NAME, f"Tuner failed to launch. A crash log was written to logs/tuner_crash_latest.log.\n\n{exc}")
        except Exception:
            print(f"Tuner failed to launch: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
