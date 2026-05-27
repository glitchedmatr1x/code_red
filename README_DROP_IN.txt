Code RED Content RPF Deep Scanner v1

Drop these files into your Code_RED folder.

Install deps once:
  .\install_content_rpf_deep_scan_deps.bat

Deep scan content.rpf:
  $env:CODERED_RDR_EXE="%RDR_GAME_DIR%"
  .\Run_CodeRED_Content_RPF_DeepScan.bat scan --rpf content.rpf --out logs\content_rpf_deep_scan --export-candidates

Main outputs:
  logs\content_rpf_deep_scan\summary.md
  logs\content_rpf_deep_scan\summary.json
  logs\content_rpf_deep_scan\entries.csv
  logs\content_rpf_deep_scan\candidate_files.csv
  logs\content_rpf_deep_scan\vehicle_id_hits.csv
  logs\content_rpf_deep_scan\target_string_hits.csv
  logs\content_rpf_deep_scan\target_hash_hits.csv
  logs\content_rpf_deep_scan\decode_report.csv

This is read-only. It does not modify content.rpf.
