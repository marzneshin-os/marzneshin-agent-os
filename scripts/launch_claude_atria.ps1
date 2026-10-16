# ==============================================================================
# Atria-Dawn-Preview Claude Code Launcher (PowerShell Edition)
# Connects Claude Code CLI to Shanghai AI Lab's 744B MoE Atria-Dawn Engine
# ==============================================================================

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$ClaudeArgs
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $ProjectRoot ".env.atria"

Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║             ⚡ ATRIA-DAWN CLAUDE CODE RUNNER ⚡                  ║" -ForegroundColor Cyan
Write-Host "║          744B MoE Agentic Intelligence (100M Free Tokens)        ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 1. Load Environment Configuration
$Key = $env:ATRIA_API_KEY
if (-not $Key -and (Test-Path $EnvFile)) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $k = $parts[0].Trim()
            $v = $parts[1].Trim().Trim('"').Trim("'")
            if ($k -eq "ATRIA_API_KEY" -or $k -eq "ANTHROPIC_AUTH_TOKEN") {
                if ($v) { $Key = $v }
            }
        }
    }
}

# 2. Check for API Key
if (-not $Key) {
    Write-Host "[!] ATRIA_API_KEY not found in .env.atria" -ForegroundColor Yellow
    Write-Host "You can get 100M free tokens at: https://api.atria-asi.ai" -ForegroundColor Cyan
    Write-Host ""
    $InputKey = Read-Host "Please enter your Atria API Key"
    if ($InputKey) {
        $Key = $InputKey.Trim()
        Add-Content -Path $EnvFile -Value "`nATRIA_API_KEY=`"$Key`"`nANTHROPIC_AUTH_TOKEN=`"$Key`""
        Write-Host "[✓] API Key saved to .env.atria" -ForegroundColor Green
    } else {
        Write-Host "[✗] Error: API Key is required to run Atria-Dawn." -ForegroundColor Red
        exit 1
    }
}

# 3. Connectivity Verification
Write-Host "[*] Verifying connectivity to Atria Gateway (api.atria-asi.ai)..." -ForegroundColor Cyan
try {
    $req = [System.Net.WebRequest]::Create("https://api.atria-asi.ai")
    $req.Timeout = 4000
    $resp = $req.GetResponse()
    $resp.Close()
    Write-Host "[✓] Gateway reachable." -ForegroundColor Green
} catch {
    Write-Host "[!] Warning: Gateway ping took longer than expected or was unreachable. Continuing anyway..." -ForegroundColor Yellow
}

# 4. Set Environment Variables
$env:ANTHROPIC_BASE_URL = "https://api.atria-asi.ai"
$env:ANTHROPIC_AUTH_TOKEN = $Key
$env:ANTHROPIC_API_KEY = $Key

Write-Host ""
Write-Host "Target Model:     Atria-Dawn-Preview (744B MoE)" -ForegroundColor Green
Write-Host "Base URL:         https://api.atria-asi.ai" -ForegroundColor Green
Write-Host "Project Context:  $ProjectRoot" -ForegroundColor Cyan
Write-Host ""
Write-Host ">> Launching Claude Code CLI with Atria Backend..." -ForegroundColor Green
Write-Host "──────────────────────────────────────────────────────────────────"

Set-Location $ProjectRoot

# Launch claude
& claude --model Atria-Dawn-Preview @ClaudeArgs
