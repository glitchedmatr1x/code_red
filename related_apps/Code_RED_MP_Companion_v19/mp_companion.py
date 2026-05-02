from __future__ import annotations

import base64
import importlib.util
import json
import queue
import shutil
import socket
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from textwrap import dedent
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

APP_DIR = Path(__file__).resolve().parent
RUNTIME_PATH = APP_DIR / 'runtime' / 'codered_runtime.py'
PATCHES_DIR = APP_DIR / 'patches' / 'content.rpf'
BACKUPS_DIR = APP_DIR / 'backups'
CONFIG_DIR = APP_DIR / 'config'
LOGS_DIR = APP_DIR / 'logs'
ACTIVE_SESSION_PATH = CONFIG_DIR / 'active_session.json'
INVITE_PATH = CONFIG_DIR / 'last_invite.txt'
PROFILE_PATH = CONFIG_DIR / 'player_profile.json'
VOICE_PATH = CONFIG_DIR / 'voice_profile.json'
TRAINER_PATH = CONFIG_DIR / 'trainer_profile.json'
RECENT_HOSTS_PATH = CONFIG_DIR / 'recent_hosts.json'
SESSION_CACHE_PATH = CONFIG_DIR / 'discovered_sessions.json'
WORKBENCH_SYNC_PATH = CONFIG_DIR / 'workbench_sync.json'
APP_SETTINGS_PATH = CONFIG_DIR / 'app_settings.json'
HOTSWAP_MANIFEST_PATH = CONFIG_DIR / 'hotswap_manifest.json'
HOOK_STATE_PATH = CONFIG_DIR / 'hook_state.json'
HOOK_DISABLED_SUFFIX = '.codered.disabled'
CHAT_LOG_PATH = LOGS_DIR / 'session_chat.log'
LAUNCH_BRIDGE_DIRNAME = 'Code_RED_Launch'
LAUNCH_BRIDGE_STATUS = 'bridge_status.json'
LAUNCH_BRIDGE_RUNTIME = 'codered_bridge_runtime.py'
LAUNCH_BRIDGE_GAME_PROCESS = 'game_process.json'
LAUNCH_BRIDGE_CONSUMER = 'codered_bridge_consumer.py'
LAUNCH_BRIDGE_CONSUMER_STATUS = 'consumer_status.json'
LAUNCH_BRIDGE_ACTIVATION_REQUEST = 'synthetic_activation_request.json'
LAUNCH_BRIDGE_SYNTHETIC_ROUTE = 'synthetic_freemode_bridge.json'
TRAINER_BRIDGE_STATE = 'trainer_bridge_state.json'
TRAINER_COMMAND_JSON = 'trainer_command.json'
TRAINER_COMMAND_QUEUE_JSON = 'trainer_command_queue.json'
TRAINER_RUNTIME_JSON = 'trainer_runtime_state.json'
TRAINER_BRIDGE_PACK_DIRNAME = 'Code_RED_TrainerBridge'
TRAINER_BRIDGE_BOOTSTRAP = 'trainer_bootstrap.json'
TRAINER_BRIDGE_README = 'Code_RED_TrainerBridge_README.txt'
TRAINER_BRIDGE_MANIFEST = 'Code_RED_TrainerBridge_manifest.json'
TRAINER_DONOR_SCAN_JSON = 'trainer_donor_scan.json'
TRAINER_DONOR_SCAN_MD = 'trainer_donor_scan.md'
BOOT_VALIDATOR_REPORT_JSON = 'boot_route_validator.json'
BOOT_VALIDATOR_REPORT_MD = 'boot_route_validator.md'
GAME_ROOT_VALIDATOR_JSON = 'game_root_validator.json'
GAME_ROOT_VALIDATOR_MD = 'game_root_validator.md'
SAVE_SCAN_REPORT_JSON = 'save_scan_report.json'
SAVE_SCAN_REPORT_MD = 'save_scan_report.md'
PLAYERLIST_REPORT_JSON = 'playerlist_focus_report.json'
PLAYERLIST_REPORT_MD = 'playerlist_focus_report.md'
ROOT_LAUNCHER_MANIFEST = 'Code_RED_Launcher_manifest.json'
HOOK_PACK_DIRNAME = 'Code_RED_HookBridge'
HOOK_BOOTSTRAP_JSON = 'hook_bootstrap.json'
HOOK_PLUGIN_SOURCE = 'Code_RED_BridgePlugin.cpp'
HOOK_PLUGIN_BUILD_BAT = 'build_red_plugin.bat'
HOOK_PLUGIN_VCXPROJ = 'Code_RED_BridgePlugin.vcxproj'
HOOK_PLUGIN_README = 'Code_RED_BridgePlugin_README.txt'
HOOK_PLUGIN_OUTPUT = 'Code_RED_Bridge.red'
HOOK_PLUGIN_LOG = 'Code_RED_BridgePlugin.log'
HOOK_PACK_MANIFEST = 'Code_RED_HookBridge_manifest.json'
PLAYERLIST_BRIDGE_DIRNAME = 'Code_RED_PlayerlistBridge'
PLAYERLIST_BRIDGE_BOOTSTRAP = 'playerlist_bootstrap.json'
PLAYERLIST_BRIDGE_RUNTIME = 'playerlist_runtime_state.json'
PLAYERLIST_BRIDGE_COMMAND = 'playerlist_command.json'
PLAYERLIST_BRIDGE_LOG = 'playerlist_bridge.log'
PLAYERLIST_BRIDGE_SOURCE = 'Code_RED_PlayerlistBridge.cpp'
PLAYERLIST_BRIDGE_BUILD_BAT = 'build_playerlist_bridge.bat'
PLAYERLIST_BRIDGE_VCXPROJ = 'Code_RED_PlayerlistBridge.vcxproj'
PLAYERLIST_BRIDGE_README = 'Code_RED_PlayerlistBridge_README.txt'
PLAYERLIST_BRIDGE_MANIFEST = 'Code_RED_PlayerlistBridge_manifest.json'
PLAYERLIST_BRIDGE_SIM = 'playerlist_bridge_sim.py'
PLAYERLIST_BRIDGE_OUTPUT = 'Code_RED_PlayerlistBridge.red'
HOOK_PROOF_DIRNAME = 'Code_RED_HookProof'
HOOK_PROOF_WATCHER = 'probe_redhook_logs.py'
HOOK_PROOF_BUILD_BAT = 'build_all_red_plugins.bat'
HOOK_PROOF_EXPECTED_JSON = 'expected_log_markers.json'
HOOK_PROOF_REPORT_JSON = 'first_live_action_report.json'
HOOK_PROOF_README = 'Code_RED_HookProof_README.txt'
OVERLAY_DIRNAME = 'Code_RED_Overlay'
OVERLAY_BOOTSTRAP_JSON = 'overlay_bootstrap.json'
OVERLAY_SCRIPT = 'code_red_overlay.py'
OVERLAY_BUILD_BAT = 'build_overlay_exe.bat'
OVERLAY_LAUNCH_BAT = 'launch_overlay.bat'
OVERLAY_GAME_LAUNCH_BAT = 'launch_game_with_overlay.bat'
OVERLAY_README = 'Code_RED_Overlay_README.txt'
OVERLAY_MANIFEST = 'Code_RED_Overlay_manifest.json'
OVERLAY_STATE_JSON = 'overlay_state.json'
OVERLAY_EXE = 'Code_RED_Overlay.exe'
HOTSWAP_DIR = APP_DIR / 'hotswap'
HOTSWAP_STAGING_DIR = HOTSWAP_DIR / 'staged'
HOTSWAP_RUNTIME_DIR = APP_DIR / 'patches' / '_runtime'
HOTSWAP_SWAP_RETRIES = 12
HOTSWAP_SWAP_DELAY = 0.35
DISCOVERY_PORT = 6688
MAX_CHAT_HISTORY = 300

for folder in (PATCHES_DIR, BACKUPS_DIR, CONFIG_DIR, LOGS_DIR, HOTSWAP_DIR, HOTSWAP_STAGING_DIR, HOTSWAP_RUNTIME_DIR):
    folder.mkdir(parents=True, exist_ok=True)


