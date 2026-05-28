<#
Code RED SC-CL lane sorter

Purpose:
- Sort only the script compiling / SC-CL lane.
- Preserve old files by moving them under script_compiling/sccl/obsolete/.
- Create one active compile lane from the existing repo files.
- Do not delete source.

Run from the Code_RED repo root:
  powershell -ExecutionPolicy Bypass -File tools\Apply_CodeRED_SCCL_Lane_Sort_From_Repo.ps1

Then review with:
  git status
#>

param([string]$RepoRoot = ".")

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path

function New-Dir($Path) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function Copy-IfExists($FromRel, $ToRel) {
    $from = Join-Path $RepoRoot $FromRel
    $to = Join-Path $RepoRoot $ToRel
    if (Test-Path $from) {
        New-Dir (Split-Path -Parent $to)
        Copy-Item -Path $from -Destination $to -Recurse -Force
        Write-Host "Copied: $FromRel -> $ToRel"
        return $true
    }
    Write-Warning "Missing: $FromRel"
    return $false
}

function Move-IfExists($FromRel, $ToRel) {
    $from = Join-Path $RepoRoot $FromRel
    $to = Join-Path $RepoRoot $ToRel
    if (Test-Path $from) {
        New-Dir (Split-Path -Parent $to)
        if (Test-Path $to) { Remove-Item $to -Recurse -Force }
        Move-Item -Path $from -Destination $to
        Write-Host "Moved obsolete: $FromRel -> $ToRel"
        return $true
    }
    Write-Host "Already absent: $FromRel"
    return $false
}

function Write-Text($Rel, $Text) {
    $path = Join-Path $RepoRoot $Rel
    New-Dir (Split-Path -Parent $path)
    Set-Content -Path $path -Value $Text -Encoding UTF8
    Write-Host "Wrote: $Rel"
}

$active = "script_compiling\sccl"
$oldBundle = "related_apps\code_red_sccl_attempt_bundle_v1"
$oldKit = "$oldBundle\code_red_sccl_windows_build_kit_v1"
$oldLab = "$oldBundle\code_red_script_compile_lab_v1"
$oldPeek = "related_apps\compiled_vehicle_menu_probe"

New-Dir (Join-Path $RepoRoot $active)
New-Dir (Join-Path $RepoRoot "$active\include")
New-Dir (Join-Path $RepoRoot "$active\projects\vehicle_menu_probe\src")
New-Dir (Join-Path $RepoRoot "$active\projects\vehicle_menu_probe\scripts")
New-Dir (Join-Path $RepoRoot "$active\obsolete")

Write-Text "script_compiling\README.md" @"
# Code RED Script Compiling

This folder is the active script-compiling workspace.

Current active lane:

```text
script_compiling/sccl/
```

Rules:

- Keep SC-CL proof work here.
- Use real headers only.
- Keep old/incorrect compile attempts under `script_compiling/sccl/obsolete/`.
- Do not use scattered `related_apps` pass folders as the active compiler path.
"@

Write-Text "$active\README.md" @"
# Code RED SC-CL Lane

This is the active SC-CL compile lane.

Expected layout:

```text
script_compiling/sccl/
  output/SC-CL.exe                 optional local compiler location; not committed
  include/                         active headers
  projects/vehicle_menu_probe/     active proof source
  obsolete/                        preserved old compile attempts
```

Compile goal:

```bat
py -3 script_compiling\sccl\projects\vehicle_menu_probe\scripts\validate_vehicle_menu_probe.py
script_compiling\sccl\compile_vehicle_menu_probe_windows.bat
```

If `SC-CL.exe` is somewhere else, set:

```bat
set SCCL_EXE=C:\path\to\SC-CL.exe
```

Do not build the full Code RED menu through SC-CL until native signatures are verified one at a time.
"@

