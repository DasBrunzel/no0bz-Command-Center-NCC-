[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Agent", "Server")]
    [string]$Component,
    [switch]$Tailscale,
    [ValidatePattern('^[A-Za-z0-9.:-]+$')]
    [string]$ServerUrl,
    [switch]$ReplaceConfig,
    [ValidateSet("Service", "Task")]
    [string]$AgentMode = "Service"
)

$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Component $Component"
    if ($Tailscale) { $arguments += " -Tailscale" }
    if ($ServerUrl) { $arguments += " -ServerUrl $ServerUrl" }
    if ($ReplaceConfig) { $arguments += " -ReplaceConfig" }
    if ($AgentMode -eq "Task") { $arguments += " -AgentMode Task" }
    Start-Process powershell.exe -Verb RunAs -ArgumentList $arguments
    exit
}

function Read-SecretText([string]$Prompt) {
    $secure = Read-Host $Prompt -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
}

function Quote-DotEnv([string]$Value) {
    if ($Value.Contains("`r") -or $Value.Contains("`n")) { throw "Konfigurationswerte dürfen keine Zeilenumbrüche enthalten." }
    return '"' + $Value.Replace('\', '\\').Replace('"', '\"') + '"'
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$installRoot = Join-Path $env:ProgramData "no0bz\NCC"
$venvRoot = Join-Path $installRoot "venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$configRoot = Join-Path $installRoot "config"
$migrationRoot = Join-Path $installRoot "migrations"
New-Item -ItemType Directory -Force -Path $installRoot, $configRoot, (Join-Path $installRoot "logs") | Out-Null

if (-not (Test-Path $venvPython)) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) { & $launcher.Source -3 -m venv $venvRoot }
    else { & (Get-Command python -ErrorAction Stop).Source -m venv $venvRoot }
}
& $venvPython -m pip install --upgrade $projectRoot
if ($LASTEXITCODE -ne 0) { throw "NCC konnte nicht in die Dienstumgebung installiert werden." }

$name = $Component.ToLowerInvariant()
$configPath = Join-Path $configRoot "$name.env"
if (-not (Test-Path $configPath) -or $ReplaceConfig) {
    if ($Component -eq "Agent") {
        $configuredServerUrl = ""
        if ($Tailscale) {
            $target = $ServerUrl
            if (-not $target) { $target = Read-Host "Tailscale-IP oder MagicDNS-Name des NCC-Servers" }
            if ($target -notmatch '^[A-Za-z0-9.:-]+$') { throw "Ungültige Tailscale-Adresse." }
            if ($target.Contains(":")) { $configuredServerUrl = "http://[${target}]:8350" }
            else { $configuredServerUrl = "http://${target}:8350" }
        } else {
            $configuredServerUrl = if ($ServerUrl) { $ServerUrl } else { Read-Host "NCC Server-URL (HTTPS)" }
        }
        if (-not $configuredServerUrl) { throw "Eine Server-URL ist erforderlich." }
        $env:NCC_VALIDATE_URL = $configuredServerUrl
        $env:NCC_VALIDATE_INSECURE = [int]$Tailscale.IsPresent
        try {
            & $venvPython -c "import os; from ncc_service.doctor import validate_url; validate_url(os.environ['NCC_VALIDATE_URL'], os.environ['NCC_VALIDATE_INSECURE'] == '1')"
            if ($LASTEXITCODE -ne 0) { throw "Die Server-URL ist nicht zulässig." }
        } finally {
            Remove-Item Env:NCC_VALIDATE_URL, Env:NCC_VALIDATE_INSECURE -ErrorAction SilentlyContinue
        }
        $dataRoot = Join-Path $installRoot "agent-data"
        New-Item -ItemType Directory -Force -Path $dataRoot | Out-Null
        $pairingId = & $venvPython -c "import secrets; print(secrets.token_urlsafe(18))"
        $pairingSecret = & $venvPython -c "import secrets; print(secrets.token_urlsafe(32))"
        $lines = @(
            "NCC_AGENT_SERVER_URL=$(Quote-DotEnv $configuredServerUrl)",
            "NCC_AGENT_PAIRING_ID=$(Quote-DotEnv $pairingId)",
            "NCC_AGENT_PAIRING_SECRET=$(Quote-DotEnv $pairingSecret)",
            "NCC_AGENT_DATA_DIR=$(Quote-DotEnv $dataRoot)",
            "NCC_AGENT_ALLOW_INSECURE_HTTP=$([int]$Tailscale.IsPresent)"
        )
    } else {
        $bindHost = "127.0.0.1"
        if ($Tailscale) {
            $tailscaleCommand = Get-Command tailscale -ErrorAction SilentlyContinue
            if (-not $tailscaleCommand) { throw "Tailscale wurde nicht gefunden." }
            $bindHost = (& $tailscaleCommand.Source ip -4 | Select-Object -First 1).Trim()
            if ($bindHost -notmatch '^100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.') { throw "Keine gültige Tailscale-IP gefunden." }
        } else {
            $enteredHost = Read-Host "Bind-Adresse des Servers [127.0.0.1]"
            if ($enteredHost) { $bindHost = $enteredHost }
        }
        $databaseUrl = Read-SecretText "PostgreSQL-Verbindungs-URL"
        if (-not $databaseUrl) { throw "Die Datenbank-URL ist erforderlich." }
        $dashboardToken = & $venvPython -c "import secrets; print(secrets.token_urlsafe(32))"
        $lines = @(
            "NCC_SERVER_HOST=$(Quote-DotEnv $bindHost)",
            "NCC_SERVER_PORT=8350",
            "NCC_SERVER_DATABASE_URL=$(Quote-DotEnv $databaseUrl)",
            "NCC_SERVER_DASHBOARD_TOKEN=$(Quote-DotEnv $dashboardToken)",
            "NCC_SERVER_DASHBOARD_ALLOW_LOOPBACK_WITHOUT_TOKEN=0"
        )
        if (Test-Path $migrationRoot) { Remove-Item -LiteralPath $migrationRoot -Recurse -Force }
        Copy-Item -LiteralPath (Join-Path $projectRoot "migrations") -Destination $migrationRoot -Recurse
        Copy-Item -LiteralPath (Join-Path $projectRoot "alembic.ini") -Destination (Join-Path $installRoot "alembic.ini") -Force
    }
    [IO.File]::WriteAllLines($configPath, $lines, [Text.UTF8Encoding]::new($false))
    $configAction = if ($ReplaceConfig) { "ersetzt" } else { "geschützt gespeichert" }
    Write-Host "[NCC] Neue $Component-Konfiguration wurde $configAction."
    if ($Component -eq "Server") { Write-Host "[NCC] Dashboard-Token (jetzt sicher notieren): $dashboardToken" }
} else {
    Write-Host "[NCC] Vorhandene $Component-Konfiguration bleibt erhalten."
    if ($Component -eq "Server") {
        if (Test-Path $migrationRoot) { Remove-Item -LiteralPath $migrationRoot -Recurse -Force }
        Copy-Item -LiteralPath (Join-Path $projectRoot "migrations") -Destination $migrationRoot -Recurse
        Copy-Item -LiteralPath (Join-Path $projectRoot "alembic.ini") -Destination (Join-Path $installRoot "alembic.ini") -Force
    }
}
& icacls.exe $configPath /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' | Out-Null

