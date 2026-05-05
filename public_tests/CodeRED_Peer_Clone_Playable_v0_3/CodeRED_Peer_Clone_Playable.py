#!/usr/bin/env python3
"""
Code RED Peer Clone Playable v0.3
Portable two-player sandbox for proving live peer/clone movement before game hooks.
No third-party dependencies: Python standard library only.
"""
from __future__ import annotations

import argparse
import json
import math
import queue
import random
import socket
import socketserver
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

APP_NAME = "Code RED Peer Clone Playable v0.3"
PROTOCOL = "codered.peer.clone.v1"
DEFAULT_PORT = 47666
ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "runtime"
RUNTIME.mkdir(exist_ok=True)


def now_ms() -> int:
    return int(time.time() * 1000)


def send_json(file_obj, payload: dict) -> None:
    file_obj.write((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))
    file_obj.flush()


def append_jsonl(filename: str, payload: dict) -> None:
    with (RUNTIME / filename).open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, separators=(",", ":")) + "\n")


class RelayState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.clients: Dict[str, dict] = {}


class ThreadedRelay(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class RelayHandler(socketserver.BaseRequestHandler):
    def setup(self) -> None:
        self.client_id = ""
        self.file = self.request.makefile("rwb")

    def roster(self):
        with self.server.state.lock:  # type: ignore[attr-defined]
            return [
                {
                    "client_id": cid,
                    "name": c["name"],
                    "actor": c["actor"],
                    "color": c.get("color", "red"),
                    "addr": c["addr"],
                }
                for cid, c in self.server.state.clients.items()  # type: ignore[attr-defined]
            ]

    def broadcast(self, payload: dict, include_self: bool = False) -> None:
        with self.server.state.lock:  # type: ignore[attr-defined]
            clients = list(self.server.state.clients.values())  # type: ignore[attr-defined]
        for client in clients:
            if not include_self and client["id"] == self.client_id:
                continue
            try:
                send_json(client["file"], payload)
            except Exception:
                pass

    def handle(self) -> None:
        try:
            line = self.file.readline()
            if not line:
                return
            hello = json.loads(line.decode("utf-8", errors="replace"))
            if hello.get("type") != "hello" or hello.get("protocol") != PROTOCOL:
                send_json(self.file, {"type": "error", "error": "bad protocol", "expected": PROTOCOL})
                return

            self.client_id = str(hello.get("client_id") or f"peer_{random.randint(1000, 9999)}")[:64]
            name = str(hello.get("name") or self.client_id)[:64]
            actor = str(hello.get("actor") or "ACTOR_player_jack")[:96]
            color = str(hello.get("color") or "red")[:32]

            with self.server.state.lock:  # type: ignore[attr-defined]
                self.server.state.clients[self.client_id] = {  # type: ignore[attr-defined]
                    "id": self.client_id,
                    "name": name,
                    "actor": actor,
                    "color": color,
                    "addr": f"{self.client_address[0]}:{self.client_address[1]}",
                    "file": self.file,
                }
                roster = self.roster()

            print(f"[relay] joined {self.client_id} {name} from {self.client_address[0]}:{self.client_address[1]}", flush=True)
            send_json(self.file, {"type": "welcome", "protocol": PROTOCOL, "client_id": self.client_id, "roster": roster, "server_ms": now_ms()})
            self.broadcast({"type": "peer_joined", "peer": self.client_id, "roster": roster, "server_ms": now_ms()})

            while True:
                line = self.file.readline()
                if not line:
                    break
                payload = json.loads(line.decode("utf-8", errors="replace"))
                msg_type = payload.get("type")
                if msg_type == "bye":
                    break
                if msg_type == "ping":
                    send_json(self.file, {"type": "pong", "roster": self.roster(), "server_ms": now_ms()})
                    continue
                if msg_type not in {"state", "event"}:
                    send_json(self.file, {"type": "error", "error": f"unknown type {msg_type}"})
                    continue
                payload.update({"protocol": PROTOCOL, "client_id": self.client_id, "relay_ms": now_ms()})
                append_jsonl("relay_messages.jsonl", payload)
                self.broadcast(payload)
        except Exception as exc:
            print(f"[relay] error {self.client_id or self.client_address}: {exc}", flush=True)
        finally:
            if self.client_id:
                with self.server.state.lock:  # type: ignore[attr-defined]
                    self.server.state.clients.pop(self.client_id, None)  # type: ignore[attr-defined]
                    roster = self.roster()
                self.broadcast({"type": "peer_left", "client_id": self.client_id, "roster": roster, "server_ms": now_ms()})
                print(f"[relay] left {self.client_id}", flush=True)


def start_relay(bind: str, port: int) -> ThreadedRelay:
    relay = ThreadedRelay((bind, port), RelayHandler)
    relay.state = RelayState()  # type: ignore[attr-defined]
    thread = threading.Thread(target=relay.serve_forever, kwargs={"poll_interval": 0.25}, daemon=True)
    relay._codered_thread = thread  # type: ignore[attr-defined]
    thread.start()
    print(f"# {APP_NAME} Relay\nlistening={bind}:{port}\n", flush=True)
    return relay


def stop_relay(relay: ThreadedRelay) -> None:
    relay.shutdown()
    relay.server_close()
    try:
        relay._codered_thread.join(1)  # type: ignore[attr-defined]
    except Exception:
        pass


def host_forever(bind: str, port: int) -> None:
    relay = start_relay(bind, port)
    print("Keep this window open. Press Ctrl+C to stop.", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[relay] stopping", flush=True)
    finally:
        stop_relay(relay)


def local_ip_candidates():
    ips = []
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip not in ips:
            ips.append(ip)
    except Exception:
        pass
    if "127.0.0.1" not in ips:
        ips.append("127.0.0.1")
    return ips


def doctor() -> None:
    print(f"# {APP_NAME} Doctor")
    print(f"python={sys.version.split()[0]}")
    print(f"default_port={DEFAULT_PORT}/tcp")
    print("local_ip_candidates:")
    for ip in local_ip_candidates():
        print(f" - {ip}")
    print("\nGive your tester the LAN/VPN IP, not 127.0.0.1.")
    print("If remote join fails, allow Python through Windows Firewall or use Radmin/ZeroTier/Hamachi.")


@dataclass
class RemotePeer:
    client_id: str
    name: str = "Remote"
    actor: str = "ACTOR_mpplayer01"
    color: str = "orange"
    x: float = 0.0
    y: float = 0.0
    heading: float = 0.0
    action: str = "idle"
    health: int = 100
    last_ms: int = 0
    pulse_id: int = 0


class NetClient:
    def __init__(self, host: str, port: int, client_id: str, name: str, actor: str, color: str):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.name = name
        self.actor = actor
        self.color = color
        self.sock: Optional[socket.socket] = None
        self.file = None
        self.inbox: "queue.Queue[dict]" = queue.Queue()
        self.connected = False
        self.stop = False

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=8)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.file = self.sock.makefile("rwb")
        send_json(self.file, {
            "type": "hello", "protocol": PROTOCOL, "client_id": self.client_id,
            "name": self.name, "actor": self.actor, "color": self.color, "client_ms": now_ms(),
        })
        welcome = None
        deadline = time.time() + 8
        while time.time() < deadline:
            line = self.file.readline()
            if not line:
                break
            msg = json.loads(line.decode("utf-8", errors="replace"))
            if msg.get("type") == "welcome":
                welcome = msg
                break
            self.inbox.put(msg)
        if not welcome:
            raise RuntimeError("Relay did not send welcome before timeout")
        self.connected = True
        self.inbox.put(welcome)
        threading.Thread(target=self._rx, daemon=True).start()

    def _rx(self) -> None:
        try:
            while not self.stop and self.file:
                line = self.file.readline()
                if not line:
                    break
                self.inbox.put(json.loads(line.decode("utf-8", errors="replace")))
        except Exception as exc:
            self.inbox.put({"type": "local_error", "error": str(exc)})
        finally:
            self.connected = False

    def send_state(self, state: dict) -> None:
        if self.file and self.connected:
            send_json(self.file, state)

    def send_event(self, event: dict) -> None:
        if self.file and self.connected:
            send_json(self.file, event)

    def close(self) -> None:
        self.stop = True
        try:
            if self.file:
                send_json(self.file, {"type": "bye", "client_ms": now_ms()})
        except Exception:
            pass
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass


class HeadlessClient(NetClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.remote_seen: Dict[str, dict] = {}

    def run(self, seconds: float = 2.0, rate: float = 12.0) -> None:
        self.connect()
        start = time.time()
        seq = 0
        while time.time() - start < seconds:
            seq += 1
            angle = time.time() * 0.9 + (sum(map(ord, self.client_id)) % 360)
            state = {
                "type": "state", "protocol": PROTOCOL, "client_ms": now_ms(), "seq": seq,
                "name": self.name, "actor": self.actor, "color": self.color,
                "x": round(math.cos(angle) * 120, 2), "y": round(math.sin(angle) * 120, 2),
                "heading": round((math.degrees(angle) + 90) % 360, 2), "action": "walk",
                "health": 100, "pulse_id": 0,
            }
            self.send_state(state)
            while True:
                try:
                    msg = self.inbox.get_nowait()
                except queue.Empty:
                    break
                if msg.get("type") == "state" and msg.get("client_id") != self.client_id:
                    self.remote_seen[msg["client_id"]] = msg
            time.sleep(1.0 / rate)
        self.close()


def selftest() -> int:
    port = random.randint(49100, 59900)
    relay = start_relay("127.0.0.1", port)
    time.sleep(0.2)
    a = HeadlessClient("127.0.0.1", port, "player_a", "Player A", "ACTOR_player_jack", "red")
    b = HeadlessClient("127.0.0.1", port, "player_b", "Player B", "ACTOR_mpplayer01", "cyan")
    ta = threading.Thread(target=a.run)
    tb = threading.Thread(target=b.run)
    ta.start(); tb.start(); ta.join(5); tb.join(5)
    time.sleep(0.2)
    stop_relay(relay)
    ok_a = "player_b" in a.remote_seen
    ok_b = "player_a" in b.remote_seen
    print(f"# Selftest result: {'PASS' if ok_a and ok_b else 'FAIL'}")
    print(f"player_a saw player_b: {ok_a}")
    print(f"player_b saw player_a: {ok_b}")
    return 0 if ok_a and ok_b else 1


def run_playable(args) -> None:
    try:
        import tkinter as tk
    except Exception as exc:
        print("Tkinter is required for playable mode but was not available:", exc)
        return

    relay = None
    if args.start_relay:
        relay = start_relay(args.bind, args.port)
        time.sleep(0.25)

    client = NetClient(args.host, args.port, args.client_id, args.name, args.actor, args.color)
    try:
        client.connect()
    except Exception:
        if relay:
            stop_relay(relay)
        raise

    root = tk.Tk()
    root.title(f"{APP_NAME} - {args.name}")
    root.geometry("960x720")
    root.configure(bg="#111111")

    canvas = tk.Canvas(root, width=920, height=620, bg="#141414", highlightthickness=1, highlightbackground="#660000")
    canvas.pack(padx=10, pady=10)
    status = tk.Label(root, text="Connecting...", fg="#f0f0f0", bg="#111111", anchor="w")
    status.pack(fill="x", padx=12)
    help_label = tk.Label(root, text="WASD / arrows move | Shift boost | Space pulse | Q quit", fg="#ff5555", bg="#111111", anchor="w")
    help_label.pack(fill="x", padx=12)

    width, height = 920, 620
    player = {"x": 0.0, "y": 0.0, "heading": 0.0, "health": 100, "pulse_id": 0, "action": "idle"}
    keys = set()
    remotes: Dict[str, RemotePeer] = {}
    last_send = 0.0
    seq = 0
    trail = []
    messages = []

    def world_to_screen(x: float, y: float) -> Tuple[float, float]:
        return width / 2 + x, height / 2 - y

    def draw_grid():
        for gx in range(-400, 401, 100):
            x1, y1 = world_to_screen(gx, -300)
            x2, y2 = world_to_screen(gx, 300)
            canvas.create_line(x1, y1, x2, y2, fill="#282828")
        for gy in range(-300, 301, 100):
            x1, y1 = world_to_screen(-400, gy)
            x2, y2 = world_to_screen(400, gy)
            canvas.create_line(x1, y1, x2, y2, fill="#282828")
        canvas.create_text(12, 12, text="CODE RED PEER CLONE PLAYABLE", fill="#ff3333", anchor="nw", font=("Consolas", 14, "bold"))

    def draw_actor(x, y, heading, color, label, remote=False, pulse=0):
        sx, sy = world_to_screen(x, y)
        r = 14 if not remote else 12
        outline = "#ffffff" if not remote else "#aaaaaa"
        canvas.create_oval(sx-r, sy-r, sx+r, sy+r, fill=color, outline=outline, width=2)
        hx = sx + math.cos(math.radians(heading - 90)) * 24
        hy = sy + math.sin(math.radians(heading - 90)) * 24
        canvas.create_line(sx, sy, hx, hy, fill="#ffffff", width=2)
        canvas.create_text(sx, sy - 25, text=label, fill="#ffffff", font=("Consolas", 10, "bold"))
        if pulse:
            phase = (time.time() * 8) % 1
            pr = 24 + phase * 36
            canvas.create_oval(sx-pr, sy-pr, sx+pr, sy+pr, outline=color, width=2)

    def on_key_down(event):
        key = event.keysym.lower()
        if key == "q":
            close()
            return
        if key == "space":
            player["pulse_id"] += 1
            player["action"] = "pulse"
            client.send_event({"type": "event", "event": "pulse", "pulse_id": player["pulse_id"], "x": player["x"], "y": player["y"], "client_ms": now_ms()})
        keys.add(key)

    def on_key_up(event):
        keys.discard(event.keysym.lower())

    def process_inbox():
        while True:
            try:
                msg = client.inbox.get_nowait()
            except queue.Empty:
                break
            t = msg.get("type")
            if t == "state" and msg.get("client_id") != client.client_id:
                rid = msg.get("client_id")
                peer = remotes.get(rid) or RemotePeer(client_id=rid)
                peer.name = str(msg.get("name") or rid)
                peer.actor = str(msg.get("actor") or peer.actor)
                peer.color = str(msg.get("color") or peer.color)
                peer.x = float(msg.get("x", peer.x))
                peer.y = float(msg.get("y", peer.y))
                peer.heading = float(msg.get("heading", peer.heading))
                peer.action = str(msg.get("action") or "idle")
                peer.health = int(msg.get("health", 100))
                peer.pulse_id = int(msg.get("pulse_id", peer.pulse_id))
                peer.last_ms = now_ms()
                remotes[rid] = peer
                append_jsonl(f"{client.client_id}_remote_playable.jsonl", msg)
            elif t == "event" and msg.get("client_id") != client.client_id:
                messages.append((time.time(), f"{msg.get('client_id')} {msg.get('event')}"))
            elif t in {"welcome", "peer_joined", "peer_left", "local_error", "error"}:
                messages.append((time.time(), json.dumps(msg)[:120]))

    def tick():
        nonlocal last_send, seq
        process_inbox()
        speed = 4.5 if "shift_l" in keys or "shift_r" in keys or "shift" in keys else 2.5
        dx = dy = 0
        if "w" in keys or "up" in keys: dy += speed
        if "s" in keys or "down" in keys: dy -= speed
        if "a" in keys or "left" in keys: dx -= speed
        if "d" in keys or "right" in keys: dx += speed
        if dx or dy:
            player["x"] = max(-420, min(420, player["x"] + dx))
            player["y"] = max(-280, min(280, player["y"] + dy))
            player["heading"] = (math.degrees(math.atan2(dx, dy)) + 360) % 360
            player["action"] = "boost" if speed > 3 else "walk"
            trail.append((player["x"], player["y"], time.time()))
        else:
            if player["action"] != "pulse":
                player["action"] = "idle"
        if player["action"] == "pulse" and random.random() < 0.15:
            player["action"] = "idle"
        trail[:] = [p for p in trail if time.time() - p[2] < 1.5]

        now = time.time()
        if now - last_send >= 1 / max(1, args.rate):
            seq += 1
            last_send = now
            client.send_state({
                "type": "state", "protocol": PROTOCOL, "client_ms": now_ms(), "seq": seq,
                "name": client.name, "actor": client.actor, "color": client.color,
                "x": round(player["x"], 2), "y": round(player["y"], 2), "z": 0.0,
                "heading": round(player["heading"], 2), "action": player["action"],
                "health": player["health"], "pulse_id": player["pulse_id"],
            })

        canvas.delete("all")
        draw_grid()
        for x, y, age in trail:
            sx, sy = world_to_screen(x, y)
            canvas.create_oval(sx-3, sy-3, sx+3, sy+3, fill="#772222", outline="")
        draw_actor(player["x"], player["y"], player["heading"], client.color, f"YOU {client.name}", False, player["pulse_id"] if player["action"] == "pulse" else 0)
        for rid, peer in list(remotes.items()):
            stale = now_ms() - peer.last_ms > 2500
            label = f"{peer.name}{' (stale)' if stale else ''}"
            draw_actor(peer.x, peer.y, peer.heading, peer.color if not stale else "#555555", label, True, peer.pulse_id if peer.action == "pulse" else 0)
        y = 40
        for ts, msg in messages[-6:]:
            if time.time() - ts < 8:
                canvas.create_text(12, y, text=msg, fill="#dddddd", anchor="nw", font=("Consolas", 9))
                y += 16
        status.config(text=f"Connected to {args.host}:{args.port} as {client.client_id} | remotes={len(remotes)} | pos=({player['x']:.0f},{player['y']:.0f}) action={player['action']}")
        root.after(16, tick)

    def close():
        client.close()
        if relay:
            stop_relay(relay)
        root.destroy()

    root.bind("<KeyPress>", on_key_down)
    root.bind("<KeyRelease>", on_key_up)
    root.protocol("WM_DELETE_WINDOW", close)
    tick()
    root.mainloop()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    sub = parser.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("host")
    h.add_argument("--bind", default="0.0.0.0")
    h.add_argument("--port", type=int, default=DEFAULT_PORT)

    p = sub.add_parser("play")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--bind", default="0.0.0.0")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--client-id", default="player_a")
    p.add_argument("--name", default="Player A")
    p.add_argument("--actor", default="ACTOR_player_jack")
    p.add_argument("--color", default="red")
    p.add_argument("--rate", type=float, default=20)
    p.add_argument("--start-relay", action="store_true")

    sub.add_parser("doctor")
    sub.add_parser("selftest")
    args = parser.parse_args(argv)

    if args.cmd == "host":
        host_forever(args.bind, args.port)
    elif args.cmd == "play":
        run_playable(args)
    elif args.cmd == "doctor":
        doctor()
    elif args.cmd == "selftest":
        return selftest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
