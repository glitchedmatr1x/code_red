
from __future__ import annotations
import argparse
import sys
from pathlib import Path

def main() -> int:
    ap = argparse.ArgumentParser(description="Minimal Panda3D probe scene for Code RED related apps.")
    ap.add_argument("--screenshot", default="panda3d_probe.png")
    args = ap.parse_args()
    try:
        from panda3d.core import loadPrcFileData, Vec4, LineSegs, AntialiasAttrib
        loadPrcFileData("", "window-type offscreen")
        loadPrcFileData("", "audio-library-name null")
        loadPrcFileData("", "win-size 960 540")
        from direct.showbase.ShowBase import ShowBase
    except Exception as exc:
        print(f"Panda3D unavailable: {exc}")
        return 2
    app = ShowBase(windowType="offscreen")
    app.setBackgroundColor(0.02, 0.01, 0.014, 1)
    segs = LineSegs("code-red-grid")
    segs.setThickness(2.0)
    segs.setColor(1.0, 0.12, 0.22, 1.0)
    for i in range(-8, 9):
        segs.moveTo(i, 12, 0); segs.drawTo(i, -12, 0)
        segs.moveTo(-8, i * 1.5, 0); segs.drawTo(8, i * 1.5, 0)
    grid = app.render.attachNewNode(segs.create())
    grid.setAntialias(AntialiasAttrib.MLine)
    app.camera.setPos(0, -24, 13)
    app.camera.lookAt(0, 0, 0)
    app.graphicsEngine.renderFrame()
    app.graphicsEngine.renderFrame()
    ok = app.win.saveScreenshot(str(Path(args.screenshot).resolve()))
    app.destroy()
    print(f"screenshot_saved={bool(ok)} path={Path(args.screenshot).resolve()}")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
