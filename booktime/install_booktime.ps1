param(
    [string]$InstallDir = "$env:ProgramFiles\BookTime",
    [string]$DataDir = "",
    [switch]$NoShortcuts
)

$ErrorActionPreference = "Stop"

function Test-IsAdmin {
    $Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = New-Object Security.Principal.WindowsPrincipal($Identity)
    return $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Read-JsonHashtable($Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return @{}
    }
    $Object = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    $Table = @{}
    foreach ($Property in $Object.PSObject.Properties) {
        $Table[$Property.Name] = $Property.Value
    }
    return $Table
}

function Set-Default($Table, $Key, $Value) {
    if (-not $Table.ContainsKey($Key) -or $null -eq $Table[$Key] -or [string]$Table[$Key] -eq "") {
        $Table[$Key] = $Value
    }
}

if (-not (Test-IsAdmin)) {
    Write-Host "Book Time install needs administrator permission to write to Program Files."
    $ArgsList = @(
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$PSCommandPath`"",
        "-InstallDir", "`"$InstallDir`"",
        "-DataDir", "`"$DataDir`""
    )
    if ($NoShortcuts) {
        $ArgsList += "-NoShortcuts"
    }
    Start-Process -FilePath "powershell.exe" -ArgumentList $ArgsList -Verb RunAs
    exit 0
}

$SourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $DataDir) {
    $DataDir = Join-Path (Join-Path $env:USERPROFILE "Documents") "BookTime"
}
$InstallDir = [IO.Path]::GetFullPath($InstallDir)
$DataDir = [IO.Path]::GetFullPath($DataDir)
$ConfigPath = Join-Path $DataDir "booktime_config.json"

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
New-Item -ItemType Directory -Path $DataDir -Force | Out-Null

$ExcludeDirs = @("__pycache__", ".git", "story_memory")
$ExcludeFiles = @(".booktime_state.json")

Get-ChildItem -LiteralPath $SourceRoot -Force | ForEach-Object {
    if ($_.PSIsContainer -and ($ExcludeDirs -contains $_.Name)) {
        return
    }
    if (-not $_.PSIsContainer -and ($ExcludeFiles -contains $_.Name)) {
        return
    }
    $Target = Join-Path $InstallDir $_.Name
    Copy-Item -LiteralPath $_.FullName -Destination $Target -Recurse -Force
}

$Config = @{}
if (Test-Path -LiteralPath $ConfigPath) {
    $Config = Read-JsonHashtable $ConfigPath
} else {
    $InstalledConfigPath = Join-Path $InstallDir "booktime_config.json"
    $SourceConfigPath = Join-Path $SourceRoot "booktime_config.json"
    if (Test-Path -LiteralPath $InstalledConfigPath) {
        $Config = Read-JsonHashtable $InstalledConfigPath
    } elseif (Test-Path -LiteralPath $SourceConfigPath) {
        $Config = Read-JsonHashtable $SourceConfigPath
    }
}

if (-not $Config) {
    $Config = @{}
}
$Config["memory_dir"] = $DataDir
$Config["lmstudio_preset_dir"] = Join-Path $InstallDir "lmstudio_presets"
Set-Default $Config "booktime_host" "127.0.0.1"
Set-Default $Config "booktime_port" 8765
Set-Default $Config "ollama_url" "http://127.0.0.1:11434"
Set-Default $Config "book_id" "booktime"

$Json = $Config | ConvertTo-Json -Depth 20
[IO.File]::WriteAllText($ConfigPath, $Json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))

$CopiedConfigPath = Join-Path $InstallDir "booktime_config.json"
if (Test-Path -LiteralPath $CopiedConfigPath) {
    Remove-Item -LiteralPath $CopiedConfigPath -Force
}

if (-not $NoShortcuts) {
    & (Join-Path $InstallDir "install_booktime_shortcuts.ps1")
}

Write-Host "Book Time installed."
Write-Host "App: $InstallDir"
Write-Host "Memory: $DataDir"
