# Security Policy

## Threat model

NCC handles process control and LAN file exchange. Its main risks are unauthorized
process termination, DNS rebinding, cross-site requests, malicious uploads and leaked
tokens. NCC therefore binds to loopback by default, authenticates all writes and
WebSockets outside explicitly allowed local access, validates Host and Origin headers,
rate-limits sensitive routes, sanitizes uploads and emits restrictive browser headers.

NCC sends no telemetry or usage data to third parties. Optional providers communicate
only with explicitly configured local tools or the configured NCC master.

## LAN deployment

Bind to `0.0.0.0` only deliberately. Put NCC behind a trusted HTTPS reverse proxy,
restrict ingress with a firewall, rotate `NCC_TOKEN`, and do not expose port 8350 to
the public internet. Use a private network or VPN between nodes.

## Reporting

Please use GitHub private vulnerability reporting and avoid publishing exploit details
before a fix is available. Include NCC version, platform, reproduction steps and impact.

