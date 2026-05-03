Code RED CodeX / ModelXML Lane Patch
=====================================

Apply over the latest Code_RED patch state.

Adds:
- tools/codered_codex_modelxml_validation.py

Updates:
- python_workbench.py
- codered_app/launcher_registry.py

Proof reports:
- logs/CodeRED_CodeX_ModelXML_Validation_Report.md
- logs/CodeRED_CodeX_ModelXML_Validation_Report.json
- logs/CodeRED_CodeX_ModelXML_Lane_Pass_2026-05-03.md
- logs/one_app_status/one_app_lane_status.md
- logs/one_app_status/one_app_lane_status.json

This pass validates CodeX-style and ModelXML-style bundle export/import proof.
It does not include large source archives such as fragments2.rpf.
Stage fragments2.rpf or fragments2.zip in imports/ when rerunning the validator.
