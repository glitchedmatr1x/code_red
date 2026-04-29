from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
import traceback
from pathlib import Path
from typing import Callable, Iterable

from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    Filename,
    Fog,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomTristrips,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    KeyboardButton,
    MouseButton,
    PointLight,
    PNMImage,
    TransparencyAttrib,
    Vec3,
    WindowProperties,
    loadPrcFileData,
)
from direct.gui.DirectGui import DirectFrame
from direct.gui.OnscreenText import OnscreenText
from direct.showbase.ShowBase import ShowBase
from direct.task import Task

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

VIRTUAL_W = 1920
VIRTUAL_H = 1080


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 0.0
    t = clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def mix(a: float, b: float, t: float) -> float:
    return a * (1.0 - t) + b * t


def fract(x: float) -> float:
    return x - math.floor(x)


def hash2(x: float, y: float) -> float:
    return fract(math.sin(x * 127.1 + y * 311.7) * 43758.5453123)


def value_noise(x: float, y: float) -> float:
    xi = math.floor(x)
    yi = math.floor(y)
    xf = x - xi
    yf = y - yi
    v00 = hash2(xi, yi)
    v10 = hash2(xi + 1, yi)
    v01 = hash2(xi, yi + 1)
    v11 = hash2(xi + 1, yi + 1)
    u = xf * xf * (3.0 - 2.0 * xf)
    v = yf * yf * (3.0 - 2.0 * yf)
    return mix(mix(v00, v10, u), mix(v01, v11, u), v)


def fbm(x: float, y: float, octaves: int = 5) -> float:
    total = 0.0
    amplitude = 0.5
    frequency = 1.0
    for _ in range(octaves):
        total += amplitude * value_noise(x * frequency, y * frequency)
        frequency *= 2.03
        amplitude *= 0.5
    return total