if ($Component -eq "Agent") {
    $pairingId = & $venvPython -c "from pathlib import Path; from ncc_service.environment import load_environment_file; e=load_environment_file(Path(r'$configPath')); print(e['NCC_AGENT_PAIRING_ID'])"
    $configuredServerUrl = & $venvPython -c "from pathlib import Path; from ncc_service.environment import load_environment_file; e=load_environment_file(Path(r'$configPath')); print(e['NCC_AGENT_SERVER_URL'])"
    if ($LASTEXITCODE -ne 0 -or -not $pairingId -or -not $configuredServerUrl) {
        throw "Die vorhandene Agent-Konfiguration konnte nicht für das Browser-Pairing gelesen werden."
    }
}

if ($Component -eq "Server") {
    & $venvPython -m ncc_service.migrate --config $configPath --alembic (Join-Path $installRoot "alembic.ini")
    if ($LASTEXITCODE -ne 0) { throw "Die Datenbankmigration ist fehlgeschlagen." }
}

if ($Component -eq "Server" -and $AgentMode -ne "Service") {
    throw "Der Task-Modus ist ausschließlich für den NCC-Agenten verfügbar."
}

if ($Component -eq "Agent" -and $AgentMode -eq "Task") {
    $taskName = "NccAgent"
    $service = Get-Service -Name $taskName -ErrorAction SilentlyContinue
    if ($service) {
        if ($service.Status -ne "Stopped") { Stop-Service -Name $taskName -Force -ErrorAction SilentlyContinue }
        & $venvPython -m ncc_service.windows agent remove
        if ($LASTEXITCODE -ne 0) { throw "Der bisherige Windows-Dienst konnte nicht entfernt werden." }
    }
    $taskCommand = "`"$venvPython`" -m ncc_service.task_runner agent"
    & schtasks.exe /Create /TN $taskName /SC ONSTART /RU SYSTEM /RL HIGHEST /TR $taskCommand /F | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Die NCC-Agent-Systemaufgabe konnte nicht erstellt werden." }
    & schtasks.exe /Run /TN $taskName | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Die NCC-Agent-Systemaufgabe konnte nicht gestartet werden." }
    Write-Host "[NCC] Agent läuft als Systemaufgabe und startet automatisch mit Windows."
    Write-Host "[NCC] Konfiguration: $configPath"
    Write-Host "[NCC] Logdatei: $(Join-Path $installRoot 'logs\agent.log')"
    Write-Host "[NCC] Browser-Freigabe: $configuredServerUrl/?pair=$pairingId"
    exit
}

$serviceName = if ($Component -eq "Agent") { "NccAgent" } else { "NccServer" }
$serviceExists = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
$verb = if ($serviceExists) { "update" } else { "install" }
& $venvPython -m ncc_service.windows $name --startup auto $verb
if ($LASTEXITCODE -ne 0) { throw "Der Windows-Dienst konnte nicht registriert werden." }
& sc.exe failure $serviceName reset= 86400 actions= restart/5000/restart/15000/restart/60000 | Out-Null
if ($serviceExists -and $serviceExists.Status -eq "Running") { Restart-Service -Name $serviceName }
else { Start-Service -Name $serviceName }
Write-Host "[NCC] $Component-Dienst läuft. Konfiguration: $configPath"
Write-Host "[NCC] Logdatei: $(Join-Path $installRoot "logs\$name.log")"
if ($Component -eq "Agent" -and $pairingId) { Write-Host "[NCC] Browser-Freigabe: $configuredServerUrl/?pair=$pairingId" }
