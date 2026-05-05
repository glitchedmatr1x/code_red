# Code RED Layout Consolidation Pass Report

## Scope

Clean up and consolidate the Code RED main app layout after prior reports showed the app was useful but not finished.

## Findings used

- Prior passes already established Code RED branding, red/black/white theme, top toolbar branding, resource lanes, and screenshot validation.
- Prior passes still did not claim direct binary injection into texture containers, automatic RPF write-back, or full mesh structural editing.
- The safest cleanup path is to reduce button sprawl and keep mutation actions staged until their backend validation is real.

## What changed in this package

- Added a consolidated `code_red_main.py` shell.
- Added compatibility launcher `run_workbench.py`.
- Centralized all button creation in one `_button(...)` factory.
- Locked the main layout to:
  - top toolbar
  - left resource lane rail
  - center workspace table
  - right inspector notebook
  - bottom status line
- Added read-only file/folder/zip scanning and lane classification.
- Added bounded SHA1 prefix hashing so huge RPF/resource files do not freeze the app.
- Added JSON report export.
- Added static layout test that blocks absolute placement and scattered direct button construction.
- Added an SVG layout wireframe.

## Validation

- `python -m py_compile code_red_main.py run_workbench.py tests/layout_static_test.py`
- `python tests/layout_static_test.py`
- `python code_red_main.py --self-test`
- `python tools/write_layout_wireframe.py`

## Not claimed

- I did not mutate the live GitHub repository.
- I did not perform a real GUI screenshot because this container has no display server.
- This does not implement RPF write-back or binary injection.
- This is a conservative consolidation shell/patch base, not a final RDR editor.

## Next safe merge target

Connect the existing Code RED resource-analysis functions to `ResourceRecord` output and keep all editing/export operations behind validated report/plan steps.
