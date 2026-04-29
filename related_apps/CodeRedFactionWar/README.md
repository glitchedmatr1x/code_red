# Code Red Faction War

Resource-only faction war mod lane for Code RED.

This directory stores the repo-friendly source for the Faction War passes: patch recipes, research notes, validation manifests, and helper scripts. Large generated RPF files should stay out of GitHub and be distributed as test artifacts/releases.

## Current focus

Pass 13 moves the mod toward stronger world simulation:

- wilderness event pressure
- persistent camps and refgroups
- rival gang showdowns
- law response/capture posse design
- US Army bodyguard posse research
- train robbery/event pressure
- navres-supported battle vehicle and camp props

## Safe development rule

Keep the repository clean:

- commit patch recipes and scripts
- commit research and validation reports
- do not commit huge generated `content.rpf` or `tune_d11generic.rpf` unless intentionally making a release artifact
- never require EXE/DLL/BAT/CMD/PS1 files for the resource-only mod path

## Test install pattern

Generated test packs should use this structure:

```text
DROP_IN_<PASS_NAME>/
  content.rpf
  tune_d11generic.rpf
  reports/
  README_INSTALL_AND_TEST.txt
```

The user should copy the generated RPFs over backed-up test copies only.
