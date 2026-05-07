from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from .paths import CodeRedPaths


@dataclass(frozen=True)
class AppLane:
    id: str
    title: str
    category: str
    description: str
    command: tuple[str, ...]
    required_paths: tuple[str, ...] = ()
    optional_paths: tuple[str, ...] = ()
    proof_paths: tuple[str, ...] = ()
    replaces_external: tuple[str, ...] = ()
    notes: str = ""


@dataclass
class LaneStatus:
    id: str
    title: str
    category: str
    state: str
    ready_required: int
    total_required: int
    ready_optional: int
    total_optional: int
    command: list[str]
    missing_required: list[str] = field(default_factory=list)
    present_required: list[str] = field(default_factory=list)
    present_optional: list[str] = field(default_factory=list)
    present_proof: list[str] = field(default_factory=list)
    replaces_external: list[str] = field(default_factory=list)
    description: str = ""
    notes: str = ""


LANES: tuple[AppLane, ...] = (
    AppLane(
        id="main_workbench",
        title="Code RED Workbench",
        category="Core",
        description="Canonical one-app host path. Starts at repo root by default.",
        command=("py", "-3", "main.py"),
        required_paths=("main.py", "python_workbench.py", "Code_RED.bat"),
        proof_paths=("logs/CodeRED_Main_Launcher_Unification_Pass_2026-05-03.md",),
    ),
    AppLane(
        id="repo_doctor",
        title="Repo Doctor",
        category="Core",
        description="Checks active folders, launchers, generated clutter, and obvious repo drift.",
        command=("py", "-3", "tools/codered_repo_doctor.py"),
        required_paths=("tools/codered_repo_doctor.py", "Run_CodeRED_Repo_Doctor.bat"),
    ),
    AppLane(
        id="regression_guard",
        title="Regression Guard",
        category="Core",
        description="Compares the current package against a checkpoint zip/folder, flags unexpected removals, and prevents obsolete salvaged files from returning.",
        command=("py", "-3", "tools/codered_regression_guard.py"),
        required_paths=("tools/codered_regression_guard.py", "main.py", "python_workbench.py"),
        optional_paths=("Code_RED.zip", "imports/Code_RED.zip", "logs/CodeRED_Regression_Guard_Report.md", "data/codered/regression_guard_manifest.csv"),
        proof_paths=("logs/CodeRED_Regression_Guard_Report.json", "logs/CodeRED_Regression_Guard_Report.md"),
        replaces_external=("manual checkpoint zip comparison", "manual obsolete-file cleanup", "manual source-folder decode spot checks"),
        notes="Use this after applying checkpoint zips. run_workbench.py is treated as intentionally obsolete once main.py has absorbed its useful behavior. Put an older Code_RED.zip in the root or imports/ to diff against it.",
    ),
    AppLane(
        id="build_assistant",
        title="Build Assistant",
        category="Build",
        description="Guided ASI/build/install assistant for Code RED ScriptHook lanes.",
        command=("py", "-3", "tools/codered_build_assistant.py", "gui"),
        required_paths=("tools/codered_build_assistant.py", "Run_CodeRED_Build_Assistant.bat"),
    ),
    AppLane(
        id="ai_trainer_menu",
        title="AI Trainer / ScriptHookRDR Menu",
        category="AI Trainer",
        description="Builds/validates the AI Menu, actor enum map, rosters, and behavior actions.",
        command=("py", "-3", "tools/codered_ai_trainer_validation.py"),
        required_paths=(
            "Run_CodeRED_AI_Menu_Setup.bat",
            "tools/codered_actor_enum_tool.py",
            "tools/codered_ai_trainer_validation.py",
            "data/codered/npc_roster.txt",
            "data/codered/actor_enum_map.csv",
            "data/codered/ai_behavior_actions.csv",
            "related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.cpp",
            "related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.ini",
        ),
        proof_paths=(
            "logs/CodeRED_AI_Trainer_Validation_Report.json",
            "logs/CodeRED_AI_Trainer_Validation_Report.md",
            "logs/CodeRED_AI_Menu_Behavior_Faction_Pass_2026-05-02.md",
        ),
        replaces_external=("standalone trainer menu setup", "manual actor enum sanity checks"),
        notes="Run this validation before building/installing the AI Menu ASI. It proves enum, roster, action, INI, and native-hook readiness without touching the game.",
    ),
    AppLane(
        id="trainer_controller",
        title="Trainer AI Controller",
        category="AI Trainer",
        description="Writes trainer-spawned companion state/action plans for follow, guard, attack, regroup, mount, and dismiss.",
        command=("py", "-3", "tools/codered_trainer_ai_controller_v1.py", "status"),
        required_paths=("tools/codered_trainer_ai_controller_v1.py", "tools/codered_npc_roster.py"),
        optional_paths=("scratch/codered_trainer_ai_state.json", "scratch/codered_trainer_ai_action_plan.json"),
    ),
    AppLane(
        id="native_probe",
        title="Native Database / Bridge Prep",
        category="Natives",
        description="Builds the local native database from bundled headers and source scans, then writes selected bridge-prep proof stubs.",
        command=("py", "-3", "tools/codered_native_bridge_generation.py"),
        required_paths=(
            "tools/codered_native_database.py",
            "tools/codered_native_bridge_generation.py",
            "related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1/include/RDR/natives32.h",
            "data/ScriptHookRDR/sdk/inc/natives.h",
        ),
        optional_paths=(
            "tools/codered_dualgun_native_probe.py",
            "tools/codered_dualgun_plan_builder.py",
            "related_apps/Code_RED_ScriptHookRDR_DualGunLab/CodeRED_DualGunLab.cpp",
            "data/natives.json",
            "data/codered/native_database.csv",
            "data/codered/native_bridge_prep_stubs.cpp",
            "data/codered/native_bridge_manifest.json",
            "data/codered/native_bridge_manifest.csv",
            "data/codered/native_bridge_selected_wrappers.cpp",
            "data/codered/native_bridge_compile_probe.cpp",
        ),
        proof_paths=(
            "logs/CodeRED_Native_Database_Report.json",
            "logs/CodeRED_Native_Database_Report.md",
            "logs/CodeRED_Native_Bridge_Generation_Report.json",
            "logs/CodeRED_Native_Bridge_Generation_Report.md",
        ),
        replaces_external=("manual native hash searches", "Magic/Codex native lookup passes"),
        notes="This lane imports/categorizes natives and generates selected bridge wrappers from SDK hashes. It still does not blindly wire every discovered native into the ASI; compile and in-game proof remain one profile at a time.",
    ),
    AppLane(
        id="ai_menu_bridge_integration",
        title="AI Menu Bridge Integration Prep",
        category="AI Trainer",
        description="Generates a safe AI Menu bridge-candidate source using selected native wrappers, plus manifest, diff, and Windows build helper.",
        command=("py", "-3", "tools/codered_ai_menu_bridge_integration.py"),
        required_paths=(
            "tools/codered_ai_menu_bridge_integration.py",
            "related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.cpp",
            "data/codered/native_bridge_selected_wrappers.cpp",
            "data/codered/native_bridge_manifest.json",
        ),
        optional_paths=(
            "related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.bridge_candidate.cpp",
            "related_apps/Code_RED_ScriptHookRDR_AI_Menu/build_bridge_candidate.bat",
            "logs/CodeRED_AI_Menu_Bridge_Integration_Candidate.diff",
        ),
        proof_paths=(
            "logs/CodeRED_AI_Menu_Bridge_Integration_Report.json",
            "logs/CodeRED_AI_Menu_Bridge_Integration_Report.md",
            "logs/CodeRED_AI_Menu_Bridge_Integration_Lane_Pass_2026-05-03.md",
        ),
        replaces_external=("manual AI Menu native-wrapper copy/paste", "manual selected-native bridge prep"),
        notes="This lane creates a reviewable bridge candidate and Windows build helper. It does not overwrite the live AI Menu source and does not install an ASI.",
    ),
    AppLane(
        id="script_compile_lab",
        title="Script Compile Lab",
        category="Scripts",
        description="Validates the active SC-CL source compile lane, vehicle menu probe source, native symbols, constants, and Windows build-kit staging.",
        command=("cmd", "/c", "script_compiling\\sccl\\compile_vehicle_menu_probe_windows.bat"),
        required_paths=(
            "script_compiling/sccl/README.md",
            "script_compiling/sccl/compile_vehicle_menu_probe_windows.bat",
            "script_compiling/sccl/stage_sccl_runtime_windows.ps1",
            "script_compiling/sccl/promote_real_sccl_headers_windows.ps1",
            "script_compiling/sccl/projects/vehicle_menu_probe/src/main.c",
            "script_compiling/sccl/projects/vehicle_menu_probe/include/RDR/natives32.h",
            "script_compiling/sccl/projects/vehicle_menu_probe/include/RDR/consts32.h",
        ),
        optional_paths=(
            "related_apps/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1",
            "logs/CodeRED_Script_Compile_Windows_Build_Plan.txt",
        ),
        proof_paths=(
            "logs/CodeRED_Script_Compile_Validation_Report.json",
            "logs/CodeRED_Script_Compile_Validation_Report.md",
            "logs/CodeRED_Script_Compile_Lane_Pass_2026-05-03.md",
        ),
        replaces_external=("SC-CL manual detection", "Magic RDR script compile helpers", "manual vehicle-menu probe validation"),
        notes="This proves the bundled compile lab and sample source are coherent. Full existing-binary WSC/XSC/SCO roundtrip remains proof-gated until a Windows SC-CL compile output is verified.",
    ),
    AppLane(
        id="script_workshop_decode",
        title="Script Workshop Decode / Editor Bridge",
        category="Scripts",
        description="Merges Script Lab/Script Workshop full-file decode, editable-source manifests, binary script string mining, and capability proof into the Code RED app.",
        command=("py", "-3", "tools/codered_script_workshop_decode.py"),
        required_paths=(
            "tools/codered_script_workshop_decode.py",
            "script_compiling/sccl/projects/vehicle_menu_probe/src/main.c",
            "script_compiling/sccl/projects/vehicle_menu_probe/include/RDR/natives32.h",
        ),
        optional_paths=(
            "docs/beat_crime_holdup.wsc",
            "research/menu resources",
            "related_apps/CodeRED_Tuner/Mods/Game - Train Spawns Cars",
            "data/codered/script_workshop_decode_manifest.csv",
            "data/codered/script_workshop_capabilities.json",
        ),
        proof_paths=(
            "logs/CodeRED_Script_Workshop_Decode_Report.json",
            "logs/CodeRED_Script_Workshop_Decode_Report.md",
            "logs/CodeRED_Script_Workshop_Decode_Lane_Pass_2026-05-03.md",
        ),
        replaces_external=("separate Script Lab preview workflow", "separate Script Workshop binary-string scan", "manual source/editability manifesting"),
        notes="This lane proves full source decode, loose compiled-script full reads, token/string mining, and an editable/read-only manifest. Existing binary script roundtrip and semantic bytecode editing remain proof-gated.",
    ),
    AppLane(
        id="script_workshop_compile_prep",
        title="Script Workshop Compile / Edit Prep",
        category="Scripts",
        description="Creates safe edit copies, source compile candidates, native dependency maps, and a Windows compile-proof workspace from the decoded Script Workshop manifest.",
        command=("py", "-3", "tools/codered_script_workshop_compile_prep.py"),
        required_paths=(
            "tools/codered_script_workshop_compile_prep.py",
            "data/codered/script_workshop_decode_manifest.json",
            "data/codered/native_database.json",
            "data/codered/native_bridge_manifest.json",
        ),
        optional_paths=(
            "scratch/script_workshop_compile",
            "scratch/script_workshop_compile/SCRIPT_WORKSHOP_COMPILE_PLAN.md",
            "scratch/script_workshop_compile/run_script_workshop_compile_probe.bat",
            "data/codered/script_workshop_compile_candidates.csv",
            "data/codered/script_workshop_compile_capabilities.json",
        ),
        proof_paths=(
            "logs/CodeRED_Script_Workshop_Compile_Prep_Report.json",
            "logs/CodeRED_Script_Workshop_Compile_Prep_Report.md",
            "logs/CodeRED_Script_Workshop_Compile_Edit_Prep_Lane_Pass_2026-05-03.md",
        ),
        replaces_external=("manual Script Workshop edit staging", "manual SC-CL source workspace setup", "manual native dependency preflight"),
        notes="This lane creates safe edit copies and compile-candidate mirrors only. Existing compiled binaries remain read-only until Windows compile and roundtrip proof pass.",
    ),
    AppLane(
        id="script_pipeline",
        title="Script Pipeline / Import-Recompile Queue",
        category="Scripts",
        description="Builds the full scripting workflow: scan, read, open, edit, export decompiled/readable, import queue, recompile queue, and new script templates.",
        command=("py", "-3", "tools/codered_script_pipeline.py"),
        required_paths=(
            "tools/codered_script_pipeline.py",
            "tools/codered_script_workshop_decode.py",
            "tools/codered_script_workshop_compile_prep.py",
            "data/codered/script_workshop_decode_manifest.json",
            "data/codered/script_workshop_compile_candidates.json",
        ),
        optional_paths=(
            "scratch/script_workshop_pipeline",
            "scratch/script_workshop_pipeline/SCRIPT_PIPELINE_GUIDE.md",
            "scratch/script_workshop_pipeline/open_script_workshop.bat",
            "scratch/script_workshop_pipeline/import_queue/IMPORT_QUEUE.json",
            "scratch/script_workshop_pipeline/recompile_queue/RECOMPILE_QUEUE.json",
            "scratch/script_workshop_pipeline/new_script_templates",
            "data/codered/script_pipeline_manifest.csv",
            "data/codered/script_pipeline_capabilities.json",
        ),
        proof_paths=(
            "logs/CodeRED_Script_Pipeline_Report.json",
            "logs/CodeRED_Script_Pipeline_Report.md",
            "logs/CodeRED_Script_Pipeline_Lane_Pass_2026-05-03.md",
        ),
        replaces_external=("manual script scan/read/open/edit workflow", "manual pseudo-decompile export staging", "manual import/recompile queue setup", "manual new-script template setup"),
        notes="This lane makes scripting the primary workflow. Source/text files are safe-edit and import/recompile candidates. Compiled WSC/CSC/XSC/SCO/YSC binaries are fully read/exported but binary bytecode roundtrip remains proof-gated until real compiler/decompiler proof exists.",
    ),
    AppLane(
        id="decompile_recompile_hub",
        title="Decompile / Recompile Hub",
        category="Scripts",
        description="Single capability matrix for RPF extract/decode, copied-archive patching, Script Workshop read/decode, and SC-CL source compile proof.",
        command=("py", "-3", "tools/codered_decompile_recompile_hub.py"),
        required_paths=(
            "tools/codered_decompile_recompile_hub.py",
            "tools/codered_rpf_utils.py",
            "tools/codered_rpf_utils_patch.py",
            "tools/codered_file_io_validation.py",
            "tools/codered_script_pipeline.py",
            "script_compiling/sccl/README.md",
            "Run_CodeRED_Decompile_Recompile_Hub.bat",
            "Run_CodeRED_RPF_Edit_Lab.bat",
        ),
        optional_paths=(
            "script_compiling/sccl/output/SC-CL.exe",
            "script_compiling/sccl/output/vehicle_menu_probe/vehicle_menu_probe.xsc",
            "script_compiling/sccl/output/camp_car_probe_sco/camp_car_probe.sco",
            "docs/CodeRED_DECOMPILE_RECOMPILE_GUIDE.md",
        ),
        proof_paths=(
            "logs/CodeRED_Decompile_Recompile_Hub_Report.json",
            "logs/CodeRED_Decompile_Recompile_Hub_Report.md",
            "logs/MILESTONE_SCCL_Compile_Lane_Proven_2026-05-04.md",
        ),
        replaces_external=("Magic RDR one-off archive browsing", "manual SC-CL compile path checks", "manual decompile/recompile capability audits"),
        notes="This is the honest top-level capability map. RPF extract/patch-on-copy and source compile are ready; existing compiled-script bytecode-to-source decompile remains blocked until a real decompiler is proven.",
    ),
    AppLane(
        id="file_io_decode",
        title="File IO / Full Decode",
        category="Core",
        description="Validates full-file reading, full text decoding, ZIP full-entry reads, and full RPF per-entry extraction/resource payload processing.",
        command=("py", "-3", "tools/codered_file_io_validation.py"),
        required_paths=(
            "tools/codered_file_io_validation.py",
            "python_workbench.py",
            "data/codered/actor_enum_map.csv",
            "research/CodeRED_RESEARCH_MANIFEST.csv",
        ),
        optional_paths=(
            "imports/content.rpf",
            "imports/tune_d11generic.rpf",
            "imports/fragments2.rpf",
            "imports/terrainboundres.rpf",
            "content.rpf",
            "tune_d11generic.rpf",
        ),
        proof_paths=(
            "logs/CodeRED_File_IO_Decode_Report.json",
            "logs/CodeRED_File_IO_Decode_Report.md",
            "data/codered/file_io_decode_manifest.csv",
        ),
        replaces_external=("manual file preview checks", "partial/snippet-only decode checks", "manual full-entry RPF extraction checks"),
        notes="This lane full-reads files and full-walks staged RPF entries. Opaque payload warnings are surfaced instead of hidden. It is read-only and does not modify source archives.",
    ),
    AppLane(
        id="rpf_edit_lab",
        title="Archive / RPF Lane",
        category="Archives",
        description="Validates staged RPF6 archives, inventories entries, sample-reads contents, and keeps copied-archive patching/proof utilities available inside Code RED.",
        command=("py", "-3", "tools/codered_archive_lane_validation.py"),
        required_paths=(
            "tools/codered_archive_lane_validation.py",
            "related_apps/rpf_edit_lab.py",
            "tools/codered_rpf_utils.py",
            "tools/codered_rpf_utils_patch.py",
            "python_workbench.py",
        ),
        optional_paths=(
            "imports/content.rpf",
            "imports/tune_d11generic.rpf",
            "game/content.rpf",
            "game/tune_d11generic.rpf",
            "content.rpf",
            "tune_d11generic.rpf",
        ),
        proof_paths=(
            "logs/CodeRED_Archive_Lane_Validation_Report.json",
            "logs/CodeRED_Archive_Lane_Validation_Report.md",
            "logs/code_red_archive_proof_latest.md",
        ),
        replaces_external=("Magic RDR basic RPF browsing/patch staging", "manual archive inventory", "manual copied-archive proof setup"),
        notes="Run this after staging one or more RPFs in imports/, game/, the package root, or the parent sources folder. Validation is read-only and does not modify source archives.",
    ),
    AppLane(
        id="codex_bundle",
        title="CodeX / Model XML Bundle Helpers",
        category="Archives",
        description="Validates CodeX-style and ModelXML-style model bundle export/import workflows with raw rebuild proof.",
        command=("py", "-3", "tools/codered_codex_modelxml_validation.py"),
        required_paths=(
            "tools/codered_codex_modelxml_validation.py",
            "tools/codered_codex_bundle_cli.py",
            "tools/codered_codex_bundle_import_cli.py",
            "tools/codered_modelxml_bundle_cli.py",
            "tools/codered_modelxml_bundle_import_cli.py",
        ),
        optional_paths=(
            "Export_CodeX_Bundle_CLI.bat",
            "Import_CodeX_Bundle_CLI.bat",
            "Export_ModelXML_Bundle_CLI.bat",
            "Import_Model_XML_Bundle_CLI.bat",
            "imports/fragments2.rpf",
            "imports/fragments2.zip",
        ),
        proof_paths=(
            "logs/CodeRED_CodeX_ModelXML_Validation_Report.json",
            "logs/CodeRED_CodeX_ModelXML_Validation_Report.md",
            "logs/CodeRED_CodeX_ModelXML_Lane_Pass_2026-05-03.md",
        ),
        replaces_external=("CodeX batch bundle steps", "Magic RDR model bundle spot checks", "manual model XML import/export proof"),
        notes="Validation exports one model-like entry and imports it back into a rebuilt resource file. Optional copied-archive readback exists in the validator, but the Archive/RPF lane owns archive patch proof. Full semantic model editing remains separate from this proof lane.",
    ),
    AppLane(
        id="wft_edit_bridge",
        title="WFT / RSC5 Edit Bridge",
        category="Models",
        description="WFT/RSC5 inspection, unpack, preview, and model bridge research lane.",
        command=("py", "-3", "tools/codered_wft_rsc5_tool.py"),
        required_paths=("tools/codered_wft_rsc5_tool.py", "related_apps/Code_RED_WFT_RSC5_EditBridge_Pass9_MENU_FIX"),
        optional_paths=("tools/codered_wft_wedt_attachment_decoder.py", "tools/codered_obj_viewer.py"),
        replaces_external=("partial model viewer/export helpers",),
    ),
    AppLane(
        id="wsi_tools",
        title="WSI / Map / Gringo Tools",
        category="World",
        description="WSI explorer, sector/array export, WGD export, gringo correlator, and map-layer resolver.",
        command=("py", "-3", "tools/codered_wsi_gringo_correlator.py"),
        required_paths=(
            "tools/codered_wsi_explorer.py",
            "tools/codered_wsi_sector_export.py",
            "tools/codered_wsi_array_export.py",
            "tools/codered_gringo_wgd_export.py",
            "tools/codered_wsi_gringo_correlator.py",
            "tools/codered_map_layer_correlator.py",
        ),
        proof_paths=("research/blackwater_wsi_gringo_correlation_outputs/wsi_gringo_correlation_master.json",),
        replaces_external=("manual WSI/WGD cross-checking",),
    ),
    AppLane(
        id="terrain_tools",
        title="Terrainboundres Tools",
        category="World",
        description="Terrain-bound inventory/export/patch-proof lane for WTB tiles.",
        command=("py", "-3", "tools/codered_terrainboundres_validation.py"),
        required_paths=("tools/codered_terrainboundres_tool.py", "tools/codered_terrainboundres_validation.py"),
        optional_paths=("imports/terrainboundres.rpf", "game/terrainboundres.rpf", "terrainboundres.rpf"),
        proof_paths=(
            "logs/CodeRED_Terrainboundres_Validation_Report.json",
            "logs/CodeRED_Terrainboundres_Validation_Report.md",
            "logs/CodeRED_Terrainboundres_Tooling_Changelog_2026-04-30.md",
        ),
        replaces_external=("manual terrainboundres browsing", "manual terrain-bound decode proof"),
        notes="Run this validation after staging terrainboundres.rpf in imports/ or game/. It proves inventory/decode readiness without modifying the source archive.",
    ),
    AppLane(
        id="vehicle_research",
        title="Vehicle / Gringo Research",
        category="Vehicles",
        description="Car/truck inventory, vehicle generator trace, gringo scripts, locsets, and templates.",
        command=("py", "-3", "tools/codered_car_truck_inventory.py"),
        required_paths=("tools/codered_car_truck_inventory.py", "research/CodeRED_RESEARCH_SYNTHESIS_2026-04-29.md"),
        proof_paths=("research/car_truck_inventory/car_truck_inventory.md",),
    ),
    AppLane(
        id="tuner_arcade",
        title="CodeRED Tuner / Arcade",
        category="Tuner",
        description="Vehicle tune UI, presets, arcade smoke test, screenshots, and runtime settings.",
        command=("cmd", "/c", "related_apps/CodeRED_Tuner/run_CodeRED_Tuner.bat"),
        required_paths=("related_apps/CodeRED_Tuner/codered_tuner.py", "related_apps/CodeRED_Tuner/code_red_arcade.py", "related_apps/CodeRED_Tuner/run_CodeRED_Tuner.bat"),
        optional_paths=("related_apps/CodeRED_Tuner/run_CodeRed_Arcade.bat", "related_apps/CodeRED_Tuner/stock_vehicle_files"),
    ),
    AppLane(
        id="mp_companion",
        title="MP Companion",
        category="Companion",
        description="Companion lane kept as an internal app section, not a competing startup workspace.",
        command=("py", "-3", "related_apps/run_mp_companion.py"),
        required_paths=("related_apps/run_mp_companion.py", "related_apps/Code_RED_MP_Companion_v19/mp_companion.py"),
    ),
    AppLane(
        id="logs_research",
        title="Logs / Research Browser",
        category="Research",
        description="Curated in-app browser for pass logs, proof reports, research manifest entries, docs, and regression checkpoint zips.",
        command=("py", "-3", "main.py", "--one-app-status"),
        required_paths=("logs", "research/CodeRED_RESEARCH_MANIFEST.csv", "python_workbench.py"),
        optional_paths=("logs/CodeRED_LOG_INDEX.md", "research/CodeRED_RESEARCH_SYNTHESIS_2026-04-29.md", "docs/CodeRED_One_App_Upgrade_Plan_2026-05-03.md"),
        proof_paths=("logs/CodeRED_Research_Browser_Report.md", "logs/CodeRED_Research_Browser_Report.json"),
        replaces_external=("manual log hunting", "manual research-manifest lookup", "manual regression-checkpoint browsing"),
        notes="Use the Research tab to browse curated logs, generated proof reports, manifest entries, docs, and any checkpoint zips copied into the package root.",
    ),
)


