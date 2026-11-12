#!/usr/bin/env python3
"""Umbrel setup page for Self-hosted LiveSync. Obsidian does not use this port."""

import base64
import html
import os
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

ENV_PATH = os.environ.get("LIVESYNC_ENV", "/mnt/app/.env")
TS_ENV_PATH = os.environ.get("TS_ENV", "/mnt/app/data/tailscale/.env")
COUCH_URL = os.environ.get("COUCHDB_URL", "http://couchdb:5984").rstrip("/")
COUCH_USER = os.environ.get("COUCHDB_USER", "livesync")
COUCH_PASSWORD = os.environ.get("COUCHDB_PASSWORD", "")
HOST_NAME = re.compile(r"^[A-Za-z0-9-]+$")
URL_HOST = re.compile(r"^[A-Za-z0-9.-]+\.ts\.net$")
VAULTS_PATH = os.environ.get("VAULTS_PATH", "/vaults")
BIND = os.environ.get("LIVESYNC_BIND", "0.0.0.0")
PORT = int(os.environ.get("LIVESYNC_PORT", "8080"))

DB_NAME = re.compile(r"^[a-z][a-z0-9_$()+/-]*$")
KEY_LINE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def read_env(path):
    values = {}
    if not os.path.isfile(path):
        return values
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            name = name.strip()
            if not KEY_LINE.match(name):
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[name] = value
    return values


def write_env(path, updates):
    lines = []
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    seen = set()
    rewritten = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            name = stripped.split("=", 1)[0].strip()
            if name in updates:
                rewritten.append(f"{name}={updates[name]}")
                seen.add(name)
                continue
        rewritten.append(line)
    for name, value in updates.items():
        if name not in seen:
            if rewritten and rewritten[-1] != "":
                rewritten.append("")
            rewritten.append(f"{name}={value}")
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, mode=0o700, exist_ok=True)
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write("\n".join(rewritten).rstrip() + "\n")
    os.chmod(temporary, 0o600)
    try:
        stat = os.stat(directory)
        os.chown(temporary, stat.st_uid, stat.st_gid)
    except OSError:
        pass
    os.replace(temporary, path)


def parse_url(raw):
    raw = raw.strip()
    if not raw:
        return ""
    if "\n" in raw or "\r" in raw or len(raw) > 200:
        raise ValueError("The address is not valid.")
    host = raw
    for prefix in ("https://", "http://"):
        if host.startswith(prefix):
            host = host[len(prefix) :]
            break
    host = host.split("/", 1)[0].split(":", 1)[0]
    if not URL_HOST.match(host):
        raise ValueError("Use an https://name.tailnet.ts.net address.")
    return "https://" + host


def parse_hostname(raw):
    raw = (raw or "").strip() or "livesync"
    if "\n" in raw or "\r" in raw or not HOST_NAME.match(raw):
        raise ValueError("Hostname must use letters, numbers, and hyphens.")
    return raw


def parse_databases(raw):
    names = []
    for part in raw.split(","):
        name = part.strip().lower()
        if not name:
            continue
        if name.startswith("_") or not DB_NAME.match(name):
            raise ValueError(
                f"{part.strip()} is not a CouchDB database name. "
                "Use lowercase letters, numbers, and _ $ ( ) + / -."
            )
        if name not in names:
            names.append(name)
    if not names:
        names = ["test"]
    if len(names) > 16:
        raise ValueError("Use at most 16 databases.")
    return names


def couch_request(path):
    request = urllib.request.Request(COUCH_URL + path)
    token = f"{COUCH_USER}:{COUCH_PASSWORD}".encode()
    request.add_header("Authorization", "Basic " + base64.b64encode(token).decode())
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        return error.code, body
    except Exception as error:
        return 0, str(error)


def vault_names():
    if not os.path.isdir(VAULTS_PATH):
        return None
    names = []
    for entry in sorted(os.listdir(VAULTS_PATH)):
        if entry.startswith("."):
            continue
        if os.path.isdir(os.path.join(VAULTS_PATH, entry)):
            names.append(entry)
    return names


