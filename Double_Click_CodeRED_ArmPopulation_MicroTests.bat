@echo off
cd /d "%~dp0"
echo Code RED Arm Population Micro Tests
echo.
echo 1. Scan arm_population.wsc
echo 2. Make preview-only micro tests
echo 3. Make Car01 micro tests
echo 4. Make Truck01 micro tests
echo.
choice /c 1234 /n /m "Choose: "
if errorlevel 4 goto truck
if errorlevel 3 goto car
if errorlevel 2 goto preview
if errorlevel 1 goto scan
:scan
call Run_CodeRED_ArmPopulation_MicroTests.bat scan --input imports\arm_population.wsc --out logs\arm_population_microtests\scan
pause
exit /b
:preview
call Run_CodeRED_ArmPopulation_MicroTests.bat make-micro-tests --input imports\arm_population.wsc --out-dir logs\arm_population_microtests\preview --preview-only
pause
exit /b
:car
call Run_CodeRED_ArmPopulation_MicroTests.bat make-micro-tests --input imports\arm_population.wsc --out-dir patches\arm_population_microtests_car --target-ids 1194 --max-replacements 4
pause
exit /b
:truck
call Run_CodeRED_ArmPopulation_MicroTests.bat make-micro-tests --input imports\arm_population.wsc --out-dir patches\arm_population_microtests_truck --target-ids 1193 --max-replacements 4
pause
exit /b
