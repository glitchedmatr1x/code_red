Code RED Pass 26 - FBI Car/Truck Focus
======================================

This package focuses only on car and truck clues in the uploaded fbi02.wsc and fbi04.wsc files.

Important:
- The uploaded files are raw RSC85 script resources, not decompiled text.
- The readable switch line `case 0x0000003C: return "CAR";` is not present as ASCII in these raw files.
- Car01 and Truck01 actor enum byte patterns appear in the raw data, but raw high-entropy RSC85 hits are not safe patch points.

Open in Code RED:
- OPEN_IN_CODERED/fbi02.wsc
- OPEN_IN_CODERED/fbi04.wsc

After exporting/decompiling readable text from Code RED:
1. Place text files in DROP_DECOMPILED_FBI_HERE/
2. Run RUN_PARSE_DECOMPILED_FBI_CAR_TRUCK.bat
3. Check reports/decompiled_car_truck_parse/vehicle_case_returns.csv

Reports:
- reports/pass26_car_truck_fbi_summary.json
- reports/fbi_car_truck_raw_hit_counts.csv
- reports/fbi_car_truck_raw_hits.csv
- reports/candidate_vehicle_value_swap_table_DO_NOT_PATCH_YET.csv

No game files are patched in this package.
