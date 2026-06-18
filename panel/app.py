#!/usr/bin/env python3
import base64
import hashlib
import hmac
import html
import json
import os
import shutil
import subprocess
import time
import uuid
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode


CONFIG_PATH = Path(os.environ.get("XRAY_CONFIG", "/usr/local/etc/xray/config.json"))
SETTINGS_PATH = Path(os.environ.get("PANEL_SETTINGS", "/usr/local/etc/xray/key-panel-settings.json"))
BIND_HOST = os.environ.get("PANEL_HOST", "127.0.0.1")
BIND_PORT = int(os.environ.get("PANEL_PORT", "8765"))
PANEL_TOKEN = os.environ.get("PANEL_TOKEN", "")
PANEL_SECRET = os.environ.get("PANEL_SECRET", PANEL_TOKEN or "change-me")


CSS = """
:root {
  color-scheme: dark;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #0d1117;
  color: #e6edf3;
  --bg: #0d1117;
  --panel: #151b23;
  --panel-strong: #1c2430;
  --line: #303946;
  --line-soft: #242c38;
  --text: #e6edf3;
  --muted: #9aa7b5;
  --accent: #3b82f6;
  --accent-hover: #2563eb;
  --accent-soft: #10284d;
  --danger: #ef4444;
  --danger-hover: #dc2626;
  --ok-bg: #102f24;
  --ok-text: #8ee6b0;
  --warn-bg: #2c240d;
  --warn-text: #ffd37a;
  --error-bg: #35191d;
  --error-text: #ffb4a8;
}
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; }
main { max-width: 1120px; margin: 0 auto; padding: 28px 18px 48px; }
header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 22px; }
h1 { margin: 0 0 6px; font-size: 26px; letter-spacing: 0; }
h2 { margin: 0 0 14px; font-size: 18px; }
p { margin: 0; color: var(--muted); }
.grid { display: grid; grid-template-columns: 1fr; gap: 16px; }
.card { background: linear-gradient(180deg, var(--panel), #121820); border: 1px solid var(--line); border-radius: 8px; padding: 18px; box-shadow: 0 18px 45px rgba(0, 0, 0, .22); }
.toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
label { display: block; font-size: 13px; font-weight: 650; margin-bottom: 6px; color: #c9d5e1; }
input { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 10px 11px; font: inherit; background: #0f141b; color: var(--text); }
input::placeholder { color: #6f7c8b; }
input:focus { outline: 2px solid rgba(59, 130, 246, .35); border-color: var(--accent); }
button, .button { border: 0; border-radius: 6px; background: var(--accent); color: #fff; padding: 10px 13px; font-weight: 700; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; min-height: 38px; transition: background .15s ease, transform .15s ease, border-color .15s ease; }
button:hover, .button:hover { background: var(--accent-hover); }
button:active, .button:active { transform: translateY(1px); }
button.secondary, .button.secondary { background: #222b37; color: #d5dde7; border: 1px solid #354253; }
button.secondary:hover, .button.secondary:hover { background: #2a3544; }
button.danger { background: var(--danger); }
button.danger:hover { background: var(--danger-hover); }
button:disabled { opacity: .55; cursor: default; }
.notice { border-radius: 6px; padding: 11px 12px; margin-bottom: 16px; background: var(--warn-bg); color: var(--warn-text); border: 1px solid #5a4514; }
.error { background: var(--error-bg); color: var(--error-text); border-color: #71323a; white-space: pre-wrap; }
.ok { background: var(--ok-bg); color: var(--ok-text); border-color: #1f6b4d; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; border-bottom: 1px solid var(--line-soft); padding: 12px 8px; vertical-align: top; }
th { font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: #7f8da0; }
code, textarea { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
textarea { width: 100%; min-height: 78px; resize: vertical; border: 1px solid var(--line); border-radius: 6px; padding: 10px; background: #0f141b; color: #d6e2ef; font-size: 12px; }
textarea:focus { outline: 2px solid rgba(59, 130, 246, .35); border-color: var(--accent); }
.muted { color: var(--muted); font-size: 13px; }
.pill { display: inline-flex; border-radius: 999px; padding: 4px 8px; font-size: 12px; font-weight: 700; background: var(--accent-soft); color: #bdd7ff; }
.client-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.login { max-width: 420px; margin: 10vh auto; }
@media (max-width: 720px) {
  header, .row { display: block; }
  .row > div { margin-bottom: 12px; }
  table, thead, tbody, tr, th, td { display: block; }
  thead { display: none; }
  td { border-bottom: 0; padding: 7px 0; }
  tr { border-bottom: 1px solid var(--line-soft); padding: 10px 0; }
}
"""


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def sign(value: str) -> str:
    mac = hmac.new(PANEL_SECRET.encode(), value.encode(), hashlib.sha256).digest()
    return f"{value}.{b64url(mac)}"


