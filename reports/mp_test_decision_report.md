# Code RED MP Test Decision Report

This report ingests manual test notes and exported-back byte verification only. It does not modify archives or scripts.

## Decision

- Classification: `do_not_patch_yet`
- Acceptance action: `keep testing CSC`
- Exact next lane: `baseline_no_mp_restore`
- Reason: manual evidence is incomplete; establish the next baseline/CSC lane before selecting a patch

## Lane status

| Lane | Name | Tested | Runtime signal | Export verification | Conclusion |
| --- | --- | --- | --- | --- | --- |
| A | baseline_no_mp_restore | no | no | not_applicable:1 |  |
| B | release64_csc_only | no | no | export_folder_missing:1 |  |
| C | release_csc_only | no | no | export_folder_missing:1 |  |
| D | both_release_and_release64_csc | no | no | export_folder_missing:1 |  |
| E | xsc_review_only | no | no | review_only_not_approved:1 |  |

## Export verification summary

| Status | Rows |
| --- | --- |
| export_folder_missing | 3 |
| not_applicable | 1 |
| review_only_not_approved | 1 |

## Decision boundaries

- `xsc_review_only` remains review-only unless `approved_for_import` is explicitly set truthy in `mp_test_results.csv`.
- Exported-back byte drift blocks runtime conclusions until size, SHA1, and CRC32 changes are understood.
- Authentication/profile/public-server blockers are report-only in this pass.

