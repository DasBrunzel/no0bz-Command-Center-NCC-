#!/usr/bin/env sh
set -eu

[ "$(id -u)" -eq 0 ] || { echo "[FEHLER] Bitte mit sudo starten." >&2; exit 1; }
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
prefix=/opt/no0bz/ncc
config_dir=/etc/ncc
tailscale=0
if [ "${1:-}" = "--tailscale" ]; then tailscale=1; shift; fi

id ncc >/dev/null 2>&1 || useradd --system --home-dir "$prefix" --shell /usr/sbin/nologin ncc
python3 -m venv "$prefix/venv"
"$prefix/venv/bin/python" -m pip install --upgrade "$root"
install -d -o ncc -g ncc -m 0755 "$prefix" "$config_dir"
rm -rf "$prefix/migrations"
cp -R "$root/migrations" "$prefix/migrations"
install -m 0644 "$root/alembic.ini" "$prefix/alembic.ini"
chown -R ncc:ncc "$prefix/migrations" "$prefix/alembic.ini"

if [ ! -f "$config_dir/server.env" ]; then
  bind_host=${NCC_INSTALL_BIND_HOST:-127.0.0.1}
  if [ "$tailscale" -eq 1 ]; then
    command -v tailscale >/dev/null 2>&1 || { echo "[FEHLER] Tailscale wurde nicht gefunden." >&2; exit 1; }
    bind_host=${NCC_INSTALL_BIND_HOST:-$(tailscale ip -4 | head -n 1)}
  fi
  database_url=${NCC_INSTALL_DATABASE_URL:-}
  if [ -z "$database_url" ]; then printf "PostgreSQL-Verbindungs-URL: "; read -r database_url; fi
  dashboard_token=${NCC_INSTALL_DASHBOARD_TOKEN:-}
  if [ -z "$dashboard_token" ]; then dashboard_token=$("$prefix/venv/bin/python" -c 'import secrets; print(secrets.token_urlsafe(32))'); fi
  [ -n "$database_url" ] || { echo "[FEHLER] Die Datenbank-URL ist erforderlich." >&2; exit 1; }
  umask 077
  {
    printf 'NCC_SERVER_HOST="%s"\n' "$bind_host"
    printf 'NCC_SERVER_PORT=8350\n'
    printf 'NCC_SERVER_DATABASE_URL="%s"\n' "$database_url"
    printf 'NCC_SERVER_DASHBOARD_TOKEN="%s"\n' "$dashboard_token"
    printf 'NCC_SERVER_DASHBOARD_ALLOW_LOOPBACK_WITHOUT_TOKEN=0\n'
  } > "$config_dir/server.env"
  echo "[NCC] Dashboard-Token (jetzt sicher notieren): $dashboard_token"
  echo "[NCC] Der Token wurde außerdem geschützt in $config_dir/server.env gespeichert."
else
  echo "[NCC] Vorhandene Server-Konfiguration bleibt erhalten."
fi
chown root:ncc "$config_dir/server.env"
chmod 0640 "$config_dir/server.env"

install -m 0644 "$root/packaging/systemd/ncc-server.service" /etc/systemd/system/ncc-server.service
systemctl daemon-reload
systemctl enable --now ncc-server.service
echo "[NCC] Server-Dienst installiert. Status: systemctl status ncc-server"
