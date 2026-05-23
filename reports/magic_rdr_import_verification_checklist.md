# Magic RDR Import Verification Checklist

Use one isolated Pass 2 package per copied archive test.

1. Back up the target PC `content.rpf` and work on a copy.
2. Choose exactly one package: `import_test_release_csc`, `import_test_release64_csc`, or `import_test_both_csc`.
3. Import raw files into the matching internal content paths. Do not mix in `import_test_xsc_review` during the first CSC test.
4. Save the copied RPF and immediately reopen it in Magic RDR before launching the game.
5. Verify the expected internal `content/release.../multiplayer/` paths exist after reopen.
6. Export representative imports back out: `mp_idle.csc`, `multiplayer_update_thread.csc`, `freemode/freemode.csc`, and one region/action-area file.
7. Compare exported SHA1 and CRC32 against `raw_byte_preservation_report.csv` or the donor file. Record whether Magic RDR changed payload bytes.
8. If reopen or export comparison fails, stop. Mark that package rejected before any launch test.
9. Launch only after RPF reopen and export-byte verification pass.
10. Record the package name, internal paths tested, exported hashes, boot result, pause/menu result, and any loader log/crash.

For the XSC review package, keep it separate until raw XSC import behavior or a validated rewrap path is proven.