class CleanRoomWorldV32(ShowBase):
    def __init__(self, capture_path: str | None = None, camera_mode: str = "flyover", proof_mode: bool = False) -> None:
        self.capture_path = capture_path
        self.camera_mode = camera_mode
        self.proof_mode = proof_mode
        self.seed = 143
        self.random = random.Random(self.seed)
        self.near_half_extent = 2085.0
        self.far_half_extent = 2720.0
        self.lod_half_extent = 7120.0
        self.near_steps = 112 if proof_mode else 392
        self.far_steps = 24 if proof_mode else 152
        self.lod_steps = 18 if proof_mode else 104
        self.water_level = -5.0
        self.river_width = 76.0
        self.hud_visible = not bool(capture_path)
        self.settings_visible = False
        self.mouse_anchor: tuple[float, float] | None = None
        self.heading = 24.0
        self.pitch = -18.0
        self.move_speed = 215.0

        super().__init__()
        self.disableMouse()
        self._configure_window()
        self._setup_scene()
        self._build_world()
        self._setup_ui()
        self._bind_controls()
        self._set_initial_camera(camera_mode)

        self.taskMgr.add(self._update, "world_update")
        if self.capture_path:
            self.taskMgr.doMethodLater(0.25, self._capture_and_quit, "capture_and_quit")

    def _configure_window(self) -> None:
        props = WindowProperties()
        props.setTitle("Code RED Clean-Room World v32")
        props.setSize(VIRTUAL_W, VIRTUAL_H)
        if hasattr(self.win, "requestProperties"):
            self.win.requestProperties(props)
        self.setBackgroundColor(0.80, 0.84, 0.89, 1.0)
        self.camLens.setFov(72)
        self.camLens.setNearFar(0.1, 9000.0)

    def _setup_scene(self) -> None:
        ambient = AmbientLight("ambient")
        ambient.setColor((0.58, 0.55, 0.52, 1.0))
        self.render.setLight(self.render.attachNewNode(ambient))

        sun = DirectionalLight("sun")
        sun.setColor((0.98, 0.92, 0.84, 1.0))
        sun_np = self.render.attachNewNode(sun)
        sun_np.setHpr(34, -41, 0)
        self.render.setLight(sun_np)

        fill = DirectionalLight("fill")
        fill.setColor((0.44, 0.47, 0.51, 1.0))
        fill_np = self.render.attachNewNode(fill)
        fill_np.setHpr(-122, -16, 0)
        self.render.setLight(fill_np)

        town_light = PointLight("town")
        town_light.setColor((0.86, 0.74, 0.54, 1.0))
        town_np = self.render.attachNewNode(town_light)
        town_np.setPos(100.0, -20.0, 95.0)
        self.render.setLight(town_np)

        self.setBackgroundColor(0.80, 0.84, 0.89, 1.0)
        fog = Fog("distance_fog")
        fog.setColor(0.90, 0.91, 0.93)
        fog.setExpDensity(0.000068 if self.proof_mode else 0.000082)
        self.render.setFog(fog)

    def river_center(self, x: float) -> float:
        return math.sin(x * 0.00175 - 0.2) * 175.0 - 210.0 + math.sin(x * 0.0055 + 0.6) * 34.0

    def river_distance(self, x: float, y: float) -> float:
        return y - self.river_center(x)

    def terrain_height(self, x: float, y: float) -> float:
        scale = 0.00165
        base = (fbm(x * scale, y * scale, 6) - 0.5) * 48.0
        broad = (fbm(x * 0.00066 + 41.0, y * 0.00066 - 11.0, 5) - 0.5) * 150.0
        detail = (fbm(x * 0.0045 + 7.0, y * 0.0045 - 3.0, 4) - 0.5) * 10.5

        radial = math.sqrt((x / self.far_half_extent) ** 2 + (y / self.far_half_extent) ** 2)
        land_crown = (1.0 - smoothstep(0.38, 1.04, radial)) * 104.0
        basin = -smoothstep(0.08, 0.58, radial) * 34.0
        outer_ring = smoothstep(0.68, 1.04, radial) * 92.0
        edge_shelf = smoothstep(0.78, 1.02, radial) * 36.0

        north_wall = smoothstep(180.0, 980.0, y) * 118.0
        south_ridge = (1.0 - smoothstep(-1080.0, -180.0, y)) * 92.0
        west_high = (1.0 - smoothstep(-1040.0, -120.0, x)) * 80.0
        east_break = smoothstep(120.0, 1120.0, x) * 62.0
        shoreline_bluff = smoothstep(self.river_width * 4.4, self.river_width * 1.2, abs(self.river_distance(x, y))) * 26.0
        southwest_mass = max(0.0, 1.0 - math.sqrt(((x + 760.0) / 760.0) ** 2 + ((y + 620.0) / 680.0) ** 2)) * 72.0
        east_wall = max(0.0, 1.0 - math.sqrt(((x - 980.0) / 700.0) ** 2 + ((y - 60.0) / 980.0) ** 2)) * 64.0
        north_cap = max(0.0, 1.0 - math.sqrt(((x + 120.0) / 1480.0) ** 2 + ((y - 1120.0) / 520.0) ** 2)) * 58.0
        northwest_mass = max(0.0, 1.0 - math.sqrt(((x + 980.0) / 720.0) ** 2 + ((y - 700.0) / 620.0) ** 2)) * 82.0
        northeast_mass = max(0.0, 1.0 - math.sqrt(((x - 900.0) / 760.0) ** 2 + ((y - 760.0) / 680.0) ** 2)) * 72.0
        southeast_mass = max(0.0, 1.0 - math.sqrt(((x - 960.0) / 720.0) ** 2 + ((y + 720.0) / 620.0) ** 2)) * 84.0
        southwest_apron = max(0.0, 1.0 - math.sqrt(((x + 980.0) / 860.0) ** 2 + ((y + 860.0) / 760.0) ** 2)) * 64.0
        boundary_spine_n = smoothstep(440.0, 1360.0, y) * (1.0 - smoothstep(1120.0, 1900.0, abs(x))) * 48.0
        boundary_spine_s = (1.0 - smoothstep(-1460.0, -320.0, y)) * (1.0 - smoothstep(1080.0, 1880.0, abs(x))) * 42.0
        boundary_spine_w = (1.0 - smoothstep(-1520.0, -380.0, x)) * (1.0 - smoothstep(980.0, 1800.0, abs(y))) * 40.0
        boundary_spine_e = smoothstep(380.0, 1520.0, x) * (1.0 - smoothstep(980.0, 1800.0, abs(y))) * 36.0
        north_arc = max(0.0, 1.0 - math.sqrt(((x - 40.0) / 1680.0) ** 2 + ((y - 1320.0) / 420.0) ** 2)) * 74.0
        south_arc = max(0.0, 1.0 - math.sqrt(((x + 20.0) / 1600.0) ** 2 + ((y + 1360.0) / 430.0) ** 2)) * 66.0
        west_arc = max(0.0, 1.0 - math.sqrt(((x + 1380.0) / 420.0) ** 2 + ((y + 20.0) / 1500.0) ** 2)) * 58.0
        east_arc = max(0.0, 1.0 - math.sqrt(((x - 1380.0) / 430.0) ** 2 + ((y - 20.0) / 1460.0) ** 2)) * 50.0
        northeast_plate = max(0.0, 1.0 - math.sqrt(((x - 1180.0) / 560.0) ** 2 + ((y - 1180.0) / 380.0) ** 2)) * 48.0
        northwest_plate = max(0.0, 1.0 - math.sqrt(((x + 1260.0) / 520.0) ** 2 + ((y - 1120.0) / 420.0) ** 2)) * 54.0
        southeast_plate = max(0.0, 1.0 - math.sqrt(((x - 1220.0) / 560.0) ** 2 + ((y + 1120.0) / 400.0) ** 2)) * 46.0
        southwest_plate = max(0.0, 1.0 - math.sqrt(((x + 1240.0) / 600.0) ** 2 + ((y + 1180.0) / 430.0) ** 2)) * 44.0
        north_headwall = max(0.0, 1.0 - math.sqrt(((x - 120.0) / 980.0) ** 2 + ((y - 1540.0) / 240.0) ** 2)) * 52.0
        east_headwall = max(0.0, 1.0 - math.sqrt(((x - 1520.0) / 240.0) ** 2 + ((y - 40.0) / 980.0) ** 2)) * 34.0
        west_headwall = max(0.0, 1.0 - math.sqrt(((x + 1540.0) / 260.0) ** 2 + ((y + 60.0) / 1020.0) ** 2)) * 40.0
        south_headwall = max(0.0, 1.0 - math.sqrt(((x + 20.0) / 960.0) ** 2 + ((y + 1540.0) / 250.0) ** 2)) * 36.0
        northeast_hook = max(0.0, 1.0 - math.sqrt(((x - 1480.0) / 300.0) ** 2 + ((y - 1120.0) / 560.0) ** 2)) * 44.0
        northwest_hook = max(0.0, 1.0 - math.sqrt(((x + 1480.0) / 320.0) ** 2 + ((y - 1100.0) / 540.0) ** 2)) * 48.0
        southeast_hook = max(0.0, 1.0 - math.sqrt(((x - 1460.0) / 320.0) ** 2 + ((y + 1080.0) / 560.0) ** 2)) * 38.0
        southwest_hook = max(0.0, 1.0 - math.sqrt(((x + 1440.0) / 360.0) ** 2 + ((y + 1120.0) / 580.0) ** 2)) * 42.0
        north_barrier = max(0.0, 1.0 - math.sqrt(((x + 40.0) / 1880.0) ** 2 + ((y - 1640.0) / 210.0) ** 2)) * 40.0
        south_barrier = max(0.0, 1.0 - math.sqrt(((x - 40.0) / 1800.0) ** 2 + ((y + 1660.0) / 220.0) ** 2)) * 34.0
        east_barrier = max(0.0, 1.0 - math.sqrt(((x - 1640.0) / 220.0) ** 2 + ((y + 20.0) / 1720.0) ** 2)) * 30.0
        west_barrier = max(0.0, 1.0 - math.sqrt(((x + 1660.0) / 240.0) ** 2 + ((y - 20.0) / 1740.0) ** 2)) * 36.0
        northwest_stitch = max(0.0, 1.0 - math.sqrt(((x + 1180.0) / 520.0) ** 2 + ((y - 1360.0) / 300.0) ** 2)) * 34.0
        northeast_stitch = max(0.0, 1.0 - math.sqrt(((x - 1160.0) / 520.0) ** 2 + ((y - 1380.0) / 300.0) ** 2)) * 30.0
        southwest_stitch = max(0.0, 1.0 - math.sqrt(((x + 1200.0) / 560.0) ** 2 + ((y + 1380.0) / 320.0) ** 2)) * 28.0
        southeast_stitch = max(0.0, 1.0 - math.sqrt(((x - 1180.0) / 540.0) ** 2 + ((y + 1360.0) / 320.0) ** 2)) * 30.0
        north_mid_stitch = max(0.0, 1.0 - math.sqrt(((x - 40.0) / 920.0) ** 2 + ((y - 1480.0) / 250.0) ** 2)) * 26.0
        south_mid_stitch = max(0.0, 1.0 - math.sqrt(((x + 20.0) / 940.0) ** 2 + ((y + 1480.0) / 260.0) ** 2)) * 22.0
        east_mid_stitch = max(0.0, 1.0 - math.sqrt(((x - 1500.0) / 260.0) ** 2 + ((y + 10.0) / 980.0) ** 2)) * 18.0
        west_mid_stitch = max(0.0, 1.0 - math.sqrt(((x + 1520.0) / 280.0) ** 2 + ((y - 10.0) / 1000.0) ** 2)) * 22.0
        northeast_diagonal = max(0.0, 1.0 - math.sqrt(((x - 1020.0) / 900.0) ** 2 + ((y - 1280.0) / 280.0) ** 2)) * 24.0
        northwest_diagonal = max(0.0, 1.0 - math.sqrt(((x + 1040.0) / 920.0) ** 2 + ((y - 1260.0) / 300.0) ** 2)) * 26.0
        southeast_diagonal = max(0.0, 1.0 - math.sqrt(((x - 1040.0) / 920.0) ** 2 + ((y + 1260.0) / 300.0) ** 2)) * 22.0
        southwest_diagonal = max(0.0, 1.0 - math.sqrt(((x + 1060.0) / 940.0) ** 2 + ((y + 1280.0) / 320.0) ** 2)) * 24.0
        north_wide_swell = max(0.0, 1.0 - math.sqrt(((x - 20.0) / 1620.0) ** 2 + ((y - 1080.0) / 620.0) ** 2)) * 28.0
        south_wide_swell = max(0.0, 1.0 - math.sqrt(((x + 10.0) / 1560.0) ** 2 + ((y + 1120.0) / 640.0) ** 2)) * 24.0
        east_wide_swell = max(0.0, 1.0 - math.sqrt(((x - 1120.0) / 700.0) ** 2 + ((y + 40.0) / 1440.0) ** 2)) * 20.0
        west_wide_swell = max(0.0, 1.0 - math.sqrt(((x + 1160.0) / 740.0) ** 2 + ((y - 20.0) / 1460.0) ** 2)) * 22.0
        northeast_shoulder = max(0.0, 1.0 - math.sqrt(((x - 1380.0) / 520.0) ** 2 + ((y - 780.0) / 760.0) ** 2)) * 18.0
        northwest_shoulder = max(0.0, 1.0 - math.sqrt(((x + 1400.0) / 560.0) ** 2 + ((y - 760.0) / 780.0) ** 2)) * 20.0
        southeast_shoulder = max(0.0, 1.0 - math.sqrt(((x - 1360.0) / 540.0) ** 2 + ((y + 760.0) / 760.0) ** 2)) * 18.0
        southwest_shoulder = max(0.0, 1.0 - math.sqrt(((x + 1380.0) / 580.0) ** 2 + ((y + 780.0) / 780.0) ** 2)) * 20.0
        perimeter_step = smoothstep(0.80, 1.04, radial) * (31.0 + (fbm(x * 0.0013 + 19.0, y * 0.0013 - 13.0, 3) - 0.5) * 15.0)
        outer_breakup = (fbm(x * 0.00095 - 14.0, y * 0.00095 + 8.0, 4) - 0.5) * 18.0 * smoothstep(0.66, 1.03, radial)
        perimeter_wave = (fbm(x * 0.00042 - 22.0, y * 0.00042 + 17.0, 4) - 0.5) * 24.0 * smoothstep(0.70, 1.03, radial)
        central_basin = max(0.0, 1.0 - math.sqrt(((x - 40.0) / 560.0) ** 2 + ((y + 10.0) / 360.0) ** 2))
        central_apron = max(0.0, 1.0 - math.sqrt(((x + 180.0) / 820.0) ** 2 + ((y + 180.0) / 560.0) ** 2))
        south_bench = max(0.0, 1.0 - math.sqrt(((x + 30.0) / 720.0) ** 2 + ((y + 360.0) / 420.0) ** 2))
        east_delta = max(0.0, 1.0 - math.sqrt(((x - 700.0) / 620.0) ** 2 + ((y + 60.0) / 480.0) ** 2))

        mesa_a = max(0.0, 1.0 - math.sqrt(((x - 350.0) / 310.0) ** 2 + ((y - 185.0) / 245.0) ** 2))
        mesa_b = max(0.0, 1.0 - math.sqrt(((x + 430.0) / 350.0) ** 2 + ((y + 260.0) / 280.0) ** 2))
        mesa_c = max(0.0, 1.0 - math.sqrt(((x - 560.0) / 250.0) ** 2 + ((y + 360.0) / 200.0) ** 2))
        plateau = smoothstep(0.10, 0.92, mesa_a) * 172.0
        plateau += smoothstep(0.16, 0.88, mesa_b) * 122.0
        plateau += smoothstep(0.20, 0.86, mesa_c) * 96.0

        canyon_main_curve = math.sin(x * 0.0024 + 1.1) * 100.0 + math.sin(x * 0.0072) * 10.0
        canyon_main = -smoothstep(210.0, 0.0, abs(y - canyon_main_curve)) * 124.0
        canyon_branch = -smoothstep(116.0, 0.0, abs(y + 330.0 + math.sin(x * 0.0037 - 0.8) * 68.0)) * 82.0
        canyon_fork = -smoothstep(132.0, 0.0, abs(y - 235.0 - math.sin(x * 0.0032 + 0.9) * 56.0)) * 74.0
        canyon_west = -smoothstep(150.0, 0.0, abs(y + 120.0 + math.sin(x * 0.0021 - 2.0) * 90.0)) * 54.0
        north_tributary = -smoothstep(92.0, 0.0, abs(x - 220.0 - math.sin(y * 0.0023) * 92.0)) * smoothstep(180.0, 860.0, y) * 42.0
        south_wash = -smoothstep(120.0, 0.0, abs(y + 520.0 + math.sin(x * 0.0027) * 54.0)) * 34.0
        east_wash = -smoothstep(98.0, 0.0, abs(x - 760.0 - math.sin(y * 0.0028 + 0.5) * 66.0)) * smoothstep(-120.0, 760.0, y) * 26.0
        west_gully = -smoothstep(86.0, 0.0, abs(x + 760.0 + math.sin(y * 0.0031 - 0.4) * 74.0)) * smoothstep(-520.0, 420.0, y) * 24.0
        north_edge_gash = -smoothstep(118.0, 0.0, abs(x + 160.0 - math.sin(y * 0.0018 + 0.4) * 140.0)) * smoothstep(700.0, 1500.0, y) * 26.0
        southeast_gash = -smoothstep(128.0, 0.0, abs(y + 820.0 - math.sin(x * 0.0021 - 0.7) * 110.0)) * smoothstep(420.0, 1460.0, x) * 22.0
        north_outlet = -smoothstep(142.0, 0.0, abs(x - 120.0 - math.sin(y * 0.0019 + 0.2) * 118.0)) * smoothstep(760.0, 1640.0, y) * 28.0
        south_outlet = -smoothstep(148.0, 0.0, abs(x + 90.0 - math.sin(y * 0.0017 - 0.3) * 124.0)) * (1.0 - smoothstep(-1660.0, -720.0, y)) * 24.0
        east_outlet = -smoothstep(136.0, 0.0, abs(y + 120.0 - math.sin(x * 0.0018 + 0.4) * 116.0)) * smoothstep(720.0, 1620.0, x) * 20.0
        west_outlet = -smoothstep(132.0, 0.0, abs(y - 40.0 - math.sin(x * 0.0019 - 0.6) * 108.0)) * (1.0 - smoothstep(-1620.0, -760.0, x)) * 18.0
        northwest_drain = -smoothstep(112.0, 0.0, abs(x + 960.0 - math.sin(y * 0.0021 + 0.1) * 88.0)) * smoothstep(620.0, 1460.0, y) * 16.0
        northeast_drain = -smoothstep(108.0, 0.0, abs(x - 980.0 - math.sin(y * 0.0020 - 0.2) * 84.0)) * smoothstep(620.0, 1480.0, y) * 14.0
        southwest_drain = -smoothstep(120.0, 0.0, abs(x + 940.0 - math.sin(y * 0.0018 - 0.1) * 92.0)) * (1.0 - smoothstep(-1500.0, -660.0, y)) * 12.0
        southeast_drain = -smoothstep(116.0, 0.0, abs(x - 960.0 - math.sin(y * 0.0019 + 0.2) * 90.0)) * (1.0 - smoothstep(-1480.0, -660.0, y)) * 13.0
        north_outlet_wall = smoothstep(240.0, 88.0, abs(x - 100.0 - math.sin(y * 0.0019 + 0.15) * 118.0)) * smoothstep(760.0, 1680.0, y) * 16.0
        south_outlet_wall = smoothstep(250.0, 94.0, abs(x + 80.0 - math.sin(y * 0.0017 - 0.2) * 124.0)) * (1.0 - smoothstep(-1680.0, -760.0, y)) * 13.0
        east_outlet_wall = smoothstep(220.0, 90.0, abs(y + 120.0 - math.sin(x * 0.0018 + 0.4) * 116.0)) * smoothstep(780.0, 1660.0, x) * 12.0
        west_outlet_wall = smoothstep(226.0, 94.0, abs(y - 40.0 - math.sin(x * 0.0019 - 0.6) * 108.0)) * (1.0 - smoothstep(-1660.0, -780.0, x)) * 12.0
        canyon_shoulder = smoothstep(286.0, 92.0, abs(y - canyon_main_curve)) * 30.0
        canyon_terrace = smoothstep(350.0, 166.0, abs(y - canyon_main_curve)) * 13.0
        canyon_outer_terrace = smoothstep(472.0, 228.0, abs(y - canyon_main_curve)) * 9.5

        river = self.river_distance(x, y)
        river_cut = -smoothstep(self.river_width * 2.1, 0.0, abs(river)) * 52.0
        shore_banks = smoothstep(self.river_width * 3.0, self.river_width * 0.65, abs(river)) * 14.0
        inlet = -smoothstep(130.0, 0.0, math.sqrt((x + 60.0) ** 2 + (y - (self.river_center(-60.0) + 44.0)) ** 2)) * 16.0

        shelves = 0.0
        plateau_mass = max(plateau + broad * 0.14, 0.0)
        if plateau_mass > 40.0:
            shelves = math.floor(plateau_mass / 18.0) * 5.5

        boundary_fill = southwest_mass + east_wall + north_cap + edge_shelf
        boundary_fill += northwest_mass + northeast_mass + southeast_mass + southwest_apron
        boundary_fill += boundary_spine_n + boundary_spine_s + boundary_spine_w + boundary_spine_e
        boundary_fill += north_arc + south_arc + west_arc + east_arc + outer_breakup
        boundary_fill += northeast_plate + northwest_plate + southeast_plate + southwest_plate
        boundary_fill += north_headwall + east_headwall + west_headwall + south_headwall
        boundary_fill += northeast_hook + northwest_hook + southeast_hook + southwest_hook
        boundary_fill += north_barrier + south_barrier + east_barrier + west_barrier + perimeter_step
        boundary_fill += northwest_stitch + northeast_stitch + southwest_stitch + southeast_stitch
        boundary_fill += north_mid_stitch + south_mid_stitch + east_mid_stitch + west_mid_stitch
        boundary_fill += northeast_diagonal + northwest_diagonal + southeast_diagonal + southwest_diagonal
        boundary_fill += north_wide_swell + south_wide_swell + east_wide_swell + west_wide_swell
        boundary_fill += northeast_shoulder + northwest_shoulder + southeast_shoulder + southwest_shoulder
        boundary_fill += perimeter_wave
        z = base + broad + detail
        z += land_crown + basin + outer_ring + boundary_fill
        z += north_wall + south_ridge + west_high + east_break + shoreline_bluff
        z += plateau + canyon_main + canyon_branch + canyon_fork + canyon_west + north_tributary + south_wash + east_wash + west_gully + north_edge_gash + southeast_gash + north_outlet + south_outlet + east_outlet + west_outlet
        z += northwest_drain + northeast_drain + southwest_drain + southeast_drain
        z += north_outlet_wall + south_outlet_wall + east_outlet_wall + west_outlet_wall + canyon_shoulder + canyon_terrace + canyon_outer_terrace
        z += river_cut + shore_banks + inlet + shelves
        z += central_basin * 26.0 + central_apron * 38.0 + east_delta * 24.0 + south_bench * 18.0
        town_mask = max(0.0, 1.0 - math.sqrt(((x - 80.0) / 420.0) ** 2 + ((y - 10.0) / 300.0) ** 2))
        depot_mask = max(0.0, 1.0 - math.sqrt(((x - 190.0) / 280.0) ** 2 + ((y + 160.0) / 210.0) ** 2))
        outskirts_mask = max(0.0, 1.0 - math.sqrt(((x + 120.0) / 960.0) ** 2 + ((y + 120.0) / 700.0) ** 2))
        z = mix(z, 35.0 + broad * 0.18 + base * 0.08, town_mask * 0.40)
        z = mix(z, 29.0 + broad * 0.16, depot_mask * 0.30)
        z = mix(z, z * 0.86 + 24.0, outskirts_mask * 0.10)
        return z

    def terrain_color(self, x: float, y: float, z: float) -> tuple[float, float, float, float]:
        river_abs = abs(self.river_distance(x, y))
        radial = math.sqrt((x / self.far_half_extent) ** 2 + (y / self.far_half_extent) ** 2)
        highland = smoothstep(35.0, 170.0, z)
        mesa = smoothstep(90.0, 230.0, z)
        low_basin = 1.0 - smoothstep(5.0, 65.0, z)
        shore = 1.0 - smoothstep(self.river_width * 3.2, self.river_width * 0.9, river_abs)
        canyon = smoothstep(-70.0, 5.0, z)
        fog_fade = smoothstep(0.72, 1.04, radial)

        low = (0.41, 0.34, 0.23)
        shore_col = (0.54, 0.44, 0.30)
        high = (0.48, 0.36, 0.25)
        rock = (0.56, 0.44, 0.34)
        dry = (0.60, 0.52, 0.40)
        green = (0.34, 0.39, 0.24)

        r, g, b = low
        r = mix(r, green[0], low_basin * 0.22)
        g = mix(g, green[1], low_basin * 0.22)
        b = mix(b, green[2], low_basin * 0.22)
        r = mix(r, shore_col[0], shore * 0.78)
        g = mix(g, shore_col[1], shore * 0.78)
        b = mix(b, shore_col[2], shore * 0.78)
        r = mix(r, high[0], highland * 0.66)
        g = mix(g, high[1], highland * 0.66)
        b = mix(b, high[2], highland * 0.66)
        r = mix(r, rock[0], mesa * 0.84)
        g = mix(g, rock[1], mesa * 0.84)
        b = mix(b, rock[2], mesa * 0.84)
        r = mix(r, dry[0], canyon * 0.30)
        g = mix(g, dry[1], canyon * 0.30)
        b = mix(b, dry[2], canyon * 0.30)
        r = mix(r, 0.78, fog_fade * 0.34)
        g = mix(g, 0.76, fog_fade * 0.34)
        b = mix(b, 0.73, fog_fade * 0.34)
        return (r, g, b, 1.0)

    def sample_normal(self, x: float, y: float, step: float = 5.0) -> Vec3:
        h_l = self.terrain_height(x - step, y)
        h_r = self.terrain_height(x + step, y)
        h_d = self.terrain_height(x, y - step)
        h_u = self.terrain_height(x, y + step)
        n = Vec3(h_l - h_r, h_d - h_u, 2.0 * step)
        n.normalize()
        return n

    def make_grid_mesh(
        self,
        name: str,
        half_extent: float,
        steps: int,
        height_fn: Callable[[float, float], float],
        color_fn: Callable[[float, float, float], tuple[float, float, float, float]],
        hole_half_extent: float | None = None,
        hole_radius: float | None = None,
    ):
        fmt = GeomVertexFormat.getV3n3c4()
        vdata = GeomVertexData(name, fmt, Geom.UHStatic)
        v_writer = GeomVertexWriter(vdata, "vertex")
        n_writer = GeomVertexWriter(vdata, "normal")
        c_writer = GeomVertexWriter(vdata, "color")
        step = (half_extent * 2.0) / steps

        for yi in range(steps + 1):
            y = -half_extent + yi * step
            for xi in range(steps + 1):
                x = -half_extent + xi * step
                z = height_fn(x, y)
                v_writer.addData3(x, y, z)
                n_writer.addData3(self.sample_normal(x, y))
                c_writer.addData4(*color_fn(x, y, z))

        tris = GeomTriangles(Geom.UHStatic)
        row = steps + 1
        for yi in range(steps):
            for xi in range(steps):
                x0 = -half_extent + xi * step
                x1 = x0 + step
                y0 = -half_extent + yi * step
                y1 = y0 + step
                if hole_half_extent is not None:
                    if (
                        abs(x0) < hole_half_extent
                        and abs(x1) < hole_half_extent
                        and abs(y0) < hole_half_extent
                        and abs(y1) < hole_half_extent
                    ):
                        continue
                if hole_radius is not None:
                    cx = x0 + step * 0.5
                    cy = y0 + step * 0.5
                    if math.sqrt(cx * cx + cy * cy) < hole_radius:
                        continue
                i0 = yi * row + xi
                i1 = i0 + 1
                i2 = i0 + row
                i3 = i2 + 1
                tris.addVertices(i0, i2, i1)
                tris.addVertices(i1, i2, i3)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode(name)
        node.addGeom(geom)
        return self.render.attachNewNode(node)

    def create_ribbon(
        self,
        name: str,
        path: list[tuple[float, float]],
        width: float,
        color: tuple[float, float, float, float],
        z_mode: str = "terrain",
        z_bias: float = 0.0,
        constant_z: float | None = None,
    ):
        fmt = GeomVertexFormat.getV3n3c4()
        vdata = GeomVertexData(name, fmt, Geom.UHStatic)
        v_writer = GeomVertexWriter(vdata, "vertex")
        n_writer = GeomVertexWriter(vdata, "normal")
        c_writer = GeomVertexWriter(vdata, "color")
        strip = GeomTristrips(Geom.UHStatic)

        for i, (x, y) in enumerate(path):
            if i == len(path) - 1:
                dx = x - path[i - 1][0]
                dy = y - path[i - 1][1]
            else:
                dx = path[i + 1][0] - x
                dy = path[i + 1][1] - y
            length = max(1e-4, math.sqrt(dx * dx + dy * dy))
            nx = -dy / length
            ny = dx / length
            for side in (-1.0, 1.0):
                px = x + nx * width * 0.5 * side
                py = y + ny * width * 0.5 * side
                if z_mode == "terrain":
                    pz = self.terrain_height(px, py) + z_bias
                    normal = (0, 0, 1)
                else:
                    pz = (constant_z if constant_z is not None else self.water_level) + z_bias
                    normal = (0, 0, 1)
                v_writer.addData3(px, py, pz)
                n_writer.addData3(*normal)
                c_writer.addData4(*color)
        for i in range(len(path) * 2):
            strip.addVertex(i)
        strip.closePrimitive()
        geom = Geom(vdata)
        geom.addPrimitive(strip)
        node = GeomNode(name)
        node.addGeom(geom)
        return self.render.attachNewNode(node)

    def make_box(self, name: str, sx: float, sy: float, sz: float, color: tuple[float, float, float, float]):
        fmt = GeomVertexFormat.getV3n3c4()
        vdata = GeomVertexData(name, fmt, Geom.UHStatic)
        v = GeomVertexWriter(vdata, "vertex")
        n = GeomVertexWriter(vdata, "normal")
        c = GeomVertexWriter(vdata, "color")
        tris = GeomTriangles(Geom.UHStatic)
        hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
        faces = [
            ((0, 0, 1), [(-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]),
            ((0, 0, -1), [(-hx, hy, -hz), (hx, hy, -hz), (hx, -hy, -hz), (-hx, -hy, -hz)]),
            ((0, 1, 0), [(-hx, hy, hz), (hx, hy, hz), (hx, hy, -hz), (-hx, hy, -hz)]),
            ((0, -1, 0), [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz)]),
            ((1, 0, 0), [(hx, -hy, hz), (hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz)]),
            ((-1, 0, 0), [(-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz), (-hx, hy, -hz)]),
        ]
        idx = 0
        for normal, points in faces:
            for p in points:
                v.addData3(*p)
                n.addData3(*normal)
                c.addData4(*color)
            tris.addVertices(idx, idx + 1, idx + 2)
            tris.addVertices(idx, idx + 2, idx + 3)
            idx += 4
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode(name)
        node.addGeom(geom)
        return node

    def _build_world(self) -> None:
        near_terrain = self.make_grid_mesh("near_terrain", self.near_half_extent, self.near_steps, self.terrain_height, self.terrain_color)
        near_terrain.setTwoSided(True)

        seam_outer = self.near_half_extent + 980.0
        lod_transition_outer = self.far_half_extent + 1860.0

        seam_shell = self.make_grid_mesh(
            "seam_shell",
            seam_outer,
            42 if self.proof_mode else 184,
            self.seam_height,
            self.seam_color,
            hole_radius=self.near_half_extent * 0.86,
        )
        seam_shell.setTwoSided(True)
        seam_shell.setBin("background", 3)

        far_shell = self.make_grid_mesh(
            "far_shell",
            self.far_half_extent,
            self.far_steps,
            self.far_height,
            self.far_color,
            hole_radius=seam_outer + 180.0,
        )
        far_shell.setTwoSided(True)
        far_shell.setBin("background", 1)

        lod_transition_shell = self.make_grid_mesh(
            "lod_transition_shell",
            lod_transition_outer,
            36 if self.proof_mode else 140,
            self.lod_transition_height,
            self.lod_transition_color,
            hole_radius=self.far_half_extent + 140.0,
        )
        lod_transition_shell.setTwoSided(True)
        lod_transition_shell.setBin("background", -1)

        lod_shell = self.make_grid_mesh(
            "terrain_lod_shell",
            self.lod_half_extent,
            self.lod_steps,
            self.lod_height,
            self.lod_color,
            hole_radius=lod_transition_outer + 180.0,
        )
        lod_shell.setTwoSided(True)
        lod_shell.setBin("background", -5)
        self._build_water()
        self._build_roads_and_rail()
        self._build_town_streets()
        self._build_settlements()
        self._build_boundary_tracks()
        self._build_bridge()
        self._build_shoreline_structures()
        self._build_outskirt_clusters()
        self._build_lot_boundaries()
        self._build_embankments()
        self._build_telegraph_line()
        self._build_vegetation()
        self._build_landmarks()
        self._build_rim_props()

    def _project_to_radius(self, x: float, y: float, radius: float) -> tuple[float, float]:
        dist = math.sqrt(x * x + y * y)
        if dist < 1e-4:
            return 0.0, 0.0
        s = radius / dist
        return x * s, y * s

    def _near_edge_height(self, x: float, y: float) -> float:
        px, py = self._project_to_radius(x, y, self.near_half_extent - 90.0)
        return self.terrain_height(px, py)

    def _near_edge_color(self, x: float, y: float) -> tuple[float, float, float, float]:
        px, py = self._project_to_radius(x, y, self.near_half_extent - 90.0)
        pz = self.terrain_height(px, py)
        return self.terrain_color(px, py, pz)

    def _far_edge_height(self, x: float, y: float) -> float:
        px, py = self._project_to_radius(x, y, self.far_half_extent - 140.0)
        return self.far_height(px, py)

    def _projected_ring_samples(self, x: float, y: float, radius: float, tangent_offset: float = 220.0) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
        px, py = self._project_to_radius(x, y, radius)
        dist = math.sqrt(x * x + y * y)
        if dist < 1e-4:
            return (px, py), (px, py), (px, py)
        tx = -y / dist
        ty = x / dist
        plus = (px + tx * tangent_offset, py + ty * tangent_offset)
        minus = (px - tx * tangent_offset, py - ty * tangent_offset)
        return (px, py), plus, minus

    def _near_edge_profile(self, x: float, y: float) -> tuple[float, tuple[float, float, float, float], float]:
        center, plus, minus = self._projected_ring_samples(x, y, self.near_half_extent - 90.0, 210.0)
        cz = self.terrain_height(*center)
        pz = self.terrain_height(*plus)
        mz = self.terrain_height(*minus)
        ridge = ((pz + mz) * 0.5 - cz)
        col = self.terrain_color(center[0], center[1], cz)
        return cz, col, ridge

    def _far_edge_profile(self, x: float, y: float) -> tuple[float, tuple[float, float, float, float], float]:
        center, plus, minus = self._projected_ring_samples(x, y, self.far_half_extent - 140.0, 240.0)
        cz = self.far_height(*center)
        pz = self.far_height(*plus)
        mz = self.far_height(*minus)
        ridge = ((pz + mz) * 0.5 - cz)
        col = self.far_color(center[0], center[1], cz)
        return cz, col, ridge

    def seam_height(self, x: float, y: float) -> float:
        dist = math.sqrt(x * x + y * y)
        near_edge_z, _, near_ridge = self._near_edge_profile(x, y)
        far_local_z = self.far_height(x, y)
        seam_t = smoothstep(self.near_half_extent * 0.92, self.near_half_extent * 1.34, dist)
        radial_growth = max(0.0, dist - self.near_half_extent)
        inherited = near_edge_z + near_ridge * 0.90
        growth_noise = (fbm(x * 0.00058 + 8.0, y * 0.00056 - 6.0, 4) - 0.5) * 16.0
        growth_swells = (fbm(x * 0.00030 - 12.0, y * 0.00028 + 7.0, 4) - 0.5) * 34.0
        target = inherited + radial_growth * 0.042 + growth_noise * seam_t + growth_swells * seam_t * 0.82
        target += (far_local_z - inherited) * 0.55 * seam_t
        target += smoothstep(self.near_half_extent * 1.04, self.near_half_extent * 1.32, dist) * near_ridge * 0.55
        return mix(inherited, target, seam_t)

    def seam_color(self, x: float, y: float, z: float) -> tuple[float, float, float, float]:
        dist = math.sqrt(x * x + y * y)
        _, near_col, _ = self._near_edge_profile(x, y)
        far_col = self.far_color(x, y, self.far_height(x, y))
        blend = smoothstep(self.near_half_extent * 0.96, self.near_half_extent * 1.32, dist)
        return (mix(near_col[0], far_col[0], blend), mix(near_col[1], far_col[1], blend), mix(near_col[2], far_col[2], blend), 1.0)

    def lod_transition_height(self, x: float, y: float) -> float:
        dist = math.sqrt(x * x + y * y)
        far_edge_z, _, far_ridge = self._far_edge_profile(x, y)
        lod_z = self.lod_height(x, y)
        blend = smoothstep(self.far_half_extent * 1.00, self.far_half_extent * 1.42, dist)
        radial_growth = max(0.0, dist - self.far_half_extent)
        soft = (fbm(x * 0.00034 + 15.0, y * 0.00036 - 11.0, 3) - 0.5) * 14.0 * blend
        inherited = far_edge_z + far_ridge * 0.80 + radial_growth * 0.018
        target = inherited + (lod_z - inherited) * 0.62 + soft
        return mix(inherited, target, blend)

    def lod_transition_color(self, x: float, y: float, z: float) -> tuple[float, float, float, float]:
        dist = math.sqrt(x * x + y * y)
        _, far_col, _ = self._far_edge_profile(x, y)
        lod_col = self.lod_color(x, y, self.lod_height(x, y))
        blend = smoothstep(self.far_half_extent * 1.02, self.far_half_extent * 1.38, dist)
        return (mix(far_col[0], lod_col[0], blend), mix(far_col[1], lod_col[1], blend), mix(far_col[2], lod_col[2], blend), 1.0)

    def far_height(self, x: float, y: float) -> float:
        local_z = self.terrain_height(x, y)
        radial = math.sqrt((x / self.far_half_extent) ** 2 + (y / self.far_half_extent) ** 2)
        angle = math.atan2(y, x)
        near_edge_z, _, near_ridge = self._near_edge_profile(x, y)
        shell_noise = (fbm(x * 0.00078 + 17.0, y * 0.00078 - 23.0, 4) - 0.5) * 18.0
        shell_swells = (fbm(x * 0.00038 - 41.0, y * 0.00038 + 12.0, 4) - 0.5) * 32.0
        directional_push = (math.sin(angle * 2.3 + 0.6) * 16.0 + math.cos(angle * 3.7 - 1.2) * 10.0) * smoothstep(0.76, 1.04, radial)
        rim_mesas = abs(fbm(x * 0.00052 - 8.0, y * 0.00048 + 11.0, 4) - 0.5) * 22.0 * smoothstep(0.80, 1.02, radial)
        growth = smoothstep(0.74, 1.04, radial)
        inherited = near_edge_z + near_ridge * 0.65
        target = inherited + 18.0 * growth + shell_noise * 0.65 * growth + shell_swells * 0.75 * growth + directional_push + rim_mesas
        target += (local_z - inherited) * 0.28 * smoothstep(0.84, 1.02, radial)
        target -= smoothstep(0.98, 1.10, radial) * 9.0 + 1.0
        return mix(inherited, target, growth)

    def lod_height(self, x: float, y: float) -> float:
        clamped_x = clamp(x, -self.far_half_extent, self.far_half_extent)
        clamped_y = clamp(y, -self.far_half_extent, self.far_half_extent)
        boundary_sample = self.far_height(clamped_x, clamped_y)
        dist = math.sqrt(x * x + y * y)
        if dist < 1e-4:
            dist = 1e-4
        radial = dist / self.lod_half_extent
        angle = math.atan2(y, x)

        far_edge_z, _, far_ridge = self._far_edge_profile(x, y)
        radial_out = max(0.0, dist - self.far_half_extent)
        seam_fade = 1.0 - smoothstep(self.far_half_extent + 300.0, self.far_half_extent + 1500.0, dist)

        nx = x / dist
        ny = y / dist
        north_w = smoothstep(0.10, 0.80, ny)
        south_w = smoothstep(0.10, 0.80, -ny)
        east_w = smoothstep(0.10, 0.80, nx)
        west_w = smoothstep(0.10, 0.80, -nx)
        ne_w = north_w * east_w
        nw_w = north_w * west_w
        se_w = south_w * east_w
        sw_w = south_w * west_w

        overlap_noise = (fbm(x * 0.00056 + 31.0, y * 0.00056 - 12.0, 4) - 0.5) * 38.0
        overlap_swells = (fbm(x * 0.00031 - 22.0, y * 0.00031 + 15.0, 4) - 0.5) * 104.0
        overlap_canyon = -smoothstep(340.0, 0.0, abs(y - math.sin(x * 0.0019 + 0.5) * 200.0)) * seam_fade * 44.0
        overlap_spurs = abs(fbm(x * 0.00074 - 4.0, y * 0.00068 + 9.0, 3) - 0.5) * 42.0 * seam_fade
        inherited_skirt = far_edge_z + far_ridge * 0.78 - 18.0 + radial_out * 0.018
        overlap_target = inherited_skirt + overlap_noise * seam_fade + overlap_swells * seam_fade + overlap_canyon + overlap_spurs
        overlap_target += smoothstep(self.far_half_extent + 80.0, self.far_half_extent + 1780.0, dist) * (boundary_sample * 0.18 + far_ridge * 0.42)

        macro_a = (fbm(x * 0.00015 + 81.0, y * 0.00015 - 27.0, 5) - 0.5) * 600.0
        macro_b = (fbm(x * 0.000082 - 53.0, y * 0.000082 + 66.0, 4) - 0.5) * 500.0
        macro_c = (fbm(x * 0.00022 + 19.0, y * 0.00020 - 41.0, 4) - 0.5) * 250.0
        ridge_field = abs(fbm(x * 0.00036 + 13.0, y * 0.00030 - 9.0, 4) - 0.5) * 360.0
        mesa_field = abs(fbm(x * 0.00027 - 7.0, y * 0.00023 + 14.0, 4) - 0.5) * 240.0
        angle_bias = (math.sin(angle * 2.0 + 0.4) * 180.0 + math.cos(angle * 3.0 - 0.8) * 120.0 + math.sin(angle * 5.0 + 1.2) * 72.0) * smoothstep(0.68, 1.06, radial)

        north_plateau = max(0.0, 1.0 - math.sqrt(((x - 180.0) / 3040.0) ** 2 + ((y - 3280.0) / 920.0) ** 2)) * 420.0
        south_badlands = max(0.0, 1.0 - math.sqrt(((x + 140.0) / 2980.0) ** 2 + ((y + 3340.0) / 980.0) ** 2)) * 330.0
        east_escarpment = max(0.0, 1.0 - math.sqrt(((x - 3620.0) / 980.0) ** 2 + ((y + 80.0) / 3140.0) ** 2)) * 412.0
        west_uplands = max(0.0, 1.0 - math.sqrt(((x + 3720.0) / 1040.0) ** 2 + ((y - 40.0) / 3240.0) ** 2)) * 438.0

        north_headwall = max(0.0, 1.0 - math.sqrt(((x - 120.0) / 2860.0) ** 2 + ((y - 4240.0) / 520.0) ** 2)) * 260.0 * north_w
        south_broken_wall = max(0.0, 1.0 - math.sqrt(((x + 60.0) / 2920.0) ** 2 + ((y + 4320.0) / 620.0) ** 2)) * 214.0 * south_w
        east_longwall = max(0.0, 1.0 - math.sqrt(((x - 4740.0) / 620.0) ** 2 + ((y + 60.0) / 3380.0) ** 2)) * 256.0 * east_w
        west_basin_wall = max(0.0, 1.0 - math.sqrt(((x + 4880.0) / 700.0) ** 2 + ((y - 40.0) / 3520.0) ** 2)) * 286.0 * west_w

        northeast_frontier = max(0.0, 1.0 - math.sqrt(((x - 4100.0) / 1440.0) ** 2 + ((y - 3660.0) / 1120.0) ** 2)) * 346.0
        northwest_frontier = max(0.0, 1.0 - math.sqrt(((x + 4280.0) / 1540.0) ** 2 + ((y - 3780.0) / 1200.0) ** 2)) * 390.0
        southeast_frontier = max(0.0, 1.0 - math.sqrt(((x - 4040.0) / 1420.0) ** 2 + ((y + 3740.0) / 1140.0) ** 2)) * 310.0
        southwest_frontier = max(0.0, 1.0 - math.sqrt(((x + 4200.0) / 1500.0) ** 2 + ((y + 3880.0) / 1220.0) ** 2)) * 366.0

        north_cleft = -smoothstep(420.0, 0.0, abs(x - 220.0 - math.sin(y * 0.00106 + 0.2) * 520.0)) * smoothstep(2400.0, 5200.0, y) * 146.0
        south_cleft = -smoothstep(440.0, 0.0, abs(x + 260.0 - math.sin(y * 0.00102 + 0.9) * 560.0)) * (1.0 - smoothstep(-5200.0, -2400.0, y)) * 136.0
        east_cleft = -smoothstep(400.0, 0.0, abs(y + 160.0 - math.sin(x * 0.00102 - 0.4) * 500.0)) * smoothstep(2600.0, 5200.0, x) * 130.0
        west_cleft = -smoothstep(420.0, 0.0, abs(y - 140.0 - math.sin(x * 0.00104 + 0.7) * 520.0)) * (1.0 - smoothstep(-5200.0, -2600.0, x)) * 142.0

        terrace_seed = max(north_plateau + northeast_frontier * 0.6 + northwest_frontier * 0.7 + east_escarpment * 0.35 + west_uplands * 0.40, 0.0)
        terrace_steps = math.floor(max(0.0, terrace_seed - 50.0) / 26.0) * 10.0 * smoothstep(0.76, 1.08, radial)

        sector_shape = 0.0
        sector_shape += north_w * (north_plateau + north_headwall + ridge_field * 0.26 + mesa_field * 0.18)
        sector_shape += south_w * (south_badlands + south_broken_wall + ridge_field * 0.20 + mesa_field * 0.28)
        sector_shape += east_w * (east_escarpment + east_longwall + ridge_field * 0.22 + mesa_field * 0.16)
        sector_shape += west_w * (west_uplands + west_basin_wall + ridge_field * 0.24 + mesa_field * 0.20)
        sector_shape += ne_w * northeast_frontier + nw_w * northwest_frontier + se_w * southeast_frontier + sw_w * southwest_frontier

        seam_mass_n = max(0.0, 1.0 - math.sqrt(((x - 40.0) / 2520.0) ** 2 + ((y - 2880.0) / 780.0) ** 2)) * 140.0 * seam_fade
        seam_mass_s = max(0.0, 1.0 - math.sqrt(((x + 60.0) / 2480.0) ** 2 + ((y + 2960.0) / 820.0) ** 2)) * 124.0 * seam_fade
        seam_mass_e = max(0.0, 1.0 - math.sqrt(((x - 3180.0) / 860.0) ** 2 + ((y + 60.0) / 2560.0) ** 2)) * 126.0 * seam_fade
        seam_mass_w = max(0.0, 1.0 - math.sqrt(((x + 3260.0) / 940.0) ** 2 + ((y - 40.0) / 2680.0) ** 2)) * 142.0 * seam_fade

        basin_lift = smoothstep(0.58, 1.04, radial) * 180.0
        horizon_drop = smoothstep(0.91, 1.05, radial) * 250.0
        outer_bury = smoothstep(0.978, 1.08, radial) * 240.0

        target = 164.0 + macro_a + macro_b + macro_c + angle_bias
        target += sector_shape
        target += north_cleft + south_cleft + east_cleft + west_cleft
        target += seam_mass_n + seam_mass_s + seam_mass_e + seam_mass_w
        target += basin_lift + terrace_steps - horizon_drop - outer_bury
        inner_blend = smoothstep(self.far_half_extent * 1.06, self.far_half_extent * 1.98, dist)
        return mix(overlap_target, target, inner_blend)

    def far_color(self, x: float, y: float, z: float) -> tuple[float, float, float, float]:
        _, near_edge_col, _ = self._near_edge_profile(x, y)
        local_base = self.terrain_color(x, y, self.terrain_height(x, y))
        dist = math.sqrt(x * x + y * y)
        inherit_t = smoothstep(self.near_half_extent * 0.94, self.far_half_extent * 0.90, dist)
        base = (
            mix(near_edge_col[0], local_base[0], inherit_t * 0.35),
            mix(near_edge_col[1], local_base[1], inherit_t * 0.35),
            mix(near_edge_col[2], local_base[2], inherit_t * 0.35),
            1.0,
        )
        fog_t = smoothstep(self.near_half_extent * 1.08, self.far_half_extent * 0.98, dist)
        return (
            mix(base[0], 0.67, fog_t * 0.22),
            mix(base[1], 0.66, fog_t * 0.22),
            mix(base[2], 0.67, fog_t * 0.22),
            1.0,
        )

    def lod_color(self, x: float, y: float, z: float) -> tuple[float, float, float, float]:
        dist = math.sqrt(x * x + y * y)
        seam_t = smoothstep(self.far_half_extent * 0.96, self.far_half_extent * 1.48, dist)
        fog_t = smoothstep(self.far_half_extent * 1.72, self.lod_half_extent * 0.998, dist)
        base = self.far_color(clamp(x, -self.far_half_extent, self.far_half_extent), clamp(y, -self.far_half_extent, self.far_half_extent), z)
        high = smoothstep(150.0, 520.0, z)
        mesa = smoothstep(260.0, 640.0, z)
        r = mix(base[0], 0.47, seam_t * 0.66)
        g = mix(base[1], 0.39, seam_t * 0.66)
        b = mix(base[2], 0.31, seam_t * 0.66)
        r = mix(r, 0.84, fog_t)
        g = mix(g, 0.86, fog_t)
        b = mix(b, 0.89, fog_t)
        r = mix(r, 0.59, high * 0.28)
        g = mix(g, 0.52, high * 0.28)
        b = mix(b, 0.45, high * 0.28)
        r = mix(r, 0.70, mesa * 0.26)
        g = mix(g, 0.64, mesa * 0.26)
        b = mix(b, 0.58, mesa * 0.26)
        return (r, g, b, 1.0)

    def _build_water(self) -> None:
        path = [(x, self.river_center(x)) for x in range(-1780, 1781, 70)]
        water = self.create_ribbon(
            "river_water",
            path,
            self.river_width * 2.4,
            (0.10, 0.19, 0.23, 0.84),
            z_mode="constant",
            constant_z=self.water_level,
        )
        water.setTransparency(TransparencyAttrib.MAlpha)
        water.setTwoSided(True)
        foam = self.create_ribbon(
            "river_highlight",
            path,
            self.river_width * 1.52,
            (0.18, 0.30, 0.35, 0.34),
            z_mode="constant",
            constant_z=self.water_level + 0.18,
        )
        foam.setTransparency(TransparencyAttrib.MAlpha)
        foam.setTwoSided(True)

        inlet_path = [(-240.0 + t * 24.0, self.river_center(-120.0) + 56.0 + math.sin(t * 0.38) * 7.0 + t * 5.5) for t in range(11)]
        inlet = self.create_ribbon(
            "harbor_inlet",
            inlet_path,
            42.0,
            (0.11, 0.20, 0.24, 0.78),
            z_mode="constant",
            constant_z=self.water_level + 0.08,
        )
        inlet.setTransparency(TransparencyAttrib.MAlpha)
        inlet.setTwoSided(True)

    def _build_roads_and_rail(self) -> None:
        road_path = [(t * 55.0, -45.0 + math.sin(t * 0.34) * 38.0) for t in range(-18, 19)]
        self.create_ribbon("main_road", road_path, 26.0, (0.18, 0.14, 0.12, 1.0), z_mode="terrain", z_bias=0.7)

        spur_path = [(40.0 + t * 40.0, -8.0 + t * 31.0 + math.sin(t * 0.42) * 10.0) for t in range(14)]
        self.create_ribbon("mesa_road", spur_path, 20.0, (0.20, 0.16, 0.12, 1.0), z_mode="terrain", z_bias=0.8)

        ranch_path = [(-260.0 + t * 32.0, 120.0 + math.sin(t * 0.55) * 14.0) for t in range(16)]
        self.create_ribbon("ranch_track", ranch_path, 13.0, (0.23, 0.18, 0.13, 1.0), z_mode="terrain", z_bias=0.65)

        shore_road = [(-210.0 + t * 26.0, self.river_center(-220.0 + t * 26.0) + 96.0 + math.sin(t * 0.33) * 10.0) for t in range(17)]
        self.create_ribbon("shore_road", shore_road, 18.0, (0.22, 0.17, 0.12, 1.0), z_mode="terrain", z_bias=0.82)

        east_connector = [(220.0 + t * 44.0, 74.0 + math.sin(t * 0.28) * 26.0 - t * 8.0) for t in range(12)]
        self.create_ribbon("east_connector", east_connector, 16.0, (0.21, 0.16, 0.11, 1.0), z_mode="terrain", z_bias=0.78)
        south_approach = [(-160.0 + t * 38.0, -220.0 + math.sin(t * 0.34 + 0.2) * 18.0) for t in range(14)]
        self.create_ribbon("south_approach", south_approach, 15.0, (0.21, 0.16, 0.11, 1.0), z_mode="terrain", z_bias=0.75)

        rail_path = [(t * 48.0, -250.0 + math.sin(t * 0.21 + 0.7) * 50.0) for t in range(-18, 19)]
        self.create_ribbon("rail_bed", rail_path, 21.0, (0.22, 0.20, 0.18, 1.0), z_mode="terrain", z_bias=1.0)
        sleeper_model = self.make_box("sleeper", 4.6, 1.4, 0.45, (0.26, 0.18, 0.12, 1.0))
        rail_model = self.make_box("rail", 0.33, 7.4, 0.30, (0.44, 0.42, 0.40, 1.0))
        for i, (x, y) in enumerate(rail_path[:-1]):
            dx = rail_path[i + 1][0] - x
            dy = rail_path[i + 1][1] - y
            h = math.degrees(math.atan2(dx, dy))
            z = self.terrain_height(x, y) + 1.2
            if i % 2 == 0:
                sleeper = self.render.attachNewNode(sleeper_model)
                sleeper.setPos(x, y, z)
                sleeper.setH(h)
            if i % 3 == 0:
                left = self.render.attachNewNode(rail_model)
                left.setPos(x - math.cos(math.radians(h)) * 2.5, y + math.sin(math.radians(h)) * 2.5, z + 0.12)
                left.setH(h)
                right = self.render.attachNewNode(rail_model)
                right.setPos(x + math.cos(math.radians(h)) * 2.5, y - math.sin(math.radians(h)) * 2.5, z + 0.12)
                right.setH(h)

    def _build_boundary_tracks(self) -> None:
        north_track = [(-1480.0 + t * 98.0, 1040.0 + math.sin(t * 0.24) * 52.0) for t in range(33)]
        south_track = [(-1420.0 + t * 94.0, -1040.0 + math.sin(t * 0.31 + 1.2) * 42.0) for t in range(33)]
        west_track = [(-1340.0, -980.0 + t * 88.0) for t in range(25)]
        east_track = [(1320.0, -900.0 + t * 82.0) for t in range(25)]
        northwest_connector = [(-1360.0 + t * 54.0, 720.0 + math.sin(t * 0.34 + 0.2) * 34.0 + t * 16.0) for t in range(11)]
        northeast_connector = [(960.0 + t * 52.0, 760.0 + math.sin(t * 0.30 + 0.5) * 32.0 + t * 14.0) for t in range(10)]
        southeast_connector = [(860.0 + t * 58.0, -640.0 + math.sin(t * 0.28 - 0.2) * 30.0 - t * 18.0) for t in range(10)]
        southwest_connector = [(-940.0 + t * 48.0, -760.0 + math.sin(t * 0.26 + 0.3) * 28.0 - t * 14.0) for t in range(10)]
        self.create_ribbon("north_boundary_track", north_track, 16.0, (0.22, 0.17, 0.12, 1.0), z_mode="terrain", z_bias=0.72)
        self.create_ribbon("south_boundary_track", south_track, 14.0, (0.23, 0.18, 0.13, 1.0), z_mode="terrain", z_bias=0.72)
        self.create_ribbon("west_boundary_track", west_track, 12.0, (0.22, 0.18, 0.12, 1.0), z_mode="terrain", z_bias=0.65)
        self.create_ribbon("east_boundary_track", east_track, 12.0, (0.22, 0.18, 0.12, 1.0), z_mode="terrain", z_bias=0.65)
        self.create_ribbon("northwest_boundary_connector", northwest_connector, 11.0, (0.22, 0.18, 0.12, 1.0), z_mode="terrain", z_bias=0.68)
        self.create_ribbon("northeast_boundary_connector", northeast_connector, 10.5, (0.22, 0.18, 0.12, 1.0), z_mode="terrain", z_bias=0.68)
        self.create_ribbon("southeast_boundary_connector", southeast_connector, 11.0, (0.22, 0.18, 0.12, 1.0), z_mode="terrain", z_bias=0.68)
        self.create_ribbon("southwest_boundary_connector", southwest_connector, 10.5, (0.22, 0.18, 0.12, 1.0), z_mode="terrain", z_bias=0.68)

    def _build_settlements(self) -> None:
        self._build_town_cluster((70.0, -20.0), 34, 1.0)
        self._build_town_cluster((198.0, 64.0), 18, 0.84)
        self._build_town_cluster((-58.0, 82.0), 14, 0.76)
        self._build_town_cluster((-420.0, 170.0), 11, 0.8)
        self._build_town_cluster((308.0, 116.0), 12, 0.72)
        self._build_town_cluster((-210.0, -28.0), 10, 0.68)
        self._build_town_cluster((390.0, -18.0), 9, 0.62)
        self._build_town_cluster((-300.0, -120.0), 8, 0.60)
        self._build_depot((162.0, -178.0))
        self._build_depot((258.0, -132.0))
        self._build_ranch((-280.0, 130.0))
        self._build_ranch((-398.0, 44.0))
        self._build_fort((530.0, 320.0))
        self._build_dock((-120.0, self.river_center(-120.0) + 38.0))

    def _build_town_streets(self) -> None:
        avenue_a = [(-90.0 + t * 26.0, -10.0 + math.sin(t * 0.25) * 8.0) for t in range(15)]
        avenue_b = [(-40.0 + t * 22.0, 78.0 + math.sin(t * 0.32 + 0.8) * 7.0) for t in range(13)]
        avenue_c = [(86.0 + t * 19.0, -92.0 + t * 14.0) for t in range(9)]
        avenue_d = [(140.0 + t * 18.0, 34.0 + math.sin(t * 0.28 + 0.2) * 6.0) for t in range(11)]
        avenue_e = [(-150.0 + t * 20.0, -32.0 + math.sin(t * 0.30 + 0.4) * 7.0) for t in range(10)]
        avenue_f = [(210.0 + t * 18.0, -18.0 + math.sin(t * 0.26 + 0.5) * 5.0) for t in range(9)]
        avenue_g = [(-250.0 + t * 18.0, -112.0 + math.sin(t * 0.22) * 6.0) for t in range(9)]
        for idx, path in enumerate((avenue_a, avenue_b, avenue_c, avenue_d, avenue_e, avenue_f, avenue_g), start=1):
            self.create_ribbon(f"town_street_{idx}", path, 14.0, (0.20, 0.16, 0.12, 1.0), z_mode="terrain", z_bias=0.95)

        crossing_model = self.make_box("rail_crossing", 18.0, 12.0, 0.8, (0.34, 0.28, 0.22, 1.0))
        for x, y in [(-82.0, -232.0), (18.0, -216.0), (112.0, -204.0), (204.0, -188.0), (292.0, -170.0)]:
            slab = self.render.attachNewNode(crossing_model)
            slab.setPos(x, y, self.terrain_height(x, y) + 1.08)
            slab.setH(10.0)

    def _build_town_cluster(self, center: tuple[float, float], count: int, scale: float) -> None:
        house_model = self.make_box("house", 18 * scale, 26 * scale, 12 * scale, (0.47, 0.38, 0.30, 1.0))
        roof_model = self.make_box("roof", 20 * scale, 28 * scale, 3.0 * scale, (0.40, 0.18, 0.11, 1.0))
        tower_model = self.make_box("tower", 12 * scale, 12 * scale, 46 * scale, (0.40, 0.34, 0.28, 1.0))
        sign_model = self.make_box("sign", 4 * scale, 1.2 * scale, 3.4 * scale, (0.34, 0.23, 0.12, 1.0))
        for i in range(count):
            angle = (i / max(1, count)) * math.tau
            radius = 28.0 + (i % 6) * 16.0 + self.random.uniform(-8.0, 10.0)
            x = center[0] + math.cos(angle) * radius + self.random.uniform(-9.0, 9.0)
            y = center[1] + math.sin(angle) * radius + self.random.uniform(-9.0, 9.0)
            z = self.terrain_height(x, y)
            h = self.random.uniform(0.0, 360.0)
            house = self.render.attachNewNode(house_model)
            house.setPos(x, y, z + 6.0 * scale)
            house.setH(h)
            roof = self.render.attachNewNode(roof_model)
            roof.setPos(x, y, z + 13.4 * scale)
            roof.setH(h)
            if i % 5 == 0:
                sign = self.render.attachNewNode(sign_model)
                sign.setPos(x + math.cos(angle) * 9.0 * scale, y + math.sin(angle) * 9.0 * scale, z + 2.8 * scale)
                sign.setH(h)
        tower = self.render.attachNewNode(tower_model)
        tx, ty = center[0] + 46.0 * scale, center[1] - 28.0 * scale
        tower.setPos(tx, ty, self.terrain_height(tx, ty) + 23.0 * scale)

    def _build_depot(self, center: tuple[float, float]) -> None:
        hall_model = self.make_box("depot_hall", 42.0, 22.0, 15.0, (0.46, 0.31, 0.20, 1.0))
        shed_model = self.make_box("depot_shed", 22.0, 16.0, 11.0, (0.42, 0.29, 0.20, 1.0))
        tank_model = self.make_box("water_tank", 10.0, 10.0, 24.0, (0.36, 0.31, 0.28, 1.0))
        crate_model = self.make_box("crate", 5.0, 5.0, 4.0, (0.36, 0.23, 0.14, 1.0))
        cx, cy = center
        hall = self.render.attachNewNode(hall_model)
        hall.setPos(cx, cy, self.terrain_height(cx, cy) + 7.5)
        hall.setH(12.0)
        shed = self.render.attachNewNode(shed_model)
        shed.setPos(cx + 35.0, cy + 18.0, self.terrain_height(cx + 35.0, cy + 18.0) + 5.5)
        shed.setH(-8.0)
        tank = self.render.attachNewNode(tank_model)
        tank.setPos(cx - 42.0, cy + 16.0, self.terrain_height(cx - 42.0, cy + 16.0) + 12.0)
        for ox, oy in [(-20.0, -18.0), (-12.0, -10.0), (10.0, -16.0), (26.0, -12.0), (42.0, -18.0)]:
            crate = self.render.attachNewNode(crate_model)
            x = cx + ox
            y = cy + oy
            crate.setPos(x, y, self.terrain_height(x, y) + 2.0)

    def _build_ranch(self, center: tuple[float, float]) -> None:
        house_model = self.make_box("ranch_house", 28.0, 20.0, 12.0, (0.32, 0.25, 0.18, 1.0))
        barn_model = self.make_box("barn", 24.0, 34.0, 16.0, (0.38, 0.20, 0.12, 1.0))
        fence_model = self.make_box("fence", 18.0, 1.2, 2.0, (0.30, 0.21, 0.14, 1.0))
        cx, cy = center
        hz = self.terrain_height(cx, cy)
        house = self.render.attachNewNode(house_model)
        house.setPos(cx - 12.0, cy, hz + 6.0)
        barn = self.render.attachNewNode(barn_model)
        barn.setPos(cx + 22.0, cy + 12.0, self.terrain_height(cx + 22.0, cy + 12.0) + 8.0)
        for dx in (-28.0, -10.0, 8.0, 26.0):
            north = self.render.attachNewNode(fence_model)
            north.setPos(cx + dx, cy + 26.0, self.terrain_height(cx + dx, cy + 26.0) + 1.1)
            south = self.render.attachNewNode(fence_model)
            south.setPos(cx + dx, cy - 22.0, self.terrain_height(cx + dx, cy - 22.0) + 1.1)
        side_model = self.make_box("fence_side", 1.2, 14.0, 2.0, (0.30, 0.21, 0.14, 1.0))
        for dy in (-16.0, 0.0, 16.0):
            west = self.render.attachNewNode(side_model)
            west.setPos(cx - 36.0, cy + dy, self.terrain_height(cx - 36.0, cy + dy) + 1.1)
            east = self.render.attachNewNode(side_model)
            east.setPos(cx + 38.0, cy + dy, self.terrain_height(cx + 38.0, cy + dy) + 1.1)

    def _build_dock(self, center: tuple[float, float]) -> None:
        deck_model = self.make_box("dock_deck", 38.0, 10.0, 1.2, (0.34, 0.25, 0.16, 1.0))
        side_model = self.make_box("dock_side", 20.0, 8.0, 1.2, (0.30, 0.22, 0.14, 1.0))
        post_model = self.make_box("dock_post", 1.5, 1.5, 9.0, (0.30, 0.22, 0.14, 1.0))
        x, y = center
        deck = self.render.attachNewNode(deck_model)
        deck.setPos(x, y, self.water_level + 1.6)
        side = self.render.attachNewNode(side_model)
        side.setPos(x + 16.0, y + 10.0, self.water_level + 1.6)
        side.setH(78.0)
        for dx in (-12.0, -4.0, 4.0, 12.0):
            for dy in (-3.0, 3.0):
                post = self.render.attachNewNode(post_model)
                post.setPos(x + dx, y + dy, self.water_level - 2.0)

    def _build_fort(self, center: tuple[float, float]) -> None:
        wall_model = self.make_box("fort_wall", 18.0, 62.0, 14.0, (0.50, 0.41, 0.32, 1.0))
        tower_model = self.make_box("fort_tower", 18.0, 18.0, 28.0, (0.46, 0.38, 0.31, 1.0))
        core_model = self.make_box("fort_core", 40.0, 26.0, 16.0, (0.40, 0.31, 0.24, 1.0))
        gate_model = self.make_box("fort_gate", 22.0, 8.0, 18.0, (0.30, 0.21, 0.14, 1.0))
        cx, cy = center
        for dx, dy, h in [(-50.0, 0.0, 90.0), (50.0, 0.0, 90.0), (0.0, -50.0, 0.0), (0.0, 50.0, 0.0)]:
            wall = self.render.attachNewNode(wall_model)
            wall.setPos(cx + dx, cy + dy, self.terrain_height(cx + dx, cy + dy) + 6.0)
            wall.setH(h)
        for dx, dy in [(-50.0, -50.0), (-50.0, 50.0), (50.0, -50.0), (50.0, 50.0)]:
            tower = self.render.attachNewNode(tower_model)
            tower.setPos(cx + dx, cy + dy, self.terrain_height(cx + dx, cy + dy) + 12.0)
        core = self.render.attachNewNode(core_model)
        core.setPos(cx, cy, self.terrain_height(cx, cy) + 7.0)
        gate = self.render.attachNewNode(gate_model)
        gate.setPos(cx, cy - 52.0, self.terrain_height(cx, cy - 52.0) + 9.0)

    def _build_shoreline_structures(self) -> None:
        retaining = self.make_box("retaining_wall", 24.0, 6.0, 6.0, (0.44, 0.37, 0.30, 1.0))
        warehouse = self.make_box("warehouse", 26.0, 18.0, 14.0, (0.50, 0.34, 0.22, 1.0))
        boat = self.make_box("boat", 12.0, 4.0, 2.2, (0.30, 0.18, 0.10, 1.0))
        for x in range(-300, 181, 34):
            y = self.river_center(x) + 82.0
            wall = self.render.attachNewNode(retaining)
            wall.setPos(x, y, self.terrain_height(x, y) + 3.0)
            wall.setH(-8.0)
        for x, y in [(-176.0, self.river_center(-176.0) + 88.0), (-124.0, self.river_center(-124.0) + 92.0), (-72.0, self.river_center(-72.0) + 98.0), (-18.0, self.river_center(-18.0) + 108.0), (42.0, self.river_center(42.0) + 116.0)]:
            wh = self.render.attachNewNode(warehouse)
            wh.setPos(x, y, self.terrain_height(x, y) + 7.0)
            wh.setH(12.0)
        for x, y in [(-240.0, self.river_center(-240.0) + 14.0), (-176.0, self.river_center(-176.0) + 10.0), (-112.0, self.river_center(-112.0) + 5.0), (-52.0, self.river_center(-52.0) - 4.0)]:
            craft = self.render.attachNewNode(boat)
            craft.setPos(x, y, self.water_level + 1.1)
            craft.setH(22.0)


    def _build_outskirt_clusters(self) -> None:
        shack = self.make_box("outskirt_shack", 16.0, 12.0, 9.0, (0.42, 0.31, 0.22, 1.0))
        lean_to = self.make_box("lean_to", 10.0, 8.0, 6.0, (0.34, 0.25, 0.18, 1.0))
        spots = [
            (-520.0, -180.0), (-470.0, -120.0), (-380.0, -150.0),
            (420.0, -80.0), (520.0, -20.0), (620.0, 40.0),
            (-610.0, 220.0), (-540.0, 300.0), (700.0, 180.0),
        ]
        for i, (x, y) in enumerate(spots):
            z = self.terrain_height(x, y)
            node = self.render.attachNewNode(shack if i % 2 == 0 else lean_to)
            node.setPos(x, y, z + (4.5 if i % 2 == 0 else 3.0))
            node.setH((i * 37.0) % 360)

    def _build_lot_boundaries(self) -> None:
        fence_model = self.make_box("lot_fence", 14.0, 0.6, 1.3, (0.40, 0.31, 0.22, 1.0))
        posts_model = self.make_box("lot_post", 0.7, 0.7, 2.2, (0.34, 0.25, 0.18, 1.0))
        lots = [
            (-48.0, 22.0, 76.0, 44.0),
            (36.0, 28.0, 64.0, 40.0),
            (118.0, 18.0, 72.0, 46.0),
            (148.0, 92.0, 58.0, 36.0),
            (-106.0, 102.0, 64.0, 42.0),
            (202.0, -24.0, 78.0, 44.0),
            (252.0, 52.0, 72.0, 42.0),
            (-172.0, 40.0, 84.0, 50.0),
            (4.0, 136.0, 80.0, 46.0),
            (282.0, 110.0, 78.0, 42.0),
            (236.0, -18.0, 74.0, 40.0),
            (-230.0, -20.0, 70.0, 40.0),
        ]
        for cx, cy, sx, sy in lots:
            segments = [
                (cx, cy - sy * 0.5, sx, 0.0),
                (cx, cy + sy * 0.5, sx, 0.0),
                (cx - sx * 0.5, cy, sy, 90.0),
                (cx + sx * 0.5, cy, sy, 90.0),
            ]
            for px, py, length, h in segments:
                fence = self.render.attachNewNode(fence_model)
                fence.setScale(length / 14.0, 1.0, 1.0)
                fence.setPos(px, py, self.terrain_height(px, py) + 1.2)
                fence.setH(h)
            for dx in (-sx * 0.5, sx * 0.5):
                for dy in (-sy * 0.5, sy * 0.5):
                    post = self.render.attachNewNode(posts_model)
                    post.setPos(cx + dx, cy + dy, self.terrain_height(cx + dx, cy + dy) + 1.1)

    def _build_embankments(self) -> None:
        berm_model = self.make_box("berm", 30.0, 10.0, 4.0, (0.46, 0.38, 0.28, 1.0))
        alley_model = self.make_box("service_shed", 10.0, 7.0, 7.5, (0.39, 0.29, 0.20, 1.0))
        for x in range(-240, 301, 36):
            y = self.river_center(x) + 112.0
            berm = self.render.attachNewNode(berm_model)
            berm.setPos(x, y, self.terrain_height(x, y) + 1.8)
            berm.setH(8.0)
        for x, y in [(-84.0, -96.0), (-38.0, -88.0), (-10.0, -72.0), (42.0, -64.0), (96.0, -58.0), (174.0, -46.0), (236.0, -28.0), (286.0, -8.0)]:
            shed = self.render.attachNewNode(alley_model)
            shed.setPos(x, y, self.terrain_height(x, y) + 3.8)
            shed.setH(14.0)

    def _build_telegraph_line(self) -> None:
        pole_model = self.make_box("telegraph_pole", 1.3, 1.3, 16.0, (0.34, 0.25, 0.16, 1.0))
        arm_model = self.make_box("telegraph_arm", 8.0, 0.7, 0.7, (0.38, 0.29, 0.20, 1.0))
        path = [(-520.0 + i * 86.0, -98.0 + math.sin(i * 0.35) * 18.0) for i in range(14)]
        for x, y in path:
            z = self.terrain_height(x, y)
            pole = self.render.attachNewNode(pole_model)
            pole.setPos(x, y, z + 8.0)
            arm = self.render.attachNewNode(arm_model)
            arm.setPos(x, y, z + 14.0)

    def _build_bridge(self) -> None:
        x0, x1 = -210.0, 155.0
        y = self.river_center(-20.0)
        deck_model = self.make_box("bridge_deck", x1 - x0, 22.0, 2.8, (0.38, 0.29, 0.20, 1.0))
        deck = self.render.attachNewNode(deck_model)
        z = max(self.terrain_height(x0, y), self.terrain_height(x1, y), self.water_level + 15.0)
        deck.setPos((x0 + x1) * 0.5, y, z)
        rail_model = self.make_box("bridge_rail", x1 - x0, 1.2, 1.4, (0.30, 0.22, 0.16, 1.0))
        for side in (-8.8, 8.8):
            rail = self.render.attachNewNode(rail_model)
            rail.setPos((x0 + x1) * 0.5, y + side, z + 1.6)
        for px in (-150.0, -60.0, 30.0, 120.0):
            support_model = self.make_box("support", 5.0, 5.0, z - self.water_level + 3.0, (0.22, 0.18, 0.16, 1.0))
            support = self.render.attachNewNode(support_model)
            support.setPos(px, y, (z + self.water_level) * 0.5)

    def _build_vegetation(self) -> None:
        tree_trunk = self.make_box("tree_trunk", 1.2, 1.2, 8.5, (0.32, 0.20, 0.11, 1.0))
        tree_crown = self.make_box("tree_crown", 5.4, 5.4, 5.4, (0.26, 0.36, 0.20, 1.0))
        cactus_model = self.make_box("cactus", 1.9, 1.9, 9.4, (0.28, 0.42, 0.24, 1.0))
        scrub_model = self.make_box("scrub", 3.4, 3.4, 1.3, (0.40, 0.42, 0.24, 1.0))
        placed = 0
        attempts = 0
        while placed < 1180 and attempts < 21000:
            attempts += 1
            x = self.random.uniform(-self.near_half_extent * 0.96, self.near_half_extent * 0.96)
            y = self.random.uniform(-self.near_half_extent * 0.96, self.near_half_extent * 0.96)
            z = self.terrain_height(x, y)
            river_abs = abs(self.river_distance(x, y))
            if river_abs < self.river_width * 1.55:
                if self.random.random() < 0.72:
                    trunk = self.render.attachNewNode(tree_trunk)
                    trunk.setPos(x, y, z + 4.0)
                    crown = self.render.attachNewNode(tree_crown)
                    crown.setPos(x, y, z + 10.5)
                    placed += 1
                continue
            if z > 115.0 and self.random.random() < 0.58:
                scrub = self.render.attachNewNode(scrub_model)
                scrub.setPos(x, y, z + 0.6)
                scrub.setH(self.random.uniform(0.0, 360.0))
                placed += 1
                continue
            if z < 75.0 and self.random.random() < 0.42:
                cactus = self.render.attachNewNode(cactus_model)
                cactus.setPos(x, y, z + 4.4)
                cactus.setH(self.random.uniform(0.0, 360.0))
                placed += 1

    def _build_landmarks(self) -> None:
        monolith = self.render.attachNewNode(self.make_box("mesa_monolith", 14.0, 14.0, 72.0, (0.42, 0.34, 0.27, 1.0)))
        monolith.setPos(375.0, 185.0, self.terrain_height(375.0, 185.0) + 31.0)
        watch = self.render.attachNewNode(self.make_box("watch_post", 10.0, 10.0, 24.0, (0.34, 0.29, 0.24, 1.0)))
        watch.setPos(-520.0, -235.0, self.terrain_height(-520.0, -235.0) + 11.0)
        pillar = self.render.attachNewNode(self.make_box("stone_pillar", 10.0, 10.0, 40.0, (0.40, 0.34, 0.28, 1.0)))
        pillar.setPos(620.0, -260.0, self.terrain_height(620.0, -260.0) + 20.0)
        church = self.render.attachNewNode(self.make_box("church_tower", 14.0, 18.0, 34.0, (0.54, 0.44, 0.34, 1.0)))
        church.setPos(236.0, 108.0, self.terrain_height(236.0, 108.0) + 16.0)
        windmill = self.render.attachNewNode(self.make_box("windmill_tower", 8.0, 8.0, 34.0, (0.50, 0.40, 0.30, 1.0)))
        wx, wy = -310.0, 130.0
        windmill.setPos(wx, wy, self.terrain_height(wx, wy) + 17.0)
        blades = self.render.attachNewNode(self.make_box("windmill_blades", 2.0, 20.0, 2.0, (0.62, 0.56, 0.46, 1.0)))
        blades.setPos(wx, wy, self.terrain_height(wx, wy) + 31.0)
        blades.setP(45.0)

    def _build_rim_props(self) -> None:
        rim_model = self.make_box("rim_stack", 16.0, 16.0, 40.0, (0.52, 0.42, 0.33, 1.0))
        for angle_index in range(52):
            a = (angle_index / 18.0) * math.tau
            r = 1120.0 + (angle_index % 5) * 95.0
            x = math.cos(a) * r
            y = math.sin(a) * r
            z = self.terrain_height(x, y)
            if z < 40.0:
                continue
            stack = self.render.attachNewNode(rim_model)
            stack.setPos(x, y, z + 17.0)
            stack.setH(math.degrees(a) + 20.0)
            stack.setScale(0.78 + (angle_index % 4) * 0.22)

    def _setup_ui(self) -> None:
        self.hud_nodes = []
        self.settings_nodes = []

        hud_bg = DirectFrame(frameColor=(0.04, 0.05, 0.06, 0.72), frameSize=(-0.52, 0.52, -0.10, 0.10), pos=(-1.16, 0, -0.86))
        hud_bg.setScale(0.30)
        self.hud_nodes.append(hud_bg)

        self.hud_text = OnscreenText(
            text="WASD move   RMB look   Q/E vertical   Shift sprint   H HUD   Esc settings   F1 whole map   F2 ground",
            parent=self.aspect2d,
            pos=(-1.27, -0.93),
            align=0,
            scale=0.036,
            fg=(0.82, 0.85, 0.88, 0.95),
            mayChange=True,
        )
        self.hud_nodes.append(self.hud_text)

        self.status_text = OnscreenText(
            text="Clean-Room World v28",
            parent=self.aspect2d,
            pos=(-1.27, 0.94),
            align=0,
            scale=0.038,
            fg=(0.78, 0.83, 0.90, 0.94),
            mayChange=True,
        )
        self.hud_nodes.append(self.status_text)
        if self.capture_path:
            self.hud_text.hide()
            self.status_text.hide()
            self.hud_visible = False

        settings_bg = DirectFrame(frameColor=(0.05, 0.06, 0.08, 0.90), frameSize=(-0.44, 0.44, -0.34, 0.34), pos=(1.08, 0, 0.66))
        settings_bg.setScale(0.38)
        self.settings_nodes.append(settings_bg)
        self.settings_nodes.append(OnscreenText(text="View / Settings", parent=self.aspect2d, pos=(0.80, 0.88), align=0, scale=0.052, fg=(0.90, 0.92, 0.96, 1.0)))
        self.settings_nodes.append(OnscreenText(text="Esc close\nF1 whole-map camera\nF2 ground camera\nMouse stays free until RMB is held\n16:9 framing, center kept clear\nmilestone alignment pass active", parent=self.aspect2d, pos=(0.80, 0.73), align=0, scale=0.042, fg=(0.78, 0.83, 0.90, 0.96)))
        for node in self.settings_nodes:
            node.hide()

    def _bind_controls(self) -> None:
        self.accept("escape", self.toggle_settings)
        self.accept("h", self.toggle_hud)
        self.accept("f1", lambda: self._set_initial_camera("flyover"))
        self.accept("f2", lambda: self._set_initial_camera("ground"))
        self.accept("mouse3", self._reset_camera)

    def _reset_camera(self) -> None:
        self.heading = 24.0
        self.pitch = -18.0
        self.camera.setHpr(self.heading, self.pitch, 0.0)

    def toggle_settings(self) -> None:
        self.settings_visible = not self.settings_visible
        for node in self.settings_nodes:
            node.show() if self.settings_visible else node.hide()

    def toggle_hud(self) -> None:
        self.hud_visible = not self.hud_visible
        for node in self.hud_nodes:
            node.show() if self.hud_visible else node.hide()

    def _set_initial_camera(self, mode: str) -> None:
        if mode == "ground":
            self.camera.setPos(-720.0, -1380.0, self.terrain_height(-720.0, -1380.0) + 205.0)
            self.camera.lookAt(520.0, 260.0, self.terrain_height(520.0, 260.0) + 62.0)
        else:
            self.camera.setPos(-2380.0, -5960.0, 2260.0)
            self.camera.lookAt(280.0, 520.0, self.terrain_height(280.0, 520.0) + 150.0)
        self.heading = self.camera.getH()
        self.pitch = self.camera.getP()

    def _mouse_look(self) -> None:
        watcher = self.mouseWatcherNode
        if watcher is None or not watcher.hasMouse():
            self.mouse_anchor = None
            return
        if not watcher.isButtonDown(MouseButton.three()):
            self.mouse_anchor = None
            return
        mouse = watcher.getMouse()
        current = (mouse.getX(), mouse.getY())
        if self.mouse_anchor is None:
            self.mouse_anchor = current
            return
        dx = current[0] - self.mouse_anchor[0]
        dy = current[1] - self.mouse_anchor[1]
        self.mouse_anchor = current
        self.heading -= dx * 95.0
        self.pitch = clamp(self.pitch + dy * 75.0, -88.0, 88.0)
        self.camera.setHpr(self.heading, self.pitch, 0.0)

    def _update(self, task: Task):
        dt = globalClock.getDt()
        self._mouse_look()

        watcher = self.mouseWatcherNode
        move = Vec3(0, 0, 0)
        if watcher is not None and watcher.isButtonDown(KeyboardButton.asciiKey(b'w')):
            move.y += 1
        if watcher is not None and watcher.isButtonDown(KeyboardButton.asciiKey(b's')):
            move.y -= 1
        if watcher is not None and watcher.isButtonDown(KeyboardButton.asciiKey(b'a')):
            move.x -= 1
        if watcher is not None and watcher.isButtonDown(KeyboardButton.asciiKey(b'd')):
            move.x += 1
        if watcher is not None and watcher.isButtonDown(KeyboardButton.asciiKey(b'q')):
            move.z -= 1
        if watcher is not None and watcher.isButtonDown(KeyboardButton.asciiKey(b'e')):
            move.z += 1
        speed = self.move_speed * (2.2 if watcher is not None and watcher.isButtonDown(KeyboardButton.shift()) else 1.0)
        if move.lengthSquared() > 0.0:
            move.normalize()
            forward = self.camera.getQuat(self.render).getForward()
            right = self.camera.getQuat(self.render).getRight()
            up = Vec3(0, 0, 1)
            self.camera.setPos(self.camera.getPos() + (right * move.x + forward * move.y + up * move.z) * speed * dt)

        cam = self.camera.getPos()
        terrain_z = self.terrain_height(cam.x, cam.y)
        if cam.z < terrain_z + 3.0:
            self.camera.setZ(terrain_z + 3.0)
            cam = self.camera.getPos()
        self.status_text.setText(f"Clean-Room World v32   milestone alignment pass   X {cam.x:7.1f}   Y {cam.y:7.1f}   Z {cam.z:6.1f}")
        return Task.cont

    def _capture_and_quit(self, task: Task):
        for _ in range(18 if self.proof_mode else 12):
            self.graphicsEngine.renderFrame()
        if self.capture_path:
            pnm = PNMImage()
            target = Filename.fromOsSpecific(str(Path(self.capture_path).resolve()))
            if hasattr(self.win, "getScreenshot"):
                self.win.getScreenshot(pnm)
                pnm.write(target)
            else:
                self.win.saveScreenshot(target)
            meta = {
                "camera_mode": self.camera_mode,
                "camera_pos": [round(v, 3) for v in self.camera.getPos()],
                "camera_hpr": [round(v, 3) for v in self.camera.getHpr()],
                "proof_mode": self.proof_mode,
                "timestamp": time.time(),
            }
            Path(self.capture_path).with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)


def configure_prc(offscreen: bool = False) -> None:
    loadPrcFileData("", "sync-video false")
    loadPrcFileData("", f"win-size {VIRTUAL_W} {VIRTUAL_H}")
    loadPrcFileData("", "show-frame-rate-meter false")
    loadPrcFileData("", "audio-library-name null")
    if offscreen:
        loadPrcFileData("", "window-type offscreen")


def write_crash_report(exc: BaseException) -> Path:
    path = LOG_DIR / "cleanroom_world_v32_crash.log"
    path.write_text("".join(traceback.format_exception(exc)), encoding="utf-8")
    return path


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Code RED Clean-Room World v32")
    parser.add_argument("--capture", type=str, default=None)
    parser.add_argument("--camera", type=str, choices=["flyover", "ground"], default="flyover")
    parser.add_argument("--proof", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    configure_prc(offscreen=bool(args.capture))
    app = CleanRoomWorldV32(capture_path=args.capture, camera_mode=args.camera, proof_mode=args.proof)
    app.run()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        report = write_crash_report(exc)
        print(f"Crash report written to {report}", file=sys.stderr)
        raise
