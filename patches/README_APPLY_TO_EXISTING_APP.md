# Applying this pass to the existing Code RED source

This package is a conservative consolidation shell because the live source tree was not safely readable in the current tool session. To merge it into the existing app:

1. Copy `code_red_main.py` beside the current `python_workbench.py`.
2. Keep the current RPF/resource analysis modules as service functions.
3. Route their outputs into `ResourceRecord` rows instead of creating ad-hoc UI buttons.
4. Replace direct `Button(...)` construction with `CodeRedApp._button(...)`.
5. Keep the main layout grid-only:
   - row 0: toolbar
   - row 1: body
   - row 2: status
   - body col 0: resource lane rail
   - body col 1: workspace table
   - body col 2: inspector notebook
6. Do not add archive write-back buttons until write-back validation is real. Use report/export actions only.

The goal is to remove visual drift: all buttons live in either the top toolbar or the fixed left rail.
