[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$FirstSetup,
    [Parameter(Mandatory = $true)][string]$NextSetup,
    [Parameter(Mandatory = $true)][string]$NextManifest
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ncc_installer_ci_helpers.ps1')
$temporary = Join-Path $env:TEMP ('ncc-auto-update-ci-' + [Guid]::NewGuid().ToString('N'))
$openssl = @('C:\Program Files\Git\usr\bin\openssl.exe', 'C:\Program Files\Git\mingw64\bin\openssl.exe') |
    Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $openssl) { throw 'OpenSSL is required for the CI HTTPS feed.' }
$python = (Get-Command python -ErrorAction Stop).Source
$server = $null
$certificate = $null
New-Item -ItemType Directory -Force -Path $temporary | Out-Null
try {
    $crt = Join-Path $temporary 'server.crt'
    $key = Join-Path $temporary 'server.key'
    & $openssl genrsa -out $key 2048
    if ($LASTEXITCODE -ne 0) { throw 'Could not create CI HTTPS private key.' }
    & $openssl req -new -x509 -key $key -out $crt -days 1 -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost'
    if ($LASTEXITCODE -ne 0) { throw 'Could not create CI HTTPS certificate.' }
    $certificate = Import-Certificate -FilePath $crt -CertStoreLocation 'Cert:\LocalMachine\Root'
    Copy-Item -LiteralPath $NextSetup -Destination (Join-Path $temporary (Split-Path -Leaf $NextSetup))
    $feedFile = Join-Path $temporary 'update-feed.json'
    $validFeedJson = Get-Content -LiteralPath $NextManifest -Raw
    $unsignedFeed = $validFeedJson | ConvertFrom-Json
    $unsignedFeed.SignatureValue = ''
    [IO.File]::WriteAllText($feedFile, ($unsignedFeed | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
    $serverScript = Join-Path $temporary 'feed.py'
    @'
import http.server
import ssl
import sys

root, cert, key = sys.argv[1:]
handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(*args, directory=root, **kwargs)
server = http.server.ThreadingHTTPServer(("127.0.0.1", 18443), handler)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(certfile=cert, keyfile=key)
server.socket = context.wrap_socket(server.socket, server_side=True)
server.serve_forever()
'@ | Set-Content -LiteralPath $serverScript -Encoding ASCII
    $serverStdout = Join-Path $temporary 'feed.stdout.log'
    $serverStderr = Join-Path $temporary 'feed.stderr.log'
    $server = Start-Process -FilePath $python -ArgumentList @($serverScript, $temporary, $crt, $key) `
        -PassThru -WindowStyle Hidden -RedirectStandardOutput $serverStdout -RedirectStandardError $serverStderr
    $feedUrl = 'https://localhost:18443/update-feed.json'
    $ready = $false
    $lastFeedError = ''
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Seconds 1
        $lastFeedError = (& curl.exe --silent --fail --max-time 3 --noproxy '*' --cacert $crt $feedUrl | Out-String).Trim()
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        if ($server.HasExited) { break }
    }
    if (-not $ready) {
        Write-Output "FEED_SERVER_EXITED=$($server.HasExited) EXIT_CODE=$(if ($server.HasExited) { $server.ExitCode })"
        Write-Output "FEED_LAST_ERROR=$lastFeedError"
        if (Test-Path $serverStderr) { Get-Content $serverStderr -Tail 30 }
        throw 'CI HTTPS update feed did not become ready.'
    }

    $root = Join-Path $env:ProgramData 'no0bz\NCC Agent'
    $appDir = Join-Path $env:ProgramFiles 'no0bz\NCC Agent'
    $setupArgs = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SERVERURL=http://127.0.0.1:8350')
    $install = Start-NccInstallerAndWait -Path $FirstSetup -Arguments $setupArgs
    if ($install.ExitCode -ne 0) { throw "Version A installation failed: $($install.ExitCode)" }
    $config = Join-Path $root 'config\core.env'
    $pairing = Get-Content $config | Where-Object { $_ -like 'NCC_AGENT_PAIRING_ID=*' }
    $data = Join-Path $root 'data\ci-auto-update.txt'
    Set-Content -LiteralPath $data -Value 'preserve-through-auto-update' -NoNewline
    $hostLogPath = Join-Path $root 'logs\service-host.log'
    function Wait-ForRejection([string]$Pattern) {
        $until = (Get-Date).AddSeconds(80)
        do {
            Start-Sleep -Seconds 2
            $text = if (Test-Path -LiteralPath $hostLogPath) { Get-Content -LiteralPath $hostLogPath -Raw } else { '' }
            if ($text -match $Pattern) { return }
        } while ((Get-Date) -lt $until)
        throw "Agent did not reject an invalid installer release: $Pattern"
    }
    Wait-ForRejection 'Installer feed metadata is invalid'
    if ((Get-Content (Join-Path $appDir 'installer-version.txt') -Raw).Trim() -ne '0.6.0-beta.8-dev.1') {
        throw 'Unsigned installer was activated.'
    }
    $tamperedFeed = $validFeedJson | ConvertFrom-Json
    $tamperedFeed.SignatureValue = [Convert]::ToBase64String((New-Object byte[] 64))
    [IO.File]::WriteAllText($feedFile, ($tamperedFeed | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
    Restart-Service NccAgentCore
    Wait-ForRejection 'Installer signature verification failed'
    if ((Get-Content (Join-Path $appDir 'installer-version.txt') -Raw).Trim() -ne '0.6.0-beta.8-dev.1') {
        throw 'Tampered installer signature was activated.'
    }
    Copy-Item -LiteralPath $NextManifest -Destination $feedFile -Force
    Restart-Service NccAgentCore

    $deadline = (Get-Date).AddMinutes(4)
    $updated = $false
    do {
        Start-Sleep -Seconds 3
        try {
            $state = Get-Content (Join-Path $root 'core-state\state\core-state.json') -Raw | ConvertFrom-Json
            $version = (Get-Content (Join-Path $appDir 'installer-version.txt') -Raw).Trim()
            $running = (Get-Service NccAgentCore).Status -eq 'Running'
            $updated = $running -and $version -eq '0.6.0-beta.8-dev.2' -and
                $state.active_payload -eq '0.6.0-beta.8-ci.2' -and $state.health -eq 'healthy'
        } catch { }
    } while (-not $updated -and (Get-Date) -lt $deadline)
    if (-not $updated) {
        $log = Join-Path $root 'logs\service-host.log'
        if (Test-Path $log) { Get-Content $log -Tail 60 }
        $errorLog = Join-Path $env:ProgramData 'no0bz\NCC Agent Setup\install-error.log'
        if (Test-Path $errorLog) { Get-Content $errorLog -Tail 30 }
        throw 'Agent did not download and activate signed version B automatically.'
    }
    if ((Get-Content $data -Raw) -ne 'preserve-through-auto-update') { throw 'Agent data changed during automatic update.' }
    if ((Get-Content $config | Where-Object { $_ -like 'NCC_AGENT_PAIRING_ID=*' }) -ne $pairing) {
        throw 'Pairing identity changed during automatic update.'
    }
    $hostLog = Get-Content (Join-Path $root 'logs\service-host.log') -Raw
    if ($hostLog -notmatch 'Signed NCC Agent installer 0\.6\.0-beta\.8-dev\.2 launched') {
        throw 'Version B was not launched by the service updater.'
    }
    # Health is reported before Inno completes its final cleanup. Avoid
    # launching the uninstaller while the automatic setup still owns files.
    Start-Sleep -Seconds 15
    $uninstaller = Join-Path $appDir 'unins000.exe'
    $uninstall = Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -Wait -PassThru
    if ($uninstall.ExitCode -ne 0) { throw "Post-update uninstall failed: $($uninstall.ExitCode)" }
    Start-Sleep -Seconds 3
    if (Get-Service NccAgentCore -ErrorAction SilentlyContinue) { throw 'Agent service remains after uninstall.' }
    if (Test-Path $root) {
        Get-ChildItem -LiteralPath $root -Force -Recurse -ErrorAction SilentlyContinue |
            Select-Object -First 40 -ExpandProperty FullName | ForEach-Object { Write-Output "REMAINING=$_" }
        $uninstallLog = Join-Path $env:ProgramData 'no0bz\NCC Agent Setup\install-error.log'
        if (Test-Path $uninstallLog) { Get-Content $uninstallLog -Tail 30 }
        throw 'Agent data remains after uninstall.'
    }
} finally {
    if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue }
    if ($certificate) { Remove-Item -LiteralPath "Cert:\LocalMachine\Root\$($certificate.Thumbprint)" -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $temporary -Recurse -Force -ErrorAction SilentlyContinue
}
