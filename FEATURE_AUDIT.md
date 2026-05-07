# Code RED Feature Audit

## Present / documented from prior passes

- Code RED branding in the Python fallback/workbench.
- Archive browser title updated to Code RED.
- Format-aware routing for extracted archive children.
- Texture lane inspection for `.wtd/.wtx/.wsf/.xtd/.xtx/.xsf` with slot hints and ranked companion targets.
- Conservative replacement planning for texture containers.
- Resource payload analysis for RSC85/RSC86 resource type 2.
- Best-effort AES payload decryption and zstd/zlib decompression.
- Strings, Textures, Meshes, and Scripts lanes receive resource-header-aware analysis.
- Script Lab for `.wsc/.csc/.xsc/.sco` with pseudo-decompile-style reports.
- Round-trip clone rebuild/verification from processed script payloads.
- Native DB loading for script/native-table research.
- Script table/descriptor recovery for known `.wsc` cases.

## Missing / confusing / not safe to promise yet

- One obvious app entry point in the root folder.
- Clean separation between source/build files and user launch files.
- Automatic `.rpf` write-back after editing extracted children.
- Full direct binary injection into texture containers.
- Full embedded texture dictionary parsing.
- Full mesh/fragment structural editing.
- Trusted source-level script compiler.
- Integrated vehicle/tune editor GUI in the same verified Code RED build.

## Recommended next pass

1. Add `Code_RED.bat` and/or a packaged `Code_RED.exe` as the only obvious root launch target.
2. Rename implementation files into a `source/` or `app/` folder, or leave only `run_workbench.py` visible in source builds.
3. Add a home screen checklist: Archives, Textures, Scripts, Strings, Meshes, Tuner, Injector, Reports.
4. Add disabled/locked cards for features that are staged but not safe, instead of hiding them.
5. Add a built-in self-test panel that says exactly what works and what is still plan-only.
