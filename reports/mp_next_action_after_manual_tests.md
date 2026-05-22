# Code RED MP Next Action After Manual Tests

- Decision class: `do_not_patch_yet`
- Next action: `keep testing CSC`
- Exact next lane: `baseline_no_mp_restore`
- Why: manual evidence is incomplete; establish the next baseline/CSC lane before selecting a patch

Use the named CSC/baseline lane, restore the clean backup first, then fill `mp_test_results.csv`.

