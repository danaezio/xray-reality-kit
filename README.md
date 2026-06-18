# Xray Reality Kit

One-command installer for a private Xray VPN server:

- VLESS
- REALITY
- XHTTP transport
- Cloudflare SNI target by default
- BBR speed tuning
- minimal GUI for creating/deleting client keys

The GUI edits only the `clients` list in `/usr/local/etc/xray/config.json`, validates the config, backs it up, and restarts Xray.

## Quick Install On New Ubuntu VPS

Copy this repository to the VPS, then run:

```bash
sudo bash scripts/install.sh --host YOUR_VPS_IP
```

Or with a domain:

```bash
sudo bash scripts/install.sh --host vpn.example.com
```

At the end, the script prints:

- VLESS import link
- panel token
- panel URL

## If Xray Is Already Installed

The installer will stop if `/usr/local/etc/xray/config.json` already exists.

To replace it after creating a backup:

```bash
sudo bash scripts/install.sh --host YOUR_VPS_IP --force
```

## Public GUI Access

By default, the GUI listens on `127.0.0.1:8765`.

Open it from your computer with:

```bash
ssh -L 8765:127.0.0.1:8765 root@YOUR_VPS_IP
```

Then open:

```text
http://127.0.0.1:8765
```

For direct access over the internet:

```bash
sudo bash scripts/install.sh --host YOUR_VPS_IP --panel-public
```

Then open:

```text
http://YOUR_VPS_IP:8765
```

Direct mode is plain HTTP. Use a strong token and do not share the URL.

## Useful Commands

```bash
systemctl status xray --no-pager
systemctl status xray-key-panel --no-pager
journalctl -u xray -n 80 --no-pager
journalctl -u xray-key-panel -n 80 --no-pager
grep PANEL_TOKEN /etc/xray-key-panel.env
```

## Defaults

```text
Port: 443
Transport: xhttp
XHTTP path: /xray-cloud
SNI target: www.cloudflare.com
Panel: 127.0.0.1:8765
```

Override defaults:

```bash
sudo bash scripts/install.sh \
  --host YOUR_VPS_IP \
  --sni www.cloudflare.com \
  --path /xray-cloud \
  --client iphone-main
```

## Updating Only The Panel

```bash
sudo bash scripts/install-panel.sh
sudo systemctl restart xray-key-panel
```

This does not modify the Xray config.
