# Pass 3 Result

The real playercar/wagonthief compare showed that direct printable strings are mostly random-looking bytecode noise.

Pass 3 adds:

- humanish string filtering
- byte profile JSON
- entropy chunk CSV
- common aligned u32 constants CSV
- `profile-wsc` command
- compare reports that separate raw accidental strings from likely useful labels

This still does not claim WSC decompile/recompile. It makes the Script Lab more honest and useful for compiled-script research while behavior work moves through ASI/ScriptHook.
