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
