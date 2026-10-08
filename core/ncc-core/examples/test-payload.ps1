param([string]$StateDir, [string]$Version = "0.6.0-beta.test")
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
@{ payload_version = $Version; status = "ready" } | ConvertTo-Json -Compress | Set-Content (Join-Path $StateDir "payload-health.json") -NoNewline
Start-Sleep -Seconds 300
