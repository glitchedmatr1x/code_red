# Code RED Magic RDR Import Export Verification Worksheet

Use this before every runtime launch in the Pass 3 matrix.

1. Copy the lane backup of `content.rpf`; do not edit the only clean archive.
2. Import one package only and keep its internal `content/release.../multiplayer/` path unchanged.
3. Save and reopen the copied RPF in Magic RDR.
4. Verify the expected imported paths still exist after reopen.
5. Export representative imported files back out.
6. Compare exported SHA1 and CRC32 to the staged package file and `reports/raw_byte_preservation_report.csv`.
7. Launch only when reopen and exported-byte checks pass.

| Sample file | Imported path verified | Export SHA1 | Export CRC32 | Matches staged donor |
| --- | --- | --- | --- | --- |
| freemode/freemode.csc |  |  |  |  |
| mp_idle.csc |  |  |  |  |
| multiplayer_system_thread.csc |  |  |  |  |
| multiplayer_update_thread.csc |  |  |  |  |
| deathmatch/deathmatch.csc |  |  |  |  |

Record any Magic RDR payload rewrite, missing path, import warning, export failure, or size change as a lane failure before game launch.

