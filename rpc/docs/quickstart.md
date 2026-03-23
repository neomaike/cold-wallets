# Quickstart - Private EVM RPC

RPC Ethereum privado rodando em 5 minutos. Sem API key necessaria.

## Requisitos

- Docker Desktop for Windows (WSL2 backend)
- PowerShell 5.1+
- (Opcional) Tor Browser ou Docker Tor para privacidade
- (Opcional) WireGuard para acesso remoto

## Setup Rapido

### 1. Setup Inicial (uma vez, como Admin)

```powershell
# Executa: firewall, UPnP disable, config, docker pull
.\setup-first-time.bat
```

Ou manualmente:

```powershell
cd rpc

# Copiar config modelo
Copy-Item nodes\helios\config.example.toml nodes\helios\config.toml

# Hardening (como Admin)
.\harden-system.bat
```

### 2. Iniciar Tor (Privacidade)

**Opcao A — Docker Tor (recomendado):**
```powershell
cd infra\tor
docker compose up -d
# Porta: 9050
```

**Opcao B — Tor Browser:**
```
Abra o Tor Browser e mantenha aberto.
# Porta: 9150
```

Se usar Tor Browser, edite `nodes\helios\config.toml`:
```toml
proxy = "socks5://127.0.0.1:9150"
```

### 3. Iniciar Helios

```powershell
.\start-private-rpc.bat
```

Ou manualmente:
```powershell
cd nodes\helios
docker compose up -d

# Ver logs
docker logs helios-client -f
# Aguarde "RPC server started"
# Ctrl+C para sair dos logs
```

### 4. Testar RPC

```powershell
.\quick-test.bat
```

Ou:
```powershell
curl -s -X POST http://127.0.0.1:8545 ^
  -H "Content-Type: application/json" ^
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}"

# Esperado: {"jsonrpc":"2.0","id":1,"result":"0x..."}
```

### 5. Testar Privacidade

```powershell
.\test-privacy.bat
```

Verifica que:
- Seu IP real e diferente do IP Tor
- RPC responde em localhost
- Porta 8545 nao esta exposta na rede

### 6. Configurar MetaMask

1. MetaMask > Settings > Networks > Add Network
2. Preencher:
   - Network Name: `Private RPC`
   - RPC URL: `http://127.0.0.1:8545`
   - Chain ID: `1`
   - Currency Symbol: `ETH`
3. Salvar e trocar para esta rede

## Pronto!

Seu RPC privado esta rodando. Todas as queries sao verificadas criptograficamente pelo Helios e roteadas via Tor.

---

## Opcional: mTLS Reverse Proxy

Adiciona autenticacao por certificado ao RPC.

```powershell
# 1. Gerar certificados
.\scripts\generate-certs.ps1

# 2. Iniciar proxy
cd nodes\reverse-proxy
docker compose up -d

# 3. Testar (RPC agora em 8443 com mTLS)
curl --cacert certs\ca.crt --cert certs\client.crt --key certs\client.key ^
  https://127.0.0.1:8443 -X POST -H "Content-Type: application/json" ^
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"id\":1}"
```

---

## Opcional: Acesso Remoto (WireGuard)

Acesse o RPC de fora da sua rede.

1. Instale WireGuard
2. Gere keys: `.\scripts\generate-wireguard-keys.ps1`
3. Configure tunnel: veja `wireguard/README.md`
4. No dispositivo remoto: RPC URL `http://10.0.0.1:8545`

---

## Opcional: L2 (Optimism / Arbitrum)

Templates prontos para rodar nodes L2 privados.

```powershell
# Optimism (requer ~400 GB disco, 16 GB RAM)
cd nodes\l2-templates\optimism
docker compose up -d
# RPC: http://127.0.0.1:9545, Chain ID: 10

# Arbitrum (requer ~1 TB disco, 16 GB RAM)
cd nodes\l2-templates\arbitrum
docker compose up -d
# RPC: http://127.0.0.1:8547, Chain ID: 42161
```

---

## Verificar Seguranca

```powershell
.\scripts\healthcheck.ps1
```

Esperado:
- [PASS] RPC bound a localhost
- [PASS] Porta 8545 nao acessivel da LAN
- [PASS] Helios sincronizado
- [PASS] Containers Docker saudaveis

---

## Troubleshooting

### "Connection refused" no RPC

```powershell
docker ps | findstr helios
docker logs helios-client --tail 20
```

### Docker nao inicia

```powershell
.\fix-docker.bat
```

### Tor nao conecta

```powershell
# Docker Tor
docker logs tor-hidden-service

# Tor Browser
# Verifique se esta aberto e conectado
curl --socks5 127.0.0.1:9150 https://check.torproject.org/api/ip
```

### MetaMask mostra chain errada

Chain ID deve ser `1` para mainnet. Delete e re-adicione a rede.

---

## Proximos Passos

1. Leia `docs/threat-model.md` para entender as garantias de seguranca
2. Leia `docs/runbook.md` para procedimentos operacionais
3. Execute `scripts/healthcheck.ps1` regularmente
4. Considere WireGuard se precisa de acesso remoto

---

## Arquitetura

```
Voce (MetaMask/dApp)
       |
       v
  127.0.0.1:8545
       |
       v
  Helios Light Client
   - Verifica todos os proofs
   - Zero confianca no RPC
       |
       v (via Tor)
  Bootstrap RPC
   - 1RPC.io, LlamaRPC, Ankr
   - Nao podem mentir (proofs verificados)
       |
       v
  Ethereum Network
```

Seu IP nunca e enviado com suas queries. O bootstrap RPC so ve o IP do exit node Tor e nao consegue correlacionar sua identidade com atividade on-chain.
