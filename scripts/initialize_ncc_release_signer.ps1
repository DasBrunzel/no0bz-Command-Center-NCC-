[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]{1,64}$')]
    [string]$KeyId = 'ncc-release-2026',
    [string]$SignerRoot = (Join-Path $env:ProgramData 'no0bz\NCC\release-signer')
)

# Creates a durable *encrypted* Ed25519 release signer on the release workstation.
# The private key never enters a manifest, the NCC server, or an agent. OpenSSL
# asks for its passphrase directly in the console and therefore it is never put
# on a PowerShell command line, in a transcript, or in this script's output.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Dieses Skript bitte in einer als Administrator gestarteten PowerShell ausfuehren.'
}

$openssl = Get-Command openssl.exe -ErrorAction SilentlyContinue
if (-not $openssl) { $openssl = Get-Command openssl -ErrorAction SilentlyContinue }
if (-not $openssl) { throw 'OpenSSL wurde nicht gefunden. Installiere Git for Windows oder OpenSSL und versuche es erneut.' }

$privateKey = Join-Path $SignerRoot "$KeyId-private.pem"
$publicPem = Join-Path $SignerRoot "$KeyId-public.pem"
$publicBase64 = Join-Path $SignerRoot "$KeyId-public.base64.txt"
$metadata = Join-Path $SignerRoot "$KeyId.json"
if (Test-Path -LiteralPath $privateKey) {
    throw "Ein privater Schluessel fuer '$KeyId' existiert bereits: $privateKey. Es wird nichts ueberschrieben."
}

New-Item -ItemType Directory -Force -Path $SignerRoot | Out-Null
try {
    Write-Host '[NCC] OpenSSL fragt jetzt zweimal nach einer neuen Passphrase fuer den Release-Schluessel.'
    Write-Host '[NCC] Diese Passphrase wird nicht gespeichert und nicht an NCC uebertragen.'
    & $openssl.Source genpkey -algorithm ED25519 -aes-256-cbc -out $privateKey
    if ($LASTEXITCODE -ne 0) { throw 'OpenSSL konnte keinen Ed25519-Privatschluessel erzeugen.' }

    & $openssl.Source pkey -in $privateKey -pubout -out $publicPem
    if ($LASTEXITCODE -ne 0) { throw 'OpenSSL konnte den oeffentlichen Schluessel nicht ableiten.' }
    $der = Join-Path $SignerRoot "$KeyId-public.der"
    & $openssl.Source pkey -pubin -in $publicPem -pubout -outform DER -out $der
    if ($LASTEXITCODE -ne 0) { throw 'OpenSSL konnte den oeffentlichen Schluessel nicht exportieren.' }
    $raw = [IO.File]::ReadAllBytes($der)
    Remove-Item -LiteralPath $der -Force -ErrorAction SilentlyContinue
    # SubjectPublicKeyInfo for an Ed25519 key is always the fixed 12-byte DER
    # header followed by the 32-byte raw verification key.
    if ($raw.Length -ne 44) { throw 'Unerwartetes Ed25519-Public-Key-Format.' }
    $public = [Convert]::ToBase64String($raw[12..43])
    [IO.File]::WriteAllText($publicBase64, "$public`n", [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText(
        $metadata,
        (@{ key_id = $KeyId; public_key_base64 = $public; created_at_utc = [DateTime]::UtcNow.ToString('o') } | ConvertTo-Json),
        [Text.UTF8Encoding]::new($false)
    )
    # The directory needs inheritable rights, while each existing key file
    # needs an explicit usable ACE. (OI)(CI) alone would not grant access to
    # the file itself on every Windows/NTFS combination.
    & icacls.exe $SignerRoot /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Die Ordnerberechtigungen fuer den Release-Schluessel konnten nicht sicher gesetzt werden.' }
    Get-ChildItem -LiteralPath $SignerRoot -Force -File | ForEach-Object {
        & icacls.exe $_.FullName /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Die Berechtigungen konnten nicht sicher gesetzt werden: $($_.Name)" }
    }

    [pscustomobject]@{
        Result = 'Encrypted NCC Ed25519 release signer created'
        KeyId = $KeyId
        PrivateKey = $privateKey
        PublicKeyBase64 = $public
        PublicKeyFile = $publicBase64
        NextStep = "Install the public key only: .\\scripts\\install_ncc_core_trusted_key.ps1 -KeyId $KeyId -PublicKey <PublicKeyBase64>"
    } | ConvertTo-Json
} catch {
    Remove-Item -LiteralPath $privateKey, $publicPem, $publicBase64, $metadata -Force -ErrorAction SilentlyContinue
    throw
}
