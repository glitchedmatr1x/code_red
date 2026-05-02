# CodeRED WFT/WEDT Attachment Decoder Pass

This package adds a read-only model/attachment scanner and includes proof reports from `fragments2.rpf` and `tune_d11generic.rpf`.

## Run

```powershell
py -3 tools\codered_wft_wedt_attachment_decoder.py ^
  "D:\Games\Red Dead Redemption\game\fragments2.rpf" ^
  "D:\Games\Red Dead Redemption\game\tune_d11generic.rpf" ^
  --outdir reports\wft_wedt_attachment_lab
```

For a larger fragments archive, run the same tool against `fragments.rpf` once the split archive is fully extracted locally.

## Main outputs

- `reports/wft_wedt_attachment_lab/model_resource_summary.csv`
- `reports/wft_wedt_attachment_lab/fragment_bundle_map.csv`
- `reports/wft_wedt_attachment_lab/candidate_transforms.csv`
- `reports/wft_wedt_attachment_lab/smic_attachment_map.csv`
- `reports/wft_wedt_attachment_lab/smic_player_hand_rows.csv`
- `reports/wft_wedt_attachment_lab/smic_gunbelt_rows.csv`
- `reports/wft_wedt_attachment_lab/weapon_dualgun_comparison.csv`
- `reports/wft_wedt_attachment_lab/script_hook_dualgun_attachment_plan.json`
- `logs/CodeRED_WFT_WEDT_Attachment_Decoder_Pass_2026-05-01.md`

## Safety

Read-only scanner. No archive mutation. No WFT/WEDT rebuild claim.
