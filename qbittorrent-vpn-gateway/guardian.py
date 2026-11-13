"""VPN Gateway guardian.

Runs inside the gateway's network namespace and talks to Docker over the
mounted socket. Every INTERVAL seconds, for each container in TARGETS:

- attached to the gateway, but started before the gateway's last start
  -> restart it, so it rejoins the tunnel's network namespace;
- running on a normal Docker network (outside the VPN)
  -> stop it when KILL_SWITCH=1, so the home IP never leaks;
- attached to a container that no longer exists
  -> report it (only the Umbrel restart of that app can recreate it).

It only ever touches the containers named in TARGETS.
Serves a status page and /api/status on PORT.
"""

import datetime as dt
import html
import http.client
import json
import os
import signal
import socket
import sys
import threading
import time
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SOCK = "/var/run/docker.sock"
GATEWAY = os.environ.get("GATEWAY", "qbittorrent-vpn-gateway_vpn_1")
TARGETS = [t.strip() for t in os.environ.get("TARGETS", "").split(",") if t.strip()]
INTERVAL = int(os.environ.get("INTERVAL", "30"))
PORT = int(os.environ.get("PORT", "8099"))
KILL_SWITCH = os.environ.get("KILL_SWITCH", "1") == "1"
SELF = os.environ.get("SELF", "")

state = {"gateway": "desconhecido", "public_ip": None, "ip_checked": 0.0, "targets": {}, "last_check": None}
events = deque(maxlen=60)
lock = threading.Lock()


def log(msg):
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{stamp}  {msg}"
    print(line, flush=True)
    with lock:
        events.appendleft(line)


class UnixConnection(http.client.HTTPConnection):
    def __init__(self):
        super().__init__("localhost", timeout=90)

    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(90)
        sock.connect(SOCK)
        self.sock = sock


def docker(method, path):
    conn = UnixConnection()
    try:
        conn.request(method, path)
        resp = conn.getresponse()
        body = resp.read()
        if body and resp.getheader("Content-Type", "").startswith("application/json"):
            return resp.status, json.loads(body)
        return resp.status, body
    finally:
        conn.close()


def inspect(ref):
    status, data = docker("GET", f"/containers/{ref}/json")
    return data if status == 200 else None


def started_at(container):
    raw = container["State"]["StartedAt"].rstrip("Z")
    base, _, frac = raw.partition(".")
    seconds = dt.datetime.fromisoformat(base).replace(tzinfo=dt.timezone.utc).timestamp()
    return seconds + float("0." + (frac or "0"))


def act(verb, name):
    status, body = docker("POST", f"/containers/{name}/{verb}?t=30")
    if status not in (204, 304):
        log(f"ERRO ao executar {verb} em {name}: HTTP {status} {body!r:.200}")
        return False
    return True


def refresh_public_ip():
    if time.time() - state["ip_checked"] < 300 and state["public_ip"]:
        return
    try:
        with urllib.request.urlopen("https://ipinfo.io/json", timeout=15) as resp:
            info = json.load(resp)
        state["public_ip"] = f'{info.get("ip")} ({info.get("org", "?")}, {info.get("country", "?")})'
    except Exception as exc:  # tunnel down or DNS not ready yet
        state["public_ip"] = f"indisponível ({exc.__class__.__name__})"
    state["ip_checked"] = time.time()