def _path_exists(root: Path, item: str) -> bool:
    path = root / item
    return path.exists()


def _resolve_command(root: Path, command: Sequence[str]) -> list[str]:
    resolved: list[str] = []
    for index, part in enumerate(command):
        if index == 0:
            resolved.append(part)
            continue
        if part.endswith((".py", ".bat", ".cmd", ".exe", ".md", ".txt")) or "/" in part or "\\" in part:
            maybe = root / part
            resolved.append(str(maybe) if maybe.exists() else part)
        else:
            resolved.append(part)
    return resolved


def lane_status(paths: CodeRedPaths, lane: AppLane) -> LaneStatus:
    root = paths.root
    present_required = [item for item in lane.required_paths if _path_exists(root, item)]
    missing_required = [item for item in lane.required_paths if not _path_exists(root, item)]
    present_optional = [item for item in lane.optional_paths if _path_exists(root, item)]
    present_proof = [item for item in lane.proof_paths if _path_exists(root, item)]

    if missing_required:
        state = "missing"
    elif lane.proof_paths and not present_proof:
        state = "ready-no-proof"
    else:
        state = "ready"

    return LaneStatus(
        id=lane.id,
        title=lane.title,
        category=lane.category,
        state=state,
        ready_required=len(present_required),
        total_required=len(lane.required_paths),
        ready_optional=len(present_optional),
        total_optional=len(lane.optional_paths),
        command=_resolve_command(root, lane.command),
        missing_required=missing_required,
        present_required=present_required,
        present_optional=present_optional,
        present_proof=present_proof,
        replaces_external=list(lane.replaces_external),
        description=lane.description,
        notes=lane.notes,
    )


