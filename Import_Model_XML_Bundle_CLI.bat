@echo off
setlocal
cd /d "%~dp0"
echo Code RED Model XML import helper
echo.
echo Example:
echo   python tools\codered_modelxml_bundle_import_cli.py --bundle exports\modelxml_bundles\your_bundle --archive imports\your_archive.rpf --entry canoe --out-archive imports\your_archive_modelxml_test.rpf --mode raw-clone
echo.
echo Import reads edits from the bundle .modelxml.xml and .model_edits.txt automatically.
echo It writes to a copied archive when --archive and --out-archive are used.
echo.
python tools\codered_modelxml_bundle_import_cli.py %*
if errorlevel 1 pause
