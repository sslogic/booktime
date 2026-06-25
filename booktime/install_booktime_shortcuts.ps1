$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher = Join-Path $Root "booktime_launcher.ps1"
$IconTarget = Join-Path $Root "booktime.ico"
$Desktop = [Environment]::GetFolderPath("Desktop")
$Programs = [Environment]::GetFolderPath("Programs")
$StartFolder = Join-Path $Programs "Book Time"

New-Item -ItemType Directory -Path $StartFolder -Force | Out-Null

$ShortcutTargets = @(
    (Join-Path $Desktop "Book Time.lnk"),
    (Join-Path $StartFolder "Book Time.lnk")
)

$Wsh = New-Object -ComObject WScript.Shell
foreach ($Path in $ShortcutTargets) {
    $Shortcut = $Wsh.CreateShortcut($Path)
    $Shortcut.TargetPath = "powershell.exe"
    $Shortcut.Arguments = "-ExecutionPolicy Bypass -File `"$Launcher`""
    $Shortcut.WorkingDirectory = $Root
    if (Test-Path -LiteralPath $IconTarget) {
        $Shortcut.IconLocation = $IconTarget
    } else {
        $Shortcut.IconLocation = "shell32.dll,220"
    }
    $Shortcut.Description = "Start Ollama, LM Studio, Book Time server, and open the Book Time webpage."
    $Shortcut.Save()
}

Write-Host "Created shortcuts:"
$ShortcutTargets | ForEach-Object { Write-Host " - $_" }
