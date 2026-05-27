$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $Root 'Code_RED_Dependency_Installer.py'
try {
  py -3 $Script
} catch {
  python $Script
}
