import http.server
import json
import urllib.request
import urllib.parse
import os

QB_HOST = os.environ.get("QB_HOST", "127.0.0.1:8080")
QB_USER = os.environ.get("QB_USER", "admin")
QB_PASS = os.environ.get("QB_PASS", "MsIFDjK6U")

def format_speed(bps):
    if bps < 1024:
        return f"{bps} B/s"
    elif bps < 1024 * 1024:
        return f"{bps/1024:.1f} KB/s"
    else:
        return f"{bps/(1024*1024):.1f} MB/s"

def query_qbittorrent():
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    
    # Attempt login if credentials are set (bypassed if LocalHostAuth is false)
    if QB_USER and QB_PASS:
        try:
            data = urllib.parse.urlencode({"username": QB_USER, "password": QB_PASS}).encode("utf-8")
            login_req = urllib.request.Request(
                f"http://{QB_HOST}/api/v2/auth/login",
                data=data,
                headers={"Referer": f"http://{QB_HOST}"}
            )
            opener.open(login_req, timeout=3)
        except Exception:
            pass

    # Transfer info
    req = urllib.request.Request(f"http://{QB_HOST}/api/v2/transfer/info")
    with opener.open(req, timeout=3) as resp:
        tinfo = json.loads(resp.read().decode())

    # Preferences
    req = urllib.request.Request(f"http://{QB_HOST}/api/v2/app/preferences")
    with opener.open(req, timeout=3) as resp:
        prefs = json.loads(resp.read().decode())

    # Torrents
    req = urllib.request.Request(f"http://{QB_HOST}/api/v2/torrents/info")
    with opener.open(req, timeout=3) as resp:
        torrents = json.loads(resp.read().decode())

    return tinfo, prefs, torrents

def get_status_widget():
    vpn_ip = "VPN Ativa"
    vpn_port = "Auto"
    dl_speed = 0
    up_speed = 0
    total_torrents = 0
    seeding = 0
    checking = 0
    downloading = 0

    try:
        tinfo, prefs, torrents = query_qbittorrent()
        vpn_ip = tinfo.get("last_external_address_v4") or vpn_ip
        dl_speed = tinfo.get("dl_info_speed", 0)
        up_speed = tinfo.get("up_info_speed", 0)
        vpn_port = str(prefs.get("listen_port", vpn_port))

        total_torrents = len(torrents)
        seeding = sum(1 for t in torrents if t.get("progress", 0) == 1.0)
        checking = sum(1 for t in torrents if t.get("progress", 0) < 1.0 and "checking" in t.get("state", ""))
        downloading = sum(1 for t in torrents if "downloading" in t.get("state", ""))
    except Exception as e:
        print("Erro ao coletar stats:", e, flush=True)

    subtext_torrents = f"{seeding} Seeding"
    if checking > 0:
        subtext_torrents += f" | {checking} Checando"
    elif downloading > 0:
        subtext_torrents += f" | {downloading} Baixando"

    return {
        "type": "four-stats",
        "refresh": "5s",
        "link": "",
        "items": [
            {
                "title": "VPN Proton",
                "text": vpn_ip,
                "subtext": "WireGuard Ativo"
            },
            {
                "title": "Porta P2P",
                "text": vpn_port,
                "subtext": "Aberta (NAT-PMP)"
            },
            {
                "title": "Velocidade",
                "text": f"↓ {format_speed(dl_speed)}",
                "subtext": f"↑ {format_speed(up_speed)}"
            },
            {
                "title": "Torrents",
                "text": f"{total_torrents} Total",
                "subtext": subtext_torrents
            }
        ]
    }

def get_torrent_list_widget():
    items = []
    vpn_ip = "VPN Ativa"
    vpn_port = "Auto"

    try:
        tinfo, prefs, torrents = query_qbittorrent()
        vpn_ip = tinfo.get("last_external_address_v4") or vpn_ip
        vpn_port = str(prefs.get("listen_port", vpn_port))
        dl_speed = tinfo.get("dl_info_speed", 0)
        up_speed = tinfo.get("up_info_speed", 0)

        # Item 1: VPN & Port Status Header
        items.append({
            "text": f"VPN: {vpn_ip} (Porta {vpn_port})",
            "subtext": f"ProtonVPN • ↓ {format_speed(dl_speed)} • ↑ {format_speed(up_speed)}"
        })

        # Sort torrents: downloading first, then checking, then active seeding
        def sort_key(t):
            state = t.get("state", "")
            if "downloading" in state:
                return (0, -t.get("dlspeed", 0))
            if "checking" in state:
                return (1, -t.get("progress", 0))
            return (2, -t.get("upspeed", 0))

        sorted_torrents = sorted(torrents, key=sort_key)

        for t in sorted_torrents[:4]:
            prog = int(t.get("progress", 0) * 100)
            name = t.get("name", "Torrent")
            state = t.get("state", "")
            dls = t.get("dlspeed", 0)
            ups = t.get("upspeed", 0)

            if "checking" in state:
                status_text = f"Checando integridade ({prog}%)"
            elif prog == 100:
                status_text = f"Seeding • ↑ {format_speed(ups)}"
            else:
                status_text = f"↓ {format_speed(dls)} • ↑ {format_speed(ups)}"

            items.append({
                "text": f"{prog}% • {name}",
                "subtext": status_text
            })
    except Exception as e:
        print("Erro ao coletar lista de torrents:", e, flush=True)
        items.append({
            "text": f"VPN Proton: {vpn_ip} (Porta {vpn_port})",
            "subtext": "Conectado e protegido"
        })

    return {
        "type": "list",
        "refresh": "3s",
        "link": "",
        "noItemsText": "Nenhum torrent ativo.",
        "items": items
    }

class WidgetHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/widgets/status", "/status", "/widgets/status/"):
            data = get_status_widget()
        elif self.path in ("/widgets/torrent-list", "/torrent-list", "/widgets/torrent-list/"):
            data = get_torrent_list_widget()
        else:
            data = get_status_widget()

        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", 80), WidgetHandler)
    print("Widget server qBittorrent VPN rodando na porta 80...", flush=True)
    server.serve_forever()
