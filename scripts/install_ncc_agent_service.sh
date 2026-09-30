#!/usr/bin/env sh
set -eu

[ "$(id -u)" -eq 0 ] || { echo "[FEHLER] Bitte mit sudo starten." >&2; exit 1; }
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
prefix=/opt/no0bz/ncc
config_dir=/etc/ncc
data_dir=/var/lib/ncc-agent
tailscale=0
if [ "${1:-}" = "--tailscale" ]; then tailscale=1; shift; fi

python3 -m venv "$prefix/venv"
"$prefix/venv/bin/python" -m pip install --upgrade "$root"
install -d -m 0755 "$config_dir" "$data_dir"

if [ ! -f "$config_dir/agent.env" ]; then
  server_url=${NCC_INSTALL_SERVER_URL:-${1:-}}
  if [ -z "$server_url" ]; then printf "NCC Server-URL: "; read -r server_url; fi
  if [ "$tailscale" -eq 1 ] && ! printf '%s' "$server_url" | grep -q '://'; then
    case "$server_url" in
      *:*) server_url="http://[$server_url]:8350" ;;
      *) server_url="http://$server_url:8350" ;;
    esac
  fi
  token=${NCC_INSTALL_AGENT_TOKEN:-}
  if [ -z "$token" ]; then
    printf "Individueller Agent-Token: "
    old_stty=$(stty -g); trap 'stty "$old_stty"' EXIT HUP INT TERM
    stty -echo; read -r token; stty "$old_stty"; trap - EXIT HUP INT TERM; printf "\n"
  fi
  [ -n "$server_url" ] && [ -n "$token" ] || { echo "[FEHLER] URL und Token sind erforderlich." >&2; exit 1; }
  NCC_VALIDATE_URL="$server_url" NCC_VALIDATE_INSECURE="$tailscale" "$prefix/venv/bin/python" -c \
    'import os; from ncc_service.doctor import validate_url; validate_url(os.environ["NCC_VALIDATE_URL"], os.environ["NCC_VALIDATE_INSECURE"] == "1")'
  umask 077
  {
    printf 'NCC_AGENT_SERVER_URL="%s"\n' "$server_url"
    printf 'NCC_AGENT_TOKEN="%s"\n' "$token"
    printf 'NCC_AGENT_DATA_DIR="%s"\n' "$data_dir"
    printf 'NCC_AGENT_ALLOW_INSECURE_HTTP=%s\n' "$tailscale"
  } > "$config_dir/agent.env"
else
  echo "[NCC] Vorhandene Agent-Konfiguration bleibt erhalten."
fi
chmod 0600 "$config_dir/agent.env"

install -m 0644 "$root/packaging/systemd/ncc-agent.service" /etc/systemd/system/ncc-agent.service
systemctl daemon-reload
systemctl enable --now ncc-agent.service
echo "[NCC] Agent-Dienst installiert. Status: systemctl status ncc-agent"