# Copy active files from the existing compile lab / kit.
Copy-IfExists "$oldLab\include" "$active\include" | Out-Null
Copy-IfExists "$oldLab\src\main.c" "$active\projects\vehicle_menu_probe\src\main.c" | Out-Null
Copy-IfExists "$oldLab\scripts\validate_vehicle_menu_probe.py" "$active\projects\vehicle_menu_probe\scripts\validate_vehicle_menu_probe.py" | Out-Null
Copy-IfExists "$oldKit\build_sccl_windows.bat" "$active\build_sccl_windows.bat" | Out-Null
Copy-IfExists "$oldKit\build_sccl_windows.ps1" "$active\build_sccl_windows.ps1" | Out-Null
Copy-IfExists "$oldKit\compile_vehicle_menu_probe_windows.bat" "$active\compile_vehicle_menu_probe_windows.bat" | Out-Null
Copy-IfExists "$oldKit\compile_vehicle_menu_probe_windows.ps1" "$active\compile_vehicle_menu_probe_windows.ps1" | Out-Null
Copy-IfExists "$oldKit\run_build_then_compile_vehicle_menu_probe.bat" "$active\run_build_then_compile_vehicle_menu_probe.bat" | Out-Null

# Mark known issue in source if present: avoid treating Vector3 constructor as proven.
$mainPath = Join-Path $RepoRoot "$active\projects\vehicle_menu_probe\src\main.c"
if (Test-Path $mainPath) {
    $main = Get-Content $mainPath -Raw
    if ($main -match 'CREATE_ACTOR_IN_LAYOUT\(gLayout, name, actorId, pos, Vector3\(0\.0f, 0\.0f, 0\.0f\)\)') {
        $main = $main -replace 'CREATE_ACTOR_IN_LAYOUT\(gLayout, name, actorId, pos, Vector3\(0\.0f, 0\.0f, 0\.0f\)\);', @'
    vector3 rot;
    rot.x = 0.0f;
    rot.y = 0.0f;
    rot.z = 0.0f;

    CREATE_ACTOR_IN_LAYOUT(gLayout, name, actorId, pos, rot);
'@
        Set-Content -Path $mainPath -Value $main -Encoding UTF8
        Write-Host "Patched source: replaced unverified Vector3 constructor with explicit vector3 rot"
    }
}

Write-Text "$active\obsolete\README.md" @"
# Obsolete SC-CL Compile Attempts

This folder preserves older SC-CL / script compile attempts that should not be used as the active compile path.

Moved here by:

```text
tools/Apply_CodeRED_SCCL_Lane_Sort_From_Repo.ps1
```

Preserve these for research/proof history, but compile from:

```text
script_compiling/sccl/
```
"@

# Move old compile-lane folders out of the active/confusing related_apps area.
Move-IfExists $oldBundle "$active\obsolete\code_red_sccl_attempt_bundle_v1" | Out-Null
Move-IfExists $oldPeek "$active\obsolete\compiled_vehicle_menu_probe" | Out-Null

Write-Text "logs\CodeRED_SCCL_Lane_Sort_Pass_2026-05-04.md" @"
# Code RED SC-CL Lane Sort Pass — 2026-05-04

## Scope

Only the SC-CL / script-compiling lane was sorted.

## Active lane

```text
script_compiling/sccl/
```

## Preserved obsolete folders

```text
script_compiling/sccl/obsolete/code_red_sccl_attempt_bundle_v1
script_compiling/sccl/obsolete/compiled_vehicle_menu_probe
```

## Why

The old compile files were scattered under `related_apps`, making it unclear which compiler path, headers, CMake files, and proof source should be used.

## Rule

Do not delete proof material. Move wrong-code or old-code compile attempts into `obsolete/` until verified.

## Next validation

```bat
py -3 script_compiling\sccl\projects\vehicle_menu_probe\scripts\validate_vehicle_menu_probe.py
script_compiling\sccl\compile_vehicle_menu_probe_windows.bat
```

If the compiler is not under `script_compiling\sccl\output\SC-CL.exe`, set `SCCL_EXE` first.
"@

Write-Text "SC_CL_SORT_MANIFEST.json" @"
{
  "pass": "CodeRED SC-CL lane sort",
  "date": "2026-05-04",
  "active_lane": "script_compiling/sccl",
  "obsolete_lane": "script_compiling/sccl/obsolete",
  "source_policy": "preserve old files; do not delete proof material",
  "next_commands": [
    "py -3 script_compiling\\sccl\\projects\\vehicle_menu_probe\\scripts\\validate_vehicle_menu_probe.py",
    "script_compiling\\sccl\\compile_vehicle_menu_probe_windows.bat"
  ]
}
"@

Write-Host ""
Write-Host "SC-CL lane sort complete. Review with: git status"