def load_runtime():
    spec = importlib.util.spec_from_file_location('codered_runtime_bundle', RUNTIME_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Runtime helper is missing: {RUNTIME_PATH}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    apply_patch = getattr(module, '_codered_apply_patch_folder_to_archive_copy', None)
    if not callable(apply_patch):
        raise RuntimeError('Bundled runtime does not expose archive patch-folder apply support.')
    return module


RUNTIME = load_runtime()


def log_line(message: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with (LOGS_DIR / 'mp_companion.log').open('a', encoding='utf-8') as fh:
        fh.write(f'[{stamp}] {message}\n')


def chat_log_line(message: str) -> None:
    stamp = datetime.now().strftime('%H:%M:%S')
    with CHAT_LOG_PATH.open('a', encoding='utf-8') as fh:
        fh.write(f'[{stamp}] {message}\n')


def best_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('8.8.8.8', 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith('127.'):
                return ip
    except Exception:
        pass
    try:
        host = socket.gethostname()
        for info in socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM):
            ip = info[4][0]
            if ip and not ip.startswith('127.'):
                return ip
    except Exception:
        pass
    return '127.0.0.1'


def encode_invite(payload: dict) -> str:
    raw = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')
    return base64.urlsafe_b64encode(raw).decode('ascii')


def decode_invite(text: str) -> dict:
    raw = base64.urlsafe_b64decode(text.strip().encode('ascii'))
    return json.loads(raw.decode('utf-8'))


class CompanionApp(tk.Tk):
    STATE_COLORS = {
        'IDLE': '#303030',
        'PREPARED': '#6E5600',
        'HOSTING': '#124C9C',
        'CONNECTING': '#8A4B00',
        'CONNECTED': '#1F7A1F',
        'FAILED': '#8B0000',
        'STOPPED': '#505050',
    }

    def __init__(self):
        super().__init__()
        self.title('Code RED Multiplayer Companion v19')
        self.geometry('1500x980')
        self.minsize(1280, 860)
        self.configure(bg='#080808')
        self.game_dir_var = tk.StringVar(value=str(APP_DIR.parent if (APP_DIR.parent / 'content.rpf').exists() else APP_DIR))
        self.game_exe_var = tk.StringVar(value='')
        self.content_rpf_var = tk.StringVar(value='')
        self.target_rpf_var = tk.StringVar(value='')
        self.host_ip_var = tk.StringVar(value=best_lan_ip())
        self.host_port_var = tk.StringVar(value='6677')
        self.session_name_var = tk.StringVar(value='Code RED Freemode')
        self.player_name_var = tk.StringVar(value='PlayerHost')
        self.world_name_var = tk.StringVar(value='freemode')
        self.boot_target_var = tk.StringVar(value='MULTI_FREE_ROAM')
        self.world_route_var = tk.StringVar(value='Recovered freemode route')
        self.startup_mode_var = tk.StringVar(value='Single Player Host')
        self.playerlist_status_var = tk.StringVar(value='Playerlist focus not analyzed yet.')
        self.connection_state_var = tk.StringVar(value='IDLE')
        self.connection_detail_var = tk.StringVar(value='No session activity yet.')
        self.discovery_status_var = tk.StringVar(value='No LAN scan yet.')
        self.lan_ip_var = tk.StringVar(value=best_lan_ip())
        self.peer_count_var = tk.StringVar(value='0')
        self.last_peer_var = tk.StringVar(value='None')
        self.roster_var = tk.StringVar(value='Host only')
        self.save_status_var = tk.StringVar(value='Save state not scanned yet.')
        self.hotswap_status_var = tk.StringVar(value='Ghost RPF inactive.')
        self.invite_var = tk.StringVar(value='')
        self.chat_input_var = tk.StringVar(value='')
        self.voice_enabled_var = tk.BooleanVar(value=True)
        self.voice_muted_var = tk.BooleanVar(value=False)
        self.voice_ptt_var = tk.StringVar(value='V')
        self.voice_device_var = tk.StringVar(value='Default Microphone')
        self.auto_reconnect_var = tk.BooleanVar(value=True)
        self.auto_hotswap_var = tk.BooleanVar(value=True)
        self.restore_hotswap_on_exit_var = tk.BooleanVar(value=False)
        self.auto_manage_hooks_var = tk.BooleanVar(value=True)
        self.restore_managed_hooks_on_exit_var = tk.BooleanVar(value=True)
        self._managed_hook_manifest = None
        self._active_bridge_dir = None
        self.trainer_god_var = tk.BooleanVar(value=False)
        self.trainer_ammo_var = tk.BooleanVar(value=False)
        self.trainer_noclip_var = tk.BooleanVar(value=False)
        self.trainer_jump_var = tk.BooleanVar(value=False)
        self.trainer_fasttravel_var = tk.BooleanVar(value=False)
        self.trainer_weather_var = tk.StringVar(value='default')
        self.trainer_time_var = tk.StringVar(value='default')
        self.trainer_action_var = tk.StringVar(value='apply_state')
        self.trainer_target_var = tk.StringVar(value='')
        self.trainer_pack_status_var = tk.StringVar(value='Trainer bridge: not installed')
        self.trainer_status_var = tk.StringVar(value='Trainer state: default')
        self._status_pill = None
        self._beacon_thread = None
        self._beacon_stop = threading.Event()
        self._beacon_socket = None
        self._discovery_thread = None
        self._discovery_stop = threading.Event()
        self._discovery_socket = None
        self._poll_thread = None
        self._poll_stop = threading.Event()
        self._ui_queue = queue.Queue()
        self._host_meta = {}
        self._chat_text = None
        self._playerlist_text = None
        self._playerlist_report = None
        self._last_playerlist_command_fingerprint = ''
        self._last_playerlist_command_detail = ''
        self._session_listbox = None
        self._session_items = []
        self._chat_history = []
        self._chat_index = 0
        self._last_chat_index = 0
        self._roster = {}
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        self._applying_startup_mode = False
        self.startup_mode_var.trace_add('write', self._on_startup_mode_changed)
        self._build_ui()
        self._load_app_settings()
        self.load_saved_profiles()
        self.apply_workbench_sync()
        self.auto_detect_content_rpf()
        self._sync_target_rpf_with_content(force=False)
        self.auto_detect_game_exe()
        self.after(100, self._process_ui_queue)
        self.after(1500, self.refresh_connection_indicator)
        log_line('Multiplayer Companion v19 ready.')

    def _queue_ui(self, fn, *args):
        self._ui_queue.put((fn, args))

    def _process_ui_queue(self):
        try:
            while True:
                fn, args = self._ui_queue.get_nowait()
                fn(*args)
        except queue.Empty:
            pass
        self.after(100, self._process_ui_queue)

    def _label(self, parent, text):
        return tk.Label(parent, text=text, bg='#080808', fg='#F0F0F0', anchor='w')

    def _button(self, parent, text, cmd, accent=False):
        return tk.Button(parent, text=text, command=cmd, bg=('#8B0000' if accent else '#181818'), fg='#FFFFFF', relief='flat', padx=12, pady=8)

    def _entry(self, parent, textvariable, width=24):
        return tk.Entry(parent, textvariable=textvariable, bg='#101010', fg='#FFFFFF', insertbackground='#FFFFFF', width=width)

    def _add_chat_line(self, message: str) -> None:
        chat_log_line(message)
        if self._chat_text is not None:
            self._chat_text.insert('end', message + '\n')
            self._chat_text.see('end')

    def _build_ui(self):
        top = tk.Frame(self, bg='#080808')
        top.pack(fill='x', padx=14, pady=12)
        self._label(top, 'Game Directory').grid(row=0, column=0, sticky='w')
        self._entry(top, self.game_dir_var, width=88).grid(row=1, column=0, sticky='we', padx=(0, 8))
        self._button(top, 'Browse', self.select_game_dir).grid(row=1, column=1, padx=4)
        self._button(top, 'Detect content.rpf', self.auto_detect_content_rpf).grid(row=1, column=2, padx=4)
        self._button(top, 'Detect Game EXE', self.auto_detect_game_exe).grid(row=1, column=3, padx=4)
        self._label(top, 'Game EXE').grid(row=2, column=0, sticky='w', pady=(10, 0))
        self._entry(top, self.game_exe_var, width=88).grid(row=3, column=0, sticky='we', padx=(0, 8))
        self._button(top, 'Choose EXE', self.select_game_exe).grid(row=3, column=1, padx=4)
        self._button(top, 'Install Launch Bridge', self.install_launch_bridge).grid(row=3, column=2, padx=4)
        self._button(top, 'Open Folder', self.open_game_dir).grid(row=3, column=3, padx=4)
        self._button(top, 'Probe Bridge', self.probe_launch_bridge).grid(row=3, column=4, padx=4)
        self._label(top, 'Detected content.rpf').grid(row=4, column=0, sticky='w', pady=(10, 0))
        self._entry(top, self.content_rpf_var, width=88).grid(row=5, column=0, sticky='we', padx=(0, 8))
        self._button(top, 'Choose content.rpf', self.select_content_rpf_file).grid(row=5, column=1, padx=4)
        self._button(top, 'Refresh', self.auto_detect_content_rpf).grid(row=5, column=2, padx=4)
        self._label(top, 'Live Game RPF To Temporarily Replace (Ghost target)').grid(row=6, column=0, sticky='w', pady=(10, 0))
        self._entry(top, self.target_rpf_var, width=88).grid(row=7, column=0, sticky='we', padx=(0, 8))
        self._button(top, 'Choose Target RPF', self.select_target_rpf_file).grid(row=7, column=1, padx=4)
        self._button(top, 'Use content.rpf', self.use_content_as_target_rpf).grid(row=7, column=2, padx=4)
        tk.Label(top, text='Pick the live game archive Code RED should clone, ghost-patch, and temporarily replace before launch. This is the original game file being swapped out for the generated Ghost copy. Default target is content.rpf.', bg='#080808', fg='#B8B8B8', anchor='w').grid(row=8, column=0, columnspan=5, sticky='w', pady=(4, 0))
        root_tools = tk.Frame(top, bg='#080808')
        root_tools.grid(row=9, column=0, columnspan=5, sticky='we', pady=(10, 0))
        self._button(root_tools, 'Validate Game Root', self.validate_game_root, accent=True).pack(side='left', padx=4)
        self._button(root_tools, 'Install Main-Dir Pack', self.install_main_dir_pack).pack(side='left', padx=4)
        tk.Label(root_tools, text='Builds root launchers, audits hook conflicts, and picks the safest executable in the game main directory.', bg='#080808', fg='#B8B8B8', anchor='w').pack(side='left', padx=10)
        tk.Checkbutton(root_tools, text='Auto disable incompatible hooks', variable=self.auto_manage_hooks_var, bg='#080808', fg='#FFFFFF', selectcolor='#101010', activebackground='#080808', activeforeground='#FFFFFF').pack(side='left', padx=8)
        top.grid_columnconfigure(0, weight=1)

        mid = tk.Frame(self, bg='#080808')
        mid.pack(fill='both', expand=True, padx=14, pady=(0, 12))

        install = tk.LabelFrame(mid, text='Install / Patch', bg='#080808', fg='#F0F0F0', bd=1)
        install.pack(fill='x', pady=(0, 12))
        for widget in (
            self._button(install, 'Backup content.rpf', self.backup_content_rpf, accent=True),
            self._button(install, 'Apply Bundled Patches', self.apply_bundled_patches),
            self._button(install, 'Apply External Patch Folder', self.apply_external_patch_folder),
            self._button(install, 'Inject Custom File', self.inject_custom_file),
            self._button(install, 'Restore Latest Backup', self.restore_latest_backup),
        ):
            widget.pack(side='left', padx=6, pady=10)
        hotswap_row = tk.Frame(install, bg='#080808')
        hotswap_row.pack(fill='x', padx=6, pady=(0, 10))
        self._button(hotswap_row, 'Build Ghost RPF', self.build_hotswap_copy, accent=True).pack(side='left', padx=4)
        self._button(hotswap_row, 'Activate Ghost RPF', self.activate_hotswap).pack(side='left', padx=4)
        self._button(hotswap_row, 'Restore Ghost RPF', self.restore_hotswap).pack(side='left', padx=4)
        tk.Checkbutton(hotswap_row, text='Auto Ghost RPF Before Launch', variable=self.auto_hotswap_var, bg='#080808', fg='#FFFFFF', selectcolor='#101010', activebackground='#080808', activeforeground='#FFFFFF').pack(side='left', padx=10)
        tk.Checkbutton(hotswap_row, text='Restore on Exit', variable=self.restore_hotswap_on_exit_var, bg='#080808', fg='#FFFFFF', selectcolor='#101010', activebackground='#080808', activeforeground='#FFFFFF').pack(side='left', padx=10)
        tk.Label(hotswap_row, textvariable=self.hotswap_status_var, bg='#080808', fg='#B8B8B8', anchor='w').pack(side='left', padx=10)

        profile = tk.LabelFrame(mid, text='Profile / Session', bg='#080808', fg='#F0F0F0', bd=1)
        profile.pack(fill='x', pady=(0, 12))
        self._label(profile, 'Session Name').grid(row=0, column=0, sticky='w', padx=8, pady=(10, 2))
        self._label(profile, 'Username').grid(row=0, column=1, sticky='w', padx=8, pady=(10, 2))
        self._label(profile, 'Host / Join IP').grid(row=0, column=2, sticky='w', padx=8, pady=(10, 2))
        self._label(profile, 'Port').grid(row=0, column=3, sticky='w', padx=8, pady=(10, 2))
        self._entry(profile, self.session_name_var, width=28).grid(row=1, column=0, padx=8, pady=(0, 10), sticky='we')
        self._entry(profile, self.player_name_var, width=24).grid(row=1, column=1, padx=8, pady=(0, 10), sticky='we')
        self._entry(profile, self.host_ip_var, width=18).grid(row=1, column=2, padx=8, pady=(0, 10), sticky='we')
        self._entry(profile, self.host_port_var, width=10).grid(row=1, column=3, padx=8, pady=(0, 10), sticky='we')
        self._button(profile, 'Save Profile', self.save_profile, accent=True).grid(row=1, column=4, padx=8)
        self._button(profile, 'Create Host Descriptor', self.create_host_descriptor).grid(row=1, column=5, padx=8)
        self._button(profile, 'Create Join Descriptor', self.create_join_descriptor).grid(row=1, column=6, padx=8)
        self._button(profile, 'Auto Setup + Launch', self.launch_game, accent=True).grid(row=1, column=7, padx=8)

        status_frame = tk.Frame(profile, bg='#080808')
        status_frame.grid(row=2, column=0, columnspan=8, sticky='we', padx=8, pady=(2, 6))
        self._label(status_frame, 'Connection State').pack(side='left', padx=(0, 8))
        self._status_pill = tk.Label(status_frame, textvariable=self.connection_state_var, width=14, bg=self.STATE_COLORS['IDLE'], fg='#FFFFFF', relief='flat', padx=8, pady=6)
        self._status_pill.pack(side='left', padx=(0, 10))
        tk.Label(status_frame, textvariable=self.connection_detail_var, bg='#080808', fg='#D0D0D0', anchor='w').pack(side='left', fill='x', expand=True)

        controls = tk.Frame(profile, bg='#080808')
        controls.grid(row=3, column=0, columnspan=8, sticky='we', padx=8, pady=(0, 4))
        self._button(controls, 'Start Host Beacon', self.start_host_beacon, accent=True).pack(side='left', padx=4)
        self._button(controls, 'Stop Beacon', self.stop_host_beacon).pack(side='left', padx=4)
        self._button(controls, 'Probe Connection', self.probe_connection).pack(side='left', padx=4)
        self._button(controls, 'Discover LAN', self.discover_lan_sessions).pack(side='left', padx=4)
        self._button(controls, 'Detect LAN IP', self.detect_lan_ip).pack(side='left', padx=4)
        self._button(controls, 'Copy Invite', self.copy_invite).pack(side='left', padx=4)
        self._button(controls, 'Load Invite', self.load_invite).pack(side='left', padx=4)
        tk.Checkbutton(controls, text='Auto Reconnect', variable=self.auto_reconnect_var, bg='#080808', fg='#FFFFFF', selectcolor='#101010', activebackground='#080808', activeforeground='#FFFFFF').pack(side='left', padx=10)

        bridge_tools = tk.Frame(profile, bg='#080808')
        bridge_tools.grid(row=4, column=0, columnspan=8, sticky='we', padx=8, pady=(0, 4))
        self._button(bridge_tools, 'Run Bridge Consumer', self.run_bridge_consumer, accent=True).pack(side='left', padx=4)
        self._button(bridge_tools, 'Solo Loopback Test', self.run_solo_loopback_test).pack(side='left', padx=4)
        self._button(bridge_tools, 'Probe Consumer', self.probe_bridge_consumer).pack(side='left', padx=4)
        tk.Label(bridge_tools, text='One-machine loopback can test host/join handoff without a second player.', bg='#080808', fg='#B8B8B8', anchor='w').pack(side='left', padx=10)

        share = tk.Frame(profile, bg='#080808')
        share.grid(row=5, column=0, columnspan=8, sticky='we', padx=8, pady=(2, 10))
        self._label(share, 'LAN IP').pack(side='left', padx=(0, 6))
        tk.Label(share, textvariable=self.lan_ip_var, bg='#101010', fg='#FFFFFF', padx=10, pady=6).pack(side='left', padx=(0, 12))
        self._label(share, 'Peers').pack(side='left', padx=(0, 6))
        tk.Label(share, textvariable=self.peer_count_var, bg='#101010', fg='#FFFFFF', padx=10, pady=6).pack(side='left', padx=(0, 12))
        self._label(share, 'Last Peer').pack(side='left', padx=(0, 6))
        tk.Label(share, textvariable=self.last_peer_var, bg='#101010', fg='#FFFFFF', padx=10, pady=6).pack(side='left', padx=(0, 12))
        self._label(share, 'Roster').pack(side='left', padx=(0, 6))
        tk.Label(share, textvariable=self.roster_var, bg='#101010', fg='#FFFFFF', padx=10, pady=6).pack(side='left', padx=(0, 12), fill='x', expand=True)

        world_frame = tk.LabelFrame(mid, text='World Target / Boot Route', bg='#080808', fg='#F0F0F0', bd=1)
        world_frame.pack(fill='x', pady=(0, 12))
        self._label(world_frame, 'World Label').grid(row=0, column=0, sticky='w', padx=8, pady=(10, 2))
        self._label(world_frame, 'Boot Target').grid(row=0, column=1, sticky='w', padx=8, pady=(10, 2))
        self._label(world_frame, 'Route Note').grid(row=0, column=2, sticky='w', padx=8, pady=(10, 2))
        self._entry(world_frame, self.world_name_var, width=18).grid(row=1, column=0, sticky='we', padx=8, pady=(0, 10))
        self._entry(world_frame, self.boot_target_var, width=24).grid(row=1, column=1, sticky='we', padx=8, pady=(0, 10))
        self._entry(world_frame, self.world_route_var, width=40).grid(row=1, column=2, sticky='we', padx=8, pady=(0, 10))
        self._button(world_frame, 'Preview Launch Plan', self.preview_launch_plan).grid(row=1, column=3, padx=8)
        self._button(world_frame, 'Validate Boot Route', self.validate_boot_route, accent=True).grid(row=1, column=4, padx=8)
        route_row = tk.Frame(world_frame, bg='#080808')
        route_row.grid(row=2, column=0, columnspan=5, sticky='we', padx=8, pady=(0, 6))
        self._label(route_row, 'Startup Route Preset (pre-launch)').pack(side='left', padx=(0, 8))
        startup_menu = tk.OptionMenu(route_row, self.startup_mode_var, 'Single Player Host', 'Recovered Freemode', 'LAN', 'Private', 'Public')
        startup_menu.configure(bg='#181818', fg='#FFFFFF', activebackground='#8B0000', activeforeground='#FFFFFF', highlightthickness=0, relief='flat')
        startup_menu['menu'].configure(bg='#101010', fg='#FFFFFF', activebackground='#8B0000', activeforeground='#FFFFFF')
        startup_menu.pack(side='left', padx=(0, 10))
        self._button(route_row, 'Build Activation Pack', self.build_activation_pack).pack(side='left', padx=4)
        self._button(route_row, 'Analyze Playerlist UI', self.analyze_playerlist_focus, accent=True).pack(side='left', padx=4)
        self._button(route_row, 'Build Playerlist Ghost', self.build_playerlist_ghost).pack(side='left', padx=4)
        save_row = tk.Frame(world_frame, bg='#080808')
        save_row.grid(row=3, column=0, columnspan=5, sticky='we', padx=8, pady=(0, 10))
        self._button(save_row, 'Check Saves', self.check_save_state).pack(side='left', padx=4)
        tk.Label(save_row, textvariable=self.save_status_var, bg='#080808', fg='#D0D0D0', anchor='w').pack(side='left', padx=10)
        tk.Label(save_row, text='Route join/switch buttons were removed here; focus is now on Playerlist/Menu discovery and pre-launch route staging.', bg='#080808', fg='#B8B8B8', anchor='w').pack(side='left', padx=10)
        world_frame.grid_columnconfigure(2, weight=1)

        for idx in range(4):
            profile.grid_columnconfigure(idx, weight=1)

        lower = tk.Frame(mid, bg='#080808')
        lower.pack(fill='both', expand=True)

        left = tk.Frame(lower, bg='#080808')
        left.pack(side='left', fill='both', expand=True)
        right = tk.Frame(lower, bg='#080808')
        right.pack(side='left', fill='both', expand=True, padx=(12, 0))

        invite_frame = tk.LabelFrame(left, text='Share / Join Info', bg='#080808', fg='#F0F0F0', bd=1)
        invite_frame.pack(fill='x', pady=(0, 12))
        self._label(invite_frame, 'Invite Code').grid(row=0, column=0, sticky='w', padx=8, pady=(10, 2))
        self._entry(invite_frame, self.invite_var, width=72).grid(row=1, column=0, sticky='we', padx=8, pady=(0, 10))
        self._button(invite_frame, 'Copy Invite', self.copy_invite, accent=True).grid(row=1, column=1, padx=8)
        self._button(invite_frame, 'Load Invite', self.load_invite).grid(row=1, column=2, padx=8)
        invite_frame.grid_columnconfigure(0, weight=1)

        browser = tk.LabelFrame(left, text='Session Browser', bg='#080808', fg='#F0F0F0', bd=1)
        browser.pack(fill='x', pady=(0, 12))
        self._session_listbox = tk.Listbox(browser, bg='#0E0E0E', fg='#FFFFFF', relief='flat', height=7, selectbackground='#8B0000', selectforeground='#FFFFFF')
        self._session_listbox.pack(fill='x', padx=8, pady=(8, 6))
        browser_controls = tk.Frame(browser, bg='#080808')
        browser_controls.pack(fill='x', padx=8, pady=(0, 8))
        self._button(browser_controls, 'Discover LAN Sessions', self.discover_lan_sessions, accent=True).pack(side='left', padx=4)
        self._button(browser_controls, 'Use Selected', self.use_selected_session).pack(side='left', padx=4)
        self._button(browser_controls, 'Probe Selected', self.probe_selected_session).pack(side='left', padx=4)
        self._button(browser_controls, 'Clear List', self.clear_session_cache).pack(side='left', padx=4)
        tk.Label(browser, textvariable=self.discovery_status_var, bg='#080808', fg='#D0D0D0', anchor='w').pack(fill='x', padx=8, pady=(0, 8))

        chat = tk.LabelFrame(left, text='Session Chat', bg='#080808', fg='#F0F0F0', bd=1)
        chat.pack(fill='both', expand=True)
        self._chat_text = tk.Text(chat, bg='#0E0E0E', fg='#FFFFFF', insertbackground='#FFFFFF', relief='flat', wrap='word', height=16)
        self._chat_text.pack(fill='both', expand=True, padx=8, pady=(8, 6))
        chat_controls = tk.Frame(chat, bg='#080808')
        chat_controls.pack(fill='x', padx=8, pady=(0, 8))
        self._entry(chat_controls, self.chat_input_var, width=56).pack(side='left', fill='x', expand=True, padx=(0, 8))
        self._button(chat_controls, 'Send Chat', self.send_chat_message, accent=True).pack(side='left', padx=4)
        self._button(chat_controls, 'Clear Chat', self.clear_chat).pack(side='left', padx=4)

        playerlist = tk.LabelFrame(right, text='Playerlist / Menu Focus', bg='#080808', fg='#F0F0F0', bd=1)
        playerlist.pack(fill='both', expand=True, pady=(0, 12))
        self._playerlist_text = tk.Text(playerlist, bg='#0E0E0E', fg='#FFFFFF', insertbackground='#FFFFFF', relief='flat', wrap='word', height=12)
        self._playerlist_text.pack(fill='both', expand=True, padx=8, pady=(8, 6))
        playerlist_controls = tk.Frame(playerlist, bg='#080808')
        playerlist_controls.pack(fill='x', padx=8, pady=(0, 8))
        self._button(playerlist_controls, 'Analyze Playerlist UI', self.analyze_playerlist_focus, accent=True).pack(side='left', padx=4)
        self._button(playerlist_controls, 'Build Playerlist Ghost', self.build_playerlist_ghost).pack(side='left', padx=4)
        self._button(playerlist_controls, 'Install Playerlist Bridge', self.install_playerlist_bridge_pack).pack(side='left', padx=4)
        tk.Label(playerlist_controls, textvariable=self.playerlist_status_var, bg='#080808', fg='#D0D0D0', anchor='w').pack(side='left', fill='x', expand=True, padx=10)

        voice = tk.LabelFrame(right, text='Voice / Mic Prep', bg='#080808', fg='#F0F0F0', bd=1)
        voice.pack(fill='x', pady=(0, 12))
        tk.Checkbutton(voice, text='Voice Enabled', variable=self.voice_enabled_var, bg='#080808', fg='#FFFFFF', selectcolor='#101010', activebackground='#080808', activeforeground='#FFFFFF').grid(row=0, column=0, sticky='w', padx=8, pady=(8, 2))
        tk.Checkbutton(voice, text='Mute Mic', variable=self.voice_muted_var, bg='#080808', fg='#FFFFFF', selectcolor='#101010', activebackground='#080808', activeforeground='#FFFFFF').grid(row=0, column=1, sticky='w', padx=8, pady=(8, 2))
        self._label(voice, 'Push-to-Talk Key').grid(row=1, column=0, sticky='w', padx=8)
        self._label(voice, 'Mic Device').grid(row=1, column=1, sticky='w', padx=8)
        self._entry(voice, self.voice_ptt_var, width=12).grid(row=2, column=0, sticky='we', padx=8, pady=(0, 8))
        self._entry(voice, self.voice_device_var, width=28).grid(row=2, column=1, sticky='we', padx=8, pady=(0, 8))
        self._button(voice, 'Save Voice Config', self.save_voice_profile, accent=True).grid(row=2, column=2, padx=8)
        self._button(voice, 'Send Voice Ping', self.send_voice_ping).grid(row=2, column=3, padx=8)
        voice.grid_columnconfigure(1, weight=1)

        trainer = tk.LabelFrame(right, text='Trainer Panel Prep', bg='#080808', fg='#F0F0F0', bd=1)
        trainer.pack(fill='both', expand=True, pady=(0, 12))
        row1 = tk.Frame(trainer, bg='#080808')
        row1.pack(fill='x', padx=8, pady=(8, 4))
        for text, var in [('God Mode', self.trainer_god_var), ('Infinite Ammo', self.trainer_ammo_var), ('NoClip', self.trainer_noclip_var), ('Super Jump', self.trainer_jump_var), ('Fast Travel', self.trainer_fasttravel_var)]:
            tk.Checkbutton(row1, text=text, variable=var, bg='#080808', fg='#FFFFFF', selectcolor='#101010', activebackground='#080808', activeforeground='#FFFFFF').pack(side='left', padx=6)
        row2 = tk.Frame(trainer, bg='#080808')
        row2.pack(fill='x', padx=8, pady=(4, 4))
        self._label(row2, 'Weather').pack(side='left', padx=(0, 6))
        self._entry(row2, self.trainer_weather_var, width=16).pack(side='left', padx=(0, 12))
        self._label(row2, 'Time').pack(side='left', padx=(0, 6))
        self._entry(row2, self.trainer_time_var, width=16).pack(side='left', padx=(0, 12))
        self._button(row2, 'Save Trainer', self.save_trainer_profile, accent=True).pack(side='left', padx=4)
        self._button(row2, 'Copy Trainer JSON', self.copy_trainer_json).pack(side='left', padx=4)
        self._button(row2, 'Send Trainer Sync', self.send_trainer_sync).pack(side='left', padx=4)
        row3 = tk.Frame(trainer, bg='#080808')
        row3.pack(fill='x', padx=8, pady=(0, 4))
        self._button(row3, 'Reset', lambda: self.apply_trainer_preset('reset')).pack(side='left', padx=4)
        self._button(row3, 'Combat', lambda: self.apply_trainer_preset('combat')).pack(side='left', padx=4)
        self._button(row3, 'Explore', lambda: self.apply_trainer_preset('explore')).pack(side='left', padx=4)
        self._button(row3, 'Host Sync', lambda: self.apply_trainer_preset('host_sync')).pack(side='left', padx=4)
        self._button(row3, 'Write Bridge State', self.write_trainer_bridge_state).pack(side='left', padx=4)
        tk.Label(row3, textvariable=self.trainer_status_var, bg='#080808', fg='#D0D0D0', anchor='w').pack(side='left', fill='x', expand=True, padx=10)

        row4 = tk.Frame(trainer, bg='#080808')
        row4.pack(fill='x', padx=8, pady=(0, 4))
        self._label(row4, 'Quick Action').pack(side='left', padx=(0, 6))
        trainer_action_menu = tk.OptionMenu(row4, self.trainer_action_var, 'apply_state', 'open_menu', 'open_playerlist', 'refresh_playerlist', 'teleport_marker', 'spawn_mount')
        trainer_action_menu.configure(bg='#181818', fg='#FFFFFF', activebackground='#8B0000', activeforeground='#FFFFFF', highlightthickness=0, relief='flat')
        trainer_action_menu['menu'].configure(bg='#101010', fg='#FFFFFF', activebackground='#8B0000', activeforeground='#FFFFFF')
        trainer_action_menu.pack(side='left', padx=(0, 12))
        self._label(row4, 'Target / Note').pack(side='left', padx=(0, 6))
        self._entry(row4, self.trainer_target_var, width=26).pack(side='left', padx=(0, 12))
        self._button(row4, 'Queue Action', self.queue_trainer_command, accent=True).pack(side='left', padx=4)
        self._button(row4, 'Install Trainer Bridge', self.install_trainer_bridge_pack).pack(side='left', padx=4)
        self._button(row4, 'Scan Donors', self.export_trainer_donor_scan).pack(side='left', padx=4)

        row5 = tk.Frame(trainer, bg='#080808')
        row5.pack(fill='x', padx=8, pady=(0, 8))
        tk.Label(row5, textvariable=self.trainer_pack_status_var, bg='#080808', fg='#9EA4AD', anchor='w').pack(side='left', fill='x', expand=True)

        notes = tk.LabelFrame(right, text='Notes', bg='#080808', fg='#F0F0F0', bd=1)
        notes.pack(fill='both', expand=True)
        self.output = tk.Text(notes, bg='#0E0E0E', fg='#FFFFFF', insertbackground='#FFFFFF', relief='flat', wrap='word')
        self.output.pack(fill='both', expand=True, padx=8, pady=8)
        for var in (self.trainer_god_var, self.trainer_ammo_var, self.trainer_noclip_var, self.trainer_jump_var, self.trainer_fasttravel_var):
            var.trace_add('write', self._on_trainer_changed)
        self.trainer_weather_var.trace_add('write', self._on_trainer_changed)
        self.trainer_time_var.trace_add('write', self._on_trainer_changed)
        self._refresh_trainer_status()

        self.write_note(
            'Companion bundle ready.\n\n'
            '- Start Host Beacon opens a lightweight host listener and LAN discovery responder.\n'
            '- Session Browser discovers LAN sessions, remembers recent hosts, and can probe the selected session.\n'
            '- Session Chat uses pull-based host sync so joiners can fetch shared chat history and roster state.\n'
            '- Voice / Mic Prep saves microphone preferences and can send a voice-ready ping to the host; real voice streaming is not implemented yet.\n'
            '- Trainer Panel Prep now has presets, quick-action queue export, donor scanning, trainer-bridge pack install, normalized weather/time input, bridge-state export, and host sync.\n'
            '- The patch lane is still safest for already-compiled or byte-compatible replacement entries.\n'
        )

    def set_connection_state(self, state: str, detail: str) -> None:
        state = (state or 'IDLE').upper()
        self.connection_state_var.set(state)
        self.connection_detail_var.set(detail)
        if self._status_pill is not None:
            self._status_pill.configure(bg=self.STATE_COLORS.get(state, '#303030'))
        log_line(f'Connection state => {state}: {detail}')

    def write_note(self, text: str):
        self.output.insert('end', text + '\n')
        self.output.see('end')
        log_line(text.replace('\n', ' | '))

    def _session_payload(self, mode: str) -> dict:
        game_dir = self.game_dir_var.get().strip()
        bridge_dir = str((Path(game_dir) / LAUNCH_BRIDGE_DIRNAME)) if game_dir else ''
        runtime_bridge_port = self._runtime_bridge_port()
        mode_key = self._mode_preset_key()
        default_session_name = {
            'singleplayer': 'Code RED Single Player Host',
            'lan': 'Code RED LAN Session',
            'private': 'Code RED Private Session',
            'public': 'Code RED Public Session',
            'freemode': 'Code RED Freemode',
        }.get(mode_key, 'Code RED Session')
        return {
            'version': 6,
            'mode': mode,
            'mode_key': mode_key,
            'session_name': self.session_name_var.get().strip() or default_session_name,
            'player_name': self.player_name_var.get().strip() or ('PlayerHost' if mode == 'host' else 'PlayerClient'),
            'host_ip': self.host_ip_var.get().strip() or best_lan_ip(),
            'port': self._normalize_port(),
            'transport': 'direct_listen_session',
            'world': self.world_name_var.get().strip() or 'freemode',
            'boot_target': self.boot_target_var.get().strip() or 'MULTI_FREE_ROAM',
            'route_note': self.world_route_var.get().strip() or 'Recovered freemode route',
            'indicator_protocol': 'codered_session_probe_v6',
            'runtime_bridge_port': runtime_bridge_port,
            'runtime_bridge_host': '127.0.0.1',
            'runtime_bridge_dir': bridge_dir,
            'voice_enabled': bool(self.voice_enabled_var.get()),
            'voice_muted': bool(self.voice_muted_var.get()),
            'trainer_profile': self.trainer_payload(),
            'game_dir': game_dir,
            'game_exe': self.game_exe_var.get().strip(),
            'startup_mode': self.startup_mode_var.get().strip() or 'Single Player Host',
        }


    def _set_session_items(self, items, status_msg: str | None = None):
        deduped = []
        seen = set()
        for item in items:
            key = (item.get('host_ip'), int(item.get('port', 0) or 0), item.get('session_name'))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        self._session_items = deduped
        if self._session_listbox is not None:
            self._session_listbox.delete(0, 'end')
            for item in self._session_items:
                label = f"{item.get('session_name', 'Unknown Session')} | {item.get('host_ip', '?')}:{item.get('port', '?')} | {item.get('player_name', 'Unknown Host')}"
                if item.get('source'):
                    label += f" | {item.get('source')}"
                self._session_listbox.insert('end', label)
        if status_msg:
            self.discovery_status_var.set(status_msg)

    def _load_json_list(self, path: Path) -> list:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding='utf-8'))
                return data if isinstance(data, list) else []
        except Exception as exc:
            log_line(f'JSON list load failed for {path}: {exc}')
        return []

    def _save_json_list(self, path: Path, items: list) -> None:
        path.write_text(json.dumps(items, indent=2), encoding='utf-8')

    def _load_session_sources(self):
        recents = self._load_json_list(RECENT_HOSTS_PATH)
        cached = self._load_json_list(SESSION_CACHE_PATH)
        merged = []
        for source_name, items in [('recent', recents), ('lan', cached)]:
            for item in items:
                row = dict(item)
                row.setdefault('source', source_name)
                merged.append(row)
        self._set_session_items(merged, f'{len(merged)} saved/discovered sessions available.')

    def _save_recent_host(self, payload: dict):
        row = {
            'session_name': payload.get('session_name', 'Code RED Freemode'),
            'player_name': payload.get('player_name', 'Unknown Host'),
            'host_ip': payload.get('host_ip', self.host_ip_var.get().strip() or best_lan_ip()),
            'port': int(payload.get('port', self._normalize_port())),
            'source': payload.get('source', 'recent'),
            'seen_at': datetime.now().isoformat(timespec='seconds'),
        }
        items = [item for item in self._load_json_list(RECENT_HOSTS_PATH) if not (item.get('host_ip') == row['host_ip'] and int(item.get('port', 0) or 0) == row['port'])]
        items.insert(0, row)
        self._save_json_list(RECENT_HOSTS_PATH, items[:25])
        self._load_session_sources()

    def _host_append_event(self, line: str):
        self._chat_index += 1
        self._chat_history.append({'i': self._chat_index, 'line': line})
        if len(self._chat_history) > MAX_CHAT_HISTORY:
            self._chat_history = self._chat_history[-MAX_CHAT_HISTORY:]
        self._queue_ui(lambda l=line: self._add_chat_line(l))

    def _update_roster(self):
        names = sorted(self._roster.keys())
        self.roster_var.set(', '.join(names[:6]) + (' ...' if len(names) > 6 else '') if names else 'Host only')
        self.peer_count_var.set(str(len(names)))

    def _record_peer(self, sender: str, addr=None, packet: dict | None = None):
        sender = sender or 'UnknownPlayer'
        pkt = packet or {}
        row = self._roster.get(sender, {})
        if addr is not None:
            row['addr'] = f'{addr[0]}:{addr[1]}'
            self.last_peer_var.set(f'{sender} @ {addr[0]}')
        row['last_seen'] = datetime.now().isoformat(timespec='seconds')
        if 'voice_enabled' in pkt:
            row['voice_enabled'] = bool(pkt.get('voice_enabled'))
            row['voice_muted'] = bool(pkt.get('voice_muted'))
        self._roster[sender] = row
        self._update_roster()

    def _persist_app_settings(self) -> None:
        payload = {
            'game_dir': self.game_dir_var.get().strip(),
            'game_exe': self.game_exe_var.get().strip(),
            'startup_mode': self.startup_mode_var.get().strip() or 'Single Player Host',
            'content_rpf': self.content_rpf_var.get().strip(),
            'target_rpf': self.target_rpf_var.get().strip(),
            'host_ip': self.host_ip_var.get().strip(),
            'host_port': self.host_port_var.get().strip(),
            'auto_hotswap': bool(self.auto_hotswap_var.get()),
            'restore_hotswap_on_exit': bool(self.restore_hotswap_on_exit_var.get()),
            'auto_manage_hooks': bool(self.auto_manage_hooks_var.get()),
            'restore_managed_hooks_on_exit': bool(self.restore_managed_hooks_on_exit_var.get()),
            'startup_mode': self.startup_mode_var.get().strip() or 'Single Player Host',
        }
        APP_SETTINGS_PATH.write_text(json.dumps(payload, indent=2), encoding='utf-8')

    def _load_app_settings(self) -> None:
        if not APP_SETTINGS_PATH.exists():
            return
        data = json.loads(APP_SETTINGS_PATH.read_text(encoding='utf-8'))
        if data.get('game_dir'):
            self.game_dir_var.set(str(data.get('game_dir')))
        if data.get('game_exe'):
            self.game_exe_var.set(str(data.get('game_exe')))
        if data.get('content_rpf'):
            self.content_rpf_var.set(str(data.get('content_rpf')))
        if data.get('target_rpf'):
            self.target_rpf_var.set(str(data.get('target_rpf')))
        if 'auto_hotswap' in data:
            self.auto_hotswap_var.set(bool(data.get('auto_hotswap')))
        if 'restore_hotswap_on_exit' in data:
            self.restore_hotswap_on_exit_var.set(bool(data.get('restore_hotswap_on_exit')))
        if 'auto_manage_hooks' in data:
            self.auto_manage_hooks_var.set(bool(data.get('auto_manage_hooks')))
        if 'restore_managed_hooks_on_exit' in data:
            self.restore_managed_hooks_on_exit_var.set(bool(data.get('restore_managed_hooks_on_exit')))
        if data.get('host_ip'):
            self.host_ip_var.set(str(data.get('host_ip')))
        if data.get('host_port'):
            self.host_port_var.set(str(data.get('host_port')))
        if data.get('startup_mode'):
            self.startup_mode_var.set(str(data.get('startup_mode')))

    def _normalize_game_dir(self, raw_path: str | Path) -> Path:
        path = Path(raw_path).expanduser()
        if path.is_file():
            path = path.parent
        if not path.exists():
            return path
        direct_hits = [path / name for name in ('PlayRDR.exe', 'RDR.exe', 'RDRMessage.exe', 'ScriptHookRDR.dll', 'dinput8.dll', 'winmm.dll')]
        if any(hit.exists() for hit in direct_hits):
            return path
        nested = path / 'Red Dead Redemption'
        if nested.exists() and nested.is_dir():
            nested_hits = [nested / name for name in ('PlayRDR.exe', 'RDR.exe', 'RDRMessage.exe', 'ScriptHookRDR.dll', 'dinput8.dll', 'winmm.dll')]
            if any(hit.exists() for hit in nested_hits):
                return nested
        return path

    def save_profile(self):
        payload = self._session_payload('host')
        PROFILE_PATH.write_text(json.dumps({
            'player_name': payload['player_name'],
            'session_name': payload['session_name'],
            'host_ip': payload['host_ip'],
            'port': payload['port'],
            'world': payload['world'],
            'boot_target': payload['boot_target'],
            'route_note': payload.get('route_note', ''),
            'content_rpf': self.content_rpf_var.get().strip(),
            'target_rpf': self.target_rpf_var.get().strip(),
            'game_dir': self.game_dir_var.get().strip(),
            'game_exe': self.game_exe_var.get().strip(),
            'startup_mode': self.startup_mode_var.get().strip() or 'Single Player Host',
        }, indent=2), encoding='utf-8')
        self.write_note(f'Profile saved: {PROFILE_PATH}')
        self._persist_app_settings()
        self.set_connection_state('PREPARED', f"Profile saved for {payload['player_name']}")

    def save_voice_profile(self):
        payload = {
            'voice_enabled': bool(self.voice_enabled_var.get()),
            'voice_muted': bool(self.voice_muted_var.get()),
            'push_to_talk': self.voice_ptt_var.get().strip() or 'V',
            'device': self.voice_device_var.get().strip() or 'Default Microphone',
        }
        VOICE_PATH.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        self.write_note(f'Voice profile saved: {VOICE_PATH}')

    def _normalize_trainer_weather(self, value: str) -> str:
        raw = (value or '').strip().lower()
        aliases = {
            '': 'default',
            'default': 'default',
            'sun': 'clear',
            'sunny': 'clear',
            'clear': 'clear',
            'day': 'clear',
            'cloudy': 'overcast',
            'overcast': 'overcast',
            'rain': 'rain',
            'rainy': 'rain',
            'storm': 'storm',
            'stormy': 'storm',
            'fog': 'fog',
            'foggy': 'fog',
            'mist': 'fog',
            'snow': 'snow',
            'snowy': 'snow',
        }
        return aliases.get(raw, raw or 'default')

    def _normalize_trainer_time(self, value: str) -> str:
        raw = (value or '').strip().lower()
        aliases = {
            '': 'default',
            'default': 'default',
            'day': '12:00',
            'noon': '12:00',
            'night': '23:00',
            'midnight': '00:00',
            'morning': '08:00',
            'sunrise': '06:00',
            'evening': '18:00',
            'sunset': '19:00',
            'dawn': '06:00',
            'dusk': '19:00',
        }
        raw = aliases.get(raw, raw or 'default')
        if raw == 'default':
            return raw
        if raw.isdigit():
            hour = max(0, min(23, int(raw)))
            return f'{hour:02d}:00'
        if ':' in raw:
            left, right = raw.split(':', 1)
            if left.isdigit() and right.isdigit():
                hour = max(0, min(23, int(left)))
                minute = max(0, min(59, int(right)))
                return f'{hour:02d}:{minute:02d}'
        return raw

    def _normalized_trainer_payload(self, payload: dict | None = None) -> dict:
        payload = payload or {}
        return {
            'god_mode': bool(payload.get('god_mode', self.trainer_god_var.get())),
            'infinite_ammo': bool(payload.get('infinite_ammo', self.trainer_ammo_var.get())),
            'noclip': bool(payload.get('noclip', self.trainer_noclip_var.get())),
            'super_jump': bool(payload.get('super_jump', self.trainer_jump_var.get())),
            'fast_travel': bool(payload.get('fast_travel', self.trainer_fasttravel_var.get())),
            'weather': self._normalize_trainer_weather(str(payload.get('weather', self.trainer_weather_var.get()))),
            'time': self._normalize_trainer_time(str(payload.get('time', self.trainer_time_var.get()))),
        }

    def _trainer_summary(self, payload: dict | None = None) -> str:
        normalized = self._normalized_trainer_payload(payload)
        flags = []
        if normalized['god_mode']:
            flags.append('god')
        if normalized['infinite_ammo']:
            flags.append('ammo')
        if normalized['noclip']:
            flags.append('noclip')
        if normalized['super_jump']:
            flags.append('jump')
        if normalized['fast_travel']:
            flags.append('travel')
        base = ', '.join(flags) if flags else 'default'
        return f"Trainer state: {base} | weather={normalized['weather']} | time={normalized['time']}"

    def _refresh_trainer_status(self) -> None:
        self.trainer_status_var.set(self._trainer_summary())

    def _on_trainer_changed(self, *_args) -> None:
        self._refresh_trainer_status()

    def _set_trainer_from_payload(self, payload: dict | None) -> dict:
        normalized = self._normalized_trainer_payload(payload or {})
        self.trainer_god_var.set(normalized['god_mode'])
        self.trainer_ammo_var.set(normalized['infinite_ammo'])
        self.trainer_noclip_var.set(normalized['noclip'])
        self.trainer_jump_var.set(normalized['super_jump'])
        self.trainer_fasttravel_var.set(normalized['fast_travel'])
        self.trainer_weather_var.set(normalized['weather'])
        self.trainer_time_var.set(normalized['time'])
        self._refresh_trainer_status()
        return normalized

    def apply_trainer_preset(self, preset_key: str) -> None:
        presets = {
            'reset': {
                'god_mode': False,
                'infinite_ammo': False,
                'noclip': False,
                'super_jump': False,
                'fast_travel': False,
                'weather': 'default',
                'time': 'default',
            },
            'combat': {
                'god_mode': True,
                'infinite_ammo': True,
                'noclip': False,
                'super_jump': False,
                'fast_travel': False,
                'weather': 'clear',
                'time': '12:00',
            },
            'explore': {
                'god_mode': False,
                'infinite_ammo': False,
                'noclip': True,
                'super_jump': True,
                'fast_travel': True,
                'weather': 'clear',
                'time': '08:00',
            },
            'host_sync': {
                'god_mode': False,
                'infinite_ammo': False,
                'noclip': False,
                'super_jump': False,
                'fast_travel': True,
                'weather': 'default',
                'time': 'default',
            },
        }
        normalized = self._set_trainer_from_payload(presets.get(preset_key, presets['reset']))
        self.write_note(f"Trainer preset applied: {preset_key} => {self._trainer_summary(normalized)}")

    def trainer_payload(self) -> dict:
        normalized = self._normalized_trainer_payload()
        return {
            **normalized,
            'ts': datetime.now().isoformat(timespec='seconds'),
            'source': 'Code RED Multiplayer Companion v19',
            'summary': self._trainer_summary(normalized),
        }

    def _trainer_bridge_path(self) -> Path | None:
        bridge_dir = self._bridge_dir_from_game_dir()
        if bridge_dir is None:
            return None
        return bridge_dir / TRAINER_BRIDGE_STATE

    def write_trainer_bridge_state(self, show_message: bool = True) -> dict | None:
        path = self._trainer_bridge_path()
        if path is None:
            if show_message:
                messagebox.showerror('Game directory missing', 'Set the game directory before writing trainer bridge state.', parent=self)
            return None
        payload = self.trainer_payload()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        self.write_note(f'Trainer bridge state written: {path}')
        if show_message:
            messagebox.showinfo('Trainer bridge state', f'Trainer bridge state written to:\n{path}', parent=self)
        return payload


    def _trainer_command_path(self) -> Path | None:
        bridge_dir = self._bridge_dir_from_game_dir()
        if bridge_dir is None:
            return None
        return bridge_dir / TRAINER_COMMAND_JSON

    def _trainer_command_queue_path(self) -> Path | None:
        bridge_dir = self._bridge_dir_from_game_dir()
        if bridge_dir is None:
            return None
        return bridge_dir / TRAINER_COMMAND_QUEUE_JSON

    def _trainer_runtime_path(self) -> Path | None:
        bridge_dir = self._bridge_dir_from_game_dir()
        if bridge_dir is None:
            return None
        return bridge_dir / TRAINER_RUNTIME_JSON

    def queue_trainer_command(self, show_message: bool = True) -> dict | None:
        command_path = self._trainer_command_path()
        queue_path = self._trainer_command_queue_path()
        runtime_path = self._trainer_runtime_path()
        if command_path is None or queue_path is None or runtime_path is None:
            if show_message:
                messagebox.showerror('Game directory missing', 'Set the game directory before queueing trainer actions.', parent=self)
            return None
        action = (self.trainer_action_var.get().strip() or 'apply_state').lower()
        target = self.trainer_target_var.get().strip()
        trainer = self.trainer_payload()
        payload = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'action': action,
            'target': target,
            'trainer_profile': trainer,
            'player_name': self.player_name_var.get().strip() or 'Player',
            'session_name': self.session_name_var.get().strip() or 'Code RED Freemode',
            'mode_key': self._mode_preset_key(),
            'mode_label': self._mode_preset_payload().get('label', ''),
            'source': 'Code RED Multiplayer Companion v19',
        }
        self._write_json_path(command_path, payload)
        existing_items = []
        try:
            if queue_path.exists():
                loaded = json.loads(queue_path.read_text(encoding='utf-8'))
                if isinstance(loaded, dict):
                    loaded = loaded.get('items', [])
                if isinstance(loaded, list):
                    existing_items = loaded
        except Exception:
            existing_items = []
        existing_items.append(payload)
        existing_items = existing_items[-24:]
        self._write_json_path(queue_path, {'items': existing_items, 'count': len(existing_items), 'latest_action': action})
        runtime_payload = {
            'ts': payload['ts'],
            'status': 'queued',
            'last_action': action,
            'last_target': target,
            'queue_count': len(existing_items),
            'trainer_summary': trainer.get('summary', ''),
            'mode_key': payload['mode_key'],
            'mode_label': payload['mode_label'],
        }
        self._write_json_path(runtime_path, runtime_payload)
        detail = f"Queued trainer action: {action}" + (f" ({target})" if target else '')
        self.trainer_pack_status_var.set(f"Trainer bridge: queued {action} | {len(existing_items)} recent")
        self.write_note(detail)
        if show_message:
            messagebox.showinfo('Trainer action queued', f'{detail}\n\nCommand file:\n{command_path}', parent=self)
        return payload

    def _trainer_donor_roots(self) -> list[tuple[str, Path]]:
        resources_root = APP_DIR.parent.parent / 'resources' / 'trainers'
        return [
            ('Trainer 2', resources_root / 'Trainer 2'),
            ('RDR-Trainer-master', resources_root / 'RDR-Trainer-master'),
            ('RDR1-Basic-Trainer-Mod-main', resources_root / 'RDR1-Basic-Trainer-Mod-main'),
            ('RedTrainer', resources_root / 'RedTrainer'),
            ('Mod Menu', resources_root / 'Mod Menu'),
        ]

    def _scan_trainer_donors(self) -> dict:
        donors = []
        for label, root in self._trainer_donor_roots():
            exists = root.exists()
            info = {
                'label': label,
                'root': str(root),
                'exists': exists,
            }
            if exists:
                try:
                    files = [p for p in root.rglob('*') if p.is_file()]
                except Exception:
                    files = []
                info.update({
                    'file_count': len(files),
                    'sample_files': [str(p.relative_to(root)) for p in files[:8]],
                    'has_solution': any(p.suffix.lower() == '.sln' for p in files),
                    'has_project': any(p.suffix.lower() in {'.vcxproj', '.csproj'} for p in files),
                    'has_script': any(p.suffix.lower() in {'.wsc', '.c', '.cpp', '.h', '.ini', '.json'} for p in files),
                })
            donors.append(info)
        return {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'clang': shutil.which('clang'),
            'clangxx': shutil.which('clang++'),
            'cl': shutil.which('cl'),
            'dotnet': shutil.which('dotnet'),
            'donors': donors,
        }

    def export_trainer_donor_scan(self) -> dict:
        report = self._scan_trainer_donors()
        json_path = LOGS_DIR / TRAINER_DONOR_SCAN_JSON
        md_path = LOGS_DIR / TRAINER_DONOR_SCAN_MD
        json_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        lines = [
            '# Code RED trainer donor scan',
            '',
            f"Generated: {report['ts']}",
            '',
            '## Host toolchains',
            f"- clang: {report.get('clang') or 'missing'}",
            f"- clang++: {report.get('clangxx') or 'missing'}",
            f"- cl: {report.get('cl') or 'missing'}",
            f"- dotnet: {report.get('dotnet') or 'missing'}",
            '',
            '## Donors',
        ]
        for donor in report['donors']:
            lines.append(f"### {donor['label']}")
            lines.append(f"- exists: {donor['exists']}")
            if donor['exists']:
                lines.append(f"- file_count: {donor.get('file_count', 0)}")
                lines.append(f"- has_solution: {donor.get('has_solution', False)}")
                lines.append(f"- has_project: {donor.get('has_project', False)}")
                lines.append(f"- has_script: {donor.get('has_script', False)}")
                for sample in donor.get('sample_files', []):
                    lines.append(f"  - {sample}")
            lines.append('')
        md_path.write_text('\n'.join(lines).strip() + '\n', encoding='utf-8')
        ready_count = sum(1 for donor in report['donors'] if donor.get('exists'))
        self.trainer_pack_status_var.set(f'Trainer bridge: {ready_count} donor roots scanned')
        self.write_note(f'Trainer donor scan exported: {md_path}')
        messagebox.showinfo('Trainer donor scan', f'Trainer donor scan exported to:\n{md_path}', parent=self)
        return report

    def install_trainer_bridge_pack(self, show_message: bool = True) -> dict | None:
        game_root = self._normalize_game_dir(self.game_dir_var.get().strip())
        bridge_dir = self._bridge_dir_from_game_dir()
        if game_root is None or bridge_dir is None:
            if show_message:
                messagebox.showerror('Game directory missing', 'Set the game directory before installing the trainer bridge pack.', parent=self)
            return None
        trainer_dir = game_root / TRAINER_BRIDGE_PACK_DIRNAME
        trainer_dir.mkdir(parents=True, exist_ok=True)
        bootstrap_path = trainer_dir / TRAINER_BRIDGE_BOOTSTRAP
        manifest_path = trainer_dir / TRAINER_BRIDGE_MANIFEST
        readme_path = trainer_dir / TRAINER_BRIDGE_README
        donor_report = self._scan_trainer_donors()
        self.write_trainer_bridge_state(show_message=False)
        self.queue_trainer_command(show_message=False)
        runtime_path = self._trainer_runtime_path()
        runtime_payload = self._read_json_path(runtime_path) if runtime_path is not None else {}
        bootstrap = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'bridge_dir': str(bridge_dir),
            'trainer_state_path': str(bridge_dir / TRAINER_BRIDGE_STATE),
            'trainer_command_path': str(bridge_dir / TRAINER_COMMAND_JSON),
            'trainer_queue_path': str(bridge_dir / TRAINER_COMMAND_QUEUE_JSON),
            'trainer_runtime_path': str(bridge_dir / TRAINER_RUNTIME_JSON),
            'playerlist_command_path': str(bridge_dir / PLAYERLIST_BRIDGE_COMMAND),
            'mode_key': self._mode_preset_key(),
            'mode_label': self._mode_preset_payload().get('label', ''),
            'overlay_fallback': str(game_root / OVERLAY_DIRNAME / OVERLAY_SCRIPT),
            'donor_labels': [donor['label'] for donor in donor_report['donors'] if donor.get('exists')],
        }
        readme = (
            'Code RED Trainer Bridge Pack\n\n'
            'This pack improves the existing trainer lane by making the current trainer state and quick actions consumable by an external hook, shim, or overlay.\n\n'
            f'- Bootstrap: {TRAINER_BRIDGE_BOOTSTRAP}\n'
            f'- Live trainer state: ..\\{LAUNCH_BRIDGE_DIRNAME}\\{TRAINER_BRIDGE_STATE}\n'
            f'- Live trainer command: ..\\{LAUNCH_BRIDGE_DIRNAME}\\{TRAINER_COMMAND_JSON}\n'
            f'- Live trainer queue: ..\\{LAUNCH_BRIDGE_DIRNAME}\\{TRAINER_COMMAND_QUEUE_JSON}\n'
            f'- Live trainer runtime: ..\\{LAUNCH_BRIDGE_DIRNAME}\\{TRAINER_RUNTIME_JSON}\n\n'
            'Recommended first consumer behavior:\n'
            '- read trainer_bridge_state.json on boot\n'
            '- watch trainer_command.json for one-shot actions\n'
            '- mirror the last processed result into trainer_runtime_state.json\n'
            '- optionally reuse the playerlist and overlay bridge lanes for visible proof\n\n'
            'Bundled donor roots detected by this pass are listed in the manifest and donor scan outputs.\n'
        )
        manifest = {
            'ts': bootstrap['ts'],
            'trainer_dir': str(trainer_dir),
            'bootstrap': str(bootstrap_path),
            'readme': str(readme_path),
            'bridge_dir': str(bridge_dir),
            'runtime_state': runtime_payload,
            'donor_scan': donor_report,
        }
        bootstrap_path.write_text(json.dumps(bootstrap, indent=2), encoding='utf-8')
        readme_path.write_text(readme, encoding='utf-8')
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        self.trainer_pack_status_var.set(f'Trainer bridge: installed at {trainer_dir.name}')
        self.write_note(f'Trainer bridge pack installed: {trainer_dir}')
        if show_message:
            messagebox.showinfo('Trainer bridge pack', f'Trainer bridge pack installed to:\n{trainer_dir}', parent=self)
        return manifest

    def save_trainer_profile(self):
        payload = self.trainer_payload()
        TRAINER_PATH.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        self._set_trainer_from_payload(payload)
        self.write_note(f'Trainer profile saved: {TRAINER_PATH}')

    def copy_trainer_json(self):
        payload = json.dumps(self.trainer_payload(), indent=2)
        self.clipboard_clear()
        self.clipboard_append(payload)
        self.update_idletasks()
        self.write_note('Trainer profile JSON copied to clipboard.')

    def load_saved_profiles(self):
        try:
            if PROFILE_PATH.exists():
                data = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))
                self.player_name_var.set(data.get('player_name', self.player_name_var.get()))
                self.session_name_var.set(data.get('session_name', self.session_name_var.get()))
                self.host_ip_var.set(data.get('host_ip', self.host_ip_var.get()))
                self.host_port_var.set(str(data.get('port', self.host_port_var.get())))
                self.world_name_var.set(data.get('world', self.world_name_var.get()))
                self.boot_target_var.set(data.get('boot_target', self.boot_target_var.get()))
                self.world_route_var.set(data.get('route_note', self.world_route_var.get()))
                if data.get('content_rpf'):
                    self.content_rpf_var.set(str(data.get('content_rpf')))
                if data.get('target_rpf'):
                    self.target_rpf_var.set(str(data.get('target_rpf')))
                if data.get('game_dir'):
                    self.game_dir_var.set(str(data.get('game_dir')))
                if data.get('game_exe'):
                    self.game_exe_var.set(str(data.get('game_exe')))
                if data.get('startup_mode'):
                    self.startup_mode_var.set(str(data.get('startup_mode')))
            if VOICE_PATH.exists():
                data = json.loads(VOICE_PATH.read_text(encoding='utf-8'))
                self.voice_enabled_var.set(bool(data.get('voice_enabled', True)))
                self.voice_muted_var.set(bool(data.get('voice_muted', False)))
                self.voice_ptt_var.set(data.get('push_to_talk', 'V'))
                self.voice_device_var.set(data.get('device', 'Default Microphone'))
            if TRAINER_PATH.exists():
                data = json.loads(TRAINER_PATH.read_text(encoding='utf-8'))
                self._set_trainer_from_payload(data)
            if CHAT_LOG_PATH.exists() and self._chat_text is not None:
                self._chat_text.insert('end', CHAT_LOG_PATH.read_text(encoding='utf-8'))
                self._chat_text.see('end')
        except Exception as exc:
            log_line(f'Profile load failed: {exc}')
        self._load_session_sources()

    def select_game_dir(self):
        chosen = filedialog.askdirectory(parent=self, title='Select Game Directory')
        if not chosen:
            return
        normalized = self._normalize_game_dir(chosen)
        self.game_dir_var.set(str(normalized))
        self.auto_detect_content_rpf()
        self._sync_target_rpf_with_content(force=False)
        self.auto_detect_game_exe()
        self._sync_target_rpf_with_content(force=False)
        self._persist_app_settings()
        self.write_note(f'Selected game directory: {normalized}')


    def select_game_exe(self):
        chosen = filedialog.askopenfilename(parent=self, title='Select Game Executable', filetypes=[('Executables', '*.exe'), ('All files', '*.*')])
        if not chosen:
            return
        picked = Path(chosen)
        self.game_exe_var.set(str(picked))
        normalized = self._normalize_game_dir(picked.parent)
        self.game_dir_var.set(str(normalized))
        self.auto_detect_content_rpf()
        self._sync_target_rpf_with_content(force=False)
        self._persist_app_settings()
        self.write_note(f'Selected game executable: {picked}')
        self.set_connection_state('PREPARED', f'Game executable set: {picked.name}')

    def auto_detect_game_exe(self):
        game_dir = self._normalize_game_dir(self.game_dir_var.get().strip())
        if game_dir and str(game_dir) != self.game_dir_var.get().strip():
            self.game_dir_var.set(str(game_dir))
        selected = ''
        targets = self._launcher_targets(game_dir)
        if targets.get('primary'):
            selected = str(targets['primary'])
        if selected:
            self.game_exe_var.set(selected)
            reason = targets.get('primary_reason', 'auto-detected')
            self.write_note(f'Detected game executable: {selected} ({reason})')
            if targets.get('hook_warnings'):
                for warning in targets['hook_warnings']:
                    self.write_note(f'Hook audit: {warning}')
            self._persist_app_settings()
        elif not self.game_exe_var.get().strip():
            self.write_note('Game executable was not found automatically under the current game directory.')

    def apply_workbench_sync(self):
        try:
            if not WORKBENCH_SYNC_PATH.exists():
                return
            data = json.loads(WORKBENCH_SYNC_PATH.read_text(encoding='utf-8'))
            if data.get('game_dir'):
                self.game_dir_var.set(str(data.get('game_dir')))
            if data.get('content_rpf'):
                self.content_rpf_var.set(str(data.get('content_rpf')))
            self._sync_target_rpf_with_content(force=False)
            if data.get('world'):
                self.world_name_var.set(data.get('world'))
            if data.get('boot_target'):
                self.boot_target_var.set(data.get('boot_target'))
            if data.get('route_note'):
                self.world_route_var.set(data.get('route_note'))
            self._persist_app_settings()
            self.write_note(f'Applied workbench sync: {WORKBENCH_SYNC_PATH}')
            self.set_connection_state('PREPARED', 'Workbench sync applied.')
        except Exception as exc:
            log_line(f'Workbench sync load failed: {exc}')

    def _launcher_targets(self, game_dir: Path) -> dict:
        info = {
            'primary': None,
            'playrdr': None,
            'rdr': None,
            'message': None,
            'all': [],
            'primary_reason': '',
            'hook_warnings': [],
            'hook_strategy': 'none',
        }
        if not game_dir.exists():
            return info
        candidates = []
        try:
            candidates.extend(sorted(game_dir.glob('*.exe')))
            if (game_dir / 'bin').exists():
                candidates.extend(sorted((game_dir / 'bin').glob('*.exe')))
        except Exception:
            candidates = []
        deduped = []
        seen = set()
        for candidate in candidates:
            key = str(candidate).lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
        info['all'] = deduped
        for candidate in deduped:
            low = candidate.name.lower()
            if low == 'playrdr.exe' and info['playrdr'] is None:
                info['playrdr'] = candidate
            elif low == 'rdr.exe' and info['rdr'] is None:
                info['rdr'] = candidate
            elif low == 'rdrmessage.exe' and info['message'] is None:
                info['message'] = candidate

        markers = {
            'redhook': (game_dir / 'RedHook.dll').exists(),
            'scripthook': (game_dir / 'ScriptHookRDR.dll').exists(),
            'dinput8': (game_dir / 'dinput8.dll').exists(),
            'winmm': (game_dir / 'winmm.dll').exists(),
        }
        mixed_hooks = markers['redhook'] and markers['scripthook']
        if mixed_hooks:
            info['hook_warnings'].append('RedHook.dll and ScriptHookRDR.dll are both present; mixed hook stacks can crash shortly after load.')
        if markers['dinput8'] and markers['winmm']:
            info['hook_warnings'].append('Both dinput8.dll and winmm.dll loader shims are present; keep only the loader your selected hook requires.')

        if mixed_hooks and info['rdr'] is not None:
            info['primary'] = info['rdr']
            info['primary_reason'] = 'mixed hook stack detected; preferring direct RDR.exe'
            info['hook_strategy'] = 'mixed_hooks_prefers_rdr'
        elif markers['scripthook'] and info['rdr'] is not None:
            info['primary'] = info['rdr']
            info['primary_reason'] = 'ScriptHookRDR detected; preferring direct RDR.exe'
            info['hook_strategy'] = 'scripthook_prefers_rdr'
        elif markers['redhook'] and info['playrdr'] is not None:
            info['primary'] = info['playrdr']
            info['primary_reason'] = 'RedHook detected; preferring PlayRDR.exe wrapper'
            info['hook_strategy'] = 'redhook_prefers_playrdr'
        else:
            preferred = [info['playrdr'], info['rdr'], info['message']]
            info['primary'] = next((candidate for candidate in preferred if candidate is not None), deduped[0] if deduped else None)
            if info['primary'] is not None:
                info['primary_reason'] = 'default executable priority'
                info['hook_strategy'] = 'default_priority'
        return info

    def _hook_groups(self, game_dir: Path) -> dict[str, list[Path]]:
        return {
            'redhook': [game_dir / 'RedHook.dll', game_dir / 'RedHook.ini', game_dir / 'winmm.dll'],
            'scripthook': [game_dir / 'ScriptHookRDR.dll', game_dir / 'dinput8.dll'],
        }

    def _disabled_hook_path(self, path: Path) -> Path:
        return path.with_name(path.name + HOOK_DISABLED_SUFFIX)

    def _park_conflicting_path(self, path: Path) -> tuple[bool, Path | None]:
        if not path.exists():
            return False, None
        disabled = self._disabled_hook_path(path)
        if disabled.exists():
            return False, disabled
        path.rename(disabled)
        return True, disabled

    def _restore_managed_hooks(self, show_message: bool = False) -> dict:
        if not HOOK_STATE_PATH.exists():
            return {'restored': 0, 'paths': []}
        try:
            manifest = json.loads(HOOK_STATE_PATH.read_text(encoding='utf-8'))
        except Exception:
            return {'restored': 0, 'paths': []}
        restored = []
        for item in manifest.get('disabled', []):
            disabled = Path(item.get('disabled', ''))
            original = Path(item.get('original', ''))
            try:
                if disabled.exists() and not original.exists():
                    disabled.rename(original)
                    restored.append(str(original))
            except Exception as exc:
                log_line(f'Hook restore failed for {disabled}: {exc}')
        try:
            HOOK_STATE_PATH.unlink()
        except Exception:
            pass
        if restored:
            self.write_note(f'Restored parked hook files: {len(restored)}')
            if show_message:
                messagebox.showinfo('Hooks restored', '\n'.join(restored), parent=self)
        return {'restored': len(restored), 'paths': restored}

    def _auto_manage_hooks_for_launch(self, game_dir: Path, root_report: dict | None = None) -> dict:
        report = root_report or {}
        conflicts = report.get('hook_conflicts', {}) or {}
        markers = (report.get('markers', {}) or {})
        if not self.auto_manage_hooks_var.get():
            targets = self._launcher_targets(game_dir)
            return {'lane': targets.get('hook_strategy', 'none'), 'disabled': [], 'recommended_exe': str(targets.get('primary')) if targets.get('primary') else ''}
        has_red = bool(markers.get('RedHook.dll') or (game_dir / 'RedHook.dll').exists())
        has_script = bool(markers.get('ScriptHookRDR.dll') or (game_dir / 'ScriptHookRDR.dll').exists())
        mixed_hooks = bool(conflicts.get('mixed_hook_stack')) or (has_red and has_script)
        mixed_loader = bool(conflicts.get('mixed_loader_stack')) or ((game_dir / 'dinput8.dll').exists() and (game_dir / 'winmm.dll').exists())
        lane = 'none'
        if mixed_hooks or mixed_loader:
            lane = 'scripthook' if has_script else ('redhook' if has_red else 'none')
        elif has_script:
            lane = 'scripthook'
        elif has_red:
            lane = 'redhook'
        disabled = []
        if lane in {'scripthook', 'redhook'}:
            groups = self._hook_groups(game_dir)
            to_disable = groups['redhook'] if lane == 'scripthook' else groups['scripthook']
            for path in to_disable:
                changed, disabled_path = self._park_conflicting_path(path)
                if changed and disabled_path is not None:
                    disabled.append({'original': str(path), 'disabled': str(disabled_path)})
            manifest = {
                'ts': datetime.now().isoformat(timespec='seconds'),
                'game_dir': str(game_dir),
                'lane': lane,
                'disabled': disabled,
            }
            if disabled:
                HOOK_STATE_PATH.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
                self._managed_hook_manifest = manifest
                self.write_note(f'Auto-managed hook lane => {lane}; parked {len(disabled)} conflicting file(s).')
        targets = self._launcher_targets(game_dir)
        recommended = str(targets.get('primary')) if targets.get('primary') else ''
        if recommended:
            self.game_exe_var.set(recommended)
            self.write_note(f'Launch executable after hook audit => {recommended}')
        return {'lane': lane, 'disabled': disabled, 'recommended_exe': recommended}

    def _candidate_save_roots(self, game_dir: Path) -> list[Path]:
        candidates: list[Path] = []
        seen: set[str] = set()

        def add(path: Path | None):
            if path is None:
                return
            key = str(path).lower()
            if key in seen:
                return
            seen.add(key)
            candidates.append(path)

        if game_dir:
            for rel in ('profiles', 'profile', 'Profile', 'savegames', 'SaveGames', 'saves', 'Saves', 'savedata', 'players'):
                add(game_dir / rel)
        userprofile = os.environ.get('USERPROFILE')
        homes = []
        if userprofile:
            homes.append(Path(userprofile))
        try:
            homes.append(Path.home())
        except Exception:
            pass
        for home in homes:
            add(home / 'Documents' / 'Rockstar Games' / 'Red Dead Redemption')
            add(home / 'Documents' / 'Rockstar Games' / 'Red Dead Redemption' / 'Profiles')
            add(home / 'Documents' / 'Rockstar Games' / 'Red Dead Redemption' / 'SaveGames')
            add(home / 'Saved Games' / 'Red Dead Redemption')
        return candidates

    def _scan_save_candidates(self, game_dir: Path) -> dict:
        roots = self._candidate_save_roots(game_dir)
        hits = []
        for root in roots:
            if not root.exists():
                continue
            try:
                if root.is_file():
                    name = root.name.lower()
                    if root.suffix.lower() in {'.sav', '.bin', '.dat', '.bak', '.save', '.sgd'} or 'save' in name or 'profile' in name:
                        hits.append(str(root))
                    continue
                for path in root.rglob('*'):
                    if len(hits) >= 30:
                        break
                    try:
                        if path.is_file():
                            name = path.name.lower()
                            if path.suffix.lower() in {'.sav', '.bin', '.dat', '.bak', '.save', '.sgd'} or 'save' in name or 'profile' in name:
                                hits.append(str(path))
                    except Exception:
                        continue
            except Exception:
                continue
        return {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'game_dir': str(game_dir),
            'candidate_roots': [str(path) for path in roots],
            'found_count': len(hits),
            'hits': hits,
            'primary_candidate': hits[0] if hits else '',
            'status': ('save(s) detected' if hits else 'no likely save files detected'),
        }

    def _render_save_scan_markdown(self, report: dict) -> str:
        lines = [
            '# Code RED save scan',
            '',
            f"- Timestamp: {report.get('ts', '')}",
            f"- Game dir: {report.get('game_dir', '')}",
            f"- Found count: {report.get('found_count', 0)}",
            f"- Status: {report.get('status', '')}",
            '',
            '## Candidate roots',
        ]
        lines.extend([f"- {value}" for value in report.get('candidate_roots', [])] or ['- none'])
        lines.extend(['', '## Detected save/profile files'])
        lines.extend([f"- {value}" for value in report.get('hits', [])] or ['- none'])
        return '\n'.join(lines).strip() + '\n'

    def check_save_state(self, show_message: bool = True) -> dict:
        game_dir = Path(self.game_dir_var.get().strip())
        report = self._scan_save_candidates(game_dir)
        md = self._render_save_scan_markdown(report)
        (CONFIG_DIR / SAVE_SCAN_REPORT_JSON).write_text(json.dumps(report, indent=2), encoding='utf-8')
        (CONFIG_DIR / SAVE_SCAN_REPORT_MD).write_text(md, encoding='utf-8')
        (LOGS_DIR / SAVE_SCAN_REPORT_JSON).write_text(json.dumps(report, indent=2), encoding='utf-8')
        (LOGS_DIR / SAVE_SCAN_REPORT_MD).write_text(md, encoding='utf-8')
        self.save_status_var.set(f"{report['found_count']} save/profile hit(s)" if report['found_count'] else 'No likely save/profile files detected')
        self.write_note(f"Save scan => {report['status']}")
        if show_message:
            messagebox.showinfo('Save scan', json.dumps(report, indent=2), parent=self)
        return report

    def _game_root_report(self, game_dir: Path) -> dict:
        targets = self._launcher_targets(game_dir)
        bridge_dir = game_dir / LAUNCH_BRIDGE_DIRNAME
        markers = {
            'title.rgl': (game_dir / 'title.rgl').exists(),
            'metadata.dat': (game_dir / 'metadata.dat').exists(),
            'dinput8.dll': (game_dir / 'dinput8.dll').exists(),
            'winmm.dll': (game_dir / 'winmm.dll').exists(),
            'ScriptHookRDR.dll': (game_dir / 'ScriptHookRDR.dll').exists(),
            'RedHook.dll': (game_dir / 'RedHook.dll').exists(),
            'RedHook.ini': (game_dir / 'RedHook.ini').exists(),
            'ScriptHookConfig.ini': (game_dir / 'ScriptHookConfig.ini').exists(),
            'NewCenter.red': (game_dir / 'NewCenter.red').exists(),
            'asiloader.log': (game_dir / 'asiloader.log').exists(),
            'RedHook.Log': (game_dir / 'RedHook.Log').exists(),
            'ScriptHookRDR.log': (game_dir / 'ScriptHookRDR.log').exists(),
        }
        content_path = self._content_rpf()
        report = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'game_dir': str(game_dir),
            'exists': game_dir.exists(),
            'selected_content_rpf': str(content_path) if content_path else '',
            'selected_mode': self._mode_preset_payload(),
            'launch_targets': {
                'primary': str(targets['primary']) if targets['primary'] else '',
                'playrdr': str(targets['playrdr']) if targets['playrdr'] else '',
                'rdr': str(targets['rdr']) if targets['rdr'] else '',
                'rdrmessage': str(targets['message']) if targets['message'] else '',
                'all': [str(candidate) for candidate in targets['all']],
            },
            'markers': markers,
            'bridge_dir': str(bridge_dir),
            'bridge_present': bridge_dir.exists(),
            'launcher_files_present': {
                'Code_RED_Launcher.bat': (game_dir / 'Code_RED_Launcher.bat').exists(),
                'Code_RED_Launcher.ps1': (game_dir / 'Code_RED_Launcher.ps1').exists(),
                'Code_RED_Launcher.py': (game_dir / 'Code_RED_Launcher.py').exists(),
                'Code_RED_Launcher.cs': (game_dir / 'Code_RED_Launcher.cs').exists(),
                ROOT_LAUNCHER_MANIFEST: (game_dir / ROOT_LAUNCHER_MANIFEST).exists(),
                f'{HOOK_PACK_DIRNAME}/{HOOK_PLUGIN_SOURCE}': (game_dir / HOOK_PACK_DIRNAME / HOOK_PLUGIN_SOURCE).exists(),
                f'{HOOK_PACK_DIRNAME}/{HOOK_PLUGIN_BUILD_BAT}': (game_dir / HOOK_PACK_DIRNAME / HOOK_PLUGIN_BUILD_BAT).exists(),
                f'{HOOK_PACK_DIRNAME}/{HOOK_PACK_MANIFEST}': (game_dir / HOOK_PACK_DIRNAME / HOOK_PACK_MANIFEST).exists(),
            },
        }
        report['ready_for_bridge_pack'] = bool(game_dir.exists() and targets['primary'])
        report['hook_support_score'] = sum(1 for key in ('dinput8.dll', 'winmm.dll', 'ScriptHookRDR.dll', 'RedHook.dll') if markers[key])
        report['hook_logs'] = {
            'asiloader.log': str(game_dir / 'asiloader.log'),
            'RedHook.Log': str(game_dir / 'RedHook.Log'),
            'ScriptHookRDR.log': str(game_dir / 'ScriptHookRDR.log'),
        }
        report['recommended_launch_strategy'] = targets.get('primary_reason') or ('PlayRDR.exe wrapper' if targets['playrdr'] else ('Direct RDR.exe wrapper' if targets['rdr'] else 'Manual EXE selection required'))
        report['recommended_hook_strategy'] = 'Generated RedHook plugin scaffold (Code_RED_HookBridge)' if markers['RedHook.dll'] else ('ScriptHook/ASI-only launch bridge' if markers['ScriptHookRDR.dll'] else 'Launcher-only bridge')
        report['recommended_primary_exe'] = str(targets['primary']) if targets.get('primary') else ''
        report['hook_warnings'] = list(targets.get('hook_warnings', []))
        report['hook_conflicts'] = {
            'mixed_hook_stack': bool(markers['RedHook.dll'] and markers['ScriptHookRDR.dll']),
            'mixed_loader_stack': bool(markers['dinput8.dll'] and markers['winmm.dll']),
        }
        return report

    def _render_game_root_markdown(self, report: dict) -> str:
        lines = [
            '# Code RED game-root validation',
            '',
            f"- timestamp: {report.get('ts', '')}",
            f"- game_dir: {report.get('game_dir', '')}",
            f"- ready_for_bridge_pack: {report.get('ready_for_bridge_pack', False)}",
            f"- recommended_launch_strategy: {report.get('recommended_launch_strategy', '')}",
            f"- recommended_hook_strategy: {report.get('recommended_hook_strategy', '')}",
            f"- selected_content_rpf: {report.get('selected_content_rpf', '')}",
            '',
            '## launch targets',
        ]
        launch_targets = report.get('launch_targets', {})
        for key in ('primary', 'playrdr', 'rdr', 'rdrmessage'):
            lines.append(f"- {key}: {launch_targets.get(key, '')}")
        lines.extend(['', '## marker files'])
        for key, value in sorted(report.get('markers', {}).items()):
            lines.append(f"- {key}: {'present' if value else 'missing'}")
        lines.extend(['', '## root launcher files'])
        for key, value in sorted(report.get('launcher_files_present', {}).items()):
            lines.append(f"- {key}: {'present' if value else 'missing'}")
        lines.extend(['', '## hook warnings'])
        for warning in report.get('hook_warnings', []) or ['none']:
            lines.append(f"- {warning}")
        lines.extend(['', '## hook conflicts'])
        for key, value in sorted(report.get('hook_conflicts', {}).items()):
            lines.append(f"- {key}: {'yes' if value else 'no'}")
        lines.extend(['', '## hook logs'])
        for key, value in sorted(report.get('hook_logs', {}).items()):
            lines.append(f"- {key}: {value}")
        lines.extend(['', '## note', 'These checks validate launcher / hook markers in the main game directory. They do not prove in-engine mode activation.'])
        return '\n'.join(lines) + '\n'

    def validate_game_root(self, show_message: bool = True) -> dict:
        game_dir = Path(self.game_dir_var.get().strip())
        report = self._game_root_report(game_dir)
        report_json_path = LOGS_DIR / GAME_ROOT_VALIDATOR_JSON
        report_md_path = LOGS_DIR / GAME_ROOT_VALIDATOR_MD
        report_json_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        report_md_path.write_text(self._render_game_root_markdown(report), encoding='utf-8')
        if report.get('launch_targets', {}).get('primary') and not self.game_exe_var.get().strip():
            self.game_exe_var.set(report['launch_targets']['primary'])
        self.write_note(f'Game-root validation saved: {report_json_path}')
        if show_message:
            messagebox.showinfo('Game-root validation', f"Validation saved to:\n{report_json_path}\n\nRecommended strategy:\n{report.get('recommended_launch_strategy', '')}", parent=self)
        return report

    def _write_root_launcher_pack(self, game_dir: Path, plan: dict, bridge_dir: Path, report: dict | None = None) -> dict:
        game_dir.mkdir(parents=True, exist_ok=True)
        report = report or self._game_root_report(game_dir)
        targets = self._launcher_targets(game_dir)
        play_name = targets['playrdr'].name if targets['playrdr'] else 'PlayRDR.exe'
        rdr_name = targets['rdr'].name if targets['rdr'] else 'RDR.exe'
        primary_name = Path(plan.get('selected_exe') or (str(targets['primary']) if targets['primary'] else play_name)).name
        bridge_name = bridge_dir.name
        py_launcher = game_dir / 'Code_RED_Launcher.py'
        bat_launcher = game_dir / 'Code_RED_Launcher.bat'
        ps_launcher = game_dir / 'Code_RED_Launcher.ps1'
        cs_launcher = game_dir / 'Code_RED_Launcher.cs'
        manifest_path = game_dir / ROOT_LAUNCHER_MANIFEST
        readme_path = game_dir / 'Code_RED_Launcher_README.txt'
        guide_path = game_dir / 'Red_Bridge_Guide.txt'
        recommendations_path = game_dir / 'Code_RED_External_Recommendations.txt'
        dep_py_path = game_dir / 'Code_RED_Dependency_Installer.py'
        dep_bat_path = game_dir / 'Code_RED_Dependency_Installer.bat'
        dep_ps_path = game_dir / 'Code_RED_Dependency_Installer.ps1'

        bat_text = dedent(fr'''
            @echo off
            setlocal
            set ROOT=%~dp0
            set BRIDGE_DIR=%ROOT%{bridge_name}
            set TARGET={primary_name}
            set OVERLAY_DIR=%ROOT%{OVERLAY_DIRNAME}
            set OVERLAY_SCRIPT=%OVERLAY_DIR%\{OVERLAY_SCRIPT}
            set OVERLAY_LAUNCHER=%OVERLAY_DIR%\{OVERLAY_LAUNCH_BAT}
            set OVERLAY_EXE=%OVERLAY_DIR%\{OVERLAY_EXE}
            if /I "%~1"=="play" set TARGET={play_name}
            if /I "%~1"=="direct" set TARGET={rdr_name}
            set CODERED_BRIDGE_DIR=%BRIDGE_DIR%
            set CODERED_ACTIVE_SESSION=%BRIDGE_DIR%\active_session.json
            set CODERED_LAUNCH_PLAN=%BRIDGE_DIR%\launch_plan.json
            set CODERED_HOOK_BOOTSTRAP=%ROOT%Code_RED_HookBridge\hook_bootstrap.json
            set CODERED_HOOK_PACK_DIR=%ROOT%Code_RED_HookBridge
            set CODERED_OVERLAY_DIR=%OVERLAY_DIR%
            set CODERED_OVERLAY_BOOTSTRAP=%OVERLAY_DIR%\{OVERLAY_BOOTSTRAP_JSON}
            set PLAYERLIST_PLUGIN=%ROOT%{PLAYERLIST_BRIDGE_OUTPUT}
            set PLAYERLIST_SIM=%ROOT%{PLAYERLIST_BRIDGE_DIRNAME}\{PLAYERLIST_BRIDGE_SIM}
            if not exist "%PLAYERLIST_PLUGIN%" if exist "%PLAYERLIST_SIM%" (
              where py >nul 2>&1 && start "Code RED Playerlist Seed" /min py -3 "%PLAYERLIST_SIM%" open_playerlist
              if errorlevel 1 where python >nul 2>&1 && start "Code RED Playerlist Seed" /min python "%PLAYERLIST_SIM%" open_playerlist
            )
            if exist "%BRIDGE_DIR%\{LAUNCH_BRIDGE_RUNTIME}" (
              where py >nul 2>&1 && start "Code RED Runtime Bridge" /min py -3 "%BRIDGE_DIR%\{LAUNCH_BRIDGE_RUNTIME}" "%BRIDGE_DIR%"
              if errorlevel 1 where python >nul 2>&1 && start "Code RED Runtime Bridge" /min python "%BRIDGE_DIR%\{LAUNCH_BRIDGE_RUNTIME}" "%BRIDGE_DIR%"
            )
            if exist "%OVERLAY_LAUNCHER%" (
              start "Code RED Overlay" /min cmd /c ""%OVERLAY_LAUNCHER%""
            ) else if exist "%OVERLAY_EXE%" (
              start "Code RED Overlay" "%OVERLAY_EXE%"
            ) else if exist "%OVERLAY_SCRIPT%" (
              where pyw >nul 2>&1 && start "Code RED Overlay" pyw -3 "%OVERLAY_SCRIPT%"
              if errorlevel 1 where py >nul 2>&1 && start "Code RED Overlay" py -3 "%OVERLAY_SCRIPT%"
              if errorlevel 1 where pythonw >nul 2>&1 && start "Code RED Overlay" pythonw "%OVERLAY_SCRIPT%"
              if errorlevel 1 where python >nul 2>&1 && start "Code RED Overlay" python "%OVERLAY_SCRIPT%"
            )
            if exist "%ROOT%%TARGET%" (
              start "" "%ROOT%%TARGET%"
            ) else (
              echo Target executable not found: %ROOT%%TARGET%
            )
            endlocal
        ''').strip() + "\r\n"

        ps_text = dedent(f'''
            $Root = Split-Path -Parent $MyInvocation.MyCommand.Path
            $BridgeDir = Join-Path $Root '{bridge_name}'
            $OverlayDir = Join-Path $Root '{OVERLAY_DIRNAME}'
            $OverlayScript = Join-Path $OverlayDir '{OVERLAY_SCRIPT}'
            $OverlayLauncher = Join-Path $OverlayDir '{OVERLAY_LAUNCH_BAT}'
            $OverlayExe = Join-Path $OverlayDir '{OVERLAY_EXE}'
            $Target = '{primary_name}'
            if ($args.Count -gt 0 -and $args[0] -eq 'play') {{ $Target = '{play_name}' }}
            if ($args.Count -gt 0 -and $args[0] -eq 'direct') {{ $Target = '{rdr_name}' }}
            $env:CODERED_BRIDGE_DIR = $BridgeDir
            $env:CODERED_ACTIVE_SESSION = Join-Path $BridgeDir 'active_session.json'
            $env:CODERED_LAUNCH_PLAN = Join-Path $BridgeDir 'launch_plan.json'
            $env:CODERED_HOOK_BOOTSTRAP = Join-Path (Join-Path $Root 'Code_RED_HookBridge') 'hook_bootstrap.json'
            $env:CODERED_HOOK_PACK_DIR = Join-Path $Root 'Code_RED_HookBridge'
            $env:CODERED_OVERLAY_DIR = $OverlayDir
            $env:CODERED_OVERLAY_BOOTSTRAP = Join-Path $OverlayDir '{OVERLAY_BOOTSTRAP_JSON}'
            $playerlistPlugin = Join-Path $Root '{PLAYERLIST_BRIDGE_OUTPUT}'
            $playerlistSim = Join-Path (Join-Path $Root '{PLAYERLIST_BRIDGE_DIRNAME}') '{PLAYERLIST_BRIDGE_SIM}'
            if (-not (Test-Path $playerlistPlugin) -and (Test-Path $playerlistSim)) {{
              Start-Process -WindowStyle Hidden -FilePath 'py' -ArgumentList @('-3', $playerlistSim, 'open_playerlist') -ErrorAction SilentlyContinue
            }}
            $runtimeScript = Join-Path $BridgeDir '{LAUNCH_BRIDGE_RUNTIME}'
            if (Test-Path $runtimeScript) {{
              Start-Process -WindowStyle Hidden -FilePath 'py' -ArgumentList @('-3', $runtimeScript, $BridgeDir) -ErrorAction SilentlyContinue
            }}
            if (Test-Path $OverlayScript) {{
              Start-Process -FilePath 'py' -ArgumentList @('-3', $OverlayScript) -ErrorAction SilentlyContinue
            }}
            $targetPath = Join-Path $Root $Target
            if (Test-Path $targetPath) {{
              Start-Process -FilePath $targetPath
            }} else {{
              Write-Host "Target executable not found: $targetPath"
            }}
        ''').strip() + "\n"

        py_text = dedent(f'''
            from __future__ import annotations
            import os
            import subprocess
            import sys
            from pathlib import Path

            ROOT = Path(__file__).resolve().parent
            BRIDGE_DIR = ROOT / '{bridge_name}'
            OVERLAY_DIR = ROOT / '{OVERLAY_DIRNAME}'
            OVERLAY_SCRIPT_PATH = OVERLAY_DIR / '{OVERLAY_SCRIPT}'
            OVERLAY_LAUNCHER = OVERLAY_DIR / '{OVERLAY_LAUNCH_BAT}'
            OVERLAY_EXE_PATH = OVERLAY_DIR / '{OVERLAY_EXE}'
            TARGETS = {{'primary': '{primary_name}', 'play': '{play_name}', 'direct': '{rdr_name}'}}
            mode = sys.argv[1].strip().lower() if len(sys.argv) > 1 else 'primary'
            target_name = TARGETS.get(mode, TARGETS['primary'])
            target = ROOT / target_name
            env = os.environ.copy()
            env['CODERED_BRIDGE_DIR'] = str(BRIDGE_DIR)
            env['CODERED_ACTIVE_SESSION'] = str(BRIDGE_DIR / 'active_session.json')
            env['CODERED_LAUNCH_PLAN'] = str(BRIDGE_DIR / 'launch_plan.json')
            env['CODERED_HOOK_BOOTSTRAP'] = str(ROOT / 'Code_RED_HookBridge' / 'hook_bootstrap.json')
            env['CODERED_HOOK_PACK_DIR'] = str(ROOT / 'Code_RED_HookBridge')
            env['CODERED_OVERLAY_DIR'] = str(OVERLAY_DIR)
            env['CODERED_OVERLAY_BOOTSTRAP'] = str(OVERLAY_DIR / '{OVERLAY_BOOTSTRAP_JSON}')
            playerlist_plugin = ROOT / '{PLAYERLIST_BRIDGE_OUTPUT}'
            playerlist_sim = ROOT / '{PLAYERLIST_BRIDGE_DIRNAME}' / '{PLAYERLIST_BRIDGE_SIM}'
            if (not playerlist_plugin.exists()) and playerlist_sim.exists():
                for candidate in (['py', '-3'], ['python']):
                    try:
                        subprocess.Popen(candidate + [str(playerlist_sim), 'open_playerlist'], cwd=str(playerlist_sim.parent), env=env)
                        break
                    except Exception:
                        pass
            runtime = BRIDGE_DIR / '{LAUNCH_BRIDGE_RUNTIME}'
            for candidate in (['py', '-3'], ['python']):
                if runtime.exists():
                    try:
                        subprocess.Popen(candidate + [str(runtime), str(BRIDGE_DIR)], cwd=str(ROOT), env=env)
                        break
                    except Exception:
                        pass
            for candidate in (['py', '-3'], ['python']):
                if OVERLAY_SCRIPT_PATH.exists():
                    try:
                        subprocess.Popen(candidate + [str(OVERLAY_SCRIPT_PATH)], cwd=str(OVERLAY_DIR), env=env)
                        break
                    except Exception:
                        pass
            if target.exists():
                subprocess.Popen([str(target)], cwd=str(ROOT), env=env)
            else:
                print(f'Target executable not found: {{target}}')
        ''').strip() + "\n"

        cs_text = dedent(f'''
            using System;
            using System.Diagnostics;
            using System.IO;

            class CodeRedLauncher
            {{
                static int Main(string[] args)
                {{
                    string root = AppDomain.CurrentDomain.BaseDirectory;
                    string bridgeDir = Path.Combine(root, "{bridge_name}");
                    string target = "{primary_name}";
                    if (args.Length > 0 && string.Equals(args[0], "play", StringComparison.OrdinalIgnoreCase)) target = "{play_name}";
                    if (args.Length > 0 && string.Equals(args[0], "direct", StringComparison.OrdinalIgnoreCase)) target = "{rdr_name}";
                    string targetPath = Path.Combine(root, target);
                    if (!File.Exists(targetPath))
                    {{
                        Console.WriteLine("Target executable not found: " + targetPath);
                        return 1;
                    }}
                    var psi = new ProcessStartInfo(targetPath)
                    {{
                        WorkingDirectory = root,
                        UseShellExecute = false,
                    }};
                    psi.EnvironmentVariables["CODERED_BRIDGE_DIR"] = bridgeDir;
                    psi.EnvironmentVariables["CODERED_ACTIVE_SESSION"] = Path.Combine(bridgeDir, "active_session.json");
                    psi.EnvironmentVariables["CODERED_LAUNCH_PLAN"] = Path.Combine(bridgeDir, "launch_plan.json");
                    psi.EnvironmentVariables["CODERED_HOOK_BOOTSTRAP"] = Path.Combine(root, "Code_RED_HookBridge", "hook_bootstrap.json");
                    psi.EnvironmentVariables["CODERED_HOOK_PACK_DIR"] = Path.Combine(root, "Code_RED_HookBridge");
                    Process.Start(psi);
                    return 0;
                }}
            }}
        ''').strip() + "\n"

        dep_py_text = dedent('''
            from __future__ import annotations
            import subprocess
            import sys
            from pathlib import Path

            ROOT = Path(__file__).resolve().parent
            REQUIREMENTS = ROOT / 'Code_RED' / 'requirements.txt'
            CORE_PACKAGES = ['pillow', 'cryptography', 'numpy', 'matplotlib']

            def run(cmd: list[str]) -> int:
                print('> ' + ' '.join(cmd))
                return subprocess.call(cmd)

            def main() -> int:
                python = sys.executable or 'python'
                code = run([python, '-m', 'pip', 'install', '--upgrade', 'pip'])
                if code:
                    return code
                if REQUIREMENTS.exists():
                    code = run([python, '-m', 'pip', 'install', '-r', str(REQUIREMENTS)])
                else:
                    code = run([python, '-m', 'pip', 'install', *CORE_PACKAGES])
                print('\nExternal components are not bundled here.')
                print('- ScriptHookRDR: recommended baseline when you want the simpler hook route.')
                print('- RedHook: advanced optional route for the generated .red bridge plugin scaffold.')
                print('- Do not assume both hook stacks should be active together; test one strategy at a time.')
                print('- Visual Studio Build Tools 2022 x64 are recommended only if you compile the C++ or C# launcher sources.')
                return code

            if __name__ == '__main__':
                raise SystemExit(main())
        ''').strip() + "\n"

        dep_bat_text = dedent('''
            @echo off
            setlocal
            where py >nul 2>&1 && py -3 "%~dp0Code_RED_Dependency_Installer.py"
            if errorlevel 1 where python >nul 2>&1 && python "%~dp0Code_RED_Dependency_Installer.py"
            if errorlevel 1 echo Python 3.11+ was not found on PATH.
            endlocal
        ''').strip() + "\r\n"

        dep_ps_text = dedent('''
            $Root = Split-Path -Parent $MyInvocation.MyCommand.Path
            $Script = Join-Path $Root 'Code_RED_Dependency_Installer.py'
            try {
              py -3 $Script
            } catch {
              python $Script
            }
        ''').strip() + "\n"

        guide_text = dedent(f'''
            Red Bridge help guide

            What this is
            - Code RED = the recovery, patching, and diagnostics workbench.
            - Red Bridge = the game-directory launch and bridge layer that carries session, mode, and activation data toward the running game.

            What Red Bridge installs
            - Code_RED_Launcher.bat / .ps1 / .py / .cs
            - Code_RED_Launch folder for runtime bridge files and activation requests
            - Code_RED_HookBridge folder for the optional advanced hook scaffold
            - Code_RED_Overlay folder for the visible trainer-style fallback that now launches automatically with the root launcher when present
            - dependency installer wrappers for Python-side pieces

            Recommended use
            1. Validate the game root in the Multiplayer Companion.
            2. Choose a mode preset and validate the boot route against content.rpf.
            3. Single Player Host can prompt for detected save/profile files and auto-host the current session on launch.
            4. Install the main-directory pack.
            5. Run the dependency installer if you plan to use the Python bridge scripts directly.
            6. Launch through Code_RED_Launcher.bat first.

            External dependency policy
            - RedHook is NOT bundled here. It stays third-party and must be obtained by the user separately if they want that route.
            - ScriptHookRDR is also external. It can be used as the simpler baseline route when RedHook is not desired.
            - Because hook stacks can conflict, treat RedHook and ScriptHookRDR as separate strategies and test one at a time.
            - If you compile the generated C++ or C# source files, use current Visual Studio Build Tools / Visual Studio with x64 tooling.

            What is proven right now
            - mode-route validation against recovered boot/taskmachine files
            - launcher pack generation
            - runtime bridge and loopback consumer proofs
            - visible external overlay fallback generation and launch wiring
            - single-player route validation and save-aware launch prompting

            What is not proven yet
            - retail in-engine activation through the live executable
            - a fully validated public multiplayer runtime

            Support files
            - {ROOT_LAUNCHER_MANIFEST} = launcher targets and validation snapshot
            - Code_RED_External_Recommendations.txt = third-party dependency notes
            - Code_RED_Dependency_Installer.* = Python dependency installer wrappers

            Credits
            GLITCHED MATRIX Prototype Lab made this possible.
        ''').strip() + "\n"

        recommendations_text = dedent('''
            Code RED external recommendations

            Not bundled
            - RedHook
            - ScriptHookRDR
            - Visual Studio / Build Tools

            Recommended baseline
            - Start with ScriptHookRDR if you want the lighter external dependency path, especially for Single Player Host experiments.
            - Use RedHook only when you specifically want the generated .red bridge plugin route.

            Compatibility note
            - RedHook and ScriptHookRDR may conflict depending on load order and other injected files.
            - This build does not claim responsibility for third-party hook conflicts. Treat them as environment choices and test them separately.

            Shipping note
            - Do not redistribute third-party hook binaries inside this package unless you have the right to do so.
            - Tell users which external tool is required for the route they choose.

            Credits
            GLITCHED MATRIX Prototype Lab made this possible.
        ''').strip() + "\n"

        manifest = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'bridge_dir': str(bridge_dir),
            'mode': plan.get('mode', ''),
            'world': plan.get('world', ''),
            'boot_target': plan.get('boot_target', ''),
            'primary_target': primary_name,
            'play_target': play_name,
            'direct_target': rdr_name,
            'overlay_launch_default': True,
            'overlay_dir': str(game_dir / OVERLAY_DIRNAME),
            'generated_files': [
                'Code_RED_Launcher.bat',
                'Code_RED_Launcher.ps1',
                'Code_RED_Launcher.py',
                'Code_RED_Launcher.cs',
                f'{OVERLAY_DIRNAME}/{OVERLAY_SCRIPT}',
                f'{OVERLAY_DIRNAME}/{OVERLAY_LAUNCH_BAT}',
                f'{OVERLAY_DIRNAME}/{OVERLAY_GAME_LAUNCH_BAT}',
                f'{OVERLAY_DIRNAME}/{OVERLAY_STATE_JSON}',
                f'{OVERLAY_DIRNAME}/{OVERLAY_EXE}',
                ROOT_LAUNCHER_MANIFEST,
                'Code_RED_Launcher_README.txt',
                'Red_Bridge_Guide.txt',
                'Code_RED_External_Recommendations.txt',
                'Code_RED_Dependency_Installer.py',
                'Code_RED_Dependency_Installer.bat',
                'Code_RED_Dependency_Installer.ps1',
            ],
            'hook_pack': {
                'dir': str(game_dir / HOOK_PACK_DIRNAME),
                'bootstrap': str(game_dir / HOOK_PACK_DIRNAME / HOOK_BOOTSTRAP_JSON),
                'plugin_source': str(game_dir / HOOK_PACK_DIRNAME / HOOK_PLUGIN_SOURCE),
                'plugin_build_script': str(game_dir / HOOK_PACK_DIRNAME / HOOK_PLUGIN_BUILD_BAT),
            },
            'ghost_menu': {
                'label': 'CODE RED',
                'keymap': self._ghost_keymap(),
            },
            'validation': report,
        }

        bat_launcher.write_text(bat_text, encoding='utf-8')
        ps_launcher.write_text(ps_text, encoding='utf-8')
        py_launcher.write_text(py_text, encoding='utf-8')
        cs_launcher.write_text(cs_text, encoding='utf-8')
        dep_py_path.write_text(dep_py_text, encoding='utf-8')
        dep_bat_path.write_text(dep_bat_text, encoding='utf-8')
        dep_ps_path.write_text(dep_ps_text, encoding='utf-8')
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        guide_path.write_text(guide_text, encoding='utf-8')
        recommendations_path.write_text(recommendations_text, encoding='utf-8')
        readme_path.write_text(dedent(f'''
            Code RED main-directory launcher pack

            Drop these files into the game root beside PlayRDR.exe / RDR.exe.
            The launchers expect the Code_RED_Launch bridge folder to exist in the same directory.
            - Code_RED_Launcher.bat = Windows wrapper that prefers PlayRDR.exe and falls back to RDR.exe
            - Code_RED_Launcher.ps1 = PowerShell wrapper
            - Code_RED_Launcher.py = Python wrapper
            - Code_RED_Launcher.cs = compile-ready source for a custom launcher EXE
            - Code_RED_Overlay launch now prefers a built Code_RED_Overlay.exe, then launch_overlay.bat, then Python fallback
            - {ROOT_LAUNCHER_MANIFEST} = resolved targets and validation snapshot
            - Red_Bridge_Guide.txt = operator help guide for Code RED + Red Bridge
            - Code_RED_External_Recommendations.txt = external dependency and hook-policy notes
            - Code_RED_Dependency_Installer.* = Python dependency installer wrappers
            - Code_RED_HookBridge/hook_bootstrap.json = root-level bootstrap manifest for a future hook consumer
            - Code_RED_HookBridge/Code_RED_BridgePlugin.cpp = compile-ready optional RedHook bridge scaffold source
            - Code_RED_HookBridge/build_red_plugin.bat = simple batch build helper for a Visual Studio tools prompt

            RedHook is not bundled here. ScriptHookRDR is also external. Test one hook strategy at a time.

            GLITCHED MATRIX Prototype Lab made this possible.
        ''').strip() + "\n", encoding='utf-8')
        return manifest


    def _write_hook_scaffold_pack(self, game_dir: Path, plan: dict, bridge_dir: Path, report: dict | None = None) -> dict:
        game_dir.mkdir(parents=True, exist_ok=True)
        report = report or self._game_root_report(game_dir)
        hook_dir = game_dir / HOOK_PACK_DIRNAME
        hook_dir.mkdir(parents=True, exist_ok=True)
        bootstrap_path = hook_dir / HOOK_BOOTSTRAP_JSON
        source_path = hook_dir / HOOK_PLUGIN_SOURCE
        build_bat_path = hook_dir / HOOK_PLUGIN_BUILD_BAT
        vcxproj_path = hook_dir / HOOK_PLUGIN_VCXPROJ
        readme_path = hook_dir / HOOK_PLUGIN_README
        manifest_path = hook_dir / HOOK_PACK_MANIFEST
        bridge_payload = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'game_root': str(game_dir),
            'bridge_dir': str(bridge_dir),
            'active_session_path': str(bridge_dir / 'active_session.json'),
            'launch_plan_path': str(bridge_dir / 'launch_plan.json'),
            'activation_request_path': str(bridge_dir / LAUNCH_BRIDGE_ACTIVATION_REQUEST),
            'synthetic_route_path': str(bridge_dir / LAUNCH_BRIDGE_SYNTHETIC_ROUTE),
            'runtime_status_path': str(bridge_dir / LAUNCH_BRIDGE_STATUS),
            'consumer_status_path': str(bridge_dir / LAUNCH_BRIDGE_CONSUMER_STATUS),
            'runtime_bridge_script': str(bridge_dir / LAUNCH_BRIDGE_RUNTIME),
            'runtime_bridge_port': int(plan.get('runtime_bridge_port') or self._runtime_bridge_port()),
            'selected_mode': self._mode_preset_payload(),
            'ghost_menu': {
                'label': 'CODE RED',
                'keymap': self._ghost_keymap(),
                'event_map': {
                    'singleplayer': 'codered.mode.singleplayer',
                    'freemode': 'codered.mode.freemode',
                    'lan': 'codered.mode.lan',
                    'private': 'codered.mode.private',
                    'public': 'codered.mode.public',
                    'open_menu': 'codered.openmenu',
                    'open_playerlist': 'codered.openplayerlist',
                },
            },
            'boot_target': plan.get('boot_target', ''),
            'world': plan.get('world', ''),
            'save_scan': plan.get('save_scan', {}),
            'launch_target': plan.get('selected_exe', ''),
            'redhook_present': bool((game_dir / 'RedHook.dll').exists()),
            'scripthook_present': bool((game_dir / 'ScriptHookRDR.dll').exists()),
            'plugin_output_name': HOOK_PLUGIN_OUTPUT,
            'plugin_output_path': str(game_dir / HOOK_PLUGIN_OUTPUT),
            'note': 'Compile the generated C++ source into a .red plugin and place the output in the game root to let RedHook consume the bridge at runtime.',
        }
        source_text = dedent(r'''#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <fstream>
#include <filesystem>
#include <string>
#include <chrono>
#include <sstream>

using ScriptRegisterFn = void(*)(HMODULE, void(*)());
using ScriptUnregisterFn = void(*)(HMODULE);
using ScriptWaitFn = void(*)(unsigned long long);

static HMODULE g_module = nullptr;
static HMODULE g_redhook = nullptr;
static ScriptRegisterFn g_register = nullptr;
static ScriptUnregisterFn g_unregister = nullptr;
static ScriptWaitFn g_wait = nullptr;
static bool g_started = false;

static std::filesystem::path ModulePath() {
    wchar_t buf[MAX_PATH] = {0};
    GetModuleFileNameW(g_module, buf, MAX_PATH);
    return std::filesystem::path(buf).parent_path();
}

static std::filesystem::path HookDir() {
    return ModulePath() / L"__HOOK_PACK_DIRNAME__";
}

static std::filesystem::path LogPath() {
    return HookDir() / L"__HOOK_PLUGIN_LOG__";
}

static std::filesystem::path BootstrapPath() {
    return HookDir() / L"__HOOK_BOOTSTRAP_JSON__";
}

static void Log(const std::string& msg) {
    try {
        std::filesystem::create_directories(HookDir());
        std::ofstream out(LogPath(), std::ios::app | std::ios::binary);
        auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
        out << "[" << now << "] " << msg << "\n";
    } catch (...) {
    }
}

static bool ResolveRedHook() {
    if (g_register && g_unregister && g_wait) return true;
    g_redhook = LoadLibraryW(L"RedHook.dll");
    if (!g_redhook) {
        Log("RedHook.dll not found");
        return false;
    }
    g_register = reinterpret_cast<ScriptRegisterFn>(GetProcAddress(g_redhook, "?ScriptRegister@@YAXPEAUHINSTANCE__@@P6AXXZ@Z"));
    g_unregister = reinterpret_cast<ScriptUnregisterFn>(GetProcAddress(g_redhook, "?ScriptUnregister@@YAXPEAUHINSTANCE__@@@Z"));
    g_wait = reinterpret_cast<ScriptWaitFn>(GetProcAddress(g_redhook, "?ScriptWait@@YAX_K@Z"));
    if (!g_register || !g_unregister || !g_wait) {
        Log("Required RedHook exports not resolved");
        return false;
    }
    return true;
}

static void Tick() {
    if (!g_started) {
        g_started = true;
        std::ostringstream ss;
        ss << "Code RED bridge plugin started; bootstrap=" << BootstrapPath().string();
        Log(ss.str());
    }
    if (g_wait) g_wait(1000ULL);
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_module = module;
        DisableThreadLibraryCalls(module);
        if (ResolveRedHook()) {
            Log("Registering Code RED bridge tick with RedHook");
            g_register(module, &Tick);
        }
    } else if (reason == DLL_PROCESS_DETACH) {
        if (g_unregister && g_module) {
            g_unregister(g_module);
        }
    }
    return TRUE;
}
''').replace('__HOOK_PACK_DIRNAME__', HOOK_PACK_DIRNAME).replace('__HOOK_PLUGIN_LOG__', HOOK_PLUGIN_LOG).replace('__HOOK_BOOTSTRAP_JSON__', HOOK_BOOTSTRAP_JSON).strip() + '\\n'
        build_bat_text = dedent(r'''@echo off
setlocal
set ROOT=%~dp0
set SRC=%ROOT%__HOOK_PLUGIN_SOURCE__
set OUT=%ROOT%..\__HOOK_PLUGIN_OUTPUT__
if not exist "%SRC%" (
  echo Missing source: %SRC%
  exit /b 1
)
where cl >nul 2>&1
if errorlevel 1 (
  echo cl.exe not found. Open a Visual Studio x64 Native Tools prompt and rerun this script.
  exit /b 1
)
cl /LD /std:c++17 /EHsc /DUNICODE /D_UNICODE "%SRC%" /Fe:"%OUT%" /link /SUBSYSTEM:WINDOWS
if errorlevel 1 exit /b 1
echo Built %OUT%
endlocal
''').replace('__HOOK_PLUGIN_SOURCE__', HOOK_PLUGIN_SOURCE).replace('__HOOK_PLUGIN_OUTPUT__', HOOK_PLUGIN_OUTPUT).strip() + '\\r\\n'
        vcxproj_text = dedent(r'''<Project DefaultTargets="Build" ToolsVersion="17.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemGroup Label="ProjectConfigurations">
    <ProjectConfiguration Include="Release|x64">
      <Configuration>Release</Configuration>
      <Platform>x64</Platform>
    </ProjectConfiguration>
  </ItemGroup>
  <PropertyGroup Label="Globals">
    <ProjectName>Code_RED_BridgePlugin</ProjectName>
    <Keyword>Win32Proj</Keyword>
    <Platform>x64</Platform>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" />
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'" Label="Configuration">
    <ConfigurationType>DynamicLibrary</ConfigurationType>
    <UseDebugLibraries>false</UseDebugLibraries>
    <PlatformToolset>v143</PlatformToolset>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.props" />
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
    <OutDir>$(ProjectDir)..\</OutDir>
    <IntDir>$(ProjectDir)obj\Release\</IntDir>
    <TargetName>Code_RED_Bridge</TargetName>
    <TargetExt>.red</TargetExt>
  </PropertyGroup>
  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
    <ClCompile>
      <LanguageStandard>stdcpp17</LanguageStandard>
      <PreprocessorDefinitions>UNICODE;_UNICODE;WIN32_LEAN_AND_MEAN;%(PreprocessorDefinitions)</PreprocessorDefinitions>
    </ClCompile>
  </ItemDefinitionGroup>
  <ItemGroup>
    <ClCompile Include="__HOOK_PLUGIN_SOURCE__" />
  </ItemGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />
</Project>
''').replace('__HOOK_PLUGIN_SOURCE__', HOOK_PLUGIN_SOURCE).strip() + '\\n'
        readme_text = (
            'Code RED RedHook bridge scaffold\n\n'
            'This folder contains a compile-ready starting point for a .red plugin that can be loaded by RedHook from the game root.\n'
            f'- Source: {HOOK_PLUGIN_SOURCE}\n'
            f'- Build script: {HOOK_PLUGIN_BUILD_BAT}\n'
            f'- Visual Studio project: {HOOK_PLUGIN_VCXPROJ}\n'
            f'- Bootstrap manifest: {HOOK_BOOTSTRAP_JSON}\n\n'
            'Expected output after build: Code_RED_Bridge.red in the game root beside RedHook.dll and PlayRDR.exe.\n'
            'The scaffold currently logs startup and points at the Code_RED_Launch bridge files so the next in-engine hook pass has a stable place to start.\n'
            'RedHook is external and is not bundled by this package. ScriptHookRDR is also external.\n'
            'Because third-party hook stacks may conflict, test one strategy at a time instead of assuming both should be active together.\n\n'
            'GLITCHED MATRIX Prototype Lab made this possible.\n'
        )
        manifest = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'game_root': str(game_dir),
            'hook_dir': str(hook_dir),
            'plugin_source': str(source_path),
            'plugin_build_script': str(build_bat_path),
            'plugin_project': str(vcxproj_path),
            'plugin_output': str(game_dir / HOOK_PLUGIN_OUTPUT),
            'bootstrap': bridge_payload,
            'validation': report,
        }
        bootstrap_path.write_text(json.dumps(bridge_payload, indent=2), encoding='utf-8')
        source_path.write_text(source_text, encoding='utf-8')
        build_bat_path.write_text(build_bat_text, encoding='utf-8')
        vcxproj_path.write_text(vcxproj_text, encoding='utf-8')
        readme_path.write_text(readme_text, encoding='utf-8')
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        return manifest



    def _write_playerlist_bridge_pack(self, game_dir: Path, plan: dict, bridge_dir: Path, playerlist_report: dict | None, source: Path) -> dict:
        playerlist_dir = game_dir / PLAYERLIST_BRIDGE_DIRNAME
        playerlist_dir.mkdir(parents=True, exist_ok=True)
        bootstrap_path = playerlist_dir / PLAYERLIST_BRIDGE_BOOTSTRAP
        runtime_state_path = playerlist_dir / PLAYERLIST_BRIDGE_RUNTIME
        command_path = bridge_dir / PLAYERLIST_BRIDGE_COMMAND
        source_path = playerlist_dir / PLAYERLIST_BRIDGE_SOURCE
        build_bat_path = playerlist_dir / PLAYERLIST_BRIDGE_BUILD_BAT
        vcxproj_path = playerlist_dir / PLAYERLIST_BRIDGE_VCXPROJ
        readme_path = playerlist_dir / PLAYERLIST_BRIDGE_README
        manifest_path = playerlist_dir / PLAYERLIST_BRIDGE_MANIFEST
        sim_path = playerlist_dir / PLAYERLIST_BRIDGE_SIM
        plugin_output_path = game_dir / PLAYERLIST_BRIDGE_OUTPUT
        playerlist_report = playerlist_report or self.analyze_playerlist_focus()
        payload = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'playerlist_dir_name': PLAYERLIST_BRIDGE_DIRNAME,
            'game_root': str(game_dir),
            'content_source': str(source),
            'bridge_dir': str(bridge_dir),
            'command_path': str(command_path),
            'runtime_state_path': str(runtime_state_path),
            'runtime_bridge_status_path': str(bridge_dir / LAUNCH_BRIDGE_STATUS),
            'consumer_status_path': str(bridge_dir / LAUNCH_BRIDGE_CONSUMER_STATUS),
            'activation_request_path': str(bridge_dir / LAUNCH_BRIDGE_ACTIVATION_REQUEST),
            'launch_plan_path': str(bridge_dir / 'launch_plan.json'),
            'active_session_path': str(bridge_dir / 'active_session.json'),
            'selected_mode': self._mode_preset_payload(),
            'keymap': self._ghost_keymap(),
            'event_map': {
                'open_menu': 'codered.openmenu',
                'open_playerlist': 'codered.openplayerlist',
                'singleplayer': 'codered.mode.singleplayer',
                'freemode': 'codered.mode.freemode',
                'lan': 'codered.mode.lan',
                'private': 'codered.mode.private',
                'public': 'codered.mode.public',
            },
            'playerlist_focus': playerlist_report,
            'plugin_output_name': PLAYERLIST_BRIDGE_OUTPUT,
            'plugin_output_path': str(plugin_output_path),
            'startup_action': 'open_playerlist',
            'note': 'Compile the generated C++ source into a .red plugin and place the output in the game root beside RedHook.dll so the game-side lane can emit trainer-style menu and playerlist commands.',
        }
        runtime_state = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'status': 'awaiting_hook',
            'last_action': '',
            'last_hotkey': '',
            'menu_state': 'idle',
            'playerlist_visible': False,
            'selected_mode': payload['selected_mode'],
            'playerlist_focus_score': playerlist_report.get('focus_score', 0),
            'startup_action': payload['startup_action'],
        }
        source_text = dedent(r'''#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <fstream>
#include <filesystem>
#include <string>
#include <chrono>
#include <sstream>

using ScriptRegisterFn = void(*)(HMODULE, void(*)());
using ScriptUnregisterFn = void(*)(HMODULE);
using ScriptWaitFn = void(*)(unsigned long long);

static HMODULE g_module = nullptr;
static HMODULE g_redhook = nullptr;
static ScriptRegisterFn g_register = nullptr;
static ScriptUnregisterFn g_unregister = nullptr;
static ScriptWaitFn g_wait = nullptr;
static bool g_started = false;
static bool g_f1 = false;
static bool g_f2 = false;
static bool g_f3 = false;
static bool g_f4 = false;
static bool g_f5 = false;
static bool g_f6 = false;
static bool g_f7 = false;

static std::filesystem::path ModulePath() {
    wchar_t buf[MAX_PATH] = {0};
    GetModuleFileNameW(g_module, buf, MAX_PATH);
    return std::filesystem::path(buf).parent_path();
}

static std::filesystem::path BridgeDir() { return ModulePath() / L"__PLAYERLIST_BRIDGE_DIRNAME__"; }
static std::filesystem::path CommandPath() { return ModulePath() / L"__LAUNCH_BRIDGE_DIRNAME__" / L"__PLAYERLIST_BRIDGE_COMMAND__"; }
static std::filesystem::path RuntimeStatePath() { return BridgeDir() / L"__PLAYERLIST_BRIDGE_RUNTIME__"; }
static std::filesystem::path LogPath() { return BridgeDir() / L"__PLAYERLIST_BRIDGE_LOG__"; }

static std::string NowStamp() {
    SYSTEMTIME st;
    GetLocalTime(&st);
    char buf[64] = {0};
    sprintf_s(buf, "%04u-%02u-%02uT%02u:%02u:%02u", st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
    return std::string(buf);
}

static void Log(const std::string& msg) {
    try {
        std::filesystem::create_directories(BridgeDir());
        std::ofstream out(LogPath(), std::ios::app | std::ios::binary);
        out << "[" << NowStamp() << "] " << msg << "\n";
    } catch (...) {}
}

static void WriteRuntimeState(const char* status, const char* action, const char* hotkey) {
    try {
        std::filesystem::create_directories(BridgeDir());
        std::ofstream out(RuntimeStatePath(), std::ios::binary);
        const std::string action_str = action ? std::string(action) : std::string();
        const std::string menu_state = action_str == "open_menu" ? "menu_requested" : (action_str == "open_playerlist" ? "playerlist_requested" : std::string(status ? status : ""));
        const bool playerlist_visible = action_str == "open_playerlist";
        out << "{\n"
            << "  \"ts\": \"" << NowStamp() << "\",\n"
            << "  \"status\": \"" << (status ? status : "") << "\",\n"
            << "  \"last_action\": \"" << action_str << "\",\n"
            << "  \"last_hotkey\": \"" << (hotkey ? hotkey : "") << "\",\n"
            << "  \"menu_state\": \"" << menu_state << "\",\n"
            << "  \"playerlist_visible\": " << (playerlist_visible ? "true" : "false") << "\n"
            << "}\n";
    } catch (...) {}
}

static void EmitCommand(const char* action, const char* hotkey) {
    try {
        std::filesystem::create_directories(CommandPath().parent_path());
        std::ofstream out(CommandPath(), std::ios::binary);
        out << "{\n"
            << "  \"ts\": \"" << NowStamp() << "\",\n"
            << "  \"action\": \"" << (action ? action : "") << "\",\n"
            << "  \"hotkey\": \"" << (hotkey ? hotkey : "") << "\",\n"
            << "  \"source\": \"playerlist_bridge_plugin\"\n"
            << "}\n";
        WriteRuntimeState("command_emitted", action, hotkey);
        Log(std::string("emit => ") + (action ? action : "") + " via " + (hotkey ? hotkey : ""));
    } catch (...) {}
}

static bool ResolveRedHook() {
    if (g_register && g_unregister && g_wait) return true;
    g_redhook = LoadLibraryW(L"RedHook.dll");
    if (!g_redhook) {
        Log("RedHook.dll not found");
        return false;
    }
    g_register = reinterpret_cast<ScriptRegisterFn>(GetProcAddress(g_redhook, "?ScriptRegister@@YAXPEAUHINSTANCE__@@P6AXXZ@Z"));
    g_unregister = reinterpret_cast<ScriptUnregisterFn>(GetProcAddress(g_redhook, "?ScriptUnregister@@YAXPEAUHINSTANCE__@@@Z"));
    g_wait = reinterpret_cast<ScriptWaitFn>(GetProcAddress(g_redhook, "?ScriptWait@@YAX_K@Z"));
    if (!g_register || !g_unregister || !g_wait) {
        Log("Required RedHook exports not resolved");
        return false;
    }
    return true;
}

static void PollHotkeys() {
    const bool shift = (GetAsyncKeyState(VK_SHIFT) & 0x8000) != 0;
    const bool f1 = (GetAsyncKeyState(VK_F1) & 0x8000) != 0;
    const bool f2 = (GetAsyncKeyState(VK_F2) & 0x8000) != 0;
    const bool f3 = (GetAsyncKeyState(VK_F3) & 0x8000) != 0;
    const bool f4 = (GetAsyncKeyState(VK_F4) & 0x8000) != 0;
    const bool f5 = (GetAsyncKeyState(VK_F5) & 0x8000) != 0;
    const bool f6 = (GetAsyncKeyState(VK_F6) & 0x8000) != 0;
    const bool f7 = (GetAsyncKeyState(VK_F7) & 0x8000) != 0;

    if (shift && f1 && !g_f1) EmitCommand("singleplayer", "Shift+F1");
    if (shift && f2 && !g_f2) EmitCommand("freemode", "Shift+F2");
    if (shift && f3 && !g_f3) EmitCommand("lan", "Shift+F3");
    if (shift && f4 && !g_f4) EmitCommand("private", "Shift+F4");
    if (shift && f5 && !g_f5) EmitCommand("public", "Shift+F5");
    if (shift && f6 && !g_f6) EmitCommand("open_menu", "Shift+F6");
    if (shift && f7 && !g_f7) EmitCommand("open_playerlist", "Shift+F7");

    g_f1 = f1; g_f2 = f2; g_f3 = f3; g_f4 = f4; g_f5 = f5; g_f6 = f6; g_f7 = f7;
}

static void Tick() {
    if (!g_started) {
        g_started = true;
        WriteRuntimeState("hook_ready", "", "");
        Log("Code RED playerlist bridge plugin started");
    }
    PollHotkeys();
    if (g_wait) g_wait(100ULL);
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_module = module;
        DisableThreadLibraryCalls(module);
        if (ResolveRedHook()) {
            Log("Registering Code RED playerlist bridge tick with RedHook");
            g_register(module, &Tick);
        }
    } else if (reason == DLL_PROCESS_DETACH) {
        if (g_unregister && g_module) {
            g_unregister(g_module);
        }
    }
    return TRUE;
}
''').replace('__PLAYERLIST_BRIDGE_DIRNAME__', PLAYERLIST_BRIDGE_DIRNAME).replace('__LAUNCH_BRIDGE_DIRNAME__', LAUNCH_BRIDGE_DIRNAME).replace('__PLAYERLIST_BRIDGE_COMMAND__', PLAYERLIST_BRIDGE_COMMAND).replace('__PLAYERLIST_BRIDGE_RUNTIME__', PLAYERLIST_BRIDGE_RUNTIME).replace('__PLAYERLIST_BRIDGE_LOG__', PLAYERLIST_BRIDGE_LOG).strip() + '\n'
        build_bat_text = dedent(r'''@echo off
setlocal
set ROOT=%~dp0
set SRC=%ROOT%__PLAYERLIST_BRIDGE_SOURCE__
set OUT=%ROOT%..\__PLAYERLIST_BRIDGE_OUTPUT__
if not exist "%SRC%" (
  echo Missing source: %SRC%
  exit /b 1
)
where cl >nul 2>&1
if errorlevel 1 (
  echo cl.exe not found. Open a Visual Studio x64 Native Tools prompt and rerun this script.
  exit /b 1
)
cl /LD /std:c++17 /EHsc /DUNICODE /D_UNICODE "%SRC%" /Fe:"%OUT%" /link /SUBSYSTEM:WINDOWS
if errorlevel 1 exit /b 1
echo Built %OUT%
endlocal
''').replace('__PLAYERLIST_BRIDGE_SOURCE__', PLAYERLIST_BRIDGE_SOURCE).replace('__PLAYERLIST_BRIDGE_OUTPUT__', PLAYERLIST_BRIDGE_OUTPUT).strip() + '\r\n'
        vcxproj_text = dedent(r'''<Project DefaultTargets="Build" ToolsVersion="17.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemGroup Label="ProjectConfigurations">
    <ProjectConfiguration Include="Release|x64">
      <Configuration>Release</Configuration>
      <Platform>x64</Platform>
    </ProjectConfiguration>
  </ItemGroup>
  <PropertyGroup Label="Globals">
    <ProjectName>Code_RED_PlayerlistBridge</ProjectName>
    <Keyword>Win32Proj</Keyword>
    <Platform>x64</Platform>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" />
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'" Label="Configuration">
    <ConfigurationType>DynamicLibrary</ConfigurationType>
    <UseDebugLibraries>false</UseDebugLibraries>
    <PlatformToolset>v143</PlatformToolset>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.props" />
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
    <OutDir>$(ProjectDir)..\</OutDir>
    <IntDir>$(ProjectDir)obj\Release\</IntDir>
    <TargetName>Code_RED_PlayerlistBridge</TargetName>
    <TargetExt>.red</TargetExt>
  </PropertyGroup>
  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
    <ClCompile>
      <LanguageStandard>stdcpp17</LanguageStandard>
      <PreprocessorDefinitions>UNICODE;_UNICODE;WIN32_LEAN_AND_MEAN;%(PreprocessorDefinitions)</PreprocessorDefinitions>
    </ClCompile>
  </ItemDefinitionGroup>
  <ItemGroup>
    <ClCompile Include="__PLAYERLIST_BRIDGE_SOURCE__" />
  </ItemGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />
</Project>
''').replace('__PLAYERLIST_BRIDGE_SOURCE__', PLAYERLIST_BRIDGE_SOURCE).strip() + '\n'
        readme_text = (
            'Code RED Playerlist Bridge\n\n'
            'This folder is the focused runtime-consumer scaffold for playerlist/menu access.\n'
            f'- Bootstrap: {PLAYERLIST_BRIDGE_BOOTSTRAP}\n'
            f'- Runtime state: {PLAYERLIST_BRIDGE_RUNTIME}\n'
            f'- Command file emitted to: {LAUNCH_BRIDGE_DIRNAME}/{PLAYERLIST_BRIDGE_COMMAND}\n'
            f'- Source scaffold: {PLAYERLIST_BRIDGE_SOURCE}\n'
            f'- Visual Studio project: {PLAYERLIST_BRIDGE_VCXPROJ}\n'
            f'- Simulator: {PLAYERLIST_BRIDGE_SIM}\n'
            f'- Compile-ready output target: {PLAYERLIST_BRIDGE_OUTPUT} in the game root\n\n'
            'Shift+F1..Shift+F5 are route hotkeys. Shift+F6 is reserved for CODE RED menu. Shift+F7 is reserved for playerlist focus.\n'
            'This pack now ships the strongest safe consumer path available here: a compile-ready RedHook plugin scaffold that emits runtime command files and state acknowledgements without claiming fully proven in-engine menu control yet.\n\n'
            'GLITCHED MATRIX Prototype Lab made this possible.\n'
        )
        sim_text = dedent(f'''
            import json
            import sys
            from pathlib import Path
            from datetime import datetime

            ROOT = Path(__file__).resolve().parent
            bootstrap = json.loads((ROOT / {PLAYERLIST_BRIDGE_BOOTSTRAP!r}).read_text(encoding="utf-8"))
            command_path = Path(bootstrap["command_path"])
            runtime_state_path = Path(bootstrap["runtime_state_path"])
            action = sys.argv[1] if len(sys.argv) > 1 else bootstrap.get("startup_action", "open_playerlist")
            payload = {{"ts": datetime.now().isoformat(timespec="seconds"), "action": action, "hotkey": "simulated", "source": "playerlist_bridge_sim"}}
            command_path.parent.mkdir(parents=True, exist_ok=True)
            command_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            runtime_state = {{
                "ts": payload["ts"],
                "status": "simulated_command_seeded",
                "last_action": action,
                "last_hotkey": "simulated",
                "menu_state": "playerlist_requested" if action == "open_playerlist" else ("menu_requested" if action == "open_menu" else "route_requested"),
                "playerlist_visible": bool(action == "open_playerlist"),
                "startup_action": bootstrap.get("startup_action", "open_playerlist"),
            }}
            runtime_state_path.parent.mkdir(parents=True, exist_ok=True)
            runtime_state_path.write_text(json.dumps(runtime_state, indent=2), encoding="utf-8")
            print(command_path)
        ''').strip() + '\n'
        manifest = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'playerlist_dir_name': PLAYERLIST_BRIDGE_DIRNAME,
            'playerlist_dir': str(playerlist_dir),
            'bootstrap': str(bootstrap_path),
            'runtime_state': str(runtime_state_path),
            'command_path': str(command_path),
            'source_scaffold': str(source_path),
            'project': str(vcxproj_path),
            'simulator': str(sim_path),
            'plugin_output': str(plugin_output_path),
            'playerlist_focus_score': playerlist_report.get('focus_score', 0),
            'playerlist_focus': playerlist_report,
        }
        bootstrap_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        runtime_state_path.write_text(json.dumps(runtime_state, indent=2), encoding='utf-8')
        source_path.write_text(source_text, encoding='utf-8')
        build_bat_path.write_text(build_bat_text, encoding='utf-8')
        vcxproj_path.write_text(vcxproj_text, encoding='utf-8')
        readme_path.write_text(readme_text, encoding='utf-8')
        sim_path.write_text(sim_text, encoding='utf-8')
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        return manifest

    def _write_hook_proof_pack(self, game_dir: Path, report: dict | None = None) -> dict:
        game_dir.mkdir(parents=True, exist_ok=True)
        report = report or self._game_root_report(game_dir)
        proof_dir = game_dir / HOOK_PROOF_DIRNAME
        proof_dir.mkdir(parents=True, exist_ok=True)
        watcher_path = proof_dir / HOOK_PROOF_WATCHER
        build_bat_path = proof_dir / HOOK_PROOF_BUILD_BAT
        expected_path = proof_dir / HOOK_PROOF_EXPECTED_JSON
        readme_path = proof_dir / HOOK_PROOF_README
        report_path = proof_dir / HOOK_PROOF_REPORT_JSON
        redhook_log_path = game_dir / 'RedHook.Log'
        bridge_status_path = game_dir / LAUNCH_BRIDGE_DIRNAME / LAUNCH_BRIDGE_STATUS
        activation_request_path = game_dir / LAUNCH_BRIDGE_DIRNAME / LAUNCH_BRIDGE_ACTIVATION_REQUEST
        playerlist_runtime_path = game_dir / PLAYERLIST_BRIDGE_DIRNAME / PLAYERLIST_BRIDGE_RUNTIME
        hook_plugin_log_path = game_dir / HOOK_PACK_DIRNAME / HOOK_PLUGIN_LOG
        playerlist_plugin_log_path = game_dir / PLAYERLIST_BRIDGE_DIRNAME / PLAYERLIST_BRIDGE_LOG
        expected = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'plugins': [HOOK_PLUGIN_OUTPUT, PLAYERLIST_BRIDGE_OUTPUT],
            'redhook_log_path': str(redhook_log_path),
            'bridge_status_path': str(bridge_status_path),
            'activation_request_path': str(activation_request_path),
            'playerlist_runtime_path': str(playerlist_runtime_path),
            'hook_plugin_log_path': str(hook_plugin_log_path),
            'playerlist_plugin_log_path': str(playerlist_plugin_log_path),
            'required_redhook_markers': [
                f"Registered script '{HOOK_PLUGIN_OUTPUT}'",
                f"Registered script '{PLAYERLIST_BRIDGE_OUTPUT}'",
                f"Started script '{HOOK_PLUGIN_OUTPUT}'",
                f"Started script '{PLAYERLIST_BRIDGE_OUTPUT}'",
            ],
            'action_priority': ['open_playerlist', 'open_menu', 'lan', 'private', 'public', 'freemode', 'singleplayer'],
        }
        watcher_text = dedent(f'''
            import json
            from datetime import datetime
            from pathlib import Path

            ROOT = Path(__file__).resolve().parent
            EXPECTED = json.loads((ROOT / {HOOK_PROOF_EXPECTED_JSON!r}).read_text(encoding="utf-8"))
            REPORT_PATH = ROOT / {HOOK_PROOF_REPORT_JSON!r}

            def read_json(path_str: str):
                path = Path(path_str)
                if not path.exists():
                    return None
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    return None

            def read_lines(path_str: str):
                path = Path(path_str)
                if not path.exists():
                    return []
                try:
                    return path.read_text(encoding="utf-8", errors="ignore").splitlines()
                except Exception:
                    return []

            redhook_lines = read_lines(EXPECTED["redhook_log_path"])
            hook_plugin_lines = read_lines(EXPECTED["hook_plugin_log_path"])
            playerlist_plugin_lines = read_lines(EXPECTED["playerlist_plugin_log_path"])
            bridge_status = read_json(EXPECTED["bridge_status_path"]) or {{}}
            activation_request = read_json(EXPECTED["activation_request_path"]) or {{}}
            playerlist_runtime = read_json(EXPECTED["playerlist_runtime_path"]) or {{}}

            matched_markers = [marker for marker in EXPECTED["required_redhook_markers"] if any(marker in line for line in redhook_lines)]
            first_action = ""
            for key in EXPECTED.get("action_priority", []):
                if activation_request.get("action") == key or playerlist_runtime.get("last_action") == key:
                    first_action = key
                    break
            if not first_action:
                first_action = str(activation_request.get("action") or playerlist_runtime.get("last_action") or bridge_status.get("action") or "")

            result = {{
                "ts": datetime.now().isoformat(timespec="seconds"),
                "plugins_expected": EXPECTED["plugins"],
                "redhook_markers_found": matched_markers,
                "redhook_ready": len(matched_markers) >= 2,
                "redhook_started": len(matched_markers) >= 4,
                "hook_plugin_log_tail": hook_plugin_lines[-12:],
                "playerlist_plugin_log_tail": playerlist_plugin_lines[-12:],
                "bridge_status": bridge_status,
                "activation_request": activation_request,
                "playerlist_runtime": playerlist_runtime,
                "first_live_action": first_action,
                "first_live_action_logged": bool(first_action),
                "notes": [
                    "This verifier only reports what reached the filesystem/logging chain.",
                    "A positive result still means hook/plugin logging proof, not full gameplay parity.",
                ],
            }}
            REPORT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(REPORT_PATH)
        ''').strip() + '\n'
        build_bat_text = dedent(f'''
            @echo off
            setlocal
            set ROOT=%~dp0
            set GAME_ROOT=%ROOT%..
            echo [Code RED] Building RedHook plugin pair...
            if exist "%GAME_ROOT%\\{HOOK_PACK_DIRNAME}\\{HOOK_PLUGIN_BUILD_BAT}" (
              call "%GAME_ROOT%\\{HOOK_PACK_DIRNAME}\\{HOOK_PLUGIN_BUILD_BAT}"
              if errorlevel 1 exit /b 1
            ) else (
              echo Missing %GAME_ROOT%\\{HOOK_PACK_DIRNAME}\\{HOOK_PLUGIN_BUILD_BAT}
              exit /b 1
            )
            if exist "%GAME_ROOT%\\{PLAYERLIST_BRIDGE_DIRNAME}\\{PLAYERLIST_BRIDGE_BUILD_BAT}" (
              call "%GAME_ROOT%\\{PLAYERLIST_BRIDGE_DIRNAME}\\{PLAYERLIST_BRIDGE_BUILD_BAT}"
              if errorlevel 1 exit /b 1
            ) else (
              echo Missing %GAME_ROOT%\\{PLAYERLIST_BRIDGE_DIRNAME}\\{PLAYERLIST_BRIDGE_BUILD_BAT}
              exit /b 1
            )
            if not exist "%GAME_ROOT%\\{HOOK_PLUGIN_OUTPUT}" (
              echo Missing built plugin: %GAME_ROOT%\\{HOOK_PLUGIN_OUTPUT}
              exit /b 1
            )
            if not exist "%GAME_ROOT%\\{PLAYERLIST_BRIDGE_OUTPUT}" (
              echo Missing built plugin: %GAME_ROOT%\\{PLAYERLIST_BRIDGE_OUTPUT}
              exit /b 1
            )
            echo [Code RED] Plugin outputs present.
            echo Launch the game once, trigger menu/playerlist input, then run:
            echo py -3 "%ROOT%{HOOK_PROOF_WATCHER}"
            endlocal
        ''').strip() + '\r\n'
        readme_text = (
            'Code RED hook proof pack\n\n'
            'Use this folder after the generated RedHook plugins are compiled on Windows.\n'
            f'- Build both plugins: {HOOK_PROOF_BUILD_BAT}\n'
            f'- After launching the game and pressing the bridge hotkeys, run: py -3 {HOOK_PROOF_WATCHER}\n'
            f'- Output proof report: {HOOK_PROOF_REPORT_JSON}\n\n'
            'The verifier checks RedHook.Log, bridge status, activation request, and the playerlist runtime state.\n'
            'This is the strongest safe path here for confirming the first live menu/playerlist action reached the file/log chain.\n'
        )
        manifest = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'proof_dir': str(proof_dir),
            'watcher': str(watcher_path),
            'build_script': str(build_bat_path),
            'expected_markers': str(expected_path),
            'report': str(report_path),
            'redhook_log_expected': str(redhook_log_path),
            'ready_for_windows_proof': bool(report.get('ready_for_bridge_pack')),
        }
        expected_path.write_text(json.dumps(expected, indent=2), encoding='utf-8')
        watcher_path.write_text(watcher_text, encoding='utf-8')
        build_bat_path.write_text(build_bat_text, encoding='utf-8')
        readme_path.write_text(readme_text, encoding='utf-8')
        return manifest

    def _write_overlay_pack(self, game_dir: Path, plan: dict, bridge_dir: Path, playerlist_report: dict | None = None) -> dict:
        game_dir.mkdir(parents=True, exist_ok=True)
        playerlist_report = playerlist_report or self._playerlist_report or self.analyze_playerlist_focus()
        overlay_dir = game_dir / OVERLAY_DIRNAME
        overlay_dir.mkdir(parents=True, exist_ok=True)
        bootstrap_path = overlay_dir / OVERLAY_BOOTSTRAP_JSON
        script_path = overlay_dir / OVERLAY_SCRIPT
        launch_bat_path = overlay_dir / OVERLAY_LAUNCH_BAT
        launch_game_bat_path = overlay_dir / OVERLAY_GAME_LAUNCH_BAT
        build_bat_path = overlay_dir / OVERLAY_BUILD_BAT
        readme_path = overlay_dir / OVERLAY_README
        manifest_path = overlay_dir / OVERLAY_MANIFEST
        command_path = bridge_dir / PLAYERLIST_BRIDGE_COMMAND
        bridge_status_path = bridge_dir / LAUNCH_BRIDGE_STATUS
        activation_request_path = bridge_dir / LAUNCH_BRIDGE_ACTIVATION_REQUEST
        playerlist_runtime_path = game_dir / PLAYERLIST_BRIDGE_DIRNAME / PLAYERLIST_BRIDGE_RUNTIME
        bootstrap = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'overlay_title': 'CODE RED',
            'game_root': str(game_dir),
            'selected_exe': str(plan.get('selected_exe') or ''),
            'selected_exe_name': Path(str(plan.get('selected_exe') or '')).name if plan.get('selected_exe') else '',
            'bridge_dir': str(bridge_dir),
            'command_path': str(command_path),
            'bridge_status_path': str(bridge_status_path),
            'state_path': str(overlay_dir / OVERLAY_STATE_JSON),
            'overlay_exe_path': str(overlay_dir / OVERLAY_EXE),
            'activation_request_path': str(activation_request_path),
            'playerlist_runtime_path': str(playerlist_runtime_path),
            'active_session_path': str(bridge_dir / 'active_session.json'),
            'keymap': self._ghost_keymap(),
            'player_name': self.player_name_var.get().strip() or 'PlayerHost',
            'session_name': self.session_name_var.get().strip() or self._session_payload('host')['session_name'],
            'world': plan.get('world') or self.world_name_var.get().strip() or 'freemode',
            'boot_target': plan.get('boot_target') or self.boot_target_var.get().strip() or 'MULTI_FREE_ROAM',
            'playerlist_focus_score': int(playerlist_report.get('focus_score', 0)),
            'mode_buttons': [
                {'label': 'Story Host', 'action': 'singleplayer'},
                {'label': 'Freemode', 'action': 'freemode'},
                {'label': 'LAN', 'action': 'lan'},
                {'label': 'Private', 'action': 'private'},
                {'label': 'Public', 'action': 'public'},
                {'label': 'Menu', 'action': 'open_menu'},
                {'label': 'Playerlist', 'action': 'open_playerlist'},
            ],
            'note': 'External trainer-style overlay fallback. This is the strongest safe path here for making CODE RED visibly appear over the game even when engine-native UI hooks are still being proven.',
        }
        script_text = dedent(r"""
            import json
            import tkinter as tk
            from datetime import datetime
            from pathlib import Path

            ROOT = Path(__file__).resolve().parent
            BOOTSTRAP = json.loads((ROOT / '__OVERLAY_BOOTSTRAP_JSON__').read_text(encoding='utf-8'))
            COMMAND_PATH = Path(BOOTSTRAP['command_path'])
            BRIDGE_STATUS_PATH = Path(BOOTSTRAP['bridge_status_path'])
            ACTIVATION_REQUEST_PATH = Path(BOOTSTRAP['activation_request_path'])
            PLAYERLIST_RUNTIME_PATH = Path(BOOTSTRAP['playerlist_runtime_path'])
            ACTIVE_SESSION_PATH = Path(BOOTSTRAP['active_session_path'])

            def read_json(path: Path):
                if not path.exists():
                    return {}
                try:
                    return json.loads(path.read_text(encoding='utf-8'))
                except Exception:
                    return {}

            def write_command(action: str, hotkey: str = 'overlay'):
                payload = {
                    'ts': datetime.now().isoformat(timespec='seconds'),
                    'action': action,
                    'hotkey': hotkey,
                    'source': 'code_red_overlay',
                }
                COMMAND_PATH.parent.mkdir(parents=True, exist_ok=True)
                COMMAND_PATH.write_text(json.dumps(payload, indent=2), encoding='utf-8')
                return payload

            class OverlayApp(tk.Tk):
                def __init__(self):
                    super().__init__()
                    self.state_path = Path(BOOTSTRAP.get('state_path') or (ROOT / 'overlay_state.json'))
                    self.hidden = False
                    self.compact = False
                    self.last_action = ''
                    self._drag_origin = None
                    self.window_geometry = '440x340+32+120'
                    self._load_state()
                    self.title(BOOTSTRAP.get('overlay_title', 'CODE RED'))
                    self.configure(bg='#060606')
                    self.geometry(self.window_geometry)
                    self.minsize(400, 220)
                    self.attributes('-topmost', True)
                    try:
                        self.wm_attributes('-alpha', 0.94)
                    except Exception:
                        pass
                    self.protocol('WM_DELETE_WINDOW', self._close)
                    self.bind('<Escape>', lambda _e: self._close())
                    self.bind('<h>', lambda _e: self._toggle_visible())
                    self.bind('<H>', lambda _e: self._toggle_visible())
                    self.bind('<Tab>', lambda _e: self._toggle_compact())

                    header = tk.Frame(self, bg='#0b0b0b', cursor='fleur')
                    header.pack(fill='x')
                    header.bind('<ButtonPress-1>', self._drag_start)
                    header.bind('<B1-Motion>', self._drag_move)
                    title = tk.Label(header, text=BOOTSTRAP.get('overlay_title', 'CODE RED'), bg='#0b0b0b', fg='#f4f4f4', font=('Segoe UI', 15, 'bold'), anchor='w')
                    title.pack(side='left', fill='x', expand=True, padx=12, pady=(10, 2))
                    title.bind('<ButtonPress-1>', self._drag_start)
                    title.bind('<B1-Motion>', self._drag_move)
                    tk.Button(header, text='HUD', command=self._toggle_compact, bg='#202225', fg='#f4f4f4', activebackground='#2e3136', activeforeground='#ffffff', relief='flat', padx=10, pady=4).pack(side='right', padx=(0, 8), pady=(8, 2))
                    tk.Button(header, text='X', command=self._close, bg='#5a1f1f', fg='#f4f4f4', activebackground='#7a2a2a', activeforeground='#ffffff', relief='flat', padx=10, pady=4).pack(side='right', padx=8, pady=(8, 2))

                    subtitle = tk.Label(self, text='Trainer-style overlay fallback', bg='#060606', fg='#9ea4ad', font=('Segoe UI', 9), anchor='w')
                    subtitle.pack(fill='x', padx=12)
                    self.status_var = tk.StringVar(value='Awaiting bridge activity')
                    self.detail_var = tk.StringVar(value=BOOTSTRAP.get('note', ''))
                    self.session_var = tk.StringVar(value='')
                    tk.Label(self, textvariable=self.status_var, bg='#111111', fg='#e0e0e0', anchor='w', padx=8, pady=6).pack(fill='x', padx=12, pady=(10, 4))
                    tk.Label(self, textvariable=self.detail_var, bg='#0b0b0b', fg='#8eb4ff', anchor='w', justify='left', wraplength=400, padx=8, pady=6).pack(fill='x', padx=12)
                    tk.Label(self, textvariable=self.session_var, bg='#060606', fg='#b9c2d0', anchor='w', justify='left', wraplength=400).pack(fill='x', padx=12, pady=(4, 2))

                    self.button_wrap = tk.Frame(self, bg='#060606')
                    self.button_wrap.pack(fill='x', padx=12, pady=(10, 6))
                    for idx, item in enumerate(BOOTSTRAP.get('mode_buttons', [])):
                        tk.Button(self.button_wrap, text=item['label'], command=lambda action=item['action']: self._issue(action), bg='#1b1d20', fg='#f1f1f1', activebackground='#2a2d31', activeforeground='#ffffff', relief='flat', padx=10, pady=6).grid(row=idx // 3, column=idx % 3, sticky='ew', padx=4, pady=4)
                    for col in range(3):
                        self.button_wrap.grid_columnconfigure(col, weight=1)

                    panel = tk.Frame(self, bg='#060606')
                    panel.pack(fill='both', expand=True, padx=12, pady=(4, 12))
                    self.menu_frame = tk.Frame(panel, bg='#060606')
                    self.playerlist_frame = tk.Frame(panel, bg='#060606')
                    self.menu_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
                    self.playerlist_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

                    menu_hint = '\n'.join([
                        f"{BOOTSTRAP['keymap'].get('singleplayer','Shift+F1')} Story Host",
                        f"{BOOTSTRAP['keymap'].get('freemode','Shift+F2')} Freemode",
                        f"{BOOTSTRAP['keymap'].get('lan','Shift+F3')} LAN",
                        f"{BOOTSTRAP['keymap'].get('private','Shift+F4')} Private",
                        f"{BOOTSTRAP['keymap'].get('public','Shift+F5')} Public",
                        f"{BOOTSTRAP['keymap'].get('open_menu','Shift+F6')} Menu",
                        f"{BOOTSTRAP['keymap'].get('open_playerlist','Shift+F7')} Playerlist",
                        "Tab Compact HUD   H Hide/Show",
                    ])
                    tk.Label(self.menu_frame, text='CODE RED ROUTES', bg='#060606', fg='#f4f4f4', font=('Segoe UI', 11, 'bold'), anchor='w').pack(fill='x')
                    tk.Label(self.menu_frame, text=menu_hint, bg='#060606', fg='#bbbbbb', justify='left', anchor='nw').pack(fill='both', expand=True, pady=(8, 0))
                    tk.Label(self.playerlist_frame, text='PLAYERLIST', bg='#060606', fg='#f4f4f4', font=('Segoe UI', 11, 'bold'), anchor='w').pack(fill='x')
                    self.listbox = tk.Listbox(self.playerlist_frame, bg='#111111', fg='#f1f1f1', relief='flat', highlightthickness=0, selectbackground='#2b5fb3')
                    self.listbox.pack(fill='both', expand=True, pady=(8, 0))
                    self._show_panel('menu')
                    self._apply_compact_state(initial=True)
                    self.after(250, self.poll_bridge)

                def _load_state(self):
                    state = read_json(self.state_path) if self.state_path.exists() else {}
                    self.window_geometry = state.get('geometry') or self.window_geometry
                    self.compact = bool(state.get('compact', False))

                def _save_state(self):
                    payload = {'geometry': self.geometry(), 'compact': self.compact, 'ts': datetime.now().isoformat(timespec='seconds')}
                    try:
                        self.state_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
                    except Exception:
                        pass

                def _close(self):
                    self._save_state()
                    self.destroy()

                def _drag_start(self, event):
                    self._drag_origin = (event.x_root, event.y_root, self.winfo_x(), self.winfo_y())

                def _drag_move(self, event):
                    if not self._drag_origin:
                        return
                    sx, sy, wx, wy = self._drag_origin
                    self.geometry(f'+{wx + (event.x_root - sx)}+{wy + (event.y_root - sy)}')

                def _toggle_visible(self):
                    if self.hidden:
                        self.deiconify()
                    else:
                        self.withdraw()
                    self.hidden = not self.hidden

                def _toggle_compact(self):
                    self.compact = not self.compact
                    self._apply_compact_state()
                    self._save_state()

                def _apply_compact_state(self, initial=False):
                    if self.compact:
                        if self.button_wrap.winfo_manager():
                            self.button_wrap.pack_forget()
                        self.menu_frame.place_forget()
                        self.playerlist_frame.place_forget()
                        if not initial:
                            self.geometry(f'440x160+{self.winfo_x()}+{self.winfo_y()}')
                    else:
                        if not self.button_wrap.winfo_manager():
                            self.button_wrap.pack(fill='x', padx=12, pady=(10, 6))
                        self.menu_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
                        self.playerlist_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

                def _show_panel(self, which):
                    if not self.compact:
                        (self.playerlist_frame if which == 'playerlist' else self.menu_frame).lift()

                def _issue(self, action):
                    payload = write_command(action)
                    self.last_action = action
                    self.status_var.set(f'Issued: {action}')
                    self.detail_var.set(f"Overlay wrote bridge command at {payload.get('ts','')}")
                    self._show_panel('playerlist' if action == 'open_playerlist' else 'menu')

                def poll_bridge(self):
                    bridge_status = read_json(BRIDGE_STATUS_PATH)
                    activation_request = read_json(ACTIVATION_REQUEST_PATH)
                    playerlist_runtime = read_json(PLAYERLIST_RUNTIME_PATH)
                    active_session = read_json(ACTIVE_SESSION_PATH)
                    action = activation_request.get('action') or playerlist_runtime.get('last_action') or bridge_status.get('action') or self.last_action
                    status = playerlist_runtime.get('status') or bridge_status.get('status') or 'awaiting_hook'
                    self.status_var.set(f"{status} | action={action or 'idle'}")
                    route_line = f"World={BOOTSTRAP.get('world','freemode')}  Boot={BOOTSTRAP.get('boot_target','MULTI_FREE_ROAM')}  Focus={BOOTSTRAP.get('playerlist_focus_score',0)}"
                    if active_session:
                        session_name = active_session.get('session_name') or BOOTSTRAP.get('session_name', 'Code RED Session')
                        player_name = active_session.get('player_name') or BOOTSTRAP.get('player_name', 'PlayerHost')
                        route_line = f"{session_name} | host={player_name} | {route_line}"
                        self.session_var.set(f"Session={session_name}   Host={player_name}")
                    else:
                        self.session_var.set(f"Target={BOOTSTRAP.get('selected_exe_name','unknown')}   Overlay ready")
                    self.detail_var.set(route_line)
                    roster = [
                        f"Host: {active_session.get('player_name') or BOOTSTRAP.get('player_name','PlayerHost')}",
                        f"Session: {active_session.get('session_name') or BOOTSTRAP.get('session_name','Code RED Session')}",
                        f"World: {active_session.get('world') or BOOTSTRAP.get('world','freemode')}",
                        f"Boot: {active_session.get('boot_target') or BOOTSTRAP.get('boot_target','MULTI_FREE_ROAM')}",
                    ]
                    if bridge_status.get('detail'):
                        roster.append(f"Bridge: {bridge_status['detail']}")
                    if playerlist_runtime.get('last_hotkey'):
                        roster.append(f"Last hotkey: {playerlist_runtime['last_hotkey']}")
                    if playerlist_runtime.get('player_count') is not None:
                        roster.append(f"Player count: {playerlist_runtime['player_count']}")
                    self.listbox.delete(0, 'end')
                    for row in roster:
                        self.listbox.insert('end', row)
                    self._show_panel('playerlist' if action == 'open_playerlist' or playerlist_runtime.get('playerlist_visible') else 'menu')
                    self.after(250, self.poll_bridge)

            if __name__ == '__main__':
                app = OverlayApp()
                app.mainloop()
        """).replace('__OVERLAY_BOOTSTRAP_JSON__', OVERLAY_BOOTSTRAP_JSON).strip() + '\n'
        launch_bat_text = dedent(r"""
            @echo off
            setlocal
            set ROOT=%~dp0
            set EXE=%ROOT%__OVERLAY_EXE__
            set SCRIPT=%ROOT%__OVERLAY_SCRIPT__
            if exist "%EXE%" (
              start "CODE RED Overlay" "%EXE%"
              exit /b 0
            )
            where pyw >nul 2>&1
            if not errorlevel 1 (
              start "CODE RED Overlay" pyw -3 "%SCRIPT%"
              exit /b 0
            )
            where py >nul 2>&1
            if not errorlevel 1 (
              start "CODE RED Overlay" py -3 "%SCRIPT%"
              exit /b 0
            )
            where pythonw >nul 2>&1
            if not errorlevel 1 (
              start "CODE RED Overlay" pythonw "%SCRIPT%"
              exit /b 0
            )
            where python >nul 2>&1
            if not errorlevel 1 (
              start "CODE RED Overlay" python "%SCRIPT%"
              exit /b 0
            )
            echo Python launcher not found. Install Python 3 or build __OVERLAY_EXE__ first.
            exit /b 1
        """).replace('__OVERLAY_SCRIPT__', OVERLAY_SCRIPT).replace('__OVERLAY_EXE__', OVERLAY_EXE).strip() + '\r\n'
        launch_game_bat_text = dedent(r"""
            @echo off
            setlocal
            set ROOT=%~dp0
            call "%ROOT%__OVERLAY_LAUNCH_BAT__"
            set GAME_EXE=__SELECTED_EXE__
            if not exist "%GAME_EXE%" (
              echo Game executable not found: %GAME_EXE%
              exit /b 1
            )
            start "CODE RED Game" "%GAME_EXE%"
            endlocal
        """).replace('__OVERLAY_LAUNCH_BAT__', OVERLAY_LAUNCH_BAT).replace('__SELECTED_EXE__', str(plan.get('selected_exe') or '')).strip() + '\r\n'
        build_bat_text = dedent(r"""
            @echo off
            setlocal
            set ROOT=%~dp0
            where pyinstaller >nul 2>&1
            if errorlevel 1 (
              echo PyInstaller not found. Install it with: py -3 -m pip install pyinstaller
              exit /b 1
            )
            if not exist "%ROOT%build" mkdir "%ROOT%build"
            pyinstaller --noconfirm --onefile --windowed --name Code_RED_Overlay --distpath "%ROOT%" --workpath "%ROOT%build" --specpath "%ROOT%build" "%ROOT%__OVERLAY_SCRIPT__"
            if exist "%ROOT%Code_RED_Overlay.exe" echo Built %ROOT%Code_RED_Overlay.exe
            endlocal
        """).replace('__OVERLAY_SCRIPT__', OVERLAY_SCRIPT).strip() + '\r\n'
        readme_text = (
            'Code RED Overlay\n\n'
            'This is the trainer-style external overlay fallback for the current hook bridge lane.\n'
            'It is intended to visibly appear over the game even when engine-native UI hooking is still being proven.\n\n'
            f'- Bootstrap: {OVERLAY_BOOTSTRAP_JSON}\n'
            f'- Overlay script: {OVERLAY_SCRIPT}\n'
            f'- Launch overlay: {OVERLAY_LAUNCH_BAT}\n'
            f'- Launch game + overlay: {OVERLAY_GAME_LAUNCH_BAT}\n'
            f'- Optional exe build: {OVERLAY_BUILD_BAT}\n'
            f'- Saved HUD state: {OVERLAY_STATE_JSON}\n\n'
            'Keys while overlay is focused:\n'
            '- H = hide/show overlay\n'
            '- Tab = compact HUD mode\n'
            '- Esc = close overlay\n\n'
            'The overlay watches Code_RED_Launch and Code_RED_PlayerlistBridge files and switches between MENU and PLAYERLIST panels based on bridge activity.\n'
            'This is the strongest safe visible-consumer fallback in this branch because it does not claim engine-native HUD parity.\n'
            'When built, launchers prefer Code_RED_Overlay.exe automatically.\n'
        )
        manifest = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'overlay_dir': str(overlay_dir),
            'bootstrap': str(bootstrap_path),
            'script': str(script_path),
            'launch_script': str(launch_bat_path),
            'launch_game_script': str(launch_game_bat_path),
            'build_exe_script': str(build_bat_path),
            'overlay_exe': str(overlay_dir / OVERLAY_EXE),
            'state_file': str(overlay_dir / OVERLAY_STATE_JSON),
            'readme': str(readme_path),
            'command_path': str(command_path),
            'selected_exe': str(plan.get('selected_exe') or ''),
            'topmost_overlay': True,
            'visible_consumer_fallback': True,
        }
        bootstrap_path.write_text(json.dumps(bootstrap, indent=2), encoding='utf-8')
        script_path.write_text(script_text, encoding='utf-8')
        launch_bat_path.write_text(launch_bat_text, encoding='utf-8')
        launch_game_bat_path.write_text(launch_game_bat_text, encoding='utf-8')
        build_bat_path.write_text(build_bat_text, encoding='utf-8')
        readme_path.write_text(readme_text, encoding='utf-8')
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        return manifest

    def install_main_dir_pack(self, show_message: bool = True) -> dict:
        plan_path = self.preview_launch_plan(show_message=False)
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        bridge_dir = self._write_runtime_bridge(plan)
        report = self.validate_game_root(show_message=False)
        game_root = Path(self.game_dir_var.get().strip())
        manifest = self._write_root_launcher_pack(game_root, plan, bridge_dir, report)
        hook_manifest = self._write_hook_scaffold_pack(game_root, plan, bridge_dir, report)
        manifest['hook_scaffold'] = hook_manifest
        try:
            playerlist_manifest = self._write_playerlist_bridge_pack(game_root, plan, bridge_dir, self._playerlist_report or self.analyze_playerlist_focus(), self._resolve_content_source())
            manifest['playerlist_bridge'] = playerlist_manifest
        except Exception as exc:
            manifest['playerlist_bridge_error'] = str(exc)
            self.write_note(f'Playerlist bridge pack skipped: {exc}')
        try:
            proof_manifest = self._write_hook_proof_pack(game_root, report)
            manifest['hook_proof_pack'] = proof_manifest
        except Exception as exc:
            manifest['hook_proof_pack_error'] = str(exc)
            self.write_note(f'Hook proof pack skipped: {exc}')
        try:
            overlay_manifest = self._write_overlay_pack(game_root, plan, bridge_dir, self._playerlist_report or self.analyze_playerlist_focus())
            manifest['overlay_pack'] = overlay_manifest
        except Exception as exc:
            manifest['overlay_pack_error'] = str(exc)
            self.write_note(f'Overlay pack skipped: {exc}')
        (game_root / ROOT_LAUNCHER_MANIFEST).write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        self.write_note(f'Main-directory launcher pack installed: {self.game_dir_var.get().strip()}')
        if show_message:
            messagebox.showinfo('Main-directory pack', f"Installed root launchers and bridge files into:\n{self.game_dir_var.get().strip()}", parent=self)
        return manifest

    def select_content_rpf_file(self):
        chosen = filedialog.askopenfilename(parent=self, title='Choose content.rpf From Anywhere', filetypes=[('RPF archives', 'content.rpf *.rpf'), ('All files', '*.*')])
        if not chosen:
            return
        picked = Path(chosen)
        self.content_rpf_var.set(str(picked))
        inferred = picked.parent
        for parent in [picked.parent, *picked.parents[:4]]:
            try:
                has_exe = any(parent.glob('*.exe')) or ((parent / 'bin').exists() and any((parent / 'bin').glob('*.exe')))
            except Exception:
                has_exe = False
            if has_exe:
                inferred = parent
                break
        normalized = self._normalize_game_dir(inferred)
        self.game_dir_var.set(str(normalized))
        self.auto_detect_game_exe()
        self._persist_app_settings()
        self.write_note(f'Selected content.rpf explicitly: {picked}')
        self.set_connection_state('PREPARED', f'Using content.rpf at {picked}')


    def _sync_target_rpf_with_content(self, force: bool = False):
        current = self.target_rpf_var.get().strip()
        content = self.content_rpf_var.get().strip()
        if force or (not current) or (current and not Path(current).exists() and content):
            if content:
                self.target_rpf_var.set(content)

    def use_content_as_target_rpf(self):
        self._sync_target_rpf_with_content(force=True)
        self._persist_app_settings()
        self.write_note(f'Ghost target set from content.rpf: {self.target_rpf_var.get().strip()}')
        self.write_note('Target RPF means the original game archive Code RED will clone and temporarily replace before launch.')
        self.hotswap_status_var.set(f'Target ready: {Path(self.target_rpf_var.get().strip()).name if self.target_rpf_var.get().strip() else "none"}')

    def select_target_rpf_file(self):
        chosen = filedialog.askopenfilename(parent=self, title='Choose Target RPF For HotSwap', filetypes=[('RPF archives', '*.rpf'), ('All files', '*.*')])
        if not chosen:
            return
        picked = Path(chosen)
        self.target_rpf_var.set(str(picked))
        inferred = picked.parent
        for parent in [picked.parent, *picked.parents[:4]]:
            try:
                has_exe = any(parent.glob('*.exe')) or ((parent / 'bin').exists() and any((parent / 'bin').glob('*.exe')))
            except Exception:
                has_exe = False
            if has_exe:
                inferred = parent
                break
        normalized = self._normalize_game_dir(inferred)
        self.game_dir_var.set(str(normalized))
        self.auto_detect_game_exe()
        self._persist_app_settings()
        self.write_note(f'Selected target RPF explicitly: {picked}')
        self.write_note('Target RPF means the original game archive Code RED will clone and temporarily replace before launch.')
        self.hotswap_status_var.set(f'Target ready: {picked.name}')
        self.set_connection_state('PREPARED', f'HotSwap target set: {picked.name}')

    def use_recovered_freemode(self):
        self._apply_mode_preset('freemode')

    def use_singleplayer_route(self):
        self._apply_mode_preset('singleplayer')

    def use_lan_route(self):
        self._apply_mode_preset('lan')

    def use_private_route(self):
        self._apply_mode_preset('private')

    def use_public_route(self):
        self._apply_mode_preset('public')

    def switch_active_mode(self, key: str | None = None, show_message: bool = True):
        if key:
            self._apply_mode_preset(key)
        validation = self.validate_boot_route(show_message=False)
        plan_path = self.preview_launch_plan(show_message=False)
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        self._write_runtime_bridge(plan)
        activation = self.build_activation_pack(show_message=False)
        mode_key = activation.get('mode_key', self._mode_preset_key())
        if mode_key == 'singleplayer' and not (self._beacon_thread is not None and self._beacon_thread.is_alive()):
            self.start_host_beacon()
            self.write_note('Single Player route auto-started the host beacon so the current session can be treated as host.')
        elif self._beacon_thread is not None and self._beacon_thread.is_alive():
            self._host_meta.update({
                'session_name': self.session_name_var.get().strip() or self._session_payload('host')['session_name'],
                'player_name': self.player_name_var.get().strip() or 'PlayerHost',
                'world': self.world_name_var.get().strip() or self._mode_preset_payload(mode_key)['world'],
                'boot_target': self.boot_target_var.get().strip() or self._mode_preset_payload(mode_key)['boot_target'],
                'trainer_profile': self.trainer_payload(),
            })
            self._host_append_event(f"[System] Active route switched to {activation.get('mode_label', mode_key)}")
        detail = f"Active route switched to {activation.get('mode_label', mode_key)}"
        self.set_connection_state('HOSTING' if (self._beacon_thread is not None and self._beacon_thread.is_alive()) else 'PREPARED', detail)
        self.write_note(detail)
        if show_message:
            messagebox.showinfo('Active mode switched', detail, parent=self)
        return activation

    def _mode_preset_key(self) -> str:
        boot = self.boot_target_var.get().strip()
        world = self.world_name_var.get().strip().lower()
        if boot == 'TriggerSinglePlayerLoad' or world in {'singleplayer', 'story', 'sp_default'}:
            return 'singleplayer'
        if boot == 'NetConf_PlayLAN' or world == 'lobby_lan':
            return 'lan'
        if boot == 'NetConf_PlayPrivate' or world == 'lobby_private':
            return 'private'
        if boot == 'NetConf_PlayPublic' or world == 'lobby_public':
            return 'public'
        return 'freemode'

    def _mode_preset_payload(self, key: str | None = None) -> dict:
        key = (key or self._mode_preset_key()).strip().lower()
        presets = {
            'singleplayer': {
                'label': 'Single Player Host',
                'world': 'singleplayer',
                'boot_target': 'TriggerSinglePlayerLoad',
                'route_note': 'TaskMachine -> TriggerSinglePlayerLoad -> HudSceneOffline (host current session by default)',
                'network_route': 'net.modeSingle',
                'net_mode': 'Single Player',
                'save_required': True,
                'required_paths': {
                    'root/content/ui/pausemenu/networking.sc.xml': ['net.modeSingle', 'Enter(NetOfflineTabs)'],
                    'root/content/ui/net/taskmachine.sc.xml': ['NetMachine.TriggerSinglePlayerLoad()', 'stackPush(HudSceneOffline)'],
                    'root/content/ui/hudscene.sc.xml': ['HudSceneOffline', 'StackPush_NoTransition(HudSceneOffline)'],
                    'root/content/ui/pausemenu/0x007B97C6/offlinemenu.sc.xml': ['Net_ContentLayer', 'NetContent_Public', 'NetContent_Private'],
                },
                'entry_route_chain': ['networking.sc.xml', 'taskmachine.sc.xml', 'hudscene.sc.xml', 'offlinemenu.sc.xml'],
            },
            'freemode': {
                'label': 'Recovered Freemode',
                'world': 'freemode',
                'boot_target': 'MULTI_FREE_ROAM',
                'route_note': 'Lobby -> SetGameWish(MULTI_FREE_ROAM) -> NetConf_StartGame',
                'network_route': 'Lobby playlist selection',
                'net_mode': 'freeroam',
                'required_paths': {
                    'root/content/ui/net/main.sc.xml': ['playerlist'],
                    'root/content/ui/net/taskmachine.sc.xml': ['NetMachine.StartMultiplayer()', "NetMachine.TriggerMultiplayerLoad('JoinWish')", 'NetTaskMachine id="NetMachine"'],
                    'root/content/ui/pausemenu/networking.sc.xml': ['NetConf_PlayPublic', 'NetConf_PlayPrivate', 'NetConf_PlayLAN'],
                    'root/content/ui/pausemenu/lobby/0x2B5C38A8': ["NetMachine.SetGameWish('MULTI_FREE_ROAM')", 'goto(NetConf_StartGame)', 'NetMachine.StartGameWish()'],
                    'root/content/ui/net/hudsceneonline.sc.xml': ['multiplayerIcons', 'playerlist'],
                },
                'entry_route_chain': ['networking.sc.xml', 'lobby/0x2B5C38A8', 'taskmachine.sc.xml', 'hudsceneonline.sc.xml'],
            },
            'lan': {
                'label': 'LAN Multiplayer',
                'world': 'lobby_lan',
                'boot_target': 'NetConf_PlayLAN',
                'route_note': 'Networking -> Play LAN -> PlayMpConf(LAN) -> Lobby / TaskMachine',
                'network_route': 'NetConf_PlayLAN',
                'net_mode': 'LAN',
                'required_paths': {
                    'root/content/ui/net/main.sc.xml': ['playerlist'],
                    'root/content/ui/net/taskmachine.sc.xml': ['NetMachine.StartMultiplayer()', 'NetTaskMachine id="NetMachine"'],
                    'root/content/ui/pausemenu/networking.sc.xml': ['NetConf_PlayLAN', "LAN Multiplayer", 'net.modeLAN'],
                    'root/content/ui/pausemenu/lobby/0x2B5C38A8': ['NetConf_StartGame', 'playerlist'],
                    'root/content/ui/net/hudsceneonline.sc.xml': ['net.modeLAN', 'multiplayerIcons'],
                },
                'entry_route_chain': ['networking.sc.xml', 'PlayMpConf.sc (LAN)', 'taskmachine.sc.xml', 'hudsceneonline.sc.xml'],
            },
            'private': {
                'label': 'Private Multiplayer',
                'world': 'lobby_private',
                'boot_target': 'NetConf_PlayPrivate',
                'route_note': 'Networking -> Play Private -> Online Multiplayer -> Lobby / TaskMachine',
                'network_route': 'NetConf_PlayPrivate',
                'net_mode': 'Private',
                'required_paths': {
                    'root/content/ui/net/main.sc.xml': ['playerlist'],
                    'root/content/ui/net/taskmachine.sc.xml': ['NetMachine.StartMultiplayer()', 'NetTaskMachine id="NetMachine"'],
                    'root/content/ui/pausemenu/networking.sc.xml': ['NetConf_PlayPrivate', 'Online Multiplayer', "NetMachine.Authenticate('Online Multiplayer')"],
                    'root/content/ui/pausemenu/lobby/0x2B5C38A8': ['NetConf_StartGame', 'NetGames_GoPrivate'],
                    'root/content/ui/net/hudsceneonline.sc.xml': ['multiplayerIcons', 'playerlist'],
                },
                'entry_route_chain': ['networking.sc.xml', 'PlayMpConf.sc (Private)', 'taskmachine.sc.xml', 'hudsceneonline.sc.xml'],
            },
            'public': {
                'label': 'Public Multiplayer',
                'world': 'lobby_public',
                'boot_target': 'NetConf_PlayPublic',
                'route_note': 'Networking -> Play Public -> Online Multiplayer -> Lobby / TaskMachine',
                'network_route': 'NetConf_PlayPublic',
                'net_mode': 'Public',
                'required_paths': {
                    'root/content/ui/net/main.sc.xml': ['playerlist'],
                    'root/content/ui/net/taskmachine.sc.xml': ['NetMachine.StartMultiplayer()', 'NetTaskMachine id="NetMachine"'],
                    'root/content/ui/pausemenu/networking.sc.xml': ['NetConf_PlayPublic', 'Online Multiplayer', "NetMachine.Authenticate('Online Multiplayer')"],
                    'root/content/ui/pausemenu/lobby/0x2B5C38A8': ['NetConf_StartGame', 'NetGames_GoPublic'],
                    'root/content/ui/net/hudsceneonline.sc.xml': ['multiplayerIcons', 'playerlist'],
                },
                'entry_route_chain': ['networking.sc.xml', 'PlayMpConf.sc (Public)', 'taskmachine.sc.xml', 'hudsceneonline.sc.xml'],
            },
        }
        return dict(presets.get(key, presets['freemode']))

    def _apply_mode_preset(self, key: str) -> None:
        preset = self._mode_preset_payload(key)
        self.world_name_var.set(preset['world'])
        self.boot_target_var.set(preset['boot_target'])
        self.world_route_var.set(preset['route_note'])
        self.write_note(f"Mode preset selected: {preset['label']} route selected.")
        self.set_connection_state('PREPARED', f"{preset['label']} route selected.")
        self._sync_startup_mode_from_world()

    def _startup_mode_map(self) -> dict[str, str]:
        return {
            'Single Player Host': 'singleplayer',
            'Recovered Freemode': 'freemode',
            'LAN': 'lan',
            'Private': 'private',
            'Public': 'public',
        }

    def _sync_startup_mode_from_world(self) -> None:
        reverse = {v: k for k, v in self._startup_mode_map().items()}
        key = (self.world_name_var.get().strip() or '').lower()
        label = reverse.get(key)
        if label and self.startup_mode_var.get() != label:
            self.startup_mode_var.set(label)

    def _on_startup_mode_changed(self, *_args) -> None:
        key = self._startup_mode_map().get(self.startup_mode_var.get().strip())
        if not key or self._applying_startup_mode:
            return
        self._applying_startup_mode = True
        try:
            self._apply_mode_preset(key)
        finally:
            self._applying_startup_mode = False

    def _render_playerlist_markdown(self, report: dict) -> str:
        lines = [
            '# Code RED playerlist focus',
            '',
            f"- Timestamp: {report.get('ts', '')}",
            f"- Content source: {report.get('content_source', '')}",
            f"- Focus score: {report.get('focus_score', 0)}",
            f"- Required core files: {report.get('required_core_present', 0)} / {report.get('required_core_count', 0)}",
            f"- Optional core files present: {report.get('optional_core_present', 0)}",
            '',
            '## Keymap',
        ]
        for key, value in sorted((report.get('keymap') or {}).items()):
            lines.append(f"- {key}: `{value}`")
        lines.extend(['', '## Core files'])
        for row in report.get('core_files', []):
            role = 'required' if row.get('required', True) else 'optional'
            mark = 'FOUND' if row.get('present') else 'MISSING'
            hits = ', '.join(row.get('matched_needles', [])) or 'no direct token match'
            lines.append(f"- {mark} ({role}) `{row.get('path')}` — {hits}")
        lines.extend(['', '## Nearby playerlist/menu paths'])
        for row in report.get('nearby_paths', [])[:32]:
            lines.append(f"- `{row}`")
        lines.extend(['', '## Recommended ghost targets'])
        for row in report.get('recommended_targets', [])[:24]:
            lines.append(f"- `{row}`")
        lines.extend(['', '## Live bridge note', 'These files are the safest current targets for a future in-game playerlist/menu consumer and Ghost RPF authoring pass.'])
        return "\n".join(lines) + "\n"

    def analyze_playerlist_focus(self) -> dict:
        source = self._resolve_content_source()
        parsed = None if source.is_dir() else RUNTIME.parse_rpf6(source)
        if source.is_dir():
            entries = [str(p.relative_to(source)).replace('\\', '/') for p in source.rglob('*') if p.is_file()]
        else:
            entries = [str(entry.get('path')) for entry in (parsed or {}).get('entries', []) if entry.get('path')]
        core_targets = [
            {'path': 'root/content/ui/net/main.sc.xml', 'needles': ['playerlist', 'NetScene'], 'required': True},
            {'path': 'root/content/ui/net/taskmachine.sc.xml', 'needles': ['NetMachine', 'JoinWish', 'playerlist'], 'required': True},
            {'path': 'root/content/ui/pausemenu/networking.sc.xml', 'needles': ['NetConf_PlayLAN', 'NetConf_PlayPrivate', 'NetConf_PlayPublic'], 'required': True},
            {'path': 'root/content/ui/pausemenu/lobby/0x2B5C38A8', 'needles': ['playerlist', 'NetConf_StartGame'], 'required': True},
            {'path': 'root/content/ui/net/hudsceneonline.sc.xml', 'needles': ['playerlist', 'HudSceneOnline'], 'required': True},
            {'path': 'root/content/ui/hudscene.sc.xml', 'needles': ['HudSceneOffline', 'PauseMenuScene'], 'required': True},
            {'path': 'root/content/ui/pausemenu/0x007B97C6/offlinemenu.sc.xml', 'needles': ['Net_ContentLayer', 'NetContent_Public', 'NetContent_Private'], 'required': True},
            {'path': 'root/content/ui/pausemenu/lobby/netplayercontextmenu.sc.xml', 'needles': ['playerlist', 'netui.success'], 'required': True},
            {'path': 'root/flash/brplru/playerlist.wsf', 'needles': ['playerlist'], 'required': False},
        ]
        core_files = []
        focus_score = 0
        recommended_targets = []
        required_core_count = sum(1 for row in core_targets if row['required'])
        required_core_present = 0
        optional_core_present = 0
        for target in core_targets:
            path_value = target['path']
            needles = list(target['needles'])
            required = bool(target.get('required', True))
            present = path_value in entries if entries else False
            text_blob = self._read_content_text(source, parsed, path_value) if present else ''
            matched = [needle for needle in needles if needle.lower() in text_blob.lower()]
            if present:
                focus_score += 2 if required else 1
                recommended_targets.append(path_value)
                if required:
                    required_core_present += 1
                else:
                    optional_core_present += 1
            if matched:
                focus_score += len(matched)
            core_files.append({'path': path_value, 'present': present, 'matched_needles': matched, 'required': required})
        nearby_tokens = ('playerlist', 'networking', 'hudsceneonline', 'taskmachine', 'lobby', 'posse', 'invite', 'hudscene', 'boot', 'contextmenu', 'offlinemenu')
        nearby = sorted(path_value for path_value in entries if any(token in path_value.lower() for token in nearby_tokens))
        recommended_targets = sorted(dict.fromkeys(recommended_targets + [
            'root/content/ui/pausemenu/0x007B97C6/publicmenu.sc.xml',
            'root/content/ui/pausemenu/0x007B97C6/privatemenu.sc.xml',
            'root/content/ui/pausemenu/0x007B97C6/lanmenu.sc.xml',
        ]))
        report = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'content_source': str(source),
            'focus_score': focus_score,
            'required_core_count': required_core_count,
            'required_core_present': required_core_present,
            'optional_core_present': optional_core_present,
            'core_files': core_files,
            'nearby_paths': nearby,
            'recommended_targets': recommended_targets,
            'keymap': self._ghost_keymap(),
            'event_map': {
                'open_menu': 'codered.openmenu',
                'open_playerlist': 'codered.openplayerlist',
                'singleplayer': 'codered.mode.singleplayer',
                'freemode': 'codered.mode.freemode',
                'lan': 'codered.mode.lan',
                'private': 'codered.mode.private',
                'public': 'codered.mode.public',
            },
        }
        (LOGS_DIR / PLAYERLIST_REPORT_JSON).write_text(json.dumps(report, indent=2), encoding='utf-8')
        markdown = self._render_playerlist_markdown(report)
        (LOGS_DIR / PLAYERLIST_REPORT_MD).write_text(markdown, encoding='utf-8')
        self._playerlist_report = report
        summary = f"Playerlist focus analyzed: score={focus_score} required={required_core_present}/{required_core_count}"
        self.playerlist_status_var.set(summary)
        if self._playerlist_text is not None:
            self._playerlist_text.delete('1.0', 'end')
            self._playerlist_text.insert('1.0', markdown)
        self.write_note(f"Playerlist focus report saved: {LOGS_DIR / PLAYERLIST_REPORT_JSON}")
        return report

    def build_playerlist_ghost(self):
        report = self.analyze_playerlist_focus()
        manifest = self.build_hotswap_copy(show_message=False)
        summary = f"Playerlist Ghost ready: score={report.get('focus_score', 0)} staged={Path(manifest['staged_copy']).name}"
        self.playerlist_status_var.set(summary)
        self.write_note(summary)
        try:
            if self.game_dir_var.get().strip():
                bridge_manifest = self.install_playerlist_bridge_pack(show_message=False)
                self.write_note(f"Playerlist bridge pack installed: {bridge_manifest.get('playerlist_dir', '')}")
        except Exception as exc:
            self.write_note(f"Playerlist bridge pack install skipped: {exc}")
        messagebox.showinfo(
            'Playerlist Ghost ready',
            f"{summary}\n\nReports:\n{LOGS_DIR / PLAYERLIST_REPORT_MD}\n{LOGS_DIR / PLAYERLIST_REPORT_JSON}",
            parent=self,
        )
        return manifest

    def install_playerlist_bridge_pack(self, show_message: bool = True) -> dict:
        source = self._resolve_content_source()
        report = self._playerlist_report or self.analyze_playerlist_focus()
        plan_path = self.preview_launch_plan(show_message=False)
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        bridge_dir = self._write_runtime_bridge(plan)
        game_root = Path(self.game_dir_var.get().strip())
        if not game_root.exists():
            game_root.mkdir(parents=True, exist_ok=True)
        manifest = self._write_playerlist_bridge_pack(game_root, plan, bridge_dir, report, source)
        self.playerlist_status_var.set(f"Playerlist bridge ready: {manifest.get('playerlist_dir_name', '')}")
        self.write_note(f"Playerlist bridge pack installed: {manifest.get('playerlist_dir', '')}")
        if show_message:
            messagebox.showinfo('Playerlist bridge installed', f"Installed playerlist bridge pack into:\n{manifest.get('playerlist_dir', '')}", parent=self)
        return manifest

    def _resolve_content_source(self) -> Path:
        value = self.content_rpf_var.get().strip()
        if not value:
            raise FileNotFoundError('content.rpf was not found. Set the game directory and detect it first.')
        path = Path(value)
        if not path.exists():
            raise FileNotFoundError(f'content source does not exist: {path}')
        return path

    def _archive_entries_by_path(self, parsed: dict) -> dict[str, dict]:
        return {str(entry.get('path')): entry for entry in parsed.get('entries', []) if entry.get('path')}

    def _read_content_text(self, source: Path, parsed: dict | None, entry_path: str) -> str:
        if source.is_dir():
            target = source / entry_path
            if target.exists():
                return target.read_text(encoding='utf-8', errors='replace')
            return ''
        if parsed is None:
            return ''
        entry = self._archive_entries_by_path(parsed).get(entry_path)
        if not entry:
            return ''
        try:
            data = RUNTIME.extract_rpf_entry(source, entry)
            return data.decode('utf-8', errors='replace') if data else ''
        except Exception as exc:
            log_line(f'Failed reading {{entry_path}} from {{source}}: {{exc}}')
            return ''

    def _render_boot_validation_markdown(self, report: dict) -> str:
        lines = [
            '# Code RED boot-route validation',
            '',
            f"- Timestamp: {report.get('ts', '')}",
            f"- Mode preset: {report.get('mode_label', '')}",
            f"- Content source: {report.get('content_source', '')}",
            f"- Boot target: {report.get('boot_target', '')}",
            f"- Route note: {report.get('route_note', '')}",
            f"- Overall pass: {'yes' if report.get('ok') else 'no'}",
            '',
            '## Checked files',
            '',
        ]
        for item in report.get('checks', []):
            lines.append(f"### {item.get('path', '')}")
            lines.append(f"- Present: {'yes' if item.get('present') else 'no'}")
            lines.append(f"- Required strings: {item.get('matched_count', 0)} / {item.get('required_count', 0)}")
            missing = item.get('missing_strings', [])
            if missing:
                lines.append('- Missing strings:')
                lines.extend([f"  - {value}" for value in missing])
            hits = item.get('matched_strings', [])
            if hits:
                lines.append('- Matched strings:')
                lines.extend([f"  - {value}" for value in hits])
            lines.append('')
        if report.get('entry_route_chain'):
            lines.append('## Entry route chain')
            lines.extend([f"- {value}" for value in report.get('entry_route_chain', [])])
            lines.append('')
        return '\n'.join(lines).strip() + '\n'

    def validate_boot_route(self, show_message: bool = True):
        try:
            source = self._resolve_content_source()
            preset = self._mode_preset_payload()
            parsed = None if source.is_dir() else RUNTIME.parse_rpf6(source)
            if not source.is_dir() and not parsed:
                raise RuntimeError(f'Failed to parse archive: {source}')
            path_map = self._archive_entries_by_path(parsed) if parsed else {}
            checks = []
            all_ok = True
            for entry_path, required_strings in preset['required_paths'].items():
                present = (entry_path in path_map) if parsed else (source / entry_path).exists()
                text_blob = self._read_content_text(source, parsed, entry_path) if present else ''
                matched = [value for value in required_strings if value in text_blob]
                missing = [value for value in required_strings if value not in text_blob]
                item_ok = bool(present and not missing)
                all_ok = all_ok and item_ok
                checks.append({
                    'path': entry_path,
                    'present': bool(present),
                    'required_count': len(required_strings),
                    'matched_count': len(matched),
                    'matched_strings': matched,
                    'missing_strings': missing,
                    'ok': item_ok,
                })
            report = {
                'ts': datetime.now().isoformat(timespec='seconds'),
                'mode_key': self._mode_preset_key(),
                'mode_label': preset['label'],
                'content_source': str(source),
                'boot_target': preset['boot_target'],
                'world': preset['world'],
                'route_note': preset['route_note'],
                'network_route': preset['network_route'],
                'entry_route_chain': preset['entry_route_chain'],
                'ok': bool(all_ok),
                'checked_paths': len(checks),
                'checks': checks,
            }
            (CONFIG_DIR / BOOT_VALIDATOR_REPORT_JSON).write_text(json.dumps(report, indent=2), encoding='utf-8')
            md = self._render_boot_validation_markdown(report)
            (CONFIG_DIR / BOOT_VALIDATOR_REPORT_MD).write_text(md, encoding='utf-8')
            (LOGS_DIR / BOOT_VALIDATOR_REPORT_JSON).write_text(json.dumps(report, indent=2), encoding='utf-8')
            (LOGS_DIR / BOOT_VALIDATOR_REPORT_MD).write_text(md, encoding='utf-8')
            detail = f"Boot route {'passed' if report['ok'] else 'failed'} for {preset['label']} using {source.name}"
            self.write_note(detail)
            self.set_connection_state('CONNECTED' if report['ok'] else 'FAILED', detail)
            if show_message:
                messagebox.showinfo('Boot route validation', json.dumps(report, indent=2), parent=self)
            return report
        except Exception as exc:
            self.set_connection_state('FAILED', f'Boot validation failed ({exc})')
            if show_message:
                messagebox.showerror('Boot validation failed', str(exc), parent=self)
            raise

    def _activation_request_payload(self, plan: dict | None = None, validation: dict | None = None) -> dict:
        preset = self._mode_preset_payload()
        plan = plan or {}
        validation = validation or {}
        save_report = self._scan_save_candidates(Path(self.game_dir_var.get().strip()))
        return {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'mode_key': self._mode_preset_key(),
            'mode_label': preset['label'],
            'requested_world': str(plan.get('world') or preset['world']),
            'requested_boot_target': str(plan.get('boot_target') or preset['boot_target']),
            'route_note': str(plan.get('route_note') or preset['route_note']),
            'network_route': preset['network_route'],
            'entry_route_chain': preset['entry_route_chain'],
            'validation_ok': bool(validation.get('ok', False)),
            'validation_source': validation.get('content_source', self.content_rpf_var.get().strip()),
            'required_paths': list(preset['required_paths'].keys()),
            'required_checks': validation.get('checks', []),
            'taskmachine_hints': ['NetMachine.StartMultiplayer()', 'NetMachine.TriggerMultiplayerLoad', 'NetMachine.StartGameWish()', 'NetMachine.TriggerSinglePlayerLoad()'],
            'save_required': bool(preset.get('save_required', False)),
            'ghost_menu': {
                'label': 'CODE RED',
                'keymap': self._ghost_keymap(),
                'event_map': {
                    'singleplayer': 'codered.mode.singleplayer',
                    'freemode': 'codered.mode.freemode',
                    'lan': 'codered.mode.lan',
                    'private': 'codered.mode.private',
                    'public': 'codered.mode.public',
                    'open_menu': 'codered.openmenu',
                    'open_playerlist': 'codered.openplayerlist',
                },
            },
            'save_scan': {
                'found_count': save_report.get('found_count', 0),
                'primary_candidate': save_report.get('primary_candidate', ''),
                'status': save_report.get('status', ''),
            },
        }

    def build_activation_pack(self, show_message: bool = True):
        validation = self.validate_boot_route(show_message=False)
        plan_path = self.preview_launch_plan(show_message=False)
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        bridge_dir = self._write_runtime_bridge(plan)
        activation = self._activation_request_payload(plan, validation)
        activation_path = bridge_dir / LAUNCH_BRIDGE_ACTIVATION_REQUEST
        activation_path.write_text(json.dumps(activation, indent=2), encoding='utf-8')
        synthetic_path = bridge_dir / LAUNCH_BRIDGE_SYNTHETIC_ROUTE
        synthetic = self._synthetic_bridge_payload(plan)
        synthetic['mode_key'] = activation['mode_key']
        synthetic['mode_label'] = activation['mode_label']
        synthetic['network_route'] = activation['network_route']
        synthetic['entry_route_chain'] = activation['entry_route_chain']
        synthetic['validation_ok'] = activation['validation_ok']
        synthetic_path.write_text(json.dumps(synthetic, indent=2), encoding='utf-8')
        detail = f"Activation pack built for {activation['mode_label']} ({'validated' if activation['validation_ok'] else 'unvalidated'})"
        self.write_note(detail)
        self.set_connection_state('PREPARED', detail)
        if show_message:
            messagebox.showinfo('Activation pack ready', json.dumps(activation, indent=2), parent=self)
        return activation

    def _run_launch_preflight(self) -> dict:
        if not self.content_rpf_var.get().strip():
            self.auto_detect_content_rpf()
        if not self.target_rpf_var.get().strip():
            self._sync_target_rpf_with_content(force=True)
        self.auto_detect_game_exe()
        root_report = self.validate_game_root(show_message=False)
        recommended = root_report.get('recommended_primary_exe', '')
        if recommended and Path(recommended).exists():
            selected = self.game_exe_var.get().strip()
            if selected != recommended:
                self.game_exe_var.set(recommended)
                self.write_note(f'Launch preflight selected recommended executable: {recommended}')
        warnings = root_report.get('hook_warnings', [])
        if warnings:
            for warning in warnings:
                self.write_note(f'Preflight warning: {warning}')
        boot_report = self.validate_boot_route(show_message=False)
        self.install_main_dir_pack(show_message=False)
        return {'root_report': root_report, 'boot_report': boot_report}

    def _confirm_launch_risks(self, root_report: dict) -> bool:
        warnings = root_report.get('hook_warnings', []) or []
        conflicts = root_report.get('hook_conflicts', {}) or {}
        if not warnings and not any(conflicts.values()):
            return True
        lines = ['Potential compatibility issues were detected before launch:', '']
        for warning in warnings:
            lines.append(f'- {warning}')
        if conflicts.get('mixed_hook_stack'):
            lines.append('- Mixed hook stack detected: safest default is direct RDR.exe unless you intentionally need the wrapper.')
        if conflicts.get('mixed_loader_stack'):
            lines.append('- Mixed loader stack detected: keep only the loader required by your chosen hook lane when possible.')
        lines.extend(['', 'Selected launch target:', self.game_exe_var.get().strip(), '', 'Continue anyway?'])
        return messagebox.askyesno('Launch compatibility audit', '\n'.join(lines), parent=self)

    def preview_launch_plan(self, show_message: bool = True):
        mode_key = self._mode_preset_key()
        effective_mode = 'host' if mode_key == 'singleplayer' or self.connection_state_var.get() in {'HOSTING', 'CONNECTED'} else 'join'
        payload = self._session_payload(effective_mode)
        save_report = self._scan_save_candidates(Path(self.game_dir_var.get().strip()))
        game_dir = Path(self.game_dir_var.get())
        exe_candidates = []
        if game_dir.exists():
            exe_candidates.extend(str(p) for p in game_dir.glob('*.exe'))
            if (game_dir / 'bin').exists():
                exe_candidates.extend(str(p) for p in (game_dir / 'bin').glob('*.exe'))
        selected_exe = str(self._resolve_game_exe() or '')
        plan = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'content_rpf': self.content_rpf_var.get().strip(),
            'target_rpf': self.target_rpf_var.get().strip(),
            'game_dir': self.game_dir_var.get().strip(),
            'mode': payload['mode'],
            'mode_key': mode_key,
            'mode_label': self._mode_preset_payload(mode_key)['label'],
            'world': payload['world'],
            'boot_target': payload['boot_target'],
            'route_note': payload.get('route_note', ''),
            'session_name': payload['session_name'],
            'player_name': payload['player_name'],
            'host_ip': payload['host_ip'],
            'port': payload['port'],
            'selected_exe': selected_exe,
            'exe_candidates': exe_candidates,
            'bridge_dir': str((Path(self.game_dir_var.get().strip()) / LAUNCH_BRIDGE_DIRNAME)) if self.game_dir_var.get().strip() else '',
            'runtime_bridge_host': '127.0.0.1',
            'runtime_bridge_port': payload['runtime_bridge_port'],
            'runtime_bridge_script': LAUNCH_BRIDGE_RUNTIME,
            'python_executable': sys.executable,
            'world_route_confidence': 'Boot-route validator checks taskmachine / networking / lobby / HUD assets and stages a local runtime handoff; actual in-game activation still needs game-side consumption proof.',
            'save_scan': {
                'found_count': save_report.get('found_count', 0),
                'primary_candidate': save_report.get('primary_candidate', ''),
                'status': save_report.get('status', ''),
            },
            'save_strategy': 'use_detected_or_prompt' if mode_key == 'singleplayer' else 'optional',
        }
        out_path = CONFIG_DIR / 'launch_plan.json'
        out_path.write_text(json.dumps(plan, indent=2), encoding='utf-8')
        self.write_note(f'Launch plan written: {out_path}')
        self.write_note(f"World target preview => {plan['world']} / {plan['boot_target']}")
        self.set_connection_state('PREPARED', f"Launch plan ready for {plan['world']} / {plan['boot_target']}")
        if show_message:
            messagebox.showinfo('Launch plan ready', str(out_path), parent=self)
        return out_path


    def _resolve_game_exe(self) -> Path | None:
        explicit = Path(self.game_exe_var.get().strip()) if self.game_exe_var.get().strip() else None
        if explicit and explicit.exists():
            return explicit
        self.auto_detect_game_exe()
        explicit = Path(self.game_exe_var.get().strip()) if self.game_exe_var.get().strip() else None
        if explicit and explicit.exists():
            return explicit
        return None

    def _write_runtime_bridge(self, plan: dict) -> Path:
        game_dir = Path(plan.get('game_dir') or self.game_dir_var.get().strip())
        if not game_dir.exists():
            raise FileNotFoundError(f'Game directory does not exist: {game_dir}')
        bridge_dir = game_dir / LAUNCH_BRIDGE_DIRNAME
        bridge_dir.mkdir(parents=True, exist_ok=True)
        self._active_bridge_dir = bridge_dir
        active_session = bridge_dir / 'active_session.json'
        launch_plan = bridge_dir / 'launch_plan.json'
        status_path = bridge_dir / LAUNCH_BRIDGE_STATUS
        game_process_path = bridge_dir / LAUNCH_BRIDGE_GAME_PROCESS
        runtime_script = bridge_dir / LAUNCH_BRIDGE_RUNTIME
        consumer_script = bridge_dir / LAUNCH_BRIDGE_CONSUMER
        consumer_status_path = bridge_dir / LAUNCH_BRIDGE_CONSUMER_STATUS
        activation_request_path = bridge_dir / LAUNCH_BRIDGE_ACTIVATION_REQUEST
        synthetic_route_path = bridge_dir / LAUNCH_BRIDGE_SYNTHETIC_ROUTE
        session_payload = self._session_payload(plan.get('mode', 'join'))
        launch_plan.write_text(json.dumps(plan, indent=2), encoding='utf-8')
        active_session.write_text(json.dumps(session_payload, indent=2), encoding='utf-8')
        if not status_path.exists():
            status_path.write_text(json.dumps({
                'ts': datetime.now().isoformat(timespec='seconds'),
                'status': 'prepared',
                'bridge_dir': str(bridge_dir),
                'bridge_port': session_payload.get('runtime_bridge_port', self._runtime_bridge_port()),
            }, indent=2), encoding='utf-8')
        if not game_process_path.exists():
            game_process_path.write_text(json.dumps({}, indent=2), encoding='utf-8')
        runtime_script.write_text(self._runtime_bridge_script_text(), encoding='utf-8')
        consumer_script.write_text(self._bridge_consumer_script_text(), encoding='utf-8')
        validation_stub = {}
        validator_json_path = CONFIG_DIR / BOOT_VALIDATOR_REPORT_JSON
        if validator_json_path.exists():
            try:
                validation_stub = json.loads(validator_json_path.read_text(encoding='utf-8'))
            except Exception:
                validation_stub = {}
        synthetic_route_path.write_text(json.dumps(self._synthetic_bridge_payload(plan), indent=2), encoding='utf-8')
        if not consumer_status_path.exists():
            consumer_status_path.write_text(json.dumps({'ts': datetime.now().isoformat(timespec='seconds'), 'status': 'prepared'}, indent=2), encoding='utf-8')
        activation_request_path.write_text(json.dumps(self._activation_request_payload(plan, validation_stub), indent=2), encoding='utf-8')
        exe_path = plan.get('selected_exe', '')
        bat = bridge_dir / 'launch_game.bat'
        sh = bridge_dir / 'launch_game.sh'
        readme = bridge_dir / 'README.txt'
        bridge_port = int(session_payload.get('runtime_bridge_port', self._runtime_bridge_port()))
        pyexe = sys.executable
        bat_lines = [
            '@echo off',
            'setlocal',
            'set CODERED_BRIDGE_DIR=%~dp0',
            f'set CODERED_BRIDGE_PORT={bridge_port}',
            f'set CODERED_WORLD={session_payload.get("world", "freemode")}',
            f'set CODERED_BOOT_TARGET={session_payload.get("boot_target", "MULTI_FREE_ROAM")}',
            'set CODERED_ACTIVE_SESSION=%CODERED_BRIDGE_DIR%active_session.json',
            'set CODERED_LAUNCH_PLAN=%CODERED_BRIDGE_DIR%launch_plan.json',
            'echo Code RED bridge using %CODERED_BRIDGE_DIR%',
            'if exist "%CODERED_BRIDGE_DIR%active_session.json" echo Active session ready',
            'if exist "%CODERED_BRIDGE_DIR%launch_plan.json" echo Launch plan ready',
            f'start "Code RED Runtime Bridge" /min "{pyexe}" "%CODERED_BRIDGE_DIR%{LAUNCH_BRIDGE_RUNTIME}" "%CODERED_BRIDGE_DIR%"',
        ]
        if exe_path:
            bat_lines.append(f'start "" "{exe_path}"')
        else:
            bat_lines.append('echo No executable selected yet.')
        bat_lines.append('endlocal')
        bat.write_text('\r\n'.join(bat_lines) + '\r\n', encoding='utf-8')
        sh_lines = [
            '#!/usr/bin/env bash',
            'set -e',
            'BRIDGE_DIR="$(cd "$(dirname "$0")" && pwd)"',
            f'export CODERED_BRIDGE_PORT={bridge_port}',
            f'export CODERED_WORLD="{session_payload.get("world", "freemode")}"',
            f'export CODERED_BOOT_TARGET="{session_payload.get("boot_target", "MULTI_FREE_ROAM")}"',
            'export CODERED_BRIDGE_DIR="${BRIDGE_DIR}"',
            'export CODERED_ACTIVE_SESSION="${BRIDGE_DIR}/active_session.json"',
            'export CODERED_LAUNCH_PLAN="${BRIDGE_DIR}/launch_plan.json"',
            'echo "Code RED bridge using ${BRIDGE_DIR}"',
            'test -f "${BRIDGE_DIR}/active_session.json" && echo "Active session ready" || true',
            'test -f "${BRIDGE_DIR}/launch_plan.json" && echo "Launch plan ready" || true',
            f'"{pyexe}" "${{BRIDGE_DIR}}/{LAUNCH_BRIDGE_RUNTIME}" "${{BRIDGE_DIR}}" >/dev/null 2>&1 &',
        ]
        if exe_path:
            sh_lines.append(f'exec "{exe_path}"')
        else:
            sh_lines.append('echo "No executable selected yet."')
        sh.write_text('\n'.join(sh_lines) + '\n', encoding='utf-8')
        try:
            os.chmod(sh, 0o755)
        except Exception:
            pass
        readme.write_text(
            'Code RED Launch Bridge\n\n'
            'This folder mirrors the active multiplayer session handoff next to the game install.\n'
            '- active_session.json = host/join/session state\n'
            '- launch_plan.json = resolved launch plan and detected executable\n'
            f'- {LAUNCH_BRIDGE_STATUS} = live runtime-bridge status written by the bridge service\n'
            f'- {LAUNCH_BRIDGE_GAME_PROCESS} = last launched game process metadata\n'
            f'- {LAUNCH_BRIDGE_RUNTIME} = local socket/file bridge for trainer/mod consumption\n'
            f'- {LAUNCH_BRIDGE_CONSUMER} = first game-side bridge consumer / synthetic join shim\n'
            f'- {LAUNCH_BRIDGE_CONSUMER_STATUS} = last consumer result for solo testing\n'
            f'- {LAUNCH_BRIDGE_ACTIVATION_REQUEST} = requested world/runtime activation payload\n'
            f'- {LAUNCH_BRIDGE_SYNTHETIC_ROUTE} = synthetic freemode bridge candidate composition\n'
            '- launch_game.bat / launch_game.sh = wrapper launch scripts with bridge env vars\n',
            encoding='utf-8',
        )
        return bridge_dir


    def _synthetic_bridge_payload(self, plan: dict | None = None) -> dict:
        plan = plan or {}
        world = str(plan.get('world') or self.world_name_var.get().strip() or 'freemode')
        boot_target = str(plan.get('boot_target') or self.boot_target_var.get().strip() or 'MULTI_FREE_ROAM')
        world_key = world.lower().strip()
        payload = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'world': world,
            'boot_target': boot_target,
            'bridge_strategy': 'synthetic_runtime_composition',
            'runtime_shell': ['medium_update_thread.wsc', 'player.wsc', 'pause.wsc'],
            'runtime_shell_secondary': ['short_update_thread.wsc', 'long_update_thread.wsc'],
            'handoff_helper': 'fuieventmonitor.wsc',
            'multiplayer_adapters': ['mp_rezbuddy.wsc', 'sc_mp_aa_challenge_wrapper.wsc'],
            'candidates': {
                'blackwater': {
                    'world_shell': 'blackwater.wsc',
                    'volume_shell': 'blackwatervol.wsc',
                    'population_shell': 'blk_population.wsc',
                },
                'tumbleweed': {
                    'world_shell': 'tumbleweed.wsc',
                    'volume_shell': 'tumbleweedvol.wsc',
                    'population_shell': 'tal_population.wsc',
                },
                'diezcoronas': {
                    'world_shell': 'diezcoronas.wsc',
                    'volume_shell': 'diezcoronasvol.wsc',
                    'population_shell': 'arm_population.wsc',
                },
            },
        }
        preferred = payload['candidates'].get(world_key, payload['candidates']['blackwater'])
        payload.update(preferred)
        preset = self._mode_preset_payload()
        payload['mode_key'] = self._mode_preset_key()
        payload['mode_label'] = preset['label']
        payload['network_route'] = preset['network_route']
        payload['entry_route_chain'] = preset['entry_route_chain']
        return payload

    def _bridge_consumer_script_text(self) -> str:
        template = dedent("""\
from __future__ import annotations

import json
import socket
import sys
from datetime import datetime
from pathlib import Path

BRIDGE_DIR = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
MODE = sys.argv[2] if len(sys.argv) > 2 else 'probe'
ALIAS = sys.argv[3] if len(sys.argv) > 3 else 'LoopbackBot'
ACTIVE_SESSION_PATH = BRIDGE_DIR / 'active_session.json'
LAUNCH_PLAN_PATH = BRIDGE_DIR / 'launch_plan.json'
RUNTIME_STATUS_PATH = BRIDGE_DIR / '__STATUS__'
CONSUMER_STATUS_PATH = BRIDGE_DIR / '__CONSUMER_STATUS__'
ACTIVATION_REQUEST_PATH = BRIDGE_DIR / '__ACTIVATION_REQUEST__'
SYNTHETIC_ROUTE_PATH = BRIDGE_DIR / '__SYNTHETIC_ROUTE__'


def read_json(path: Path) -> dict:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def send_json(host: str, port: int, payload: dict, timeout: float = 2.0) -> dict:
    with socket.create_connection((host, int(port)), timeout=timeout) as conn:
        conn.settimeout(timeout)
        conn.sendall((json.dumps(payload) + '\\n').encode('utf-8'))
        data = conn.recv(32768).decode('utf-8', errors='replace').strip()
    if not data:
        return {}
    return json.loads(data.splitlines()[0])


def main() -> int:
    active = read_json(ACTIVE_SESSION_PATH)
    plan = read_json(LAUNCH_PLAN_PATH)
    activation_request = read_json(ACTIVATION_REQUEST_PATH)
    synthetic = read_json(SYNTHETIC_ROUTE_PATH)
    runtime_port = int(active.get('runtime_bridge_port') or plan.get('runtime_bridge_port') or (int(active.get('port', 6677)) + 100))
    host_ip = str(active.get('host_ip') or '127.0.0.1')
    host_port = int(active.get('port') or 6677)
    activation = {
        'ts': datetime.now().isoformat(timespec='seconds'),
        'mode': MODE,
        'consumer_alias': ALIAS,
        'requested_world': active.get('world', plan.get('world', 'freemode')),
        'requested_boot_target': active.get('boot_target', plan.get('boot_target', 'MULTI_FREE_ROAM')),
        'runtime_bridge_port': runtime_port,
        'host_ip': host_ip,
        'host_port': host_port,
        'synthetic_bridge': synthetic,
    }
    write_json(ACTIVATION_REQUEST_PATH, activation)
    result = {
        'ok': False,
        'mode': MODE,
        'consumer_alias': ALIAS,
        'ts': activation['ts'],
        'host_ip': host_ip,
        'host_port': host_port,
        'runtime_bridge_port': runtime_port,
        'requested_world': activation['requested_world'],
        'requested_boot_target': activation['requested_boot_target'],
        'activation_request': activation_request,
        'synthetic_bridge': synthetic,
        'runtime_status': read_json(RUNTIME_STATUS_PATH),
        'activation_ready': bool(activation_request.get('validation_ok') or activation_request.get('mode_key')),
    }
    try:
        runtime = send_json('127.0.0.1', runtime_port, {'kind': 'get_state', 'from': ALIAS})
        result['runtime_bridge'] = runtime
        result['runtime_ok'] = bool(runtime.get('ok'))
    except Exception as exc:
        result['runtime_ok'] = False
        result['runtime_error'] = str(exc)

    try:
        probe = send_json(host_ip, host_port, {'kind': 'probe', 'from': ALIAS})
        result['host_probe'] = probe
        result['host_probe_ok'] = bool(probe.get('ok'))
    except Exception as exc:
        result['host_probe_ok'] = False
        result['host_probe_error'] = str(exc)

    if MODE != 'probe' and result.get('host_probe_ok'):
        try:
            chat = send_json(host_ip, host_port, {'kind': 'chat', 'from': ALIAS, 'text': '[Loopback] synthetic consumer chat test'})
            result['chat_ack'] = bool(chat.get('chat_ack'))
        except Exception as exc:
            result['chat_ack'] = False
            result['chat_error'] = str(exc)
        try:
            voice = send_json(host_ip, host_port, {'kind': 'voice_ping', 'from': ALIAS, 'voice_enabled': True, 'voice_muted': False, 'push_to_talk': 'B', 'device': 'Loopback Mic'})
            result['voice_ack'] = bool(voice.get('voice_ack'))
        except Exception as exc:
            result['voice_ack'] = False
            result['voice_error'] = str(exc)
        try:
            trainer = send_json(host_ip, host_port, {'kind': 'trainer_push', 'from': ALIAS, 'trainer_profile': {'god_mode': False, 'infinite_ammo': False, 'noclip': False, 'super_jump': False, 'fast_travel': True, 'weather': 'default', 'time': 'default'}})
            result['trainer_ack'] = bool(trainer.get('trainer_ack'))
        except Exception as exc:
            result['trainer_ack'] = False
            result['trainer_error'] = str(exc)
        try:
            poll = send_json(host_ip, host_port, {'kind': 'poll_status', 'from': ALIAS, 'last_chat_index': 0})
            result['poll_ack'] = bool(poll.get('poll_ack'))
            result['peer_count'] = int(poll.get('peer_count', 0) or 0)
            result['roster'] = poll.get('roster', []) or []
            result['chat_events'] = poll.get('chat_events', []) or []
        except Exception as exc:
            result['poll_ack'] = False
            result['poll_error'] = str(exc)
    result['ok'] = bool(result.get('runtime_ok') and result.get('host_probe_ok') and (MODE == 'probe' or (result.get('chat_ack') and result.get('voice_ack') and result.get('trainer_ack') and result.get('poll_ack'))))
    write_json(CONSUMER_STATUS_PATH, result)
    print(json.dumps(result, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
""")
        return template.replace('__STATUS__', LAUNCH_BRIDGE_STATUS).replace('__CONSUMER_STATUS__', LAUNCH_BRIDGE_CONSUMER_STATUS).replace('__ACTIVATION_REQUEST__', LAUNCH_BRIDGE_ACTIVATION_REQUEST).replace('__SYNTHETIC_ROUTE__', LAUNCH_BRIDGE_SYNTHETIC_ROUTE)

    def _runtime_bridge_port(self) -> int:
        base_port = self._normalize_port()
        port = base_port + 100
        if port > 65535:
            port = max(1025, base_port - 100)
        return port

    def _runtime_bridge_script_text(self) -> str:
        return f"""from __future__ import annotations

import json
import socket
import sys
from datetime import datetime
from pathlib import Path

BRIDGE_DIR = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
ACTIVE_SESSION_PATH = BRIDGE_DIR / 'active_session.json'
LAUNCH_PLAN_PATH = BRIDGE_DIR / 'launch_plan.json'
STATUS_PATH = BRIDGE_DIR / '{LAUNCH_BRIDGE_STATUS}'
GAME_PROCESS_PATH = BRIDGE_DIR / '{LAUNCH_BRIDGE_GAME_PROCESS}'


def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {{}}
    except Exception:
        return {{}}
    return {{}}


def _write_status(message: str, port: int, last_packet: dict | None = None) -> None:
    payload = {{
        'ts': datetime.now().isoformat(timespec='seconds'),
        'status': message,
        'bridge_dir': str(BRIDGE_DIR),
        'bridge_port': port,
        'active_session': _read_json(ACTIVE_SESSION_PATH),
        'launch_plan': _read_json(LAUNCH_PLAN_PATH),
        'game_process': _read_json(GAME_PROCESS_PATH),
        'last_packet': last_packet or {{}},
    }}
    STATUS_PATH.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def main() -> int:
    active = _read_json(ACTIVE_SESSION_PATH)
    plan = _read_json(LAUNCH_PLAN_PATH)
    port = int(active.get('runtime_bridge_port') or plan.get('runtime_bridge_port') or 6777)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', port))
    server.listen(8)
    server.settimeout(1.0)
    _write_status('ready', port)
    try:
        while True:
            try:
                conn, _addr = server.accept()
            except socket.timeout:
                _write_status('ready', port)
                continue
            except OSError:
                break
            with conn:
                raw = ''
                try:
                    raw = conn.recv(8192).decode('utf-8', errors='replace').strip()
                except OSError:
                    raw = ''
                packet = {{}}
                if raw:
                    try:
                        packet = json.loads(raw.splitlines()[0])
                    except Exception:
                        packet = {{'kind': 'probe_runtime', 'raw': raw}}
                kind = packet.get('kind', 'probe_runtime')
                active = _read_json(ACTIVE_SESSION_PATH)
                plan = _read_json(LAUNCH_PLAN_PATH)
                response = {{
                    'ok': True,
                    'kind': kind,
                    'ts': datetime.now().isoformat(timespec='seconds'),
                    'bridge_dir': str(BRIDGE_DIR),
                    'bridge_port': port,
                    'session_name': active.get('session_name', plan.get('session_name', 'Code RED Freemode')),
                    'world': active.get('world', plan.get('world', 'freemode')),
                    'boot_target': active.get('boot_target', plan.get('boot_target', 'MULTI_FREE_ROAM')),
                }}
                if kind == 'get_state':
                    response['active_session'] = active
                    response['launch_plan'] = plan
                    response['game_process'] = _read_json(GAME_PROCESS_PATH)
                elif kind == 'shutdown':
                    response['shutdown'] = True
                else:
                    response['probe_ack'] = True
                _write_status('ready', port, response)
                try:
                    conn.sendall((json.dumps(response) + '\\n').encode('utf-8'))
                except OSError:
                    pass
                if kind == 'shutdown':
                    break
    finally:
        try:
            server.close()
        except Exception:
            pass
        _write_status('stopped', port)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
"""

    def _probe_runtime_bridge(self, bridge_dir: Path) -> dict:
        status_path = bridge_dir / LAUNCH_BRIDGE_STATUS
        port = self._runtime_bridge_port()
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=2.0) as conn:
                conn.settimeout(2.0)
                conn.sendall((json.dumps({'kind': 'probe_runtime', 'from': self.player_name_var.get().strip() or 'Player'}) + '\n').encode('utf-8'))
                data = conn.recv(8192).decode('utf-8', errors='replace').strip()
            if data:
                return json.loads(data.splitlines()[0])
        except Exception:
            pass
        if status_path.exists():
            try:
                return json.loads(status_path.read_text(encoding='utf-8'))
            except Exception:
                return {}
        return {}

    def _start_runtime_bridge_service(self, bridge_dir: Path) -> tuple[dict, bool]:
        probe = self._probe_runtime_bridge(bridge_dir)
        if probe.get('ok') or probe.get('status') == 'ready':
            return probe, False
        script_path = bridge_dir / LAUNCH_BRIDGE_RUNTIME
        if not script_path.exists():
            raise FileNotFoundError(f'Runtime bridge script is missing: {script_path}')
        kwargs = {'cwd': str(bridge_dir)}
        if os.name == 'nt':
            kwargs['creationflags'] = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0)
        else:
            kwargs['start_new_session'] = True
        subprocess.Popen([sys.executable, str(script_path), str(bridge_dir)], **kwargs)
        deadline = time.time() + 4.0
        last = {}
        while time.time() < deadline:
            time.sleep(0.2)
            last = self._probe_runtime_bridge(bridge_dir)
            if last.get('ok') or last.get('status') == 'ready':
                return last, True
        return last, True

    def _shutdown_runtime_bridge_service(self, bridge_dir: Path | None = None, timeout: float = 2.0) -> bool:
        bridge_dir = bridge_dir or self._active_bridge_dir
        if bridge_dir is None:
            try:
                game_dir = Path(self.game_dir_var.get().strip())
                if game_dir.exists():
                    bridge_dir = game_dir / LAUNCH_BRIDGE_DIRNAME
            except Exception:
                bridge_dir = None
        if bridge_dir is None or not Path(bridge_dir).exists():
            return False
        port = self._runtime_bridge_port()
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=timeout) as conn:
                conn.settimeout(timeout)
                conn.sendall((json.dumps({'kind': 'shutdown', 'from': self.player_name_var.get().strip() or 'Player'}) + '\n').encode('utf-8'))
                try:
                    conn.recv(4096)
                except Exception:
                    pass
            self.write_note(f'Runtime bridge shutdown requested on localhost:{port}')
            return True
        except Exception as exc:
            log_line(f'Runtime bridge shutdown skipped: {exc}')
            return False

    def _ensure_bridge_ready(self) -> tuple[Path, dict, bool]:
        plan_path = self.preview_launch_plan(show_message=False)
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        bridge_dir = self._write_runtime_bridge(plan)
        try:
            self._write_root_launcher_pack(Path(self.game_dir_var.get().strip()), plan, bridge_dir, self.validate_game_root(show_message=False))
        except Exception as exc:
            self.write_note(f'Root launcher pack install skipped: {exc}')
        probe, started = self._start_runtime_bridge_service(bridge_dir)
        return bridge_dir, probe, started

    def _run_bridge_consumer_once(self, bridge_dir: Path, mode: str = 'probe', alias: str | None = None) -> tuple[dict, int, str]:
        script_path = bridge_dir / LAUNCH_BRIDGE_CONSUMER
        if not script_path.exists():
            raise FileNotFoundError(f'Bridge consumer script is missing: {script_path}')
        alias = alias or ((self.player_name_var.get().strip() or 'Player') + 'Bot')
        proc = subprocess.run([sys.executable, str(script_path), str(bridge_dir), mode, alias], cwd=str(bridge_dir), capture_output=True, text=True, timeout=12)
        combined = ((proc.stdout or '') + ('\n' if proc.stdout and proc.stderr else '') + (proc.stderr or '')).strip()
        status_path = bridge_dir / LAUNCH_BRIDGE_CONSUMER_STATUS
        status = {}
        if status_path.exists():
            try:
                status = json.loads(status_path.read_text(encoding='utf-8'))
            except Exception:
                status = {}
        if not status and proc.stdout.strip():
            try:
                status = json.loads(proc.stdout.strip().splitlines()[-1])
            except Exception:
                status = {}
        return status, proc.returncode, combined

    def probe_bridge_consumer(self):
        try:
            bridge_dir, _probe, _started = self._ensure_bridge_ready()
            status, rc, output = self._run_bridge_consumer_once(bridge_dir, 'probe')
            detail = f"Consumer probe {'passed' if status.get('ok') else 'failed'} on localhost:{self._runtime_bridge_port()} / host {self._advertised_host()}:{self._normalize_port()}"
            self.write_note(detail)
            if output:
                self.write_note(output[:1200])
            self.set_connection_state('CONNECTED' if status.get('ok') else 'FAILED', detail)
            messagebox.showinfo('Bridge consumer probe', json.dumps(status or {'returncode': rc}, indent=2), parent=self)
        except Exception as exc:
            self.set_connection_state('FAILED', f'Bridge consumer probe failed ({exc})')
            messagebox.showerror('Bridge consumer probe failed', str(exc), parent=self)

    def run_bridge_consumer(self):
        try:
            bridge_dir, _probe, _started = self._ensure_bridge_ready()
            status, rc, output = self._run_bridge_consumer_once(bridge_dir, 'consume')
            detail = f"Bridge consumer {'passed' if status.get('ok') else 'failed'} for {status.get('requested_world', self.world_name_var.get())} / {status.get('requested_boot_target', self.boot_target_var.get())}"
            self.write_note(detail)
            if output:
                self.write_note(output[:1200])
            self.set_connection_state('CONNECTED' if status.get('ok') else 'FAILED', detail)
            messagebox.showinfo('Bridge consumer result', json.dumps(status or {'returncode': rc}, indent=2), parent=self)
        except Exception as exc:
            self.set_connection_state('FAILED', f'Bridge consumer failed ({exc})')
            messagebox.showerror('Bridge consumer failed', str(exc), parent=self)

    def run_solo_loopback_test(self):
        host_was_running = self._beacon_thread is not None and self._beacon_thread.is_alive() and not self._beacon_stop.is_set()
        if not host_was_running:
            self.start_host_beacon()
            self.update_idletasks()
            time.sleep(0.4)
        try:
            bridge_dir, _probe, _started = self._ensure_bridge_ready()
            alias = (self.player_name_var.get().strip() or 'Player') + 'Bot'
            status, rc, output = self._run_bridge_consumer_once(bridge_dir, 'self_test', alias)
            ok = bool(status.get('ok'))
            detail = f"Solo loopback {'passed' if ok else 'failed'} with peer_count={status.get('peer_count', 0)}"
            self.write_note(detail)
            if output:
                self.write_note(output[:1500])
            self.set_connection_state('CONNECTED' if ok else 'FAILED', detail)
            messagebox.showinfo('Solo loopback test', json.dumps(status or {'returncode': rc}, indent=2), parent=self)
        except Exception as exc:
            self.set_connection_state('FAILED', f'Solo loopback failed ({exc})')
            messagebox.showerror('Solo loopback failed', str(exc), parent=self)

    def probe_launch_bridge(self):
        game_dir = Path(self.game_dir_var.get().strip()) if self.game_dir_var.get().strip() else None
        if not game_dir or not game_dir.exists():
            messagebox.showerror('Game directory missing', str(game_dir), parent=self)
            return
        bridge_dir = game_dir / LAUNCH_BRIDGE_DIRNAME
        probe = self._probe_runtime_bridge(bridge_dir)
        if probe.get('ok') or probe.get('status') == 'ready':
            detail = f"Bridge ready on localhost:{probe.get('bridge_port', self._runtime_bridge_port())} for {probe.get('world', self.world_name_var.get())} / {probe.get('boot_target', self.boot_target_var.get())}"
            self.write_note(detail)
            self.set_connection_state('CONNECTED', detail)
            messagebox.showinfo('Runtime bridge ready', detail, parent=self)
            return
        self.set_connection_state('PREPARED', 'Runtime bridge files exist, but the live bridge service is not running yet.')
        messagebox.showinfo('Runtime bridge not live', f'Bridge folder checked at:\n{bridge_dir}\n\nInstall or launch the bridge first.', parent=self)

    def install_launch_bridge(self):
        plan_path = self.preview_launch_plan(show_message=False)
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        bridge_dir = self._write_runtime_bridge(plan)
        detail = f"Launch bridge ready at {bridge_dir} on localhost:{plan.get('runtime_bridge_port', self._runtime_bridge_port())}"
        self.write_note(f'Launch bridge installed: {bridge_dir}')
        self.set_connection_state('PREPARED', detail)
        messagebox.showinfo('Launch bridge ready', detail, parent=self)


    def open_game_dir(self):
        game_dir = Path(self.game_dir_var.get())
        if not game_dir.exists():
            messagebox.showerror('Game directory missing', str(game_dir), parent=self)
            return
        try:
            if sys.platform.startswith('win'):
                subprocess.Popen(['explorer', str(game_dir)])
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(game_dir)])
            else:
                subprocess.Popen(['xdg-open', str(game_dir)])
        except Exception as exc:
            messagebox.showerror('Open folder failed', str(exc), parent=self)

    def auto_detect_content_rpf(self):
        game_dir = Path(self.game_dir_var.get())
        candidates = [
            game_dir / 'content.rpf',
            game_dir / 'game' / 'content.rpf',
            game_dir / 'packs' / 'content.rpf',
            game_dir / 'archives' / 'content.rpf',
        ]
        found = None
        for candidate in candidates:
            if candidate.exists():
                found = candidate
                break
        if found is None and game_dir.exists():
            for candidate in game_dir.rglob('content.rpf'):
                found = candidate
                break
        self.content_rpf_var.set(str(found) if found else '')
        if found and (not self.game_dir_var.get().strip()):
            self.game_dir_var.set(str(found.parent))
        if found:
            self._persist_app_settings()
        self.write_note(f'Detected content.rpf: {found}' if found else 'content.rpf was not found under the current game directory. You can also choose it from anywhere.')

    def _content_rpf(self) -> Path:
        path = Path(self.content_rpf_var.get())
        if not path.exists():
            raise FileNotFoundError('content.rpf was not found. Set the game directory and detect it first.')
        return path


    def _target_rpf(self) -> Path:
        value = self.target_rpf_var.get().strip() or self.content_rpf_var.get().strip()
        path = Path(value)
        if not path.exists():
            raise FileNotFoundError('Target RPF was not found. Choose a target archive first.')
        return path

    def _target_patch_roots(self, source: Path) -> list[Path]:
        candidates = [
            APP_DIR / 'patches' / source.name,
            APP_DIR / 'patches' / source.stem,
            HOTSWAP_RUNTIME_DIR / source.name,
            HOTSWAP_RUNTIME_DIR / source.stem,
            APP_DIR / 'patches' / 'shared',
        ]
        if source.name.lower() == 'content.rpf':
            candidates.insert(0, PATCHES_DIR)
        seen = set()
        roots: list[Path] = []
        for candidate in candidates:
            key = str(candidate.resolve()) if candidate.exists() else str(candidate)
            if key in seen:
                continue
            seen.add(key)
            if candidate.exists() and candidate.is_dir():
                has_payload = any(p.is_file() and p.name.lower() not in {'readme.txt', 'readme_hot_swap.txt'} for p in candidate.rglob('*'))
                if has_payload:
                    roots.append(candidate)
        return roots


    def _ghost_keymap(self) -> dict[str, str]:
        return {
            'singleplayer': 'Shift+F1',
            'freemode': 'Shift+F2',
            'lan': 'Shift+F3',
            'private': 'Shift+F4',
            'public': 'Shift+F5',
            'open_menu': 'Shift+F6',
            'open_playerlist': 'Shift+F7',
        }

    def _insert_before_marker(self, text: str, marker: str, insertion: str) -> str:
        if not insertion.strip():
            return text
        if insertion.strip() in text:
            return text
        if marker in text:
            return text.replace(marker, insertion + marker, 1)
        return text + '\n' + insertion

    def _replace_once(self, text: str, old: str, new: str) -> str:
        return text.replace(old, new, 1) if old in text else text

    def _strip_legacy_ghost_overlays(self, text: str) -> str:
        text = re.sub(r'\n?\s*<UILabel id="CodeRedGhostTitle"[^\n]*></UILabel>', '', text)
        text = re.sub(r'\n?\s*<UILabel id="CodeRedGhostHint"[^\n]*></UILabel>', '', text)
        text = re.sub(r'\n?\s*<!-- CODE RED[^\n]*-->', '', text)
        return text

    def _ghost_menu_comment(self, mode_hint: str, scope: str) -> str:
        return f"    <!-- CODE RED {scope}: reusing existing game menus | {mode_hint} -->\n"

    def _ghost_menu_buttons(self) -> str:
        return """    <!-- CODE RED menu reuse buttons -->
    <UIButton text="CODE RED PLAYERLIST" target="SendEvent('codered.openplayerlist')"></UIButton>
    <UIButton text="CODE RED MENU" target="SendEvent('codered.openmenu')"></UIButton>
"""

    def _ghost_route_transitions(self) -> str:
        return """  <transition event="codered.mode.singleplayer">
    <action expr="NetMachine.TriggerSinglePlayerLoad()"></action>
    <action expr="SendEvent('net.modeSingle')"></action>
  </transition>
  <transition event="codered.mode.freemode">
    <action expr="NetMachine.SetGameWish('MULTI_FREE_ROAM')"></action>
    <action expr="goto(NetConf_StartGame)"></action>
  </transition>
  <transition event="codered.mode.lan">
    <action expr="goto(NetConf_PlayLAN)"></action>
  </transition>
  <transition event="codered.mode.private">
    <action expr="goto(NetConf_PlayPrivate)"></action>
  </transition>
  <transition event="codered.mode.public">
    <action expr="goto(NetConf_PlayPublic)"></action>
  </transition>
  <transition event="codered.openmenu">
    <action expr="StackPush(OL_NetworkingMenu)"></action>
    <action expr="Enter(OL_NetworkingMenu)"></action>
  </transition>
  <transition event="codered.openplayerlist">
    <action expr="SendEvent('playerlist')"></action>
    <action expr="SendEvent('codered.playerlist.focus')"></action>
  </transition>
"""

    def _ghost_playerlist_focus_routes(self) -> str:
        return """  <transition event="codered.playerlist.focus">
    <action expr="SendEvent('playerlist')"></action>
    <action expr="SendEvent('netui.success')"></action>
  </transition>
"""

    def _ghostify_content_text(self, entry_path: str, text: str) -> str:
        keymap = self._ghost_keymap()
        mode_hint = (
            f"{keymap['singleplayer']} STORY HOST  |  "
            f"{keymap['freemode']} FREEMODE  |  "
            f"{keymap['lan']} LAN  |  "
            f"{keymap['private']} PRIVATE  |  "
            f"{keymap['public']} PUBLIC  |  "
            f"{keymap['open_menu']} MENU  |  "
            f"{keymap['open_playerlist']} PLAYERLIST"
        )
        route_transitions = self._ghost_route_transitions()
        focus_routes = self._ghost_playerlist_focus_routes()
        playerlist_button_block = self._ghost_menu_buttons()
        text = self._strip_legacy_ghost_overlays(text)
        if entry_path == 'root/content/ui/net/main.sc.xml':
            text = self._replace_once(text, '<data name="text" expr="net_main_menu_title"></data>', '<data name="text" expr="\'CODE RED ONLINE\'"></data>')
            text = self._insert_before_marker(text, '</scxml>', self._ghost_menu_comment(mode_hint, 'main net scene'))
            return text
        if entry_path == 'root/content/ui/net/taskmachine.sc.xml':
            text = self._insert_before_marker(text, '  <ifdef expr="ULTIMATE_1">', route_transitions)
            text = self._insert_before_marker(text, '</scxml>', self._ghost_menu_comment(mode_hint, 'task machine routes'))
            return text
        if entry_path == 'root/content/ui/pausemenu/networking.sc.xml':
            insert = route_transitions + self._ghost_menu_comment(mode_hint, 'networking layer routes')
            text = self._insert_before_marker(text, '    <transition event="net.playingPublic">', insert)
            return text
        if entry_path == 'root/content/ui/pausemenu/lobby/0x2B5C38A8':
            insert = playerlist_button_block + self._ghost_menu_comment(mode_hint, 'lobby menu')
            if '    <UIButton desc="mp_fe_exit"' in text:
                text = text.replace('    <UIButton desc="mp_fe_exit"', insert + '    <UIButton desc="mp_fe_exit"', 1)
            else:
                text = self._insert_before_marker(text, '</UILayer>', insert)
            return text
        if entry_path == 'root/content/ui/net/hudsceneonline.sc.xml':
            insert = route_transitions + focus_routes + self._ghost_menu_comment(mode_hint, 'online HUD routing')
            text = self._insert_before_marker(text, '    <!--default online state when nothing is visible-->', insert)
            return text
        if entry_path == 'root/content/ui/hudscene.sc.xml':
            hud_insert = route_transitions + self._ghost_menu_comment(mode_hint, 'story HUD routing')
            text = self._insert_before_marker(text, '          <transition event="uinput.disconnect" target="PauseMenuScene"></transition>', hud_insert)
            return text
        if entry_path in {
            'root/content/ui/pausemenu/0x007B97C6/lanmenu.sc.xml',
            'root/content/ui/pausemenu/0x007B97C6/publicmenu.sc.xml',
            'root/content/ui/pausemenu/0x007B97C6/privatemenu.sc.xml',
        }:
            combined_insert = route_transitions + playerlist_button_block + self._ghost_menu_comment(mode_hint, 'network mode sub-menu')
            inserted = False
            for marker in ('    <UIButton desc="mp_fe_exit"', '    <ifdef expr="XENON">', '  </NetMenu>', '  </UIMenu>'):
                if marker in text:
                    text = text.replace(marker, combined_insert + marker, 1)
                    inserted = True
                    break
            if not inserted:
                text = self._insert_before_marker(text, '</NetMenu>' if '</NetMenu>' in text else '</UIMenu>', combined_insert)
            return text
        if entry_path == 'root/content/ui/pausemenu/0x007B97C6/offlinemenu.sc.xml':
            offline_insert = route_transitions + self._ghost_menu_comment(mode_hint, 'offline networking menu')
            text = self._insert_before_marker(text, '      <NetInvitesList id="OnlineInbox" movie="list" flashObject="menu" MaxHeight="8">', offline_insert)
            return text
        if entry_path == 'root/content/ui/pausemenu/lobby/netplayercontextmenu.sc.xml':
            context_insert = focus_routes + """  <transition event="codered.openplayerlist">
    <action expr="SendEvent('codered.playerlist.focus')"></action>
    <action expr="Exit(arg0)"></action>
    <action expr="Enter(arg1)"></action>
  </transition>
  <transition event="codered.openmenu">
    <action expr="Exit(arg0)"></action>
    <action expr="SendEvent('codered.openmenu')"></action>
  </transition>
"""
            text = self._insert_before_marker(text, '  <transition event="@UI.CANCEL*RELEASED">', context_insert)
            text = self._insert_before_marker(text, '</scxml>', self._ghost_menu_comment(mode_hint, 'player context menu'))
            return text
        if entry_path == 'root/flash/brplru/playerlist.wsf':
            return text.replace('playerlist', 'playerlist\nCODE RED PLAYERLIST READY', 1) if 'playerlist' in text else ('CODE RED PLAYERLIST READY\n' + text)
        if entry_path == 'root/content/ui/boot.sc.xml':
            boot_insert = """    <transition event="codered.mode.singleplayer">
      <action expr="SendEvent('codered.mode.singleplayer')"></action>
    </transition>
    <transition event="codered.mode.freemode">
      <action expr="SendEvent('codered.mode.freemode')"></action>
    </transition>
    <transition event="codered.mode.lan">
      <action expr="SendEvent('codered.mode.lan')"></action>
    </transition>
    <transition event="codered.mode.private">
      <action expr="SendEvent('codered.mode.private')"></action>
    </transition>
    <transition event="codered.mode.public">
      <action expr="SendEvent('codered.mode.public')"></action>
    </transition>
"""
            text = self._insert_before_marker(text, '    <transition event="net.StartOnline"     target="AddDelayedEvent(\'net.StartOnline\',2.0)"   ></transition>', boot_insert)
            text = self._insert_before_marker(text, '</scxml>', self._ghost_menu_comment(mode_hint, 'boot relay'))
            return text
        return text

    def _prepare_builtin_ghost_patches(self, source: Path) -> dict:
        runtime_root = HOTSWAP_RUNTIME_DIR / source.name
        if runtime_root.exists():
            shutil.rmtree(runtime_root)
        runtime_root.mkdir(parents=True, exist_ok=True)
        manifest = {
            'ts': datetime.now().isoformat(timespec='seconds'),
            'target': str(source),
            'target_name': source.name,
            'patch_root': str(runtime_root),
            'ghost_keymap': self._ghost_keymap(),
            'patched_entries': [],
        }
        if source.name.lower() != 'content.rpf':
            return manifest
        parsed = RUNTIME.parse_rpf6(source)
        if not parsed:
            raise RuntimeError(f'Ghost RPF authoring could not parse {source.name}')
        target_entries = [
            'root/content/ui/net/main.sc.xml',
            'root/content/ui/net/taskmachine.sc.xml',
            'root/content/ui/pausemenu/networking.sc.xml',
            'root/content/ui/pausemenu/lobby/0x2B5C38A8',
            'root/content/ui/net/hudsceneonline.sc.xml',
            'root/content/ui/hudscene.sc.xml',
            'root/content/ui/pausemenu/0x007B97C6/offlinemenu.sc.xml',
            'root/content/ui/pausemenu/lobby/netplayercontextmenu.sc.xml',
            'root/content/ui/pausemenu/0x007B97C6/lanmenu.sc.xml',
            'root/content/ui/pausemenu/0x007B97C6/publicmenu.sc.xml',
            'root/content/ui/pausemenu/0x007B97C6/privatemenu.sc.xml',
            'root/content/ui/boot.sc.xml',
            'root/flash/brplru/playerlist.wsf',
        ]
        for entry_path in target_entries:
            original = self._read_content_text(source, parsed, entry_path)
            if not original:
                continue
            updated = self._ghostify_content_text(entry_path, original)
            if not updated or updated == original:
                continue
            out_path = runtime_root / entry_path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(updated, encoding='utf-8')
            manifest['patched_entries'].append(entry_path)
        if manifest['patched_entries']:
            validation = self._validate_builtin_ghost_manifest(manifest)
            manifest['validation'] = validation.get('summary', {})
            self.write_note(
                f"Ghost RPF runtime patches prepared: {len(manifest['patched_entries'])} content entries | "
                f"menu reuse confidence={manifest['validation'].get('menu_reuse_confidence', 'unknown')}"
            )
        else:
            self.write_note('Ghost RPF runtime patches were requested, but no content entries were authored.')
        return manifest


    def _clear_readonly_flag(self, path: Path) -> None:
        try:
            if path.exists():
                os.chmod(path, 0o666)
        except Exception:
            pass

    def _is_access_denied_error(self, exc: BaseException) -> bool:
        if isinstance(exc, PermissionError):
            return True
        if isinstance(exc, OSError):
            winerror = getattr(exc, 'winerror', None)
            if winerror == 5:
                return True
        lowered = str(exc).lower()
        return (
            'access is denied' in lowered
            or 'permission denied' in lowered
            or 'being used by another process' in lowered
            or 'used by another process' in lowered
        )

    def _hotswap_lock_hint(self, target: Path) -> str:
        bridge_dir = None
        try:
            game_dir_raw = self.game_dir_var.get().strip()
            if game_dir_raw:
                bridge_dir = Path(game_dir_raw) / LAUNCH_BRIDGE_DIRNAME
        except Exception:
            bridge_dir = None
        lines = [
            f'Locked file: {target}',
            '',
            'Close the game and launcher helpers before swapping Ghost RPF.',
            'Most common lockers:',
            '- RDR.exe',
            '- PlayRDR.exe',
            '- RDRMessage.exe',
            '- python.exe / py.exe from an older Code RED runtime bridge',
            '',
            'Code RED will retry automatically, but if the lock persists:',
            '1) close the game completely',
            '2) close Rockstar/launcher helper windows',
            '3) end stray RDR/python processes in Task Manager',
            '4) run the companion as administrator',
            '5) try Activate Ghost RPF again before launching',
        ]
        if bridge_dir is not None:
            lines.extend([
                '',
                f'Expected bridge folder: {bridge_dir}',
                'If the previous launch is still alive, delete/restore only after the bridge shuts down.'
            ])
        return '\n'.join(lines)

    def _replace_file_with_retry(self, src: Path, dst: Path, action_label: str, retries: int = HOTSWAP_SWAP_RETRIES, delay: float = HOTSWAP_SWAP_DELAY) -> None:
        last_exc: BaseException | None = None
        tmp = dst.with_name(dst.name + '.codered.swap.tmp')
        for attempt in range(1, retries + 1):
            try:
                src.parent.mkdir(parents=True, exist_ok=True)
                dst.parent.mkdir(parents=True, exist_ok=True)
                self._clear_readonly_flag(src)
                self._clear_readonly_flag(dst)
                self._clear_readonly_flag(tmp)
                if tmp.exists():
                    tmp.unlink()
                shutil.copy2(src, tmp)
                self._clear_readonly_flag(dst)
                os.replace(tmp, dst)
                self._clear_readonly_flag(dst)
                return
            except Exception as exc:
                if tmp.exists():
                    try:
                        self._clear_readonly_flag(tmp)
                        tmp.unlink()
                    except Exception:
                        pass
                if not self._is_access_denied_error(exc):
                    raise
                last_exc = exc
                try:
                    self.hotswap_status_var.set(f'{action_label}: waiting for file release {attempt}/{retries} ({dst.name})')
                    self.update_idletasks()
                except Exception:
                    pass
                if attempt == 1:
                    try:
                        self._shutdown_runtime_bridge_service()
                    except Exception:
                        pass
                time.sleep(delay)
        raise PermissionError(f'{action_label} failed for {dst.name}.\n\n{self._hotswap_lock_hint(dst)}\n\nLast error: {last_exc}')
    def _build_hotswap_derivative(self, source: Path) -> dict:
        HOTSWAP_STAGING_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ghost_manifest = self._prepare_builtin_ghost_patches(source)
        roots = self._target_patch_roots(source)
        derivative_dir = HOTSWAP_STAGING_DIR / source.name
        derivative_dir.mkdir(parents=True, exist_ok=True)
        if not roots:
            out_path = derivative_dir / f'{source.stem}_hotswap_{stamp}{source.suffix}'
            shutil.copy2(source, out_path)
            result = {
                'source': str(source),
                'staged_copy': str(out_path),
                'patch_roots': [],
                'applied': 0,
                'blocked': 0,
                'relocated': 0,
                'identical': 0,
                'mode': 'clone_only',
                'created_at': datetime.now().isoformat(timespec='seconds'),
                'ghost_manifest': ghost_manifest,
            }
            HOTSWAP_MANIFEST_PATH.write_text(json.dumps(result, indent=2), encoding='utf-8')
            return result
        working_source = source
        applied = blocked = relocated = identical = 0
        reports = []
        for idx, root in enumerate(roots, start=1):
            out_path = derivative_dir / f'{source.stem}_hotswap_{stamp}_{idx}{source.suffix}'
            result = RUNTIME._codered_apply_patch_folder_to_archive_copy(working_source, root, out_path)
            working_source = out_path
            applied += int(result.get('applied', 0))
            blocked += int(result.get('blocked', 0))
            relocated += int(result.get('relocated', 0))
            identical += int(result.get('identical', 0))
            reports.append({
                'root': str(root),
                'report_path': str(result.get('report_path', '')),
                'applied': int(result.get('applied', 0)),
                'blocked': int(result.get('blocked', 0)),
                'relocated': int(result.get('relocated', 0)),
                'identical': int(result.get('identical', 0)),
                'unmatched': len(result.get('unmatched', [])),
            })
        manifest = {
            'source': str(source),
            'staged_copy': str(working_source),
            'patch_roots': [str(root) for root in roots],
            'applied': applied,
            'blocked': blocked,
            'relocated': relocated,
            'identical': identical,
            'mode': 'patched_copy',
            'created_at': datetime.now().isoformat(timespec='seconds'),
            'reports': reports,
            'ghost_manifest': ghost_manifest,
        }
        HOTSWAP_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        return manifest

    def build_hotswap_copy(self, show_message: bool = True):
        source = self._target_rpf()
        manifest = self._build_hotswap_derivative(source)
        summary = f"Ghost RPF ready: {Path(manifest['staged_copy']).name}"
        if manifest.get('patch_roots'):
            summary += f" | roots={len(manifest['patch_roots'])} applied={manifest.get('applied', 0)} blocked={manifest.get('blocked', 0)}"
        else:
            summary += ' | no patch roots found, cloned original only'
        self.write_note(summary)
        self.hotswap_status_var.set(summary)
        self._persist_app_settings()
        if show_message:
            messagebox.showinfo('Ghost RPF ready', f"{summary}\n\nSource:\n{manifest['source']}\n\nStaged copy:\n{manifest['staged_copy']}", parent=self)
        return manifest


    def activate_hotswap(self, show_message: bool = True):
        manifest = self.build_hotswap_copy(show_message=False)
        source = Path(manifest['source'])
        staged = Path(manifest['staged_copy'])
        backup_dir = BACKUPS_DIR / 'hotswap_originals'
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f'{source.stem}_original_{datetime.now().strftime("%Y%m%d_%H%M%S")}{source.suffix}'
        self.write_note(f'Ghost RPF preparing backup and swap for: {source}')
        self._replace_file_with_retry(source, backup_path, 'Ghost backup')
        self._replace_file_with_retry(staged, source, 'Ghost activation')
        manifest['active'] = True
        manifest['active_backup'] = str(backup_path)
        manifest['activated_at'] = datetime.now().isoformat(timespec='seconds')
        HOTSWAP_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        detail = f'Ghost RPF active: {source.name} <= {staged.name}'
        self.write_note(detail)
        self.hotswap_status_var.set(detail)
        self.set_connection_state('PREPARED', detail)
        if show_message:
            messagebox.showinfo('Ghost RPF active', f"{detail}\n\nBackup:\n{backup_path}", parent=self)
        return manifest


    def restore_hotswap(self, show_message: bool = True):
        if not HOTSWAP_MANIFEST_PATH.exists():
            if show_message:
                messagebox.showerror('No Ghost RPF manifest', 'Build and activate a Ghost RPF first.', parent=self)
            return None
        manifest = json.loads(HOTSWAP_MANIFEST_PATH.read_text(encoding='utf-8'))
        source = Path(manifest.get('source', ''))
        backup = Path(manifest.get('active_backup', ''))
        if not source.exists() or not backup.exists():
            raise FileNotFoundError('The HotSwap restore source or backup file is missing.')
        self.write_note(f'Ghost RPF restore requested for: {source}')
        self._replace_file_with_retry(backup, source, 'Ghost restore')
        manifest['active'] = False
        manifest['restored_at'] = datetime.now().isoformat(timespec='seconds')
        HOTSWAP_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        detail = f'Restored original RPF after Ghost RPF: {source.name}'
        self.write_note(detail)
        self.hotswap_status_var.set(detail)
        if show_message:
            messagebox.showinfo('Ghost RPF restored', f"{detail}\n\nBackup used:\n{backup}", parent=self)
        return manifest

    def _normalize_port(self) -> int:
        raw = self.host_port_var.get().strip() or '6677'
        port = int(raw)
        if not (1 <= port <= 65535):
            raise ValueError(f'Port is out of range: {port}')
        self.host_port_var.set(str(port))
        return port

    def _advertised_host(self) -> str:
        host = self.host_ip_var.get().strip() or self.lan_ip_var.get().strip() or '127.0.0.1'
        self.host_ip_var.set(host)
        return host

    def _bind_host(self) -> str:
        advertised = self._advertised_host()
        if advertised in {'127.0.0.1', 'localhost'}:
            return '0.0.0.0'
        return advertised

    def detect_lan_ip(self):
        ip = best_lan_ip()
        self.lan_ip_var.set(ip)
        if self.host_ip_var.get().strip() in {'', '127.0.0.1', 'localhost'}:
            self.host_ip_var.set(ip)
        self.write_note(f'Detected LAN IP: {ip}')
        self.set_connection_state('PREPARED', f'LAN IP ready: {ip}')

    def backup_content_rpf(self):
        source = self._content_rpf()
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        target = BACKUPS_DIR / f'content_backup_{stamp}.rpf'
        shutil.copy2(source, target)
        self.write_note(f'Backup created: {target}')
        messagebox.showinfo('Backup created', str(target), parent=self)

    def restore_latest_backup(self):
        source = self._content_rpf()
        backups = sorted(BACKUPS_DIR.glob('content_backup_*.rpf'))
        if not backups:
            messagebox.showerror('No backup found', 'Create a backup first.', parent=self)
            return
        latest = backups[-1]
        shutil.copy2(latest, source)
        self.write_note(f'Restored backup to content.rpf: {latest} -> {source}')
        messagebox.showinfo('Backup restored', str(latest), parent=self)

    def _apply_patch_root(self, patch_root: Path):
        source = self._content_rpf()
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_path = source.with_name(f'{source.stem}_patched_{stamp}{source.suffix}')
        result = RUNTIME._codered_apply_patch_folder_to_archive_copy(source, patch_root, out_path)
        self.write_note(f'Patch result: {json.dumps(result, indent=2)}')
        messagebox.showinfo('Patch complete', f'Patched archive copy created:\n{out_path}', parent=self)

    def apply_bundled_patches(self):
        self._apply_patch_root(PATCHES_DIR)

    def apply_external_patch_folder(self):
        chosen = filedialog.askdirectory(parent=self, title='Select External Patch Folder')
        if not chosen:
            return
        self._apply_patch_root(Path(chosen))

    def inject_custom_file(self):
        source_file = filedialog.askopenfilename(parent=self, title='Select Replacement Payload')
        if not source_file:
            return
        internal_path = simpledialog.askstring('Internal path', 'Enter the internal archive path for this replacement\nExample: root/content/ui/net/main.sc.xml', parent=self)
        if not internal_path:
            return
        target = PATCHES_DIR / Path(internal_path.replace('\\', '/'))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target)
        self.write_note(f'Injected custom file into bundled patch tree: {source_file} -> {target}')
        messagebox.showinfo('Injected into patch tree', str(target), parent=self)

    def _write_session_descriptor(self, mode: str):
        payload = self._session_payload(mode)
        out_path = CONFIG_DIR / ('session_host.json' if mode == 'host' else 'session_join.json')
        out_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        ACTIVE_SESSION_PATH.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        self.invite_var.set(encode_invite(payload))
        INVITE_PATH.write_text(self.invite_var.get(), encoding='utf-8')
        self.write_note(f'Session descriptor written: {out_path}')
        self.set_connection_state('PREPARED', f"{mode.title()} descriptor ready on {payload['host_ip']}:{payload['port']}")
        messagebox.showinfo('Session descriptor ready', str(out_path), parent=self)

    def create_host_descriptor(self):
        self._write_session_descriptor('host')

    def create_join_descriptor(self):
        self._write_session_descriptor('join')

    def copy_invite(self):
        payload = self._session_payload('host')
        invite = encode_invite(payload)
        self.invite_var.set(invite)
        INVITE_PATH.write_text(invite, encoding='utf-8')
        self.clipboard_clear()
        self.clipboard_append(invite)
        self.update_idletasks()
        self.write_note('Invite copied to clipboard and saved to config/last_invite.txt')
        self.set_connection_state('PREPARED', f"Invite ready for {payload['host_ip']}:{payload['port']}")

    def load_invite(self):
        supplied = self.invite_var.get().strip()
        if not supplied:
            supplied = simpledialog.askstring('Invite code', 'Paste invite code', parent=self) or ''
        if not supplied:
            return
        try:
            payload = decode_invite(supplied)
        except Exception as exc:
            messagebox.showerror('Invite decode failed', str(exc), parent=self)
            self.set_connection_state('FAILED', 'Invite code was invalid.')
            return
        self.session_name_var.set(payload.get('session_name', self.session_name_var.get()))
        self.host_ip_var.set(payload.get('host_ip', self.host_ip_var.get()))
        self.host_port_var.set(str(payload.get('port', self.host_port_var.get())))
        self.invite_var.set(supplied)
        INVITE_PATH.write_text(supplied, encoding='utf-8')
        self._save_recent_host(payload)
        self.write_note(f"Invite loaded for {self.host_ip_var.get()}:{self.host_port_var.get()}")
        self.set_connection_state('PREPARED', f"Invite loaded for {self.host_ip_var.get()}:{self.host_port_var.get()}")

    def _send_json_packet(self, payload: dict) -> dict:
        host = self._advertised_host()
        port = self._normalize_port()
        with socket.create_connection((host, port), timeout=2.0) as conn:
            conn.settimeout(2.0)
            conn.sendall((json.dumps(payload) + '\n').encode('utf-8'))
            data = conn.recv(8192).decode('utf-8', errors='replace').strip()
        if not data:
            return {}
        return json.loads(data.splitlines()[0])

    def _beacon_worker(self, bind_ip: str, port: int):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._beacon_socket = server
        try:
            server.bind((bind_ip, port))
            server.listen(8)
            server.settimeout(0.5)
            self._queue_ui(lambda: self.set_connection_state('HOSTING', f'Beacon listening on {self._advertised_host()}:{port}'))
            while not self._beacon_stop.is_set():
                try:
                    conn, addr = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                with conn:
                    text = ''
                    try:
                        text = conn.recv(8192).decode('utf-8', errors='replace').strip()
                    except OSError:
                        text = ''
                    packet = {}
                    if text:
                        try:
                            packet = json.loads(text.splitlines()[0])
                        except json.JSONDecodeError:
                            packet = {'kind': 'probe', 'raw': text}
                    kind = packet.get('kind', 'probe')
                    sender = packet.get('from', 'UnknownPlayer')
                    self._queue_ui(lambda s=sender, a=addr, p=packet: self._record_peer(s, a, p))
                    payload = {
                        'ok': True,
                        'kind': kind,
                        'session_name': self._host_meta.get('session_name', 'Code RED Freemode'),
                        'player_name': self._host_meta.get('player_name', 'PlayerHost'),
                        'world': self._host_meta.get('world', 'freemode'),
                        'boot_target': self._host_meta.get('boot_target', 'MULTI_FREE_ROAM'),
                        'ts': datetime.now().isoformat(timespec='seconds'),
                    }
                    if kind == 'chat':
                        chat_text = str(packet.get('text', '')).strip()
                        if chat_text:
                            self._host_append_event(f'{sender}: {chat_text}')
                            payload['chat_ack'] = True
                            payload['chat_index'] = self._chat_index
                    elif kind == 'voice_ping':
                        payload['voice_ack'] = True
                        self._host_append_event(f"[Voice Ready] {sender} ({packet.get('push_to_talk', 'V')})")
                    elif kind == 'trainer_push':
                        trainer = packet.get('trainer_profile', {}) or {}
                        self._host_meta['trainer_profile'] = dict(trainer)
                        self._queue_ui(lambda t=trainer: self._apply_remote_trainer(t))
                        self._host_append_event(f"[Trainer Sync] {sender} updated trainer state")
                        payload['trainer_ack'] = True
                    elif kind == 'poll_status':
                        last_chat_index = int(packet.get('last_chat_index', 0) or 0)
                        payload['poll_ack'] = True
                        payload['chat_events'] = [row for row in self._chat_history if int(row.get('i', 0)) > last_chat_index][-50:]
                        payload['roster'] = sorted(self._roster.keys())
                        payload['peer_count'] = len(self._roster)
                        payload['trainer_profile'] = dict(self._host_meta.get('trainer_profile', {}))
                    else:
                        payload['probe_ack'] = True
                    try:
                        conn.sendall((json.dumps(payload) + '\n').encode('utf-8'))
                    except OSError:
                        pass
        except Exception as exc:
            self._queue_ui(lambda e=str(exc): self.set_connection_state('FAILED', f'Host beacon failed: {e}'))
        finally:
            try:
                server.close()
            except Exception:
                pass
            self._beacon_socket = None
            if not self._beacon_stop.is_set():
                self._queue_ui(lambda: self.set_connection_state('STOPPED', 'Host beacon stopped.'))

    def _discovery_worker(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('0.0.0.0', DISCOVERY_PORT))
            sock.settimeout(0.5)
            self._discovery_socket = sock
            while not self._discovery_stop.is_set():
                try:
                    data, addr = sock.recvfrom(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break
                try:
                    packet = json.loads(data.decode('utf-8', errors='replace').strip() or '{}')
                except Exception:
                    packet = {}
                if packet.get('kind') != 'discover':
                    continue
                reply = {
                    'kind': 'discover_reply',
                    'session_name': self._host_meta.get('session_name', 'Code RED Freemode'),
                    'player_name': self._host_meta.get('player_name', 'PlayerHost'),
                    'host_ip': self._advertised_host(),
                    'port': self._normalize_port(),
                    'peer_count': len(self._roster),
                    'source': 'lan',
                    'world': self._host_meta.get('world', self.world_name_var.get().strip() or 'freemode'),
                }
                try:
                    sock.sendto(json.dumps(reply).encode('utf-8'), addr)
                except OSError:
                    pass
        finally:
            try:
                sock.close()
            except Exception:
                pass
            self._discovery_socket = None

    def start_host_beacon(self):
        if self._beacon_thread is not None and self._beacon_thread.is_alive():
            self.set_connection_state('HOSTING', f'Beacon already active on {self._advertised_host()}:{self._normalize_port()}')
            return
        port = self._normalize_port()
        bind_ip = self._bind_host()
        self._roster = {self.player_name_var.get().strip() or 'PlayerHost': {'addr': f'{self._advertised_host()}:{port}', 'last_seen': datetime.now().isoformat(timespec='seconds')}}
        self._chat_history = []
        self._chat_index = 0
        self._last_chat_index = 0
        self._update_roster()
        self._host_meta = {
            'session_name': self.session_name_var.get().strip() or 'Code RED Freemode',
            'player_name': self.player_name_var.get().strip() or 'PlayerHost',
            'world': self.world_name_var.get().strip() or 'freemode',
            'boot_target': self.boot_target_var.get().strip() or 'MULTI_FREE_ROAM',
            'trainer_profile': self.trainer_payload(),
        }
        self._host_append_event(f"[System] Host online: {self._host_meta['session_name']} on {self._advertised_host()}:{port}")
        self._beacon_stop.clear()
        self._discovery_stop.clear()
        self._beacon_thread = threading.Thread(target=self._beacon_worker, args=(bind_ip, port), daemon=True)
        self._beacon_thread.start()
        self._discovery_thread = threading.Thread(target=self._discovery_worker, daemon=True)
        self._discovery_thread.start()
        self.set_connection_state('CONNECTING', f'Starting host beacon on {self._advertised_host()}:{port} ...')
        self.write_note(f'Host beacon requested on {bind_ip}:{port}')
        self._save_recent_host(self._session_payload('host'))

    def _shutdown_host_beacon(self, update_state: bool = True, detail: str = 'Host beacon stopped by user.'):
        self._beacon_stop.set()
        self._discovery_stop.set()
        self._stop_poller()
        sock = self._beacon_socket
        self._beacon_socket = None
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
        dsock = self._discovery_socket
        self._discovery_socket = None
        if dsock is not None:
            try:
                dsock.close()
            except Exception:
                pass
        if update_state:
            self.set_connection_state('STOPPED', detail)
        self.write_note(detail)

    def stop_host_beacon(self):
        self._shutdown_host_beacon(update_state=True, detail='Host beacon stopped by user.')

    def discover_lan_sessions(self):
        self.discovery_status_var.set('Scanning LAN for sessions...')
        self.detect_lan_ip()
        def worker():
            results = []
            seen = set()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.bind(('', 0))
                sock.settimeout(0.35)
                payload = json.dumps({'kind': 'discover', 'from': self.player_name_var.get().strip() or 'Player'}).encode('utf-8')
                for target in [('255.255.255.255', DISCOVERY_PORT), ('127.0.0.1', DISCOVERY_PORT)]:
                    try:
                        sock.sendto(payload, target)
                    except OSError:
                        pass
                end_time = time.time() + 1.6
                while time.time() < end_time:
                    try:
                        data, addr = sock.recvfrom(4096)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    try:
                        item = json.loads(data.decode('utf-8', errors='replace').strip() or '{}')
                    except Exception:
                        continue
                    if item.get('kind') != 'discover_reply':
                        continue
                    key = (item.get('host_ip') or addr[0], int(item.get('port', 0) or 0))
                    if key in seen:
                        continue
                    seen.add(key)
                    item['host_ip'] = item.get('host_ip') or addr[0]
                    item['source'] = 'lan'
                    results.append(item)
            finally:
                sock.close()
            self._save_json_list(SESSION_CACHE_PATH, results)
            merged = results + self._load_json_list(RECENT_HOSTS_PATH)
            self._queue_ui(lambda r=merged, n=len(results): self._set_session_items(r, f'{n} LAN session(s) found.'))
        threading.Thread(target=worker, daemon=True).start()

    def use_selected_session(self):
        if self._session_listbox is None:
            return
        sel = self._session_listbox.curselection()
        if not sel:
            self.discovery_status_var.set('Select a session from the browser first.')
            return
        item = self._session_items[sel[0]]
        self.session_name_var.set(item.get('session_name', self.session_name_var.get()))
        self.host_ip_var.set(item.get('host_ip', self.host_ip_var.get()))
        self.host_port_var.set(str(item.get('port', self.host_port_var.get())))
        self._save_recent_host(item)
        self.discovery_status_var.set(f"Selected {item.get('session_name')} at {item.get('host_ip')}:{item.get('port')}")

    def probe_selected_session(self):
        self.use_selected_session()
        self.probe_connection()

    def clear_session_cache(self):
        for path in (RECENT_HOSTS_PATH, SESSION_CACHE_PATH):
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass
        self._set_session_items([], 'Session list cleared.')

    def _stop_poller(self):
        self._poll_stop.set()

    def _start_poller(self):
        if self._poll_thread is not None and self._poll_thread.is_alive():
            return
        self._poll_stop.clear()
        self._poll_thread = threading.Thread(target=self._poll_worker, daemon=True)
        self._poll_thread.start()

    def _poll_worker(self):
        sender = self.player_name_var.get().strip() or 'Player'
        host = self._advertised_host()
        port = self._normalize_port()
        while not self._poll_stop.is_set():
            try:
                resp = self._send_json_packet({'kind': 'poll_status', 'from': sender, 'last_chat_index': self._last_chat_index})
                events = resp.get('chat_events', []) or []
                for item in events:
                    idx = int(item.get('i', 0))
                    line = str(item.get('line', '')).strip()
                    if idx > self._last_chat_index and line:
                        self._last_chat_index = idx
                        self._queue_ui(lambda l=line: self._add_chat_line(l))
                roster = resp.get('roster', []) or []
                self._queue_ui(lambda r=roster: self.roster_var.set(', '.join(r[:6]) + (' ...' if len(r) > 6 else '') if r else 'Host only'))
                self._queue_ui(lambda c=str(resp.get('peer_count', len(roster))): self.peer_count_var.set(c))
                self._queue_ui(lambda: self.set_connection_state('CONNECTED', f'Live session sync active with {host}:{port}'))
            except Exception as exc:
                if self.auto_reconnect_var.get() and not self._poll_stop.is_set():
                    self._queue_ui(lambda e=str(exc): self.set_connection_state('CONNECTING', f'Retrying session sync ({e})'))
                    time.sleep(1.5)
                    continue
                self._queue_ui(lambda e=str(exc): self.set_connection_state('FAILED', f'Session sync stopped ({e})'))
                break
            time.sleep(1.2)

    def probe_connection(self):
        host = self._advertised_host()
        port = self._normalize_port()
        self.set_connection_state('CONNECTING', f'Probing {host}:{port} ...')
        def worker():
            try:
                resp = self._send_json_packet({'kind': 'probe', 'from': self.player_name_var.get().strip() or 'Player'})
                detail = f"Connected to {resp.get('session_name', 'Unknown Session')} / host {resp.get('player_name', 'Unknown Host')} at {host}:{port}"
                self._queue_ui(lambda: self.set_connection_state('CONNECTED', detail))
                self._queue_ui(lambda: self.last_peer_var.set(f'{host}:{port}'))
                self._queue_ui(lambda r=resp: self._save_recent_host(r))
                self._start_poller()
            except Exception as exc:
                self._queue_ui(lambda e=str(exc): self.set_connection_state('FAILED', f'No response from {host}:{port} ({e})'))
        threading.Thread(target=worker, daemon=True).start()
        self.write_note(f'Connection probe started: {host}:{port}')

    def send_chat_message(self):
        text = self.chat_input_var.get().strip()
        if not text:
            return
        sender = self.player_name_var.get().strip() or 'Player'
        self.chat_input_var.set('')
        if self._beacon_thread is not None and self._beacon_thread.is_alive() and not self._beacon_stop.is_set():
            self._host_append_event(f'{sender}: {text}')
            self.set_connection_state('CONNECTED', 'Chat posted to hosted session.')
            return
        def worker():
            try:
                resp = self._send_json_packet({'kind': 'chat', 'from': sender, 'text': text})
                self._queue_ui(lambda: self.set_connection_state('CONNECTED', f"Chat delivered to {resp.get('player_name', 'host')}."))
                self._start_poller()
            except Exception as exc:
                self._queue_ui(lambda e=str(exc): self.set_connection_state('FAILED', f'Chat send failed ({e})'))
        threading.Thread(target=worker, daemon=True).start()

    def send_voice_ping(self):
        sender = self.player_name_var.get().strip() or 'Player'
        payload = {
            'kind': 'voice_ping',
            'from': sender,
            'voice_enabled': bool(self.voice_enabled_var.get()),
            'voice_muted': bool(self.voice_muted_var.get()),
            'push_to_talk': self.voice_ptt_var.get().strip() or 'V',
            'device': self.voice_device_var.get().strip() or 'Default Microphone',
        }
        if self._beacon_thread is not None and self._beacon_thread.is_alive() and not self._beacon_stop.is_set():
            self._host_append_event(f"[Voice Ready] {sender} ({payload['push_to_talk']})")
            self.set_connection_state('CONNECTED', 'Voice-ready state stored on host.')
            return
        def worker():
            try:
                self._send_json_packet(payload)
                self._queue_ui(lambda: self.set_connection_state('CONNECTED', 'Voice-ready ping acknowledged by host.'))
                self._queue_ui(lambda: self.write_note(f'Voice-ready ping sent for {sender}.'))
                self._start_poller()
            except Exception as exc:
                self._queue_ui(lambda e=str(exc): self.set_connection_state('FAILED', f'Voice ping failed ({e})'))
        threading.Thread(target=worker, daemon=True).start()

    def _apply_remote_trainer(self, trainer: dict):
        self._set_trainer_from_payload(trainer)

    def send_trainer_sync(self):
        trainer = self.trainer_payload()
        self.save_trainer_profile()
        self.write_trainer_bridge_state(show_message=False)
        if self._beacon_thread is not None and self._beacon_thread.is_alive() and not self._beacon_stop.is_set():
            self._host_meta['trainer_profile'] = dict(trainer)
            self._host_append_event('[Trainer Sync] Host updated trainer state')
            self.set_connection_state('CONNECTED', 'Trainer state stored on host.')
            return
        def worker():
            try:
                self._send_json_packet({'kind': 'trainer_push', 'from': self.player_name_var.get().strip() or 'Player', 'trainer_profile': trainer})
                self._queue_ui(lambda: self.set_connection_state('CONNECTED', 'Trainer sync acknowledged by host.'))
                self._start_poller()
            except Exception as exc:
                self._queue_ui(lambda e=str(exc): self.set_connection_state('FAILED', f'Trainer sync failed ({e})'))
        threading.Thread(target=worker, daemon=True).start()

    def clear_chat(self):
        if self._chat_text is not None:
            self._chat_text.delete('1.0', 'end')
        if CHAT_LOG_PATH.exists():
            CHAT_LOG_PATH.unlink()
        self.write_note('Chat log cleared.')

    def _bridge_dir_from_game_dir(self) -> Path | None:
        raw = self.game_dir_var.get().strip()
        if not raw:
            return None
        return Path(raw) / LAUNCH_BRIDGE_DIRNAME

    def _playerlist_bridge_dir_from_game_dir(self) -> Path | None:
        raw = self.game_dir_var.get().strip()
        if not raw:
            return None
        return Path(raw) / PLAYERLIST_BRIDGE_DIRNAME

    def _read_json_path(self, path: Path) -> dict:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding='utf-8'))
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
        return {}

    def _write_json_path(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding='utf-8')

    def _ack_playerlist_bridge_action(self, action: str, payload: dict, detail: str) -> None:
        playerlist_dir = self._playerlist_bridge_dir_from_game_dir()
        if playerlist_dir is None:
            return
        runtime_state_path = playerlist_dir / PLAYERLIST_BRIDGE_RUNTIME
        runtime_state = self._read_json_path(runtime_state_path)
        runtime_state.update({
            'ts': datetime.now().isoformat(timespec='seconds'),
            'status': 'acknowledged',
            'last_action': action,
            'last_hotkey': str(payload.get('hotkey') or ''),
            'last_source': str(payload.get('source') or 'playerlist_bridge'),
            'menu_state': 'playerlist_requested' if action == 'open_playerlist' else ('menu_requested' if action == 'open_menu' else 'route_requested'),
            'playerlist_visible': bool(action == 'open_playerlist'),
            'ack_detail': detail,
            'mode_key': self._mode_preset_key(),
            'mode_label': self._mode_preset_payload().get('label', ''),
        })
        self._write_json_path(runtime_state_path, runtime_state)
        bridge_dir = self._bridge_dir_from_game_dir()
        if bridge_dir is not None:
            self._write_json_path(bridge_dir / LAUNCH_BRIDGE_STATUS, {
                'ts': datetime.now().isoformat(timespec='seconds'),
                'status': 'playerlist_acknowledged',
                'action': action,
                'hotkey': str(payload.get('hotkey') or ''),
                'detail': detail,
                'source': str(payload.get('source') or 'playerlist_bridge'),
            })
            self._write_json_path(bridge_dir / LAUNCH_BRIDGE_ACTIVATION_REQUEST, {
                'ts': datetime.now().isoformat(timespec='seconds'),
                'requested_by': str(payload.get('source') or 'playerlist_bridge'),
                'action': action,
                'hotkey': str(payload.get('hotkey') or ''),
                'note': detail,
            })

    def _process_playerlist_bridge_command(self) -> None:
        bridge_dir = self._bridge_dir_from_game_dir()
        if bridge_dir is None:
            return
        command_path = bridge_dir / PLAYERLIST_BRIDGE_COMMAND
        if not command_path.exists():
            return
        payload = self._read_json_path(command_path)
        if not payload:
            return
        fingerprint = json.dumps(payload, sort_keys=True)
        if fingerprint == self._last_playerlist_command_fingerprint:
            try:
                command_path.unlink()
            except Exception:
                pass
            return
        action = str(payload.get('action') or '').strip().lower()
        if not action:
            return
        detail = ''
        if action in {'singleplayer', 'freemode', 'lan', 'private', 'public'}:
            activation = self.switch_active_mode(action, show_message=False)
            detail = f"Playerlist bridge requested {activation.get('mode_label', action)}"
        elif action == 'open_menu':
            detail = 'Playerlist bridge requested CODE RED menu focus.'
            self.playerlist_status_var.set(detail)
            self.set_connection_state('PREPARED', detail)
            self.write_note(detail)
        elif action == 'open_playerlist':
            detail = 'Playerlist bridge requested playerlist focus.'
            self.playerlist_status_var.set(detail)
            self.set_connection_state('PREPARED', detail)
            self.write_note(detail)
        else:
            detail = f'Playerlist bridge sent unknown action: {action}'
            self.write_note(detail)
        self._last_playerlist_command_fingerprint = fingerprint
        self._last_playerlist_command_detail = detail
        self._ack_playerlist_bridge_action(action, payload, detail)
        try:
            command_path.unlink()
        except Exception:
            pass

    def refresh_connection_indicator(self):
        if self._beacon_thread is not None and self._beacon_thread.is_alive() and not self._beacon_stop.is_set():
            if self.connection_state_var.get() not in {'CONNECTED', 'CONNECTING'}:
                self.set_connection_state('HOSTING', f'Beacon listening on {self._advertised_host()}:{self._normalize_port()}')
        elif self.connection_state_var.get() == 'HOSTING':
            self.set_connection_state('STOPPED', 'Host beacon is no longer running.')
        try:
            self._process_playerlist_bridge_command()
        except Exception as exc:
            log_line(f'Playerlist bridge command processing failed: {exc}')
        self.after(1500, self.refresh_connection_indicator)

    def launch_game(self):
        preflight = self._run_launch_preflight()
        root_report = preflight.get('root_report', {})
        if not self._confirm_launch_risks(root_report):
            self.set_connection_state('STOPPED', 'Launch cancelled after compatibility audit.')
            return
        hook_result = self._auto_manage_hooks_for_launch(Path(self.game_dir_var.get().strip()), root_report)
        if hook_result.get('disabled'):
            self.write_note('Conflicting hook files were parked automatically for this launch lane.')
        mode_key = self._mode_preset_key()
        effective_mode = 'host' if mode_key == 'singleplayer' or self.connection_state_var.get() in {'HOSTING', 'CONNECTED'} else 'join'
        payload = self._session_payload(effective_mode)
        save_report = self.check_save_state(show_message=False)
        if mode_key == 'singleplayer':
            if save_report.get('found_count', 0) > 0:
                prompt = (
                    f"Detected {save_report.get('found_count', 0)} likely save/profile file(s).\n\n"
                    f"Primary candidate:\n{save_report.get('primary_candidate', '')}\n\n"
                    "Continue and host the current session from the active single-player route?"
                )
                proceed = messagebox.askyesno('Single Player Host', prompt, parent=self)
                if not proceed:
                    self.set_connection_state('STOPPED', 'Launch cancelled before Single Player Host handoff.')
                    return
                payload['save_launch_decision'] = 'use_detected_save'
            else:
                prompt = 'No likely save/profile files were detected.\n\nContinue anyway and let the game prompt/fallback if needed?'
                proceed = messagebox.askyesno('Single Player Host', prompt, parent=self)
                if not proceed:
                    self.set_connection_state('STOPPED', 'Launch cancelled because no save/profile was approved for Single Player Host.')
                    return
                payload['save_launch_decision'] = 'continue_without_detected_save'
            if not (self._beacon_thread is not None and self._beacon_thread.is_alive()):
                self.start_host_beacon()
                self.write_note('Single Player Host auto-started the host beacon for the current session.')
        ACTIVE_SESSION_PATH.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        plan_path = self.preview_launch_plan(show_message=False)
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        plan['save_scan'] = {
            'found_count': save_report.get('found_count', 0),
            'primary_candidate': save_report.get('primary_candidate', ''),
            'status': save_report.get('status', ''),
        }
        if payload.get('save_launch_decision'):
            plan['save_launch_decision'] = payload['save_launch_decision']
        plan_path.write_text(json.dumps(plan, indent=2), encoding='utf-8')
        bridge_dir = self._write_runtime_bridge(plan)
        probe, started = self._start_runtime_bridge_service(bridge_dir)
        hotswap_manifest = None
        if self.auto_hotswap_var.get():
            try:
                hotswap_manifest = self.activate_hotswap(show_message=False)
                plan['hotswap'] = hotswap_manifest
                plan_path.write_text(json.dumps(plan, indent=2), encoding='utf-8')
            except Exception as exc:
                messagebox.showerror('Ghost RPF swap failed', str(exc), parent=self)
                self.set_connection_state('FAILED', f'Ghost swap failed: {exc}')
                return
        exe = self._resolve_game_exe()
        if exe is None:
            messagebox.showinfo('Launch pending', f'No executable was found automatically. The bridge files are ready at:\n{bridge_dir}', parent=self)
            return
        env = os.environ.copy()
        env['CODERED_BRIDGE_DIR'] = str(bridge_dir)
        env['CODERED_ACTIVE_SESSION'] = str(bridge_dir / 'active_session.json')
        env['CODERED_LAUNCH_PLAN'] = str(bridge_dir / 'launch_plan.json')
        env['CODERED_TARGET_RPF'] = str(self._target_rpf())
        if hotswap_manifest:
            env['CODERED_HOTSWAP_ACTIVE'] = '1'
            env['CODERED_HOTSWAP_SOURCE'] = str(hotswap_manifest.get('source', ''))
            env['CODERED_HOTSWAP_STAGED'] = str(hotswap_manifest.get('staged_copy', ''))
            env['CODERED_HOTSWAP_BACKUP'] = str(hotswap_manifest.get('active_backup', ''))
        env['CODERED_BRIDGE_PORT'] = str(payload.get('runtime_bridge_port', self._runtime_bridge_port()))
        env['CODERED_WORLD'] = str(payload.get('world', 'freemode'))
        env['CODERED_BOOT_TARGET'] = str(payload.get('boot_target', 'MULTI_FREE_ROAM'))
        env['CODERED_SESSION_NAME'] = str(payload.get('session_name', 'Code RED Freemode'))
        env['CODERED_SESSION_HOST'] = str(payload.get('host_ip', best_lan_ip()))
        env['CODERED_SESSION_PORT'] = str(payload.get('port', self._normalize_port()))
        try:
            proc = subprocess.Popen([str(exe)], cwd=str(exe.parent), env=env)
            game_process_path = bridge_dir / LAUNCH_BRIDGE_GAME_PROCESS
            game_process_path.write_text(json.dumps({
                'pid': proc.pid,
                'exe': str(exe),
                'launched_at': datetime.now().isoformat(timespec='seconds'),
                'runtime_bridge_port': payload.get('runtime_bridge_port', self._runtime_bridge_port()),
            }, indent=2), encoding='utf-8')
            self.write_note(f'Launched game candidate: {exe}')
            self.write_note('Launch mode => internal direct executable with preflight-installed Red Bridge pack')
            self.write_note(f'Launch bridge folder => {bridge_dir}')
            self.write_note(f"Requested world target => {payload['world']} / {payload['boot_target']}")
            if started:
                self.write_note(f"Runtime bridge service started on localhost:{payload.get('runtime_bridge_port', self._runtime_bridge_port())}")
            elif probe:
                self.write_note(f"Runtime bridge service reused on localhost:{probe.get('bridge_port', payload.get('runtime_bridge_port', self._runtime_bridge_port()))}")
            self.set_connection_state('CONNECTING', f"Launch bridge executed for {exe.name} via localhost:{payload.get('runtime_bridge_port', self._runtime_bridge_port())}")
        except Exception as exc:
            messagebox.showerror('Launch failed', str(exc), parent=self)


    def on_close(self):
        try:
            self.save_profile()
            self.save_voice_profile()
            self.save_trainer_profile()
            self._stop_poller()
            self.stop_host_beacon()
            self._shutdown_runtime_bridge_service()
            if self.restore_hotswap_on_exit_var.get() and HOTSWAP_MANIFEST_PATH.exists():
                try:
                    manifest = json.loads(HOTSWAP_MANIFEST_PATH.read_text(encoding='utf-8'))
                    if manifest.get('active'):
                        self.restore_hotswap(show_message=False)
                except Exception as exc:
                    log_line(f'HotSwap restore on exit failed: {exc}')
            if self.restore_managed_hooks_on_exit_var.get():
                try:
                    self._restore_managed_hooks(show_message=False)
                except Exception as exc:
                    log_line(f'Hook restore on exit failed: {exc}')
        except Exception:
            pass
        self.destroy()


if __name__ == '__main__':
    app = CompanionApp()
    app.mainloop()
