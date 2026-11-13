#!/usr/bin/env bash
# Anexa (ou solta) um app do Umbrel à rede do VPN Gateway.
#
#   vpn-attach.sh <id-do-app>            coloca o app na VPN
#   vpn-attach.sh <id-do-app> --detach   tira o app da VPN
#
# Edita ~/umbrel/app-data/<id>/docker-compose.yml (com backup) e depois é
# preciso reiniciar o app pelo painel do Umbrel. Atualizações do app pelo
# Umbrel podem desfazer a mudança: rode de novo nesse caso.
set -euo pipefail

APP="${1:-}"
MODE="${2:-attach}"
GATEWAY="qbittorrent-vpn-gateway_vpn_1"
UMBREL_HOME="${UMBREL_HOME:-$HOME/umbrel}"
COMPOSE="${UMBREL_HOME}/app-data/${APP}/docker-compose.yml"

if [ -z "${APP}" ] || [ ! -f "${COMPOSE}" ]; then
    echo "uso: $0 <id-do-app> [--detach]   (não achei ${COMPOSE})" >&2
    exit 1
fi

BACKUP="${COMPOSE}.bak.vpn-$(date +%Y%m%d-%H%M%S)"
cp -p "${COMPOSE}" "${BACKUP}"

python3 - "${COMPOSE}" "${APP}" "${GATEWAY}" "${MODE}" <<'PY'
import re, sys

path, app, gateway, mode = sys.argv[1:5]
lines = open(path).read().split("\n")

def indent(s):
    return len(s) - len(s.lstrip(" "))

# Service headers: lines one level below "services:".
svc_start = next(i for i, l in enumerate(lines) if l.strip() == "services:")
child_indent = next(indent(l) for l in lines[svc_start + 1:] if l.strip() and not l.strip().startswith("#"))
services = {}
for i in range(svc_start + 1, len(lines)):
    l = lines[i]
    if l.strip() and not l.strip().startswith("#") and indent(l) < child_indent:
        break
    m = re.match(r"^ {%d}([A-Za-z0-9_.-]+):\s*$" % child_indent, l)
    if m:
        services[m.group(1)] = i

def block(name):
    start = services[name]
    end = len(lines)
    for i in range(start + 1, len(lines)):
        l = lines[i]
        if l.strip() and not l.strip().startswith("#") and indent(l) <= child_indent:
            end = i
            break
    return start, end

def find_in(name, pattern):
    start, end = block(name)
    for i in range(start + 1, end):
        m = re.match(pattern, lines[i])
        if m:
            return i, m
    return None, None

host_i, host_m = find_in("app_proxy", r"^(\s*)APP_HOST:\s*['\"]?([^'\"\s]+)")
if host_i is None:
    sys.exit("não achei APP_HOST no app_proxy")
app_host = host_m.group(2)

def container_name(svc):
    i, m = find_in(svc, r"^\s*container_name:\s*['\"]?([^'\"\s]+)")
    return m.group(1) if m else f"{app}_{svc}_1"

target = None
for svc in services:
    if svc != "app_proxy" and find_in(svc, r"^\s*network_mode:\s*['\"]?container:")[0] is not None:
        target = svc
        break
if target is None:
    target = next((s for s in services if s != "app_proxy" and container_name(s) == app_host), None)
if target is None:
    sys.exit(f"não descobri qual serviço atende {app_host}")

net_i, _ = find_in(target, r"^\s*network_mode:")
start, end = block(target)
key_indent = next((indent(l) for l in lines[start + 1:end] if l.strip()), child_indent + 2)

if mode == "--detach":
    lines[host_i] = f"{host_m.group(1)}APP_HOST: {container_name(target)}"
    if net_i is not None:
        del lines[net_i]
    print(f"{app}: serviço '{target}' fora da VPN")
else:
    lines[host_i] = f"{host_m.group(1)}APP_HOST: {gateway}"
    nm = " " * key_indent + f"network_mode: container:{gateway}"
    if net_i is not None:
        lines[net_i] = nm
    else:
        lines.insert(start + 1, nm)
    print(f"{app}: serviço '{target}' anexado ao {gateway}")

open(path, "w").write("\n".join(lines))
PY

if cmp -s "${COMPOSE}" "${BACKUP}"; then
    rm -f "${BACKUP}"
    echo "Nada mudou."
else
    echo "Backup: ${BACKUP}"
    diff "${BACKUP}" "${COMPOSE}" || true
    echo "Agora reinicie o app '${APP}' pelo painel do Umbrel."
fi
