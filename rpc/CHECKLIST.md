# Security Validation Checklist

Complete antes de usar o Private RPC.

## Pre-Deployment

### Configuracao
- [ ] Copiou `config.example.toml` para `config.toml`
- [ ] Verificou `bind_ip = "127.0.0.1"` no config
- [ ] Verificou `cors_origins` restrito a extensoes de wallet (nao `*`)
- [ ] Leu `docs/threat-model.md`

### System Hardening
- [ ] Executou `hardening/windows-firewall.ps1` como Admin
- [ ] Executou `hardening/disable-upnp.ps1` como Admin
- [ ] Desabilitou UPnP no router
- [ ] Windows Update habilitado e atualizado
- [ ] Windows Defender ativo

### Docker
- [ ] Docker Desktop instalado e atualizado
- [ ] Docker usando WSL2 backend
- [ ] Images com versao pinnada (nao `:latest`)

### Tor (se usando)
- [ ] Docker Tor rodando (porta 9050) OU Tor Browser aberto (porta 9150)
- [ ] `config.toml` com proxy apontando para porta correta
- [ ] `test-privacy.bat` mostra IPs diferentes

---

## Post-Deployment — Testes Obrigatorios

### Teste 1: RPC responde em localhost (OBRIGATORIO)

```powershell
curl http://127.0.0.1:8545 -X POST -H "Content-Type: application/json" ^
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"id\":1}"
```

**Esperado**: JSON com `result` contendo block number (hex)
**Status**: [ ] PASS / [ ] FAIL

### Teste 2: Porta 8545 bound a localhost (OBRIGATORIO)

```powershell
netstat -an | findstr 8545
```

**Esperado**: `127.0.0.1:8545` — nunca `0.0.0.0:8545`
**Status**: [ ] PASS / [ ] FAIL

### Teste 3: Inacessivel da LAN (OBRIGATORIO)

De outro dispositivo na mesma rede:
```bash
curl http://SEU_IP_LAN:8545 -X POST -d '{"jsonrpc":"2.0","method":"eth_blockNumber","id":1}'
```

**Esperado**: Connection refused ou timeout
**Status**: [ ] PASS / [ ] FAIL

### Teste 4: Scan externo (OBRIGATORIO)

De fora da sua rede (dados moveis, outro local):
```bash
nmap -p 8545 SEU_IP_PUBLICO
```

**Esperado**: Port closed ou filtered
**Status**: [ ] PASS / [ ] FAIL

### Teste 5: Helios sincronizado

```powershell
curl http://127.0.0.1:8545 -X POST -H "Content-Type: application/json" ^
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_syncing\",\"id\":1}"
```

**Esperado**: `{"result":false}` (sincronizado)
**Status**: [ ] PASS / [ ] FAIL

### Teste 6: Admin APIs bloqueadas

```powershell
curl http://127.0.0.1:8545 -X POST -H "Content-Type: application/json" ^
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"admin_nodeInfo\",\"id\":1}"
```

**Esperado**: Erro (method not found)
**Status**: [ ] PASS / [ ] FAIL

### Teste 7: Privacidade Tor

```powershell
.\test-privacy.bat
```

**Esperado**: IP real diferente do IP Tor; RPC funcionando
**Status**: [ ] PASS / [ ] FAIL / [ ] N/A

---

## Opcional: WireGuard

- [ ] WireGuard tunnel ativo (`wg show`)
- [ ] RPC acessivel via `http://10.0.0.1:8545` do dispositivo remoto
- [ ] Porta 51820 aberta no router (UDP)

## Opcional: Tor Hidden Service

- [ ] `.onion` address gerado (`tor/hidden_service/hostname`)
- [ ] RPC acessivel via `.onion:8545` de dispositivo com Tor
- [ ] `.onion` address guardado de forma segura

## Opcional: mTLS Proxy

- [ ] Certificados gerados (`scripts/generate-certs.ps1`)
- [ ] Proxy respondendo em `https://127.0.0.1:8443`
- [ ] Acesso sem client cert e rejeitado

---

## Monitoramento Regular

### Semanal
- [ ] Checar updates do Helios: [releases](https://github.com/a16z/helios/releases)
- [ ] Revisar `docker logs helios-client` para erros
- [ ] Executar `scripts/healthcheck.ps1`
- [ ] Verificar status do Windows Update

### Mensal
- [ ] Revisar regras de firewall (sem mudancas inesperadas)
- [ ] Verificar espaco em disco
- [ ] Rotacionar keys WireGuard (se aplicavel)
- [ ] Testar backup: `scripts/backup.ps1`

### Apos Mudanca de Rede
- [ ] Re-executar Testes 2, 3, 4 (binding e acessibilidade)
- [ ] Verificar UPnP ainda desabilitado
- [ ] Verificar Tor ainda funcionando

---

## Resposta a Incidentes (Quick Ref)

### RPC exposto na rede
1. `docker compose down` imediatamente
2. Verificar docker-compose.yml: porta deve ter `127.0.0.1:` prefix
3. Executar `hardening/windows-firewall.ps1`
4. Reiniciar com config verificado
5. Re-executar todos os testes

### Acesso nao autorizado suspeito
1. Desconectar da rede
2. Capturar logs: `docker logs helios-client > incident.log`
3. Rotacionar todas as keys (WireGuard, Tor)
4. Revisar padroes de acesso
5. Ver `docs/runbook.md` para procedimento completo

### Helios nao sincroniza
1. Verificar bootstrap RPC acessivel (Tor funcionando?)
2. Tentar RPC alternativo no config.toml
3. Verificar `docker logs helios-client` para erros
4. Limpar dados e resincronizar: `Remove-Item nodes\helios\data\* -Recurse`

---

## Sign-Off

| Check | Data | Responsavel |
|-------|------|-------------|
| Pre-deployment completo | _____ | _____ |
| Post-deployment tests OK | _____ | _____ |
| Pronto para uso | _____ | _____ |