def discover_lanes(root: Path | None = None) -> list[LaneStatus]:
    paths = CodeRedPaths.detect(root)
    return [lane_status(paths, lane) for lane in LANES]


def build_status_report(root: Path | None = None) -> dict:
    paths = CodeRedPaths.detect(root)
    statuses = discover_lanes(paths.root)
    counts: dict[str, int] = {"ready": 0, "ready-no-proof": 0, "missing": 0}
    categories: dict[str, dict[str, int]] = {}
    for status in statuses:
        counts[status.state] = counts.get(status.state, 0) + 1
        bucket = categories.setdefault(status.category, {"ready": 0, "ready-no-proof": 0, "missing": 0, "total": 0})
        bucket[status.state] = bucket.get(status.state, 0) + 1
        bucket["total"] += 1
    # Ready lanes count fully. Proof-gated lanes count halfway so the score does not
    # claim 100% until proof logs exist for every lane that requires them.
    total = len(statuses)
    weighted_ready = counts.get("ready", 0) + (counts.get("ready-no-proof", 0) * 0.5)
    score = int(round((weighted_ready / total) * 100)) if total else 0
    return {
        "root": str(paths.root),
        "score": score,
        "counts": counts,
        "categories": categories,
        "lanes": [asdict(status) for status in statuses],
    }


