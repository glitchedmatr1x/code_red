Code RED — Vehicle Spawn Research / Trainer-Style Runtime Path Pass 6

Install:
  Copy tools/codered_vehicle_spawn_research.py into your Code_RED/tools folder.

Run examples:
  python tools/codered_vehicle_spawn_research.py gringores.rpf content.rpf tune_d11generic.rpf --outdir exports/vehicle_spawn_research --no-utf16

What it does:
  - Read-only scan.
  - Does not patch or rebuild RPF files.
  - Searches raw RPF/resource bytes for vehicle, spawn, trainer, gringo, FBI, coach, train, wagon, passenger, turret, and companion clues.
  - Creates CSV/JSON/MD reports to guide the next runtime-spawn pass.

Why this pass exists:
  The wagon placement nudge crashed, so cars should not be forced through unstable wagon physics records. Use WSI for clearing blocker props only. Use gringo/script/runtime paths for actual vehicles.

Main outputs:
  reports/vehicle_spawn_research_outputs/vehicle_spawn_strings.csv
  reports/vehicle_spawn_research_outputs/vehicle_tokens.csv
  reports/vehicle_spawn_research_outputs/candidate_wsc_scripts.csv
  reports/vehicle_spawn_research_outputs/gringo_vehicle_callsite_candidates.csv
  reports/vehicle_spawn_research_outputs/trainer_spawn_research_summary.md