def verify_signed(value: str) -> bool:
    if "." not in value:
        return False
    raw, mac = value.rsplit(".", 1)
    return hmac.compare_digest(sign(raw), value)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def load_settings() -> dict:
    if SETTINGS_PATH.exists():
        return load_json(SETTINGS_PATH)
    return {"host": "", "publicKey": ""}


def find_inbound(config: dict) -> dict:
    for inbound in config.get("inbounds", []):
        if inbound.get("protocol") != "vless":
            continue
        stream = inbound.get("streamSettings", {})
        if stream.get("security") == "reality":
            return inbound
    raise ValueError("Не найден inbound VLESS + REALITY в config.json")


def get_reality(inbound: dict) -> dict:
    return inbound.get("streamSettings", {}).get("realitySettings", {})


def get_clients(inbound: dict) -> list:
    return inbound.setdefault("settings", {}).setdefault("clients", [])


def run_cmd(args: list[str], timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(args, text=True, capture_output=True, timeout=timeout)


def validate_config(path: Path) -> None:
    result = run_cmd(["xray", "run", "-test", "-config", str(path)], timeout=25)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "xray config test failed").strip())


def restart_xray() -> None:
    result = run_cmd(["systemctl", "restart", "xray"], timeout=30)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "systemctl restart xray failed").strip())


def commit_config(config: dict) -> None:
    backup = CONFIG_PATH.with_name(f"{CONFIG_PATH.name}.panel-backup-{time.strftime('%Y%m%d-%H%M%S')}")
    tmp = CONFIG_PATH.with_suffix(".panel-test.json")
    save_json(tmp, config)
    validate_config(tmp)
    shutil.copy2(CONFIG_PATH, backup)
    try:
        save_json(CONFIG_PATH, config)
        validate_config(CONFIG_PATH)
        restart_xray()
    except Exception:
        shutil.copy2(backup, CONFIG_PATH)
        restart_xray()
        raise
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def derive_public_key(private_key: str) -> str:
    if not private_key:
        return ""
    result = run_cmd(["xray", "x25519", "-i", private_key], timeout=10)
    text = result.stdout + "\n" + result.stderr
    for line in text.splitlines():
        if "Public key:" in line:
            return line.split("Public key:", 1)[1].strip()
        if "PublicKey:" in line:
            return line.split("PublicKey:", 1)[1].strip()
    return ""


def build_link(config: dict, settings: dict, client: dict) -> str:
    inbound = find_inbound(config)
    stream = inbound.get("streamSettings", {})
    reality = get_reality(inbound)
    network = stream.get("network", "tcp")
    host = settings.get("host") or "PUT_SERVER_IP_OR_DOMAIN"
    public_key = settings.get("publicKey") or derive_public_key(reality.get("privateKey", ""))
    server_names = reality.get("serverNames") or [""]
    short_ids = reality.get("shortIds") or [""]
    params = {
        "encryption": "none",
        "security": "reality",
        "sni": server_names[0],
        "fp": "chrome",
        "pbk": public_key,
        "sid": short_ids[0],
        "type": network,
    }
    if network == "xhttp":
        xhttp = stream.get("xhttpSettings", {})
        params["path"] = xhttp.get("path", "/")
        if xhttp.get("mode"):
            params["mode"] = xhttp["mode"]
    elif network == "tcp" and client.get("flow"):
        params["flow"] = client["flow"]
        params["spx"] = reality.get("spiderX", "/")
    query = urlencode(params, quote_via=quote)
    label = quote(client.get("email") or "VLESS-Reality")
    return f"vless://{client['id']}@{host}:{inbound.get('port', 443)}?{query}#{label}"


