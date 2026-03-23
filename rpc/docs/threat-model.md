# Threat Model - Private EVM RPC with Helios Light Client

## Overview

This document describes the threat model for running a private Ethereum RPC
using Helios light client on a local Windows machine. Goal: eliminate IP
correlation with on-chain activity while minimizing storage and trust requirements.

**Deployment**: Local machine (Windows/WSL2)
**Client**: Helios (Rust light client by a16z)
**Storage**: Near zero (~100MB for checkpoints)

---

## Architecture Overview

```
+------------------------------------------+
|              YOUR LOCAL PC               |
|                                          |
|  +------------+     +----------------+   |
|  | Browser /  |     |    Helios      |   |
|  | Wallet     |---->|  Light Client  |   |
|  | (MetaMask) |     |  127.0.0.1:8545|   |
|  +------------+     +-------+--------+   |
|                             |            |
|                    [Verifies proofs      |
|                     locally]             |
|                             |            |
+-----------------------------+------------+
                              |
                              v
                    +-------------------+
                    | Bootstrap RPC     |
                    | (Infura/Alchemy)  |
                    | via Tor (optional)|
                    +-------------------+
                              |
                              v
                    [Ethereum Network]
```

---

## How Helios Works (Security Model)

1. **Bootstrap**: Connects to an untrusted RPC to fetch block headers and state proofs
2. **Verification**: Validates ALL data against consensus using cryptographic proofs
3. **Local RPC**: Exposes verified data on localhost
4. **Trust Model**: You trust Ethereum consensus, NOT the RPC provider

**Key Insight**: Even if the bootstrap RPC is malicious, it cannot:
- Serve you fake balances (proof verification fails)
- Serve you fake transactions (merkle proofs validated)
- Lie about block headers (consensus light client checks)

---

## Assets to Protect

| Asset | Criticality | Description |
|-------|-------------|-------------|
| Local RPC endpoint | HIGH | Must never be exposed to network |
| Query patterns | HIGH | What contracts/addresses you query |
| IP address | HIGH | Must not correlate with queries |
| Private keys | CRITICAL | Never on this machine; hardware wallet |
| Helios checkpoint | LOW | Public data, can be re-fetched |

---

## Threat Analysis

### T1: IP Correlation via Bootstrap RPC

**Threat**: Bootstrap RPC provider logs your IP and correlates with query patterns.

**Attack Vector**:
- Infura/Alchemy sees: IP X queried balance of wallet Y, then contract Z
- Provider can build activity profile

**Mitigations**:
| Control | Implementation | Effectiveness |
|---------|----------------|---------------|
| Tor for bootstrap | Route Helios through Tor | HIGH |
| Multiple providers | Rotate between providers | MEDIUM |
| Local caching | Helios caches verified data | MEDIUM |
| VPN | Generic IP masking | MEDIUM |

**Recommended**: Configure Helios to use Tor SOCKS proxy for bootstrap connections.

```toml
# helios config
[rpc]
proxy = "socks5://127.0.0.1:9050"  # Tor
```

---

### T2: Local Network Exposure

**Threat**: RPC accessible from LAN, allowing unauthorized access.

**Attack Vectors**:
- Other devices on same network query your RPC
- Malware on network scans for open ports
- Guest devices access

**Mitigations**:
| Control | Implementation |
|---------|----------------|
| Bind localhost only | Helios --http.addr 127.0.0.1 |
| Windows Firewall | Block inbound 8545 from all |
| No port forwarding | Router config |
| Network segmentation | Separate VLAN for untrusted devices |

**Verification**:
```powershell
# From another device on LAN - should fail
curl http://YOUR_LAN_IP:8545 -X POST -d '{"jsonrpc":"2.0","method":"eth_blockNumber","id":1}'
```

---

### T2.5: Cross-Origin Browser Attack (CORS)

**Threat**: Malicious website queries your local RPC via JavaScript.

**Attack Vector**:
- User visits malicious site while Helios is running
- Site sends `fetch('http://127.0.0.1:8545', ...)` requests
- If CORS allows `*`, browser permits the request
- Attacker reads balances, transaction history, activity patterns

**Mitigations**:
| Control | Implementation |
|---------|----------------|
| Restrict CORS origins | `cors_origins` limited to wallet extensions only |
| No wildcard | Never use `cors_origins = ["*"]` |
| Nginx CORS filter | Only allows `chrome-extension://` origins |

**Current Status**: MITIGATED - CORS restricted to MetaMask and Rabby extension IDs.

---

### T3: RPC Method Abuse

**Threat**: Dangerous RPC methods exposed.

**Analysis**: Helios is inherently safe because it's a **read-only light client**.
It does NOT support:
- `personal_*` (no keystore)
- `admin_*` (no admin functions)
- `debug_*` (no debug access)
- `eth_sendTransaction` with local signing (no keys)

**Supported (safe)**: `eth_call`, `eth_getBalance`, `eth_blockNumber`, etc.

