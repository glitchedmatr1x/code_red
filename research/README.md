# Code RED Research

This folder holds longer-lived research material, extracted-reference analysis, and supporting datasets. Generated scan reports and active tool outputs usually stay in `logs\`; stable research bundles and reference folders stay here.

## Start Here

- `..\docs\research_index\README.md` - organized master map across logs, research, docs, readmes, handoffs, and milestones.
- `CodeRED_RESEARCH_MANIFEST.csv` - older manifest of research files.
- `CodeRED_RESEARCH_SYNTHESIS_2026-04-29.md` - consolidated research synthesis.
- `extracted_root_research\` - readable extracted-root research.
- `car_truck_inventory\` - car/truck inventory research.
- `IMPORTANT_readable_root_index_2026-05-02\` - extracted-root important-file index.
- `IMPORTANT_psocache_rpf_analysis_2026-05-02\` - psocache RPF analysis.
- `IMPORTANT_later_rpf_compare_2026-05-02\` - later-version comparison notes.

## Organization Rule

Keep raw reference folders and generated datasets in place once tools or reports point to them. Add or refresh the generated index instead of moving fixed-path evidence:

```bat
py -3 tools\codered_research_log_organizer.py
```
