Code RED AI Menu Bridge Integration Lane Patch
==============================================

Apply over the latest Code RED one-app checkpoint.

Adds:
- tools/codered_ai_menu_bridge_integration.py
- AI Menu bridge candidate generation
- selected native wrapper integration candidate
- candidate build helper for Windows Visual Studio x64 Native Tools Prompt
- Dashboard/toolbar button: Prep AI Bridge
- one-app registry lane: AI Menu Bridge Integration Prep

Safety:
- Does not overwrite CodeRED_AI_Menu.cpp.
- Does not install an ASI.
- Review logs/CodeRED_AI_Menu_Bridge_Integration_Candidate.diff before compiling.
- Candidate source is related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.bridge_candidate.cpp.
- Candidate build helper is related_apps/Code_RED_ScriptHookRDR_AI_Menu/build_bridge_candidate.bat.

Validation run:
- python3 -B -m py_compile main.py python_workbench.py codered_app/*.py tools/codered_ai_menu_bridge_integration.py
- python3 -B tools/codered_ai_menu_bridge_integration.py --root .
- python3 -B tools/codered_one_app_status.py --write
- python3 -B main.py --dry-run
- python3 -B main.py --one-app-status
- xvfb-run UI smoke: Prep AI Bridge invoked successfully