**Risk Level**: LOW - Helios cannot sign transactions or expose keys.

---

### T4: Malicious Bootstrap Data

**Threat**: Compromised RPC serves malicious data.

**Analysis**: This is Helios's core security model. All data is verified:
- Block headers: Verified against consensus checkpoints
- State proofs: Merkle proofs validated cryptographically
- Transaction receipts: Inclusion proofs verified

**Attack Attempt**: RPC says your balance is 1000 ETH (it's actually 0)
**Result**: Helios rejects - proof doesn't match state root in verified header

**Risk Level**: VERY LOW - Cryptographic guarantees

---

### T5: Checkpoint Poisoning

**Threat**: Malicious checkpoint file causes Helios to follow wrong chain.

**Mitigations**:
| Control | Implementation |
|---------|----------------|
| Official checkpoints | Use Helios default or ethereum/consensus-specs |
| Multiple sources | Cross-reference checkpoint from multiple providers |
| Recent checkpoint | Use checkpoint < 2 weeks old |

**Verification**:
```bash
# Compare checkpoint hash with multiple sources
curl https://beaconcha.in/api/v1/epoch/finalized | jq '.data.epoch'
```

---

### T6: Local Machine Compromise

**Threat**: Malware on your PC accesses RPC or monitors queries.

**Attack Vectors**:
- Keylogger captures wallet passwords
- Malware queries your RPC for balance info
- Screen capture during transactions

**Mitigations**:
| Control | Implementation |
|---------|----------------|
| No keys on machine | Hardware wallet only |
| Endpoint protection | Windows Defender / reputable AV |
| Regular updates | Windows Update enabled |
| Principle of least privilege | Non-admin daily account |

**Note**: If your machine is compromised, the attacker has your access level.
This is outside Helios's threat model - it's a general security requirement.

---

### T7: Remote Access Security (WireGuard/Tor)

**Threat**: If you enable remote access, attack surface increases.

**WireGuard Risks**:
- Key compromise = full tunnel access
- Port 51820 visible to scanners

**Tor Hidden Service Risks**:
- .onion can be discovered if leaked
- Tor network attacks (unlikely for small target)

**Mitigations**:
| Control | Implementation |
|---------|----------------|
| WireGuard key rotation | Rotate keys every 90 days |
| Strong key generation | Use wg genkey properly |
| Firewall WG port | Only allow expected peer IPs |
| Tor auth | HiddenServiceAuthorizeClient |
| No public sharing | Never share .onion address |

---

## Trust Hierarchy

1. **Ethereum Consensus**: TRUSTED (cryptographic guarantees)
2. **Helios Code**: TRUSTED (open source, audited)
3. **Local Machine**: TRUSTED (you control it)
4. **Bootstrap RPC**: UNTRUSTED (data verified)
5. **Network (LAN/WAN)**: HOSTILE (no exposure)

---

## Security Controls Matrix

| Layer | Control | Required? | Status |
|-------|---------|-----------|--------|
| Network | Bind 127.0.0.1 only | YES | Default |
| Network | Firewall block 8545 inbound | YES | Configure |
| Network | Tor for bootstrap RPC | RECOMMENDED | Optional |
| Transport | WireGuard for remote | NO | Optional |
| Transport | Tor hidden service | NO | Optional |
| Application | Verify Helios binary hash | YES | Manual |
| Application | Use recent checkpoint | YES | Default |
| Data | No private keys | YES | Architecture |
| Data | Hardware wallet | YES | User responsibility |

---

## What Helios CANNOT Protect Against

1. **Compromised local machine**: If PC has malware, game over
2. **User error**: Signing malicious transactions
3. **Weak operational security**: Sharing .onion, reusing passwords
4. **Physical access**: Someone with physical access to your PC

---

## Comparison: Helios vs Full Node vs Public RPC

| Aspect | Helios | Full Node | Public RPC |
|--------|--------|-----------|------------|
| Storage | ~100 MB | 500GB-2TB | 0 |
| IP Privacy | HIGH (with Tor) | TOTAL | NONE |
| Trustless | YES | YES | NO |
| Query Privacy | LOCAL | TOTAL | NONE |
| Setup Complexity | LOW | HIGH | NONE |
| Cost | Free | Disk cost | Free/Paid |

**Helios Sweet Spot**: Maximum privacy-to-effort ratio when you can't run a full node.

---

## Incident Indicators

Monitor for:
- Unexpected network connections from Helios
- RPC responses on non-localhost interfaces
- Helios process running as different user
- Checkpoint file modifications
- Unusual WireGuard connection attempts

---

## Residual Risks (Accepted)

1. **Bootstrap RPC sees connection timing**: They know WHEN you're active, not WHAT you query (if using Tor)
2. **Tor exit node sees bootstrap traffic**: Mitigated by HTTPS to RPC
3. **ISP sees Tor usage**: Use bridges if this is a concern

See `runbook.md` for operational procedures.
