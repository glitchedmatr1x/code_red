# CodeRED Enum Source + Menu Layout Pass

Date: 2026-05-01
Branch: `codered-build-assistant-pass1`

## Goal

Adjust the no-recompile actor data tools for the newly added enum source and prepare the AI Menu panel for compact scrolling layout behavior without changing the red/black theme.

## Enum source finding

The added enum file is a cheap INI-to-header conversion, not a classic C++ enum body. Its shape is:

```text
[Enum]
actor_invalid = -1
actor_player = 0
actor_caucasian_army_easy01 = 369
...
```

The first parser only targeted C++ style:

```cpp
enum e_ActorModel {
  ACTOR_CAUCASIAN_ARMY_Easy01 = 369,
};
```

## Updated

```text
tools/codered_actor_enum_tool.py
```

The enum tool now accepts both:

- classic C++ `enum e_ActorModel` format
- INI-style `[Enum]` + `actor_name = value` format

It normalizes lowercase `actor_*` labels into `ACTOR_*` aliases and still generates `AE_*`, uppercase, lowercase, and short-name aliases so the menu can resolve labels without recompiling.

Example rebuild command:

```bat
py -3 tools\codered_actor_enum_tool.py rebuild --source enums.h --replace
```

The older form still works:

```bat
py -3 tools\codered_actor_enum_tool.py rebuild --enums-h enums.h --replace
```

## Added

```text
tools/codered_ai_menu_layout_patch.py
```

This patcher prepares the AI Menu source for a compact scrolling panel renderer. It only patches when it finds a brace-balanced `static void drawMenu()` function. If the source does not match that expected shape, it refuses cleanly instead of guessing.

The intended visual behavior is:

- keep the existing red/black theme
- reduce large empty open space
- size the panel based on visible action/roster rows
- show a compact two-column Actions/Roster view
- show scroll range hints when lists exceed the visible rows
- truncate overlong labels instead of letting them spill

Manual patch command:

```bat
py -3 tools\codered_ai_menu_layout_patch.py --replace
```

Then build with:

```bat
Run_CodeRED_Build_Assistant.bat
```

## Note

The patcher was added instead of doing a blind connector-side source replacement because the C++ file is large. This keeps the pass conservative: if the source body differs, the patcher logs/refuses instead of corrupting the menu source.

## Next cleanup

Wire the layout patcher directly into Build Assistant as an optional pre-build checkbox/button after it is confirmed on the user machine.
