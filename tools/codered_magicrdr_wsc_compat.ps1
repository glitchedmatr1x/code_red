param(
    [Parameter(Mandatory=$true)][string]$InputPath,
    [string]$MagicRdrDir = "%RDR_GAME_DIR%\game\BACKUP BEFORE MODDING\rdr1\mods\Magic-RDR-main",
    [ValidateSet("Switch","Xbox","PS3")][string]$Platform = "Switch",
    [ValidateSet("Auto","Little","Big")][string]$ReaderEndian = "Auto",
    [string]$DecompiledOut = ""
)

$ErrorActionPreference = "Stop"

function Write-JsonResult($obj) {
    $obj | ConvertTo-Json -Depth 8 -Compress
}

try {
    if (-not (Test-Path -LiteralPath $InputPath)) {
        throw "Input file not found: $InputPath"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $MagicRdrDir "MagicRDR.exe"))) {
        throw "MagicRDR.exe not found under: $MagicRdrDir"
    }

    Set-Location $MagicRdrDir
    $cache = @{}
    [AppDomain]::CurrentDomain.add_AssemblyResolve({
        param($sender, $eventArgs)
        $simple = ($eventArgs.Name -split ',')[0]
        if ($cache.ContainsKey($simple)) {
            return $cache[$simple]
        }
        foreach ($baseDir in @($MagicRdrDir, (Join-Path $MagicRdrDir "Assemblies"))) {
            $candidate = Join-Path $baseDir ($simple + ".dll")
            if (Test-Path -LiteralPath $candidate) {
                $loaded = [Reflection.Assembly]::LoadFrom($candidate)
                $cache[$simple] = $loaded
                return $loaded
            }
        }
        return $null
    }) | Out-Null

    [Reflection.Assembly]::LoadFrom((Join-Path $MagicRdrDir "MagicRDR.exe")) | Out-Null
    [AppGlobals]::SetPlatform([Enum]::Parse([AppGlobals+PlatformEnum], $Platform))

    $bytes = [IO.File]::ReadAllBytes($InputPath)
    if ($bytes.Length -lt 16) {
        throw "Input too small for RSC85 header"
    }

    $decoded = [Magic_RDR.RPF.ResourceUtils+ResourceInfo]::GetDataFromResourceBytes($bytes)
    if ($null -eq $decoded) {
        throw "MagicRDR ResourceInfo returned null decoded data"
    }

    $entry = New-Object "Magic_RDR.RPF6+RPF6TOC+FileEntry"
    $entry.Name = [IO.Path]::GetFileName($InputPath)
    $entry.SizeInArchive = $bytes.Length
    $flag1 = [BitConverter]::ToInt32($bytes, 8)
    $flag2 = [BitConverter]::ToInt32($bytes, 12)
    $entry.FlagInfo = New-Object "Magic_RDR.RPF.ResourceUtils+FlagInfo" -ArgumentList $flag1, $flag2

    $stream = New-Object IO.MemoryStream(,$decoded)
    $effectiveReaderEndian = $ReaderEndian
    if ($effectiveReaderEndian -eq "Auto") {
        $effectiveReaderEndian = $(if ($Platform -eq "Switch") { "Little" } else { "Big" })
    }
    $reader = New-Object "Magic_RDR.Application.IOReader" -ArgumentList $stream, ([Enum]::Parse([Magic_RDR.Application.IOReader+Endian], $effectiveReaderEndian))

    $script = New-Object "Magic_RDR.ScriptFile" -ArgumentList $reader, $entry
    $decompiled = [Magic_RDR.ScriptViewerForm]::DecompiledCode
    if ($DecompiledOut -ne "" -and $null -ne $decompiled) {
        $parent = Split-Path -Parent $DecompiledOut
        if ($parent -and -not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Force -Path $parent | Out-Null
        }
        [IO.File]::WriteAllText($DecompiledOut, $decompiled)
    }
    Write-JsonResult ([ordered]@{
        ok = $true
        input = (Resolve-Path -LiteralPath $InputPath).Path
        platform = $Platform
        reader_endian = $effectiveReaderEndian
        decoded_size = $decoded.Length
        object_start = $entry.FlagInfo.RSC85_ObjectStart
        function_count = $script.Functions.Count
        decompiled_chars = $(if ($null -eq $decompiled) { 0 } else { $decompiled.Length })
        error = ""
    })
    exit 0
}
catch {
    Write-JsonResult ([ordered]@{
        ok = $false
        input = $InputPath
        platform = $Platform
        reader_endian = $(if ($ReaderEndian -eq "Auto") { "" } else { $ReaderEndian })
        decoded_size = 0
        object_start = 0
        function_count = 0
        decompiled_chars = 0
        error = $_.Exception.Message
        error_type = $_.Exception.GetType().FullName
        stack = $_.ScriptStackTrace
    })
    exit 2
}
