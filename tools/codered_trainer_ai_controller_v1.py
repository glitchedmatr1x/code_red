#!/usr/bin/env python3
"""
CodeRED Trainer AI Controller v1.

Adds a roster-driven NPC/model switcher for trainer-spawned actors. The controller writes
state and an action plan that a game-side ScriptHook/trainer bridge can consume.

Offline/private singleplayer tool only. It does not connect to Xenia or public online services.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

try:
    from codered_npc_roster import RosterEntry, default_source_paths, extract_from_text, load_roster_files, save_roster, scan_binary_archive
except ImportError:  # direct execution from another cwd
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from codered_npc_roster import RosterEntry, default_source_paths, extract_from_text, load_roster_files, save_roster, scan_binary_archive

VERSION = "1.0.0-trainer-ai-npc-switcher"
COMMANDS = {
    "spawn": "request spawn with selected model",
    "follow": "follow player",
    "guard": "guard current position/player area",
    "defend": "follow and defend player",
    "attack": "attack hostiles near player",
    "regroup": "warp/regroup near player",
    "mount": "request mount behavior",
    "dismount": "request dismount behavior",
    "idle": "clear movement/combat task",
    "dismiss": "dismiss AI guest",
    "status": "print and write current state",
    "npc-list [filter]": "show model roster; filter by gent/gped/amb/name/category",
    "npc-next [filter]": "cycle to next model; optional filtered cycle",
    "npc-prev [filter]": "cycle to previous model; optional filtered cycle",
    "npc-set <index|name|query>": "select model by visible index, exact name, or search text",
    "npc-filter <text>": "set persistent cycling/list filter",
    "npc-scan <path>": "scan an RPF/archive/list and merge discovered names into scratch roster",
    "help": "show commands",
    "exit": "quit console",
}

DEFAULT_PROFILE = {
    "version": 1,
    "tool": VERSION,
    "label": "CodeRED_AI_01",
    "selected_model": "amb_fh_farmer06",
    "selected_model_filter": "",
    "follow_distance": 8.0,
    "guard_radius": 14.0,
    "warp_distance": 80.0,
    "attack_hostiles": True,
    "avoid_friendly_fire": True,
    "respawn_if_dead": True,
    "roster_sources": [
        "data/codered/npc_model_roster_v1.json",
        "scratch/codered_npc_roster.json",
        "scratch/codered_npc_roster_scan.json",
        "Smart Menu/ImportedFileNames.txt",
        "Smart_Menu/ImportedFileNames.txt",
        "ImportedFileNames.txt",
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_root_from_file() -> Path:
    return Path(__file__).resolve().parents[1]


class Controller:
    def __init__(self, root: Path):
        self.root = root
        self.profile_path = root / "data" / "codered" / "trainer_ai_profile_v1.json"
        self.state_path = root / "scratch" / "codered_trainer_ai_state.json"
        self.plan_path = root / "scratch" / "codered_trainer_ai_action_plan.json"
        self.command_log_path = root / "scratch" / "codered_trainer_ai_commands.jsonl"
        self.log_path = root / "logs" / "codered_trainer_ai_controller.log"
        self.scratch_roster_path = root / "scratch" / "codered_npc_roster_scan.json"
        self.profile = self._load_profile()
        self.roster: list[RosterEntry] = []
        self.roster_index = 0
        self.roster_filter = str(self.profile.get("selected_model_filter", ""))
        self.reload_roster()
        self.state = self._load_or_create_state()
        existing_model = (
            self.state.get("npc_roster", {}).get("selected_model")
            or self.state.get("entity", {}).get("model")
            or self.profile.get("selected_model", "")
        )
        self._sync_selected_model(existing_model, prefer_existing=True)
        self.write_all("init")

    def _load_profile(self) -> dict:
        if self.profile_path.exists():
            try:
                data = json.loads(self.profile_path.read_text(encoding="utf-8"))
                merged = dict(DEFAULT_PROFILE)
                merged.update(data)
                return merged
            except Exception as exc:
                self.log(f"profile load failed, using defaults: {exc}")
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.profile_path.write_text(json.dumps(DEFAULT_PROFILE, indent=2), encoding="utf-8")
        return dict(DEFAULT_PROFILE)

    def source_paths(self) -> list[Path]:
        paths = []
        for item in self.profile.get("roster_sources", []):
            path = Path(item)
            paths.append(path if path.is_absolute() else self.root / path)
        # Include any newly added default source without duplicating.
        seen = {str(p.resolve()) for p in paths if p.exists()}
        for path in default_source_paths(self.root):
            key = str(path.resolve())
            if key not in seen:
                paths.append(path)
        return paths

    def reload_roster(self) -> None:
        self.roster = load_roster_files(self.source_paths())
        if not self.roster:
            # Last-resort fallback so the console remains usable even before any list exists.
            fallback = [
                "amb_fh_farmer06",
                "amb_c_dworker03",
                "anc_outlaw_01",
                "com_mexicangirl_cs",
                "crm_hispanic_m_02_cs",
                "law_caucasianmarshall_06_cs",
                "misc_rebelsoldier_06_cs_hat",
                "player_bandito",
                "player_cattlerus",
                "wolfzombie01",
            ]
            self.roster = [RosterEntry(name=name, category="fallback", source="controller_fallback") for name in fallback]
        self.roster.sort(key=lambda item: (item.category, item.name))

    def _load_or_create_state(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "version": 1,
            "tool": VERSION,
            "updated_at": utc_now(),
            "active": False,
            "entity": {
                "label": self.profile.get("label", "CodeRED_AI_01"),
                "handle": None,
                "spawn_requested": False,
                "model": self.profile.get("selected_model", "amb_fh_farmer06"),
                "model_index": 0,
                "model_category": "unknown",
            },
            "behavior": {
                "mode": "offline",
                "target": "player",
                "follow_distance": self.profile.get("follow_distance", 8.0),
                "guard_radius": self.profile.get("guard_radius", 14.0),
                "warp_distance": self.profile.get("warp_distance", 80.0),
                "attack_hostiles": self.profile.get("attack_hostiles", True),
                "avoid_friendly_fire": self.profile.get("avoid_friendly_fire", True),
                "respawn_if_dead": self.profile.get("respawn_if_dead", True),
            },
            "npc_roster": {
                "count": len(self.roster),
                "selected_index": 0,
                "selected_model": self.profile.get("selected_model", "amb_fh_farmer06"),
                "selected_category": "unknown",
                "filter": self.roster_filter,
            },
            "last_command": None,
            "requests": [],
        }

    def log(self, message: str) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        line = f"[{utc_now()}] {message}\n"
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    def log_command(self, command: str, args: list[str]) -> None:
        self.command_log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"time": utc_now(), "command": command, "args": args, "selected_model": self.selected_entry().name}
        with self.command_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")

    def selected_entry(self) -> RosterEntry:
        if not self.roster:
            self.reload_roster()
        self.roster_index = max(0, min(self.roster_index, len(self.roster) - 1))
        return self.roster[self.roster_index]

    def _sync_selected_model(self, wanted: str, *, prefer_existing: bool = False) -> None:
        wanted_l = str(wanted or "").lower()
        for idx, entry in enumerate(self.roster):
            if entry.name == wanted_l:
                self.roster_index = idx
                break
        else:
            if not prefer_existing:
                self.roster_index = 0
        entry = self.selected_entry()
        self.state.setdefault("entity", {})["model"] = entry.name
        self.state["entity"]["model_index"] = self.roster_index
        self.state["entity"]["model_category"] = entry.category
        self.state.setdefault("npc_roster", {})["count"] = len(self.roster)
        self.state["npc_roster"]["selected_index"] = self.roster_index
        self.state["npc_roster"]["selected_model"] = entry.name
        self.state["npc_roster"]["selected_category"] = entry.category
        self.state["npc_roster"]["filter"] = self.roster_filter

    def filtered_indices(self, filter_text: str | None = None) -> list[int]:
        filt = (self.roster_filter if filter_text is None else filter_text).lower().strip()
        if not filt:
            return list(range(len(self.roster)))
        return [idx for idx, entry in enumerate(self.roster) if filt in entry.name or filt in entry.category]

    def set_mode(self, mode: str, requests: list[str], *, active: bool = True, spawn_requested: bool | None = None) -> None:
        self.state["active"] = active
        self.state["behavior"]["mode"] = mode
        self.state["requests"] = requests
        if spawn_requested is not None:
            self.state["entity"]["spawn_requested"] = spawn_requested
        self.state["updated_at"] = utc_now()

    def write_all(self, command: str) -> None:
        self._sync_selected_model(self.selected_entry().name, prefer_existing=True)
        self.state["tool"] = VERSION
        self.state["updated_at"] = utc_now()
        self.state["last_command"] = command
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        self.plan_path.parent.mkdir(parents=True, exist_ok=True)
        self.plan_path.write_text(json.dumps(self.build_action_plan(), indent=2), encoding="utf-8")

    def build_action_plan(self) -> dict:
        entry = self.selected_entry()
        return {
            "version": 1,
            "tool": VERSION,
            "updated_at": utc_now(),
            "active": bool(self.state.get("active", False)),
            "entity": {
                "label": self.state["entity"].get("label", "CodeRED_AI_01"),
                "handle": self.state["entity"].get("handle"),
                "spawn_requested": self.state["entity"].get("spawn_requested", False),
                "model": entry.name,
                "model_category": entry.category,
                "model_index": self.roster_index,
            },
            "behavior": self.state["behavior"],
            "npc_roster": self.state["npc_roster"],
            "requests": list(self.state.get("requests", [])),
            "bridge_notes": [
                "Game-side bridge should spawn or swap the actor model named entity.model when supported.",
                "If a model fails, bridge should report invalid_model and keep the previous valid actor alive.",
            ],
        }

    def print_status(self) -> None:
        entry = self.selected_entry()
        print(f"status={self.state['behavior']['mode']} active={self.state.get('active')} model={entry.name} index={self.roster_index}/{max(len(self.roster)-1, 0)} category={entry.category} roster={len(self.roster)}")
        print(f"state={self.state_path}")
        print(f"plan ={self.plan_path}")

    def show_list(self, filter_text: str = "", limit: int = 80) -> None:
        filt = filter_text.lower().strip() if filter_text else self.roster_filter.lower().strip()
        indices = self.filtered_indices(filt)
        print(f"roster_count={len(self.roster)} shown={len(indices)} filter={filt!r}")
        for visible_idx, roster_idx in enumerate(indices[:limit]):
            entry = self.roster[roster_idx]
            marker = "*" if roster_idx == self.roster_index else " "
            print(f"{marker}{roster_idx:04d}  {entry.name:<42}  {entry.category}")
        if len(indices) > limit:
            print(f"... {len(indices) - limit} more")

    def cycle(self, direction: int, filter_text: str = "") -> None:
        indices = self.filtered_indices(filter_text or None)
        if not indices:
            raise ValueError(f"no NPC models match filter {filter_text or self.roster_filter!r}")
        if self.roster_index in indices:
            pos = indices.index(self.roster_index)
        else:
            pos = -1 if direction > 0 else 0
        self.roster_index = indices[(pos + direction) % len(indices)]
        self._sync_selected_model(self.selected_entry().name, prefer_existing=True)
        self.set_mode(self.state["behavior"].get("mode", "offline"), ["select_model", "apply_selected_model"], active=self.state.get("active", False))
        self.write_all("npc-next" if direction > 0 else "npc-prev")
        print(f"selected {self.selected_entry().name} ({self.roster_index})")

    def set_filter(self, filter_text: str) -> None:
        self.roster_filter = filter_text.strip()
        self.state["npc_roster"]["filter"] = self.roster_filter
        self.write_all("npc-filter")
        print(f"filter={self.roster_filter!r} matches={len(self.filtered_indices())}")

    def set_model(self, query: str) -> None:
        q = query.strip().lower()
        if not q:
            raise ValueError("empty model query")
        if q.isdigit():
            idx = int(q)
            if idx < 0 or idx >= len(self.roster):
                raise ValueError(f"index out of range: {idx}")
            self.roster_index = idx
        else:
            exact = [idx for idx, entry in enumerate(self.roster) if entry.name == q]
            partial = [idx for idx, entry in enumerate(self.roster) if q in entry.name or q in entry.category]
            matches = exact or partial
            if not matches:
                raise ValueError(f"no NPC model matches: {query}")
            self.roster_index = matches[0]
        self._sync_selected_model(self.selected_entry().name, prefer_existing=True)
        self.set_mode(self.state["behavior"].get("mode", "offline"), ["select_model", "apply_selected_model"], active=self.state.get("active", False))
        self.write_all("npc-set")
        print(f"selected {self.selected_entry().name} ({self.roster_index})")

    def scan_source(self, source: str) -> None:
        path = Path(source)
        if not path.is_absolute():
            path = (self.root / path).resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        if path.suffix.lower() in {".txt", ".json", ".csv", ".lst"}:
            entries = extract_from_text(path.read_text(encoding="utf-8", errors="ignore"), str(path))
        else:
            entries = scan_binary_archive(path)
        current = {entry.name: entry for entry in load_roster_files([self.scratch_roster_path])}
        for entry in entries:
            current.setdefault(entry.name, entry)
        save_roster(sorted(current.values(), key=lambda item: (item.category, item.name)), self.scratch_roster_path, note=f"merged scan from {path}")
        self.reload_roster()
        self._sync_selected_model(self.selected_entry().name, prefer_existing=True)
        self.write_all("npc-scan")
        print(f"scan merged {len(entries)} entries; roster now {len(self.roster)} -> {self.scratch_roster_path}")

    def execute(self, line: str) -> bool:
        parts = shlex.split(line, posix=False)
        if not parts:
            return True
        command = parts[0].lower()
        args = parts[1:]
        aliases = {
            "next": "npc-next",
            "prev": "npc-prev",
            "previous": "npc-prev",
            "list": "npc-list",
            "set": "npc-set",
            "filter": "npc-filter",
            "scan": "npc-scan",
        }
        command = aliases.get(command, command)
        self.log_command(command, args)

        if command in {"exit", "quit"}:
            self.write_all("exit")
            return False
        if command == "help":
            for key, desc in COMMANDS.items():
                print(f"{key:<24} {desc}")
            return True
        if command == "status":
            self.write_all("status")
            self.print_status()
            return True
        if command == "spawn":
            self.set_mode("spawn_requested", ["ensure_spawned", "spawn_model", "equip_basic_weapon"], active=True, spawn_requested=True)
        elif command == "follow":
            self.set_mode("follow", ["ensure_spawned", "follow_player", "maintain_distance"], active=True, spawn_requested=True)
        elif command == "guard":
            self.set_mode("guard", ["ensure_spawned", "guard_position", "watch_hostiles"], active=True, spawn_requested=True)
        elif command == "defend":
            self.set_mode("follow_defend", ["ensure_spawned", "follow_player", "defend_player", "attack_hostiles"], active=True, spawn_requested=True)
        elif command == "attack":
            self.set_mode("attack_hostiles", ["ensure_spawned", "scan_hostiles", "attack_hostiles"], active=True, spawn_requested=True)
        elif command == "regroup":
            self.set_mode("regroup", ["ensure_spawned", "warp_near_player", "follow_player"], active=True, spawn_requested=True)
        elif command == "mount":
            self.set_mode("mount", ["ensure_spawned", "find_mount", "mount_request"], active=True, spawn_requested=True)
        elif command == "dismount":
            self.set_mode("dismount", ["ensure_spawned", "dismount_request"], active=True, spawn_requested=True)
        elif command == "idle":
            self.set_mode("idle", ["clear_tasks", "standby"], active=True, spawn_requested=False)
        elif command == "dismiss":
            self.set_mode("dismissed", ["dismiss_actor", "clear_handle"], active=False, spawn_requested=False)
        elif command == "npc-list":
            filt = " ".join(args).strip()
            self.show_list(filt)
            return True
        elif command == "npc-next":
            self.cycle(1, " ".join(args).strip())
            return True
        elif command == "npc-prev":
            self.cycle(-1, " ".join(args).strip())
            return True
        elif command == "npc-set":
            self.set_model(" ".join(args))
            return True
        elif command == "npc-filter":
            self.set_filter(" ".join(args))
            return True
        elif command == "npc-scan":
            if not args:
                raise ValueError("npc-scan needs a file path")
            self.scan_source(" ".join(args))
            return True
        else:
            raise ValueError(f"unknown command: {command}")

        self.write_all(command)
        self.print_status()
        return True

    def repl(self) -> int:
        print("CodeRED Trainer AI Controller v1 - NPC roster switcher")
        print("Type help for commands. Use npc-next / npc-prev / npc-list amb / npc-set gent_...")
        self.print_status()
        while True:
            try:
                line = input("codered-ai> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                self.write_all("exit")
                return 0
            try:
                if not self.execute(line):
                    return 0
            except Exception as exc:
                print(f"error: {exc}")
                self.log(f"error executing {line!r}: {exc}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CodeRED trainer AI command/state controller")
    parser.add_argument("--root", default=None, help="Repository/root path. Defaults to the folder above tools/.")
    parser.add_argument("command", nargs="*", help="Optional one-shot command, e.g. npc-next amb")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    root = Path(args.root).resolve() if args.root else repo_root_from_file()
    controller = Controller(root)
    if args.command:
        line = " ".join(args.command)
        try:
            controller.execute(line)
            return 0
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    return controller.repl()


if __name__ == "__main__":
    raise SystemExit(main())