def page(message="", error=""):
    env = read_env(ENV_PATH)
    databases = env.get("COUCHDB_DATABASES", "test") or "test"
    key = env.get("TS_AUTHKEY", "")
    key_state = "Saved" if key else "Not set"
    public_url = os.environ.get("LIVESYNC_URL", "").strip()
    up_code, up_body = couch_request("/_up")
    couch_ok = up_code == 200 and '"ok"' in up_body
    db_code, db_body = couch_request("/_all_dbs") if couch_ok else (0, "")
    remote_dbs = []
    if db_code == 200:
        remote_dbs = re.findall(r'"([^"]+)"', db_body)
        remote_dbs = [name for name in remote_dbs if not name.startswith("_")]
    vaults = vault_names()
    public = public_url or "Not set"
    uri = public_url if public_url.startswith("https://") else "https://livesync.your-tailnet.ts.net"

    def row(label, value):
        return (
            "<div class='row'><div class='label'>"
            + html.escape(label)
            + "</div><div class='value'><code>"
            + html.escape(value)
            + "</code></div></div>"
        )

    vault_html = ""
    if vaults is None:
        vault_html = (
            "<p>The vault folder is not attached yet. In this app's Umbrel settings, "
            "set Obsidian vaults to <code>documents/obsidian</code>. The <code>test</code> "
            "database is created either way.</p>"
        )
    elif not vaults:
        vault_html = "<p>The attached folder has no vault directories.</p>"
    else:
        items = []
        for name in vaults:
            database = name.strip().lower()
            if database == "test":
                mark = " — use database test"
            elif DB_NAME.match(database) and not database.startswith("_"):
                mark = f" — database name {database}"
            else:
                mark = " — choose a lowercase database name without spaces"
            items.append("<li><code>" + html.escape(name) + "</code>" + html.escape(mark) + "</li>")
        vault_html = "<ul>" + "".join(items) + "</ul>"

    banner = ""
    if error:
        banner = "<p class='banner bad'>" + html.escape(error) + "</p>"
    elif message:
        banner = "<p class='banner ok'>" + html.escape(message) + "</p>"

    couch_label = "Reachable" if couch_ok else "Not reachable yet"
    db_label = ", ".join(remote_dbs) if remote_dbs else "None yet"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LiveSync</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 0; font: 16px/1.5 ui-sans-serif, system-ui, sans-serif; background: #12141a; color: #e7e9ee; }}
  main {{ max-width: 760px; margin: 0 auto; padding: 32px 20px 64px; }}
  h1 {{ font-size: 28px; margin: 0 0 8px; }}
  h2 {{ font-size: 18px; margin: 28px 0 8px; }}
  p, li {{ color: #c5c9d3; }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: #f4f7fb; }}
  .card {{ background: #1b1e27; border: 1px solid #2c3140; border-radius: 12px; padding: 16px; }}
  .row {{ display: grid; grid-template-columns: 140px 1fr; gap: 8px; padding: 6px 0; }}
  .label {{ color: #9aa3b5; }}
  label {{ display: block; margin: 12px 0 4px; color: #c5c9d3; }}
  input[type=text], input[type=password] {{ width: 100%; box-sizing: border-box; padding: 10px 12px; border-radius: 8px; border: 1px solid #3a4154; background: #10131a; color: #f4f7fb; }}
  button {{ margin-top: 14px; margin-right: 8px; background: #e7e9ee; color: #12141a; border: 0; border-radius: 8px; padding: 10px 14px; font: inherit; cursor: pointer; }}
  .banner {{ padding: 10px 12px; border-radius: 8px; }}
  .ok {{ background: #163226; color: #c8f5dc; }}
  .bad {{ background: #3a1d22; color: #ffd0d6; }}
  .status {{ color: #9aa3b5; }}
</style>
</head>
<body>
<main>
  <h1>LiveSync</h1>
  <p>CouchDB for the Obsidian vault <code>documents/obsidian/test</code>. Database name <code>test</code>. Obsidian connects to the Tailscale address below. This page is only for setup.</p>
  {banner}
  <h2>Obsidian</h2>
  <div class="card">
    {row("URI", uri)}
    {row("Username", COUCH_USER)}
    {row("Password", COUCH_PASSWORD or "Unavailable")}
    {row("Database", "test")}
  </div>
  <p>Install Self-hosted LiveSync in the test vault and run Quick Setup with those values. Turn on end-to-end encryption. The passphrase stays on your devices. This server does not store it. Leave Obsidian Sync and any other sync plugin off for this vault.</p>
  <h2>Tailscale</h2>
  <div class="card">
    <p class="status">Saved address: <code>{html.escape(public)}</code>. Auth key: {html.escape(key_state)}.</p>
    <form method="post" action="/">
      <label for="ts_authkey">Tailscale auth key</label>
      <input id="ts_authkey" name="ts_authkey" type="password" autocomplete="off" placeholder="tskey-auth-...">
      <label for="databases">Database names</label>
      <input id="databases" name="databases" type="text" value="{html.escape(databases, quote=True)}">
      <button type="submit" name="action" value="save">Save</button>
      <button type="submit" name="action" value="clear">Remove auth key</button>
    </form>
    <p>The address and hostname are Umbrel environment variables. The auth key is not. Put <code>TS_AUTHKEY=tskey-auth-...</code> in <code>.env</code> beside <code>settings.yml</code>, or save it here. Leave the key blank to keep the saved key. Restart the app after either change.</p>
  </div>
  <h2>Server</h2>
  <div class="card">
    {row("CouchDB", couch_label)}
    {row("Databases", db_label)}
  </div>
  <h2>Vault folder</h2>
  {vault_html}
  <p>When the test vault is syncing, add the other vault folder names here as lowercase database names, save, and restart. Each vault uses its own database and the same URI, username, and password.</p>
</main>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?", 1)[0] == "/health":
            body = b"ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        self._html(page())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > 8192:
            self._html(page(error="That submission is too large."), status=400)
            return
        raw = self.rfile.read(length).decode("utf-8", "replace")
        form = parse_qs(raw, keep_blank_values=True)
        action = (form.get("action") or ["save"])[0]
        try:
            databases = parse_databases((form.get("databases") or ["test"])[0])
        except ValueError as exc:
            self._html(page(error=str(exc)), status=400)
            return
        current = read_env(ENV_PATH)
        key = current.get("TS_AUTHKEY", "")
        if action == "clear":
            key = ""
        else:
            submitted = (form.get("ts_authkey") or [""])[0].strip()
            if submitted:
                if "\n" in submitted or "\r" in submitted or len(submitted) > 300:
                    self._html(page(error="The auth key is not valid."), status=400)
                    return
                key = submitted
        updates = {
            "TS_AUTHKEY": key,
            "COUCHDB_DATABASES": ",".join(databases),
        }
        write_env(ENV_PATH, updates)
        write_env(TS_ENV_PATH, updates)
        message = "Saved. Restart the app so Tailscale and CouchDB pick this up."
        if action == "clear":
            message = "Removed the auth key. Restart the app."
        self._html(page(message=message))

    def _html(self, body, status=200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        return


def self_test():
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, ".env")
        write_env(path, {"TS_AUTHKEY": "", "COUCHDB_DATABASES": "test"})
        write_env(
            path,
            {"TS_AUTHKEY": "tskey-auth-example", "COUCHDB_DATABASES": "test,notes"},
        )
        values = read_env(path)
        assert values["TS_AUTHKEY"] == "tskey-auth-example"
        assert values["COUCHDB_DATABASES"] == "test,notes"
        assert os.stat(path).st_mode & 0o777 == 0o600
        assert parse_databases(" test, Notes ") == ["test", "notes"]
        assert parse_url("https://livesync.example.ts.net/extra") == "https://livesync.example.ts.net"
        assert parse_hostname("") == "livesync"
        try:
            parse_url("https://example.com")
        except ValueError:
            pass
        else:
            raise AssertionError("non-tailscale address was accepted")
        try:
            parse_databases("_users")
        except ValueError:
            pass
        else:
            raise AssertionError("reserved name was accepted")
    print("self-test ok")


def main():
    if os.environ.get("LIVESYNC_SELF_TEST") == "1":
        self_test()
        return
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