def check():
    gateway = inspect(GATEWAY)
    if not gateway or not gateway["State"]["Running"]:
        state["gateway"] = "parado"
        return
    state["gateway"] = "rodando"
    gateway_id = gateway["Id"]
    gateway_start = started_at(gateway)
    refresh_public_ip()

    for name in TARGETS:
        container = inspect(name)
        if container is None:
            state["targets"][name] = "não instalado"
            continue
        mode = container["HostConfig"]["NetworkMode"]
        running = container["State"]["Running"]

        if mode == f"container:{gateway_id}":
            if running and started_at(container) < gateway_start:
                log(f"{name}: a VPN reiniciou depois dele, reiniciando para reconectar ao túnel")
                act("restart", name)
                state["targets"][name] = "reiniciado pelo guardião"
            else:
                state["targets"][name] = "na VPN" if running else "na VPN (parado)"
        elif mode.startswith("container:"):
            other = inspect(mode.split(":", 1)[1])
            if other is None:
                state["targets"][name] = "sem rede: VPN antiga sumiu, reinicie o app pelo Umbrel"
            else:
                state["targets"][name] = f"usando outra rede ({other['Name'].lstrip('/')}), rode vpn-attach.sh"
        else:
            if running and KILL_SWITCH:
                log(f"{name}: rodando FORA da VPN (rede {mode}), parando (kill switch)")
                act("stop", name)
                state["targets"][name] = "FORA da VPN, parado pelo kill switch: rode vpn-attach.sh"
            else:
                state["targets"][name] = "FORA da VPN" + (" (parado)" if not running else "")

    # The guardian shares the gateway's network namespace too: after a gateway
    # restart its own network is gone, so it restarts itself last.
    me = inspect(SELF) if SELF else None
    if me and started_at(me) < gateway_start:
        log("guardião: a VPN reiniciou, reiniciando o próprio guardião para recuperar a rede")
        act("restart", SELF)


def loop():
    log(f"guardião iniciado: gateway={GATEWAY} alvos={','.join(TARGETS) or '-'} kill_switch={KILL_SWITCH}")
    while True:
        try:
            check()
        except Exception as exc:
            log(f"ERRO na verificação: {exc!r}")
        state["last_check"] = dt.datetime.now().strftime("%H:%M:%S")
        time.sleep(INTERVAL)


PAGE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="30">
<title>VPN Gateway</title><style>
:root{{--bg:#f7f7f5;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#e3e3df;--ok:#1f7a4d;--bad:#b42318}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151514;--fg:#ececea;--muted:#9b9b95;--card:#1f1f1d;--line:#30302d;--ok:#4cc38a;--bad:#f97066}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:720px;margin:0 auto;padding:24px 16px}}
h1{{font-size:22px;margin:0 0 4px}}p.sub{{color:var(--muted);margin:0 0 20px}}
section{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:14px}}
table{{width:100%;border-collapse:collapse}}td{{padding:6px 0;border-bottom:1px solid var(--line);vertical-align:top}}
tr:last-child td{{border-bottom:0}}td:first-child{{color:var(--muted);width:42%;padding-right:12px}}
.ok{{color:var(--ok)}}.bad{{color:var(--bad)}}pre{{white-space:pre-wrap;font:12px/1.45 ui-monospace,monospace;margin:0;color:var(--muted)}}
</style></head><body><main>
<h1>VPN Gateway</h1><p class="sub">Última verificação: {last}</p>
<section><table><tr><td>Túnel</td><td class="{gwc}">{gw}</td></tr><tr><td>IP de saída</td><td>{ip}</td></tr></table></section>
<section><table>{rows}</table></section>
<section><pre>{events}</pre></section>
</main></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        with lock:
            snapshot = {**state, "targets": dict(state["targets"]), "events": list(events)}
        if self.path.startswith("/api/status"):
            snapshot.pop("ip_checked", None)
            body = json.dumps(snapshot, ensure_ascii=False).encode()
            ctype = "application/json; charset=utf-8"
        else:
            rows = "".join(
                f'<tr><td>{html.escape(n)}</td><td class="{"ok" if s.startswith("na VPN") else "bad"}">{html.escape(s)}</td></tr>'
                for n, s in snapshot["targets"].items()
            ) or "<tr><td>Apps</td><td>nenhum verificado ainda</td></tr>"
            body = PAGE.format(
                last=html.escape(snapshot["last_check"] or "ainda não"),
                gw=html.escape(snapshot["gateway"]),
                gwc="ok" if snapshot["gateway"] == "rodando" else "bad",
                ip=html.escape(snapshot["public_ip"] or "verificando…"),
                rows=rows,
                events=html.escape("\n".join(snapshot["events"]) or "sem eventos"),
            ).encode()
            ctype = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    # As PID 1 the process ignores SIGTERM unless it handles it, which would
    # make every stop/restart wait for Docker's full timeout.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    threading.Thread(target=loop, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
