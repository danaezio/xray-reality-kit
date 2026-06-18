#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/xray-key-panel"
ENV_FILE="/etc/xray-key-panel.env"
SERVICE_FILE="/etc/systemd/system/xray-key-panel.service"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo bash scripts/install-panel.sh"
  exit 1
fi

install -d -m 0755 "$APP_DIR"
install -m 0755 "$REPO_DIR/panel/app.py" "$APP_DIR/app.py"

if [[ ! -f "$ENV_FILE" ]]; then
  PANEL_TOKEN="$(openssl rand -hex 16)"
  PANEL_SECRET="$(openssl rand -hex 32)"
  cat > "$ENV_FILE" <<EOF
PANEL_HOST=127.0.0.1
PANEL_PORT=8765
PANEL_TOKEN=$PANEL_TOKEN
PANEL_SECRET=$PANEL_SECRET
XRAY_CONFIG=/usr/local/etc/xray/config.json
PANEL_SETTINGS=/usr/local/etc/xray/key-panel-settings.json
EOF
  chmod 600 "$ENV_FILE"
fi

cat > "$SERVICE_FILE" <<'EOF'
[Unit]
Description=Xray Key Panel
After=network-online.target xray.service
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=/etc/xray-key-panel.env
ExecStart=/usr/bin/python3 /opt/xray-key-panel/app.py
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now xray-key-panel

echo "Panel installed: http://127.0.0.1:8765"
echo "Token: $(grep '^PANEL_TOKEN=' "$ENV_FILE" | cut -d= -f2-)"
