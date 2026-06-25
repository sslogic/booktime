param(
    [switch]$StopServer,
    [switch]$RemoveLmStudioPresets,
    [switch]$RemoveStoryData
)

$ErrorActionPreference = "Continue"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Book Time.lnk"
$StartFolder = Join-Path ([Environment]::GetFolderPath("Programs")) "Book Time"
$StartShortcut = Join-Path $StartFolder "Book Time.lnk"
$ConfigPath = Join-Path $Root "booktime_config.json"

if ($StopServer) {
    try {
        $Config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
        $Port = [int]$Config.booktime_port
        Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique |
            ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
        Write-Host "Stopped Book Time server on port $Port if it was running."
    } catch {
        Write-Host "Could not stop Book Time server: $($_.Exception.Message)"
    }
}

foreach ($Path in @($DesktopShortcut, $StartShortcut)) {
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Force
        Write-Host "Removed shortcut: $Path"
    }
}

if ((Test-Path -LiteralPath $StartFolder) -and -not (Get-ChildItem -LiteralPath $StartFolder -Force -ErrorAction SilentlyContinue)) {
    Remove-Item -LiteralPath $StartFolder -Force
    Write-Host "Removed empty Start Menu folder: $StartFolder"
}

if ($RemoveLmStudioPresets) {
    try {
        $Config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
        $LmRoot = Split-Path -Parent $Config.lmstudio_conversations_dir
        $Targets = @(
            (Join-Path $LmRoot "config-presets\booktime-writer.preset.json"),
            (Join-Path $LmRoot "user-files\booktime-writer-system-prompt.md"),
            (Join-Path $LmRoot "user-files\booktime-output-schema.json")
        )
        foreach ($Path in $Targets) {
            if (Test-Path -LiteralPath $Path) {
                Remove-Item -LiteralPath $Path -Force
                Write-Host "Removed LM Studio file: $Path"
            }
        }
    } catch {
        Write-Host "Could not remove LM Studio preset files: $($_.Exception.Message)"
    }
}

if ($RemoveStoryData) {
    try {
        $Config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
        $Memory = [string]$Config.memory_dir
        if (-not [IO.Path]::IsPathRooted($Memory)) {
            $Memory = Join-Path $Root $Memory
        }
        if ((Test-Path -LiteralPath $Memory) -and ((Resolve-Path -LiteralPath $Memory).Path.StartsWith((Resolve-Path -LiteralPath $Root).Path))) {
            Remove-Item -LiteralPath $Memory -Recurse -Force
            Write-Host "Removed story data: $Memory"
        } else {
            Write-Host "Skipped story data removal because path is outside Book Time folder: $Memory"
        }
    } catch {
        Write-Host "Could not remove story data: $($_.Exception.Message)"
    }
}

Write-Host "Book Time shortcut uninstall complete."
