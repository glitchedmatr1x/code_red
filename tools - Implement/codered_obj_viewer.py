#!/usr/bin/env python3
from __future__ import annotations

import math
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox


def load_obj(path: Path, max_vertices: int = 60000):
    vertices = []
    faces = []
    with Path(path).open('r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line.startswith('v '):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
                    except Exception:
                        pass
            elif line.startswith('f '):
                idxs = []
                for token in line.split()[1:]:
                    try:
                        idxs.append(int(token.split('/')[0]) - 1)
                    except Exception:
                        pass
                if len(idxs) >= 3:
                    faces.append(tuple(idxs[:3]))
    if len(vertices) > max_vertices:
        step = max(1, len(vertices) // max_vertices)
        vertices = vertices[::step][:max_vertices]
        # Faces no longer match after sampling, so draw point cloud only.
        faces = []
    return vertices, faces


class OBJViewer(tk.Tk):
    def __init__(self, obj_path: Path | None = None):
        super().__init__()
        self.title('Code RED OBJ Viewer')
        self.geometry('1100x760')
        self.configure(bg='#090909')
        self.vertices = []
        self.faces = []
        self.path = None
        self.rot_x = math.radians(-18)
        self.rot_y = math.radians(28)
        self.zoom = 1.0
        self.pan = [0.0, 0.0]
        self.last = None
        self.status = tk.StringVar(value='Open an OBJ preview.')
        bar = tk.Frame(self, bg='#111111')
        bar.pack(fill='x')
        tk.Button(bar, text='Open OBJ', command=self.open_dialog, bg='#202020', fg='white', relief='flat', padx=12, pady=6).pack(side='left', padx=4, pady=4)
        tk.Button(bar, text='Reset View', command=self.reset_view, bg='#202020', fg='white', relief='flat', padx=12, pady=6).pack(side='left', padx=4, pady=4)
        tk.Label(bar, textvariable=self.status, bg='#111111', fg='#dddddd', anchor='w').pack(side='left', fill='x', expand=True, padx=8)
        self.canvas = tk.Canvas(self, bg='#050505', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda e: self.draw())
        self.canvas.bind('<ButtonPress-1>', self.on_down)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<MouseWheel>', self.on_wheel)
        self.canvas.bind('<Button-4>', lambda e: self.zoom_by(1.12))
        self.canvas.bind('<Button-5>', lambda e: self.zoom_by(1/1.12))
        self.bind('r', lambda e: self.reset_view())
        self.bind('o', lambda e: self.open_dialog())
        if obj_path:
            self.load(obj_path)

    def open_dialog(self):
        path = filedialog.askopenfilename(title='Open OBJ preview', filetypes=[('OBJ files', '*.obj'), ('All files', '*.*')])
        if path:
            self.load(Path(path))

    def reset_view(self):
        self.rot_x = math.radians(-18)
        self.rot_y = math.radians(28)
        self.zoom = 1.0
        self.pan = [0.0, 0.0]
        self.draw()

    def load(self, path: Path):
        try:
            self.vertices, self.faces = load_obj(path)
        except Exception as exc:
            messagebox.showerror('OBJ load failed', str(exc), parent=self)
            return
        self.path = Path(path)
        self.status.set(f'{self.path.name} | vertices={len(self.vertices):,} faces={len(self.faces):,} | drag=rotate, wheel=zoom, R=reset')
        self.draw()

    def on_down(self, event):
        self.last = (event.x, event.y)

    def on_drag(self, event):
        if self.last is None:
            self.last = (event.x, event.y)
            return
        dx = event.x - self.last[0]
        dy = event.y - self.last[1]
        self.rot_y += dx * 0.008
        self.rot_x += dy * 0.008
        self.last = (event.x, event.y)
        self.draw()

    def on_wheel(self, event):
        self.zoom_by(1.12 if event.delta > 0 else 1 / 1.12)

    def zoom_by(self, factor):
        self.zoom = max(0.05, min(100.0, self.zoom * factor))
        self.draw()

    def projected(self):
        if not self.vertices:
            return []
        xs = [p[0] for p in self.vertices]
        ys = [p[1] for p in self.vertices]
        zs = [p[2] for p in self.vertices]
        cx = (min(xs) + max(xs)) * 0.5
        cy = (min(ys) + max(ys)) * 0.5
        cz = (min(zs) + max(zs)) * 0.5
        span = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs), 1e-6)
        sx = math.sin(self.rot_x); cxr = math.cos(self.rot_x)
        sy = math.sin(self.rot_y); cyr = math.cos(self.rot_y)
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        scale = min(w, h) * 0.78 * self.zoom / span
        out = []
        for x, y, z in self.vertices:
            x -= cx; y -= cy; z -= cz
            x2 = x * cyr + z * sy
            z2 = -x * sy + z * cyr
            y2 = y * cxr - z2 * sx
            z3 = y * sx + z2 * cxr
            px = w * 0.5 + self.pan[0] + x2 * scale
            py = h * 0.5 + self.pan[1] - y2 * scale
            out.append((px, py, z3))
        return out

    def draw(self):
        self.canvas.delete('all')
        pts = self.projected()
        if not pts:
            self.canvas.create_text(40, 40, anchor='nw', fill='#dddddd', text='Open an OBJ preview to view it here.')
            return
        if self.faces:
            # Painter-ish draw by average depth. Outlines only keeps false preview faces readable.
            face_rows = []
            for a, b, c in self.faces[:20000]:
                if 0 <= a < len(pts) and 0 <= b < len(pts) and 0 <= c < len(pts):
                    z = (pts[a][2] + pts[b][2] + pts[c][2]) / 3.0
                    face_rows.append((z, a, b, c))
            face_rows.sort()
            for _, a, b, c in face_rows:
                coords = (pts[a][0], pts[a][1], pts[b][0], pts[b][1], pts[c][0], pts[c][1])
                self.canvas.create_polygon(coords, outline='#38d8ff', fill='', width=1)
        else:
            skip = max(1, len(pts) // 45000)
            for i in range(0, len(pts), skip):
                x, y, _ = pts[i]
                self.canvas.create_rectangle(x, y, x+1, y+1, outline='#38d8ff')
        name = self.path.name if self.path else 'OBJ'
        self.canvas.create_text(10, 10, anchor='nw', fill='#e8e8e8', text=name)


def main(argv=None):
    argv = argv or sys.argv[1:]
    path = Path(argv[0]) if argv else None
    app = OBJViewer(path)
    app.mainloop()


if __name__ == '__main__':
    main()
