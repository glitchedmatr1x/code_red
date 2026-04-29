@echo off
cd /d "%~dp0"
echo Code RED Model XML export helper
echo.
echo Examples:
echo   python tools\codered_modelxml_bundle_cli.py --archive imports\your_archive.rpf --list
echo   python tools\codered_modelxml_bundle_cli.py --archive imports\your_archive.rpf --entry canoe --out exports\modelxml_bundles
echo.
echo Export creates an editable .modelxml.xml and .model_edits.txt inside the bundle folder.
echo Edit value="..." fields in the XML, then import the bundle back through the GUI or Import_Model_XML_Bundle_CLI.bat.
echo.
cmd /k