def report_to_markdown(report: dict) -> str:
    lines = [
        "# Code RED One-App Lane Status",
        "",
        f"Root: `{report['root']}`",
        f"Readiness score: **{report['score']}%**",
        "",
        "## Counts",
        "",
        f"- Ready: {report['counts'].get('ready', 0)}",
        f"- Ready but needs proof: {report['counts'].get('ready-no-proof', 0)}",
        f"- Missing required files: {report['counts'].get('missing', 0)}",
        "",
        "## Lanes",
        "",
        "| State | Category | Lane | Missing required | Replaces external |",
        "|---|---|---|---|---|",
    ]
    for lane in report["lanes"]:
        missing = ", ".join(lane["missing_required"]) if lane["missing_required"] else ""
        replaces = ", ".join(lane["replaces_external"]) if lane["replaces_external"] else ""
        lines.append(f"| {lane['state']} | {lane['category']} | {lane['title']} | {missing} | {replaces} |")
    return "\n".join(lines) + "\n"


def write_status_outputs(root: Path | None = None, out_dir: Path | None = None) -> dict:
    paths = CodeRedPaths.detect(root)
    report = build_status_report(paths.root)
    target = out_dir or (paths.logs / "one_app_status")
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "one_app_lane_status.json"
    md_path = target / "one_app_lane_status.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(report_to_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path), "report": report}