def page(title: str, body: str) -> bytes:
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>{CSS}</style>
</head>
<body>{body}</body>
</html>""".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "XrayKeyPanel/1.0"

    def log_message(self, fmt, *args):
        return

    def is_authed(self) -> bool:
        if not PANEL_TOKEN:
            return True
        raw = self.headers.get("Cookie", "")
        jar = cookies.SimpleCookie(raw)
        value = jar.get("xkp_session")
        return bool(value and verify_signed(value.value))

    def send_html(self, title: str, body: str, status: int = 200):
        data = page(title, body)
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location: str):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def read_form(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return {k: v[0] for k, v in parse_qs(raw).items()}

    def require_auth(self) -> bool:
        if self.path != "/login" and not self.is_authed():
            self.redirect("/login")
            return False
        return True

    def do_GET(self):
        if self.path == "/login":
            return self.render_login()
        if self.path == "/logout":
            self.send_response(303)
            self.send_header("Location", "/login")
            self.send_header("Set-Cookie", "xkp_session=; Max-Age=0; HttpOnly; SameSite=Lax")
            self.end_headers()
            return
        if not self.require_auth():
            return
        return self.render_home()

    def do_POST(self):
        if self.path == "/login":
            return self.handle_login()
        if not self.require_auth():
            return
        actions = {
            "/clients/add": self.add_client,
            "/clients/delete": self.delete_client,
            "/settings": self.save_settings,
            "/restart": self.restart,
        }
        action = actions.get(self.path)
        if not action:
            self.send_error(404)
            return
        try:
            action()
        except Exception as exc:
            self.render_home(error=str(exc))

    def render_login(self, error: str = ""):
        err = f'<div class="notice error">{html.escape(error)}</div>' if error else ""
        self.send_html("Вход", f"""
<main class="login">
  <section class="card">
    <h1>Xray Key Panel</h1>
    <p>Приватная панель управления клиентами VLESS Reality.</p>
    {err}
    <form method="post" action="/login" style="margin-top:18px">
      <label>Токен доступа</label>
      <input name="token" type="password" autocomplete="current-password" autofocus>
      <div style="margin-top:14px"><button type="submit">Войти</button></div>
    </form>
  </section>
</main>""")

    def handle_login(self):
        form = self.read_form()
        if not PANEL_TOKEN or hmac.compare_digest(form.get("token", ""), PANEL_TOKEN):
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie", f"xkp_session={sign('ok')}; HttpOnly; SameSite=Lax")
            self.end_headers()
            return
        self.render_login("Неверный токен")

    def render_home(self, notice: str = "", error: str = ""):
        config = load_json(CONFIG_PATH)
        settings = load_settings()
        inbound = find_inbound(config)
        stream = inbound.get("streamSettings", {})
        reality = get_reality(inbound)
        clients = get_clients(inbound)
        derived_public = derive_public_key(reality.get("privateKey", "")) if not settings.get("publicKey") else ""
        public_key = settings.get("publicKey") or derived_public
        rows = []
        for client in clients:
            link = build_link(config, {**settings, "publicKey": public_key}, client)
            cid = html.escape(client.get("id", ""))
            email = html.escape(client.get("email", ""))
            link_html = html.escape(link)
            rows.append(f"""
<tr>
  <td><strong>{email or "Без имени"}</strong><br><span class="muted">{cid}</span></td>
  <td><textarea readonly>{link_html}</textarea></td>
  <td>
    <div class="client-actions">
      <button class="secondary" type="button" onclick="copyText(this)">Копировать</button>
      <form method="post" action="/clients/delete" onsubmit="return confirm('Удалить клиента {email or cid}?')">
        <input type="hidden" name="id" value="{cid}">
        <button class="danger" type="submit">Удалить</button>
      </form>
    </div>
  </td>
</tr>""")
        clients_table = "\n".join(rows) or '<tr><td colspan="3" class="muted">Клиентов пока нет.</td></tr>'
        notice_html = f'<div class="notice ok">{html.escape(notice)}</div>' if notice else ""
        error_html = f'<div class="notice error">{html.escape(error)}</div>' if error else ""
        warning = ""
        if not public_key:
            warning = '<div class="notice error">Не удалось получить public key. Вставь его в настройках ниже, иначе ссылки будут неполными.</div>'
        if not settings.get("host"):
            warning += '<div class="notice">Укажи IP или домен VPS в настройках, чтобы ссылки импортировались без ручной правки.</div>'
        self.send_html("Xray Key Panel", f"""
