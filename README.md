# Umbrel Community App Store - qBittorrent (VPN)

Repositório customizado para o UmbrelOS contendo o **qBittorrent com VPN (Gluetun + WireGuard ProtonVPN)** integrado com Port Forwarding automático via NAT-PMP e Kill Switch no kernel.

## 🚀 Como instalar no Umbrel

1. No Umbrel, acesse a **App Store** -> **Community App Stores** (ou adicione nas configurações de repositórios).
2. Adicione este repositório:
   ```text
   https://github.com/dtelless/umbrel-community-app-store.git
   ```
3. O app **qBittorrent (VPN)** aparecerá disponível para instalação.

## 🔐 Como configurar o seu arquivo `.conf` da ProtonVPN

Você **não** precisa extrair chaves privadas ou endereços manualmente! Basta fornecer o arquivo `.conf` que a ProtonVPN gera:

1. Baixe o arquivo de configuração WireGuard no painel da **ProtonVPN** (com suporte a P2P / Port Forwarding).
2. Copie o arquivo `.conf` (por exemplo: `torresmo-BR-26.conf`) diretamente para a pasta do app no seu Umbrel:
   ```bash
   # Pode colar em qualquer um desses caminhos:
   ~/umbrel/app-data/qbittorrent-vpn/
   # ou
   ~/umbrel/app-data/qbittorrent-vpn/data/wireguard/
   ```
3. O script de inicialização do app detecta automaticamente o arquivo `.conf`, sincroniza com `wg0.conf` e inicia o túnel seguro.
4. Reinicie ou inicie o app pelo painel do Umbrel.

## 📊 Recursos Integrados

- **100% Protegido via VPN:** Kill switch ativado no kernel Docker para impedir vazamentos de IP residencial.
- **Port Forwarding Dinâmico:** Atualiza a porta de escuta do qBittorrent via WebAPI no momento em que a porta é concedida pelo NAT-PMP da VPN.
- **Widgets em Tempo Real no Dashboard:** Exibe o IP público da VPN, a porta aberta negociada, velocidades de upload/download e a lista de torrents ativos.
- **Whitelist Local:** Permite acesso direto da rede local (`192.168.11.0/24`) sem necessidade de login repetitivo.

---

# 🛡️ VPN Gateway

Um túnel WireGuard da ProtonVPN separado, para **outros apps** do Umbrel (por exemplo Paperclip e Hermes Agent) saírem pela VPN sem depender do qBittorrent.

## Como funciona

- **`vpn` (Gluetun):** o túnel. Os apps anexados usam a rede dele (`network_mode: container:qbittorrent-vpn-gateway_vpn_1`).
- **`guardian`:** a cada 30 s, para cada app da lista `TARGETS`:
  - reinicia o app se a VPN reiniciou depois dele (senão ele fica sem rede);
  - **kill switch:** para o app se ele estiver rodando fora da VPN (por exemplo, depois que uma atualização do Umbrel desfez a configuração);
  - mostra tudo numa página de status (porta do app no Umbrel) e em `/api/status`.
- O guardião usa o socket do Docker e só age nos contêineres listados em `TARGETS`.

## Instalação

1. Gere uma configuração WireGuard na ProtonVPN (**NAT-PMP desligado**; o encaminhamento de porta fica com o qBittorrent).
2. Instale o **VPN Gateway** por esta loja.
3. Copie o `.conf` (qualquer nome) para `~/umbrel/app-data/qbittorrent-vpn-gateway/data/wireguard/` e reinicie o app.
4. Anexe cada app e reinicie-o pelo painel do Umbrel:
   ```bash
   ~/umbrel/app-data/qbittorrent-vpn-gateway/vpn-attach.sh paperclip
   ~/umbrel/app-data/qbittorrent-vpn-gateway/vpn-attach.sh hermes-agent
   ```
   Para tirar um app da VPN: `vpn-attach.sh <app> --detach`.

Atualizações de apps pelo Umbrel podem desfazer o anexo. O kill switch para o app nesse caso; rode o `vpn-attach.sh` de novo e reinicie o app.
