# Runbook - Private EVM RPC Operations

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Starting Services](#starting-services)
3. [Stopping Services](#stopping-services)
4. [Health Checks](#health-checks)
5. [Updating Components](#updating-components)
6. [Key Rotation](#key-rotation)
7. [Backup Procedures](#backup-procedures)
8. [Restore Procedures](#restore-procedures)
9. [Incident Response](#incident-response)
10. [Troubleshooting](#troubleshooting)

---

## Daily Operations

### Morning Checklist

```powershell
# 1. Check Helios is running
docker ps | findstr helios

# 2. Check sync status
curl -s -X POST http://127.0.0.1:8545 ^
  -H "Content-Type: application/json" ^
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_syncing\",\"params\":[],\"id\":1}"

# 3. Check block number (should be recent)
curl -s -X POST http://127.0.0.1:8545 ^
  -H "Content-Type: application/json" ^
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}"

# 4. Verify localhost-only binding
netstat -an | findstr 8545
# Should show 127.0.0.1:8545 ONLY, never 0.0.0.0:8545
```

### Weekly Checklist

- [ ] Check for Helios updates
- [ ] Review logs for anomalies
- [ ] Verify firewall rules unchanged
- [ ] Test RPC functionality
- [ ] Check disk space

---

## Starting Services

### Start Helios (Docker)

```powershell
cd rpc/helios
docker compose up -d

# Verify startup
docker logs helios-client --tail 50
```

### Start Helios (Native Windows)

```powershell
# If using native binary
.\helios.exe `
  --network mainnet `
  --rpc-bind-ip 127.0.0.1 `
  --rpc-port 8545 `
  --execution-rpc https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY `
  --consensus-rpc https://www.lightclientdata.org
```

### Start with Tor (Optional)

```powershell
# 1. Start Tor first
docker compose -f tor/docker-compose.yml up -d

# 2. Verify Tor is running
curl --socks5 127.0.0.1:9050 https://check.torproject.org/api/ip

# 3. Start Helios with Tor proxy
docker compose up -d
```

### Start All Services

```powershell
# Full stack startup script
.\scripts\start-all.ps1
```

---

## Stopping Services

### Graceful Shutdown

```powershell
cd rpc/helios
docker compose down

# If using Tor
docker compose -f tor/docker-compose.yml down
```

### Emergency Stop

```powershell
# Stop all containers immediately
docker stop $(docker ps -q)

# Or specific container
docker kill helios-client
```

---

## Health Checks

### Quick Health Check

```powershell
.\scripts\healthcheck.ps1
```

### Manual Checks

```powershell
# 1. Container status
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 2. RPC responding
curl -s -X POST http://127.0.0.1:8545 ^
  -H "Content-Type: application/json" ^
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}"

# 3. Network not exposed
# Run from another machine on same network - should FAIL
curl http://YOUR_LAN_IP:8545

# 4. Check resource usage
docker stats --no-stream

# 5. Check logs for errors
docker logs helios-client --tail 100 2>&1 | findstr /i "error\|warn\|fail"
```

### Verify Isolation

```powershell
# Port should ONLY be on localhost
netstat -an | findstr "8545"
# Expected: TCP    127.0.0.1:8545    0.0.0.0:0    LISTENING

# Should NOT show:
# TCP    0.0.0.0:8545    ...  (DANGEROUS - exposed to all interfaces)
```

---

## Updating Components

### Update Helios

Imagens Docker estao pinnadas por versao para estabilidade. Para atualizar:

```powershell
# 1. Check current version
docker exec helios-client helios --version

# 2. Check for updates
# Visit: https://github.com/a16z/helios/releases

# 3. Edit docker-compose.yml with new version
# Example: change ghcr.io/a16z/helios:0.11.0 to :0.12.0
notepad nodes\helios\docker-compose.yml

# 4. Pull new image
docker compose pull

# 5. Recreate container
docker compose up -d --force-recreate

# 6. Verify new version
docker exec helios-client helios --version

# 7. Test RPC still works
curl -s -X POST http://127.0.0.1:8545 ^
  -H "Content-Type: application/json" ^
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}"
```

### Update Tor

```powershell
# 1. Check new version: https://hub.docker.com/r/osminogin/tor-simple/tags
# 2. Edit docker-compose.yml with new tag
cd tor
notepad docker-compose.yml

# 3. Pull and recreate
docker compose pull
docker compose up -d --force-recreate
```

### Version Pinning Reference

| Componente | Arquivo | Versao Atual |
|-----------|---------|-------------|
| Helios | `helios/docker-compose.yml` | `0.11.0` |
| Nginx | `reverse-proxy/docker-compose.yml` | `stable-alpine` |
| Tor | `tor/docker-compose.yml` | `0.4.8` |
| OP-geth | `l2-templates/optimism/docker-compose.yml` | `v1.101609.0` |
| OP-node | `l2-templates/optimism/docker-compose.yml` | `v1.16.6` |
| Nitro | `l2-templates/arbitrum/docker-compose.yml` | `v3.9.5` |

### Rollback Procedure

```powershell
# If update breaks things, revert docker-compose.yml to previous version tag
docker compose down
notepad nodes\helios\docker-compose.yml  # change version back
docker compose up -d
```

---

## Key Rotation

### Rotate WireGuard Keys (If Using Remote Access)

```powershell
# 1. Generate new server keys
wg genkey | tee server_private_new.key | wg pubkey > server_public_new.key

# 2. Generate new client keys
wg genkey | tee client_private_new.key | wg pubkey > client_public_new.key

# 3. Update server config with new keys
# Edit wireguard/wg0.conf

# 4. Update client config
# Edit wireguard/client.conf

# 5. Restart WireGuard
# On server (if applicable)
wg-quick down wg0
wg-quick up wg0

# 6. Test connection from client

# 7. Securely delete old keys
# PowerShell secure delete
$oldKey = "server_private_old.key"
$bytes = [System.IO.File]::ReadAllBytes($oldKey)
[Array]::Clear($bytes, 0, $bytes.Length)
[System.IO.File]::WriteAllBytes($oldKey, $bytes)
Remove-Item $oldKey
```

### Rotate Tor Hidden Service Keys (If Using)

```powershell
# WARNING: This changes your .onion address!

# 1. Stop Tor
docker compose -f tor/docker-compose.yml down

# 2. Backup old keys (encrypted)
.\scripts\backup.ps1

# 3. Remove old hidden service directory
# This will generate new keys on restart
Remove-Item -Recurse tor/hidden_service

# 4. Start Tor - new .onion generated
docker compose -f tor/docker-compose.yml up -d

# 5. Get new .onion address
Get-Content tor/hidden_service/hostname

# 6. Update any clients with new address
```

---

## Backup Procedures

### What to Backup

| Item | Location | Priority | Encryption Required |
|------|----------|----------|---------------------|
| Helios config | helios/config.toml | HIGH | No (no secrets) |
| WireGuard keys | wireguard/*.key | CRITICAL | YES |
| Tor hidden service | tor/hidden_service/ | HIGH | YES |
| Scripts | scripts/ | MEDIUM | No |
| Documentation | docs/ | LOW | No |

### What NOT to Backup (or encrypt first)

- Private keys (should not exist on this machine)
- WireGuard private keys (must be encrypted)
- Tor private keys (must be encrypted)
- Any .env files with secrets

### Automated Backup

```powershell
.\scripts\backup.ps1

# This will:
# 1. Create timestamped backup
# 2. Encrypt sensitive files
# 3. Store in backup directory
```

### Manual Backup

```powershell
# 1. Create backup directory
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = "backups\$timestamp"
New-Item -ItemType Directory -Path $backupDir

# 2. Copy configs (non-sensitive)
Copy-Item nodes\helios\*.toml $backupDir\
Copy-Item nodes\helios\docker-compose.yml $backupDir\

# 3. Encrypt and copy sensitive files
# Using 7-Zip with AES-256
$password = Read-Host -AsSecureString "Backup password"
$plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
  [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password))

7z a -p"$plainPassword" -mhe=on "$backupDir\wireguard-keys.7z" infra\wireguard\*.key
7z a -p"$plainPassword" -mhe=on "$backupDir\tor-hidden-service.7z" infra\tor\hidden_service\
```

---

## Restore Procedures

### Full Restore

```powershell
# 1. Extract backup
$backupDir = "backups\20240115-120000"  # Use actual backup name
Copy-Item "$backupDir\*.toml" nodes\helios\
Copy-Item "$backupDir\docker-compose.yml" nodes\helios\

# 2. Decrypt sensitive files
7z x "$backupDir\wireguard-keys.7z" -oinfra\wireguard\
7z x "$backupDir\tor-hidden-service.7z" -oinfra\tor\

# 3. Start services
docker compose up -d

# 4. Verify
.\scripts\healthcheck.ps1
```

### Restore WireGuard Keys Only

```powershell
# 1. Stop WireGuard
wg-quick down wg0

# 2. Decrypt and restore keys
7z x backups\TIMESTAMP\wireguard-keys.7z -oinfra\wireguard\

# 3. Restart WireGuard
wg-quick up wg0
```

---

## Incident Response

### IR-1: Suspected Unauthorized Access

**Indicators**:
- Unknown connections in logs
- RPC accessible from network (not just localhost)
- WireGuard connections from unknown IPs

**Response**:
```powershell
# 1. IMMEDIATE: Isolate
docker compose down
# Disconnect network if severe

# 2. Capture evidence
docker logs helios-client > incident_helios_$(Get-Date -Format yyyyMMdd).log
netstat -an > incident_netstat_$(Get-Date -Format yyyyMMdd).log
Get-EventLog -LogName Security -Newest 1000 > incident_security_$(Get-Date -Format yyyyMMdd).log

# 3. Check for exposure
# Review firewall rules
netsh advfirewall firewall show rule name=all | findstr 8545

# 4. Rotate all keys (WireGuard, Tor)
# See Key Rotation section

# 5. Review and restart with verified config
docker compose up -d
```

### IR-2: RPC Exposed to Network

**Indicators**:
- `netstat` shows 0.0.0.0:8545 instead of 127.0.0.1:8545
- External scan finds open port

**Response**:
```powershell
# 1. IMMEDIATE: Stop service
docker compose down

# 2. Fix configuration
# Verify docker-compose.yml has:
# ports:
#   - "127.0.0.1:8545:8545"  # NOT "8545:8545"

# 3. Add firewall rule
netsh advfirewall firewall add rule name="Block RPC External" ^
  dir=in action=block protocol=tcp localport=8545 ^
  remoteip=any

# 4. Allow only localhost
netsh advfirewall firewall add rule name="Allow RPC Localhost" ^
  dir=in action=allow protocol=tcp localport=8545 ^
  remoteip=127.0.0.1

# 5. Restart with correct config
docker compose up -d

# 6. Verify fix
netstat -an | findstr 8545
# Must show 127.0.0.1:8545 only
```

### IR-3: Helios Serving Bad Data

**Indicators**:
- Transactions failing unexpectedly
- Balance queries returning wrong values
- Block numbers significantly behind

**Response**:
```powershell
# 1. Verify against another source
# Compare block number with etherscan.io

# 2. Check checkpoint age
docker logs helios-client | findstr checkpoint

# 3. Force resync with fresh checkpoint
docker compose down
Remove-Item nodes\helios\data\* -Recurse
docker compose up -d

# 4. If persists, try different bootstrap RPC
# Edit config.toml to use different provider
```

### IR-4: Tor Hidden Service Compromised

**Indicators**:
- .onion address found in public (you didn't share it)
- Unexpected traffic patterns

**Response**:
```powershell
# 1. Stop Tor immediately
docker compose -f tor/docker-compose.yml down

# 2. Rotate hidden service (new .onion)
Remove-Item infra\tor\hidden_service -Recurse
docker compose -f tor/docker-compose.yml up -d

# 3. Do NOT share new address publicly
Get-Content infra\tor\hidden_service\hostname
```

---

## Troubleshooting

### Helios Won't Start

```powershell
# Check logs
docker logs helios-client

# Common issues:
# 1. Port already in use
netstat -an | findstr 8545
# Kill conflicting process

# 2. Invalid checkpoint
# Delete data and resync
Remove-Item nodes\helios\data\* -Recurse

# 3. Bootstrap RPC unreachable
# Check internet/Tor connection
curl https://eth-mainnet.g.alchemy.com/v2/demo
```

### RPC Returns Errors

```powershell
# Check if synced
curl -s -X POST http://127.0.0.1:8545 ^
  -H "Content-Type: application/json" ^
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_syncing\",\"params\":[],\"id\":1}"

# If syncing, wait for completion

# Check specific error
docker logs helios-client --tail 50
```

### WireGuard Connection Failed

```powershell
# Check WireGuard status
wg show

# Common issues:
# 1. Keys mismatch - verify public keys match on both sides
# 2. Firewall blocking UDP 51820
# 3. NAT traversal issues - try different endpoint port
```

### High Resource Usage

```powershell
# Check container resources
docker stats

# Helios should use:
# - CPU: < 10% normally
# - Memory: < 500MB
# - Disk: < 1GB

# If higher, check logs for issues
docker logs helios-client | findstr -i "error\|memory\|cpu"
```

---

## Contact and Escalation

For security issues with Helios:
- GitHub: https://github.com/a16z/helios/security

For this setup:
- Review threat-model.md
- Check CHECKLIST.md for validation steps
