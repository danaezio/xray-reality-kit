#!/usr/bin/env bash
set -euo pipefail

XRAY_CONFIG="/usr/local/etc/xray/config.json"
XRAY_DIR="/usr/local/etc/xray"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  sudo bash scripts/install.sh --host VPS_IP_OR_DOMAIN [options]

Options:
  --host VALUE          Public VPS IP or domain for generated links.
  --sni VALUE           REALITY target/SNI. Default: www.cloudflare.com
  --path VALUE          XHTTP path. Default: /xray-cloud
  --client VALUE        First client name. Default: main
  --panel-public        Expose panel on 0.0.0.0:8765.
  --force              Replace existing /usr/local/etc/xray/config.json after backup.

Examples:
  sudo bash scripts/install.sh --host 1.2.3.4
  sudo bash scripts/install.sh --host vpn.example.com --client iphone
EOF
}

HOST=""
SNI="www.cloudflare.com"
XHTTP_PATH="/xray-cloud"
CLIENT_NAME="main"
PANEL_PUBLIC="0"
FORCE="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="${2:-}"; shift 2 ;;
    --sni) SNI="${2:-}"; shift 2 ;;
    --path) XHTTP_PATH="${2:-}"; shift 2 ;;
    --client) CLIENT_NAME="${2:-}"; shift 2 ;;
    --panel-public) PANEL_PUBLIC="1"; shift ;;
    --force) FORCE="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo bash scripts/install.sh --host VPS_IP_OR_DOMAIN"
  exit 1
fi

if [[ -z "$HOST" ]]; then
  echo "Missing --host"
  usage
  exit 1
fi

apt update
apt install -y curl unzip openssl python3 ufw ca-certificates

if ! command -v xray >/dev/null 2>&1; then
  bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
fi

install -d -m 0755 "$XRAY_DIR"

if [[ -f "$XRAY_CONFIG" && "$FORCE" != "1" ]]; then
  echo "Existing config found: $XRAY_CONFIG"
  echo "Run with --force to replace it after backup."
  exit 1
fi

if [[ -f "$XRAY_CONFIG" ]]; then
  cp "$XRAY_CONFIG" "$XRAY_CONFIG.backup-$(date +%Y%m%d-%H%M%S)"
fi

UUID="$(xray uuid)"
KEYS="$(xray x25519)"
PRIVATE_KEY="$(printf '%s\n' "$KEYS" | awk -F': *' '/Private key:|PrivateKey:/ {print $2}')"
PUBLIC_KEY="$(printf '%s\n' "$KEYS" | awk -F': *' '/Public key:|PublicKey:/ {print $2}')"
SHORT_ID="$(openssl rand -hex 8)"

if [[ -z "$PRIVATE_KEY" || -z "$PUBLIC_KEY" ]]; then
  echo "Could not generate x25519 keys. Raw output:"
  echo "$KEYS"
  exit 1
fi

cat > "$XRAY_CONFIG" <<EOF
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "tag": "vless-reality-xhttp",
      "listen": "0.0.0.0",
      "port": 443,
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "$UUID",
            "email": "$CLIENT_NAME"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "xhttp",
        "xhttpSettings": {
          "path": "$XHTTP_PATH"
        },
        "security": "reality",
        "realitySettings": {
          "show": false,
          "dest": "$SNI:443",
          "serverNames": [
            "$SNI"
          ],
          "privateKey": "$PRIVATE_KEY",
          "shortIds": [
            "$SHORT_ID"
          ],
          "xver": 0
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": [
          "http",
          "tls"
        ]
      }
    }
  ],
  "outbounds": [
    {
      "tag": "direct",
      "protocol": "freedom",
      "settings": {
        "domainStrategy": "UseIPv4"
      }
    },
    {
      "tag": "block",
      "protocol": "blackhole"
    }
  ],
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
      {
        "type": "field",
        "ip": [
          "geoip:private"
        ],
        "outboundTag": "block"
      }
    ]
  }
}
EOF

xray run -test -config "$XRAY_CONFIG"
systemctl enable xray
systemctl restart xray

cat > /etc/sysctl.d/99-xray-speed.conf <<'EOF'
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
net.ipv4.tcp_mtu_probing=1
net.ipv4.tcp_slow_start_after_idle=0
EOF
sysctl --system >/dev/null

ufw allow 22/tcp
ufw allow 443/tcp
ufw --force enable

bash "$REPO_DIR/scripts/install-panel.sh"

cat > /usr/local/etc/xray/key-panel-settings.json <<EOF
{
  "host": "$HOST",
  "publicKey": "$PUBLIC_KEY"
}
EOF
chmod 600 /usr/local/etc/xray/key-panel-settings.json

if [[ "$PANEL_PUBLIC" == "1" ]]; then
  sed -i 's/^PANEL_HOST=.*/PANEL_HOST=0.0.0.0/' /etc/xray-key-panel.env
  ufw allow 8765/tcp
  systemctl restart xray-key-panel
fi

ENCODED_PATH="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$XHTTP_PATH")"
ENCODED_NAME="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$CLIENT_NAME")"
LINK="vless://$UUID@$HOST:443?encryption=none&security=reality&sni=$SNI&fp=chrome&pbk=$PUBLIC_KEY&sid=$SHORT_ID&type=xhttp&path=$ENCODED_PATH#$ENCODED_NAME"

cat <<EOF

Done.

VLESS link:
$LINK

Panel:
  Local on VPS: http://127.0.0.1:8765
  Token: $(grep '^PANEL_TOKEN=' /etc/xray-key-panel.env | cut -d= -f2-)

Open panel via SSH tunnel:
  ssh -L 8765:127.0.0.1:8765 root@$HOST
  http://127.0.0.1:8765

If installed with --panel-public:
  http://$HOST:8765

EOF
