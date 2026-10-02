[CmdletBinding()]
param(
    [int]$RetentionDays = 14,
    [switch]$InstallSchedule
)

$ErrorActionPreference = "Stop"
$root = Join-Path $env:ProgramData "no0bz\NCC"
$configPath = Join-Path $root "config\server.env"
$backupRoot = Join-Path $root "backups"
$logPath = Join-Path $root "logs\backup.log"

function Get-DotEnvValue([string]$Path, [string]$Name) {
    $line = Get-Content -LiteralPath $Path | Where-Object { $_ -match "^$([regex]::Escape($Name))=(.*)$" } | Select-Object -First 1
    if (-not $line) { throw "$Name wurde nicht in der Server-Konfiguration gefunden." }
    $value = ($line -split "=", 2)[1].Trim()
    if ($value.Length -ge 2 -and $value[0] -eq '"' -and $value[$value.Length - 1] -eq '"') { $value = $value.Substring(1, $value.Length - 2) }
    return $value.Replace('\\"', '"').Replace('\\', '\')
}

function Find-PgDump {
    $command = Get-Command pg_dump.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $candidate = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\pg_dump.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1
    if ($candidate) { return $candidate.FullName }
    throw "pg_dump.exe wurde nicht gefunden. PostgreSQL-Client-Werkzeuge sind erforderlich."
}

function Get-PostgresConnection([string]$ConnectionString) {
    $uri = [Uri]$ConnectionString
    if ($uri.Scheme -notin @("postgres", "postgresql", "postgresql+psycopg") -or -not $uri.Host) {
        throw "Die NCC_SERVER_DATABASE_URL ist keine verwendbare PostgreSQL-Verbindung."
    }
    $parts = $uri.UserInfo.Split(":", 2)
    if ($parts.Count -ne 2 -or [string]::IsNullOrWhiteSpace($parts[0]) -or [string]::IsNullOrWhiteSpace($uri.AbsolutePath.TrimStart("/"))) {
        throw "Die NCC_SERVER_DATABASE_URL enthält keinen vollständigen Datenbank-Zugang."
    }
    return @{
        Host = $uri.Host
        Port = if ($uri.Port -gt 0) { $uri.Port } else { 5432 }
        User = [Uri]::UnescapeDataString($parts[0])
        Password = [Uri]::UnescapeDataString($parts[1])
        Database = [Uri]::UnescapeDataString($uri.AbsolutePath.TrimStart("/"))
    }
}

if ($InstallSchedule) {
    $managedScriptDirectory = Join-Path $root "scripts"
    $managedScriptPath = Join-Path $managedScriptDirectory "backup_ncc_postgres.ps1"
    New-Item -ItemType Directory -Force -Path $managedScriptDirectory | Out-Null
    if ((Resolve-Path -LiteralPath $PSCommandPath).Path -ne $managedScriptPath) {
        Copy-Item -LiteralPath $PSCommandPath -Destination $managedScriptPath -Force
    }
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$managedScriptPath`" -RetentionDays $RetentionDays"
    $trigger = New-ScheduledTaskTrigger -Daily -At 3:30AM
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    Register-ScheduledTask -TaskName "NCC PostgreSQL Backup" -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
    Write-Host "[NCC] Tägliches Backup um 03:30 Uhr eingerichtet; Aufbewahrung: $RetentionDays Tage."
    exit 0
}

if ($RetentionDays -lt 1 -or $RetentionDays -gt 365) { throw "RetentionDays muss zwischen 1 und 365 liegen." }
if (-not (Test-Path $configPath)) { throw "NCC-Server-Konfiguration wurde nicht gefunden: $configPath" }

New-Item -ItemType Directory -Force -Path $backupRoot, (Split-Path -Parent $logPath) | Out-Null
$aclArguments = @($backupRoot, "/inheritance:r", "/grant:r", "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F")
& icacls.exe @aclArguments | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Die Zugriffsrechte für den NCC-Backup-Ordner konnten nicht gesetzt werden." }
$databaseUrl = Get-DotEnvValue $configPath "NCC_SERVER_DATABASE_URL"
$database = Get-PostgresConnection $databaseUrl
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$temporary = Join-Path $backupRoot "ncc-$timestamp.dump.partial"
$destination = Join-Path $backupRoot "ncc-$timestamp.dump"

try {
    $env:PGPASSWORD = $database.Password
    & (Find-PgDump) --format=custom "--file=$temporary" "--host=$($database.Host)" "--port=$($database.Port)" "--username=$($database.User)" $database.Database 2>> $logPath
    if ($LASTEXITCODE -ne 0) { throw "pg_dump ist mit Exit-Code $LASTEXITCODE fehlgeschlagen." }
    Move-Item -LiteralPath $temporary -Destination $destination
    Get-ChildItem -LiteralPath $backupRoot -Filter "ncc-*.dump" -File |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$RetentionDays) } |
        Remove-Item -Force
    Add-Content -LiteralPath $logPath -Value "$(Get-Date -Format o) backup complete: $([IO.Path]::GetFileName($destination))"
} catch {
    Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
    Add-Content -LiteralPath $logPath -Value "$(Get-Date -Format o) backup failed: $($_.Exception.Message)"
    throw
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}