<main>
  <header>
    <div>
      <h1>Xray Key Panel</h1>
      <p>VLESS Reality: {html.escape(stream.get("network", "?"))} · порт {html.escape(str(inbound.get("port", "?")))} · SNI {html.escape((reality.get("serverNames") or ["?"])[0])}</p>
    </div>
    <div class="toolbar">
      <form method="post" action="/restart"><button class="secondary" type="submit">Перезапустить Xray</button></form>
      <a class="button secondary" href="/logout">Выйти</a>
    </div>
  </header>
  {notice_html}{error_html}{warning}
  <section class="grid">
    <div class="card">
      <h2>Создать ключ</h2>
      <form method="post" action="/clients/add" class="toolbar">
        <div style="flex:1; min-width:240px">
          <label>Имя клиента</label>
          <input name="email" placeholder="iphone-mom, laptop-main, test-user" required>
        </div>
        <div style="align-self:end"><button type="submit">Создать</button></div>
      </form>
    </div>
    <div class="card">
      <h2>Клиенты</h2>
      <table>
        <thead><tr><th>Клиент</th><th>Ссылка</th><th>Действия</th></tr></thead>
        <tbody>{clients_table}</tbody>
      </table>
    </div>
    <div class="card">
      <h2>Настройки ссылок</h2>
      <form method="post" action="/settings">
        <div class="row">
          <div>
            <label>IP или домен VPS</label>
            <input name="host" value="{html.escape(settings.get("host", ""))}" placeholder="1.2.3.4 или vpn.example.com">
          </div>
          <div>
            <label>Reality public key</label>
            <input name="publicKey" value="{html.escape(public_key)}" placeholder="public key">
          </div>
        </div>
        <div style="margin-top:12px"><button type="submit">Сохранить</button></div>
      </form>
    </div>
  </section>
</main>
<script>
function copyText(button) {{
  const area = button.closest('tr').querySelector('textarea');
  area.select();
  navigator.clipboard.writeText(area.value).then(() => {{
    const old = button.textContent;
    button.textContent = 'Скопировано';
    setTimeout(() => button.textContent = old, 1200);
  }});
}}
</script>""")

    def add_client(self):
        form = self.read_form()
        email = form.get("email", "").strip()
        if not email:
            raise ValueError("Имя клиента не может быть пустым")
        config = load_json(CONFIG_PATH)
        inbound = find_inbound(config)
        clients = get_clients(inbound)
        if any(c.get("email") == email for c in clients):
            raise ValueError("Клиент с таким именем уже есть")
        client = {"id": str(uuid.uuid4()), "email": email}
        if inbound.get("streamSettings", {}).get("network") == "tcp":
            client["flow"] = "xtls-rprx-vision"
        clients.append(client)
        commit_config(config)
        self.render_home(notice=f"Клиент {email} создан")

    def delete_client(self):
        form = self.read_form()
        client_id = form.get("id", "")
        config = load_json(CONFIG_PATH)
        inbound = find_inbound(config)
        clients = get_clients(inbound)
        new_clients = [c for c in clients if c.get("id") != client_id]
        if len(new_clients) == len(clients):
            raise ValueError("Клиент не найден")
        inbound["settings"]["clients"] = new_clients
        commit_config(config)
        self.render_home(notice="Клиент удален")

    def save_settings(self):
        form = self.read_form()
        save_json(SETTINGS_PATH, {
            "host": form.get("host", "").strip(),
            "publicKey": form.get("publicKey", "").strip(),
        })
        self.render_home(notice="Настройки сохранены")

    def restart(self):
        validate_config(CONFIG_PATH)
        restart_xray()
        self.render_home(notice="Xray перезапущен")


def main():
    if not CONFIG_PATH.exists():
        raise SystemExit(f"Config not found: {CONFIG_PATH}")
    httpd = ThreadingHTTPServer((BIND_HOST, BIND_PORT), Handler)
    print(f"Xray Key Panel listening on http://{BIND_HOST}:{BIND_PORT}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
