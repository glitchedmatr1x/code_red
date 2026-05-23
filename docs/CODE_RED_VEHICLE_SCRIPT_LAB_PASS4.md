# Code RED Vehicle Script Lab v4

Pass 4 fixes the main weakness seen in the `playercar.wsc` / `beat_crime_wagonthief.wsc` run: the previous scanner was profiling the packed `RSC85` wrapper instead of the decompressed compiled-script payload.

## Added

- RSC05/RSC85/RSC86 header detection.
- Zstandard/zlib payload decompression before string/hash/profile scans.
- Expected unpacked-size calculation from RSC85 flags for zstd frames without content size.
- `*.payload.bin` export beside reports for script payload research.
- Scan/profile summaries now show raw size vs analysis payload size, codec, and RSC metadata.

## Still intentionally out of scope

- Full WSC bytecode decompile.
- Full WSC source recompilation.
- Unsafe random byte patching.

Use WSC output as research evidence for the ASI/ScriptHook bridge lane.
