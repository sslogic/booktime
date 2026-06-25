$ErrorActionPreference = "Continue"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigPath = Join-Path $Root "booktime_config.json"
$Config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$Port = [int]$Config.booktime_port
$HostName = [string]$Config.booktime_host
if (-not $HostName) { $HostName = "127.0.0.1" }

function Test-Port($Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Test-Ollama($Url) {
    try {
        Invoke-RestMethod -Uri (($Url.TrimEnd('/')) + "/api/tags") -TimeoutSec 3 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Start-Ollama {
    if (Test-Ollama $Config.ollama_url) {
        Write-Host "Ollama is already running."
        return
    }
    $OllamaExe = [string]$Config.ollama_exe_path
    if (-not (Test-Path -LiteralPath $OllamaExe)) {
        $cmd = Get-Command ollama -ErrorAction SilentlyContinue
        if ($cmd) { $OllamaExe = $cmd.Source }
    }
    if ($OllamaExe -and (Test-Path -LiteralPath $OllamaExe)) {
        Write-Host "Starting Ollama..."
        Start-Process -FilePath $OllamaExe -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 3
    } else {
        Write-Host "Ollama executable not found. Download it at https://ollama.com/download or set it on the Book Time setup page."
    }
}

function Start-LMStudio {
    $LmExe = [string]$Config.lmstudio_exe_path
    if ($LmExe -and (Test-Path -LiteralPath $LmExe)) {
        $running = Get-Process | Where-Object { $_.Path -eq $LmExe } | Select-Object -First 1
        if (-not $running) {
            Write-Host "Starting LM Studio..."
            Start-Process -FilePath $LmExe
            Start-Sleep -Seconds 4
        } else {
            Write-Host "LM Studio is already running."
        }
    } else {
        Write-Host "LM Studio executable not found. Download it at https://lmstudio.ai/download or set it on the Book Time setup page."
    }

    $lms = Get-Command lms -ErrorAction SilentlyContinue
    if ($lms) {
        Write-Host "Starting LM Studio local server..."
        & lms server start | Out-Host
    } else {
        Write-Host "lms CLI not found. LM Studio local server may need to be started manually."
    }
}

function Start-BookTimeServer {
    if (Test-Port $Port) {
        Write-Host "Book Time server is already running on port $Port."
        return
    }
    Write-Host "Starting Book Time server..."
    Start-Process -FilePath "python" -ArgumentList "booktime_server.py" -WorkingDirectory $Root -WindowStyle Hidden
    Start-Sleep -Seconds 2
}

Start-Ollama
Start-LMStudio
Start-BookTimeServer

$Url = "http://$HostName`:$Port/"
Start-Process $Url
Write-Host ""
Write-Host "Book Time is open at $Url"
Write-Host "If the page says a model is missing, load your LM Studio writing model in LM Studio and confirm the Ollama model on Setup."
Write-Host "Downloads: Ollama https://ollama.com/download | LM Studio https://lmstudio.ai/download"
