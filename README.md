# Cold Wallets

Offline-first Bitcoin & Ethereum wallet toolkit with privacy by default.

All network operations routed through Tor. Transaction signing happens with the internet physically disabled. RPC queries verified cryptographically via Helios light client.

## Features

- **Offline signing** — internet disabled automatically during key generation and TX signing (requires Admin)
- **Send-all** — always sends entire balance, no change output (BTC) or residual wei (ETH)
- **Tor-only networking** — all RPC calls, UTXO lookups, and broadcasts go through Tor (SOCKS5 127.0.0.1:9150)
- **EIP-1559 fees** — ETH uses type 2 transactions with `eth_feeHistory` percentile-based estimation; legacy `gasPrice` as fallback
- **BTC fee by address type** — `detect_address_type()` + `estimate_tx_vsize()` for accurate fee calculation (p2wkh=68, np2wkh=91, p2pkh=148 vB/input)
- **Trustless RPC** — Helios light client verifies all Ethereum responses cryptographically via Docker
- **Disposable addresses** — hot address pool with lifecycle management (unused -> active -> funded -> spent)
- **MetaMask privacy** — local proxy routes MetaMask RPC calls through Tor

## Requirements

- **Python 3.14** — `C:\Python314\python.exe`
- **Tor Browser** running (port 9150) — or Docker Tor (port 9050)
- **Administrator** — required for network control (disable/enable internet)
- **Docker Desktop** — optional, for Helios light client

### Install dependencies

```
C:\Python314\python.exe -m pip install eth-account bit requests[socks] PySocks
```

Or run `cold_wallets\install.bat`.

## Project Structure

```
Cold-Wallets/
|-- cold_wallets/               Core: generate, sign, send crypto
|   |-- generate_wallets.py     Generate 3 ETH + 3 BTC wallets offline
|   |-- sign_eth.py             Sign ETH offline (send-all + EIP-1559)
|   |-- sign_btc.py             Sign BTC offline (send-all + fee by type)
|   |-- enviar_eth.py           Automated send-all ETH (EIP-1559 + Tor)
|   |-- enviar_btc.py           Automated send-all BTC (fee by type + Tor)
|   |-- address_validation.py   ETH (EIP-55) and BTC (base58/bech32) validation
|   |-- network_control.py      Internet on/off control (requires Admin)
|   |-- tools/
|   |   |-- fetch_tx_data.py    Fetch nonce/UTXOs via Tor
|   |   +-- broadcast_tor.py    Broadcast signed TXs via Tor
|   +-- hot_disposable/         Disposable address system
|       |-- generate_disposable.py
|       |-- disposable_manager.py
|       +-- sweep_to_cold.py
|
|-- tools/                      Privacy tools & unified startup
|   |-- check_tor.py / .bat     Verify Tor connection
|   |-- eth_rpc_proxy.py        RPC proxy for MetaMask (Tor fallback)
|   |-- start_all_services.bat  Unified startup: Tor + Helios/Proxy + Bitcoin
|   |-- stop_all_services.bat   Stop Helios + Proxy
|   +-- status.bat              Service status check
|
|-- rpc/                        Trustless RPC (Helios light client)
|   |-- helios/                 Docker Compose + config
|   |-- tor/                    Docker Tor (hidden service, optional)
|   |-- hardening/              Windows firewall + disable UPnP
|   |-- scripts/                PowerShell: healthcheck, backup, certs
|   +-- docs/                   quickstart, threat model, runbook
|
|-- hardware/                   PowerShell scripts for disk setup + Bitcoin Core
+-- audit_output/               Security audit results + applied patches
```

## Quick Start

### Generate wallets (offline)

```
cold_wallets\gerar.bat          (run as Admin)
```

1. Script disables internet automatically
2. Generates 3 ETH + 3 BTC wallets
3. Saves to `cold_wallets\generated\`
4. Script re-enables internet
5. **Write down the keys and DELETE the JSON file**

### Send Bitcoin (send-all)

```
cold_wallets\enviar_btc.bat     (run as Admin)
```

1. Enter WIF (private key)
2. Script detects funded address (tests bc1q, 3..., 1...) via Tor
3. Enter destination — script calculates fee by address type:
   - `bc1q` (Native SegWit): 68 vB/input
   - `3...` (Nested SegWit): 91 vB/input
   - `1...` (Legacy): 148 vB/input
4. Sends TOTAL balance (amount = balance - fee, no change)
5. Disables internet, signs OFFLINE
6. Re-enables internet, broadcasts via Tor

### Send Ethereum (send-all + EIP-1559)

```
cold_wallets\enviar_eth.bat     (run as Admin)
```

1. Enter private key (hex)
2. Script fetches balance/nonce/EIP-1559 fees via Tor (`eth_feeHistory`)
3. Enter destination — script calculates:
   - `gas_cost = 21000 * maxFeePerGas`
   - `send = balance - gas_cost`
4. Sends TOTAL balance
5. Signs as type 2 (EIP-1559) or legacy (fallback)
6. Disables internet, signs OFFLINE
7. Re-enables internet, broadcasts via Tor

### Disposable addresses

```
cd cold_wallets\hot_disposable
run_generate_disposable.bat --count 20 --crypto both   # generate pool
run_manager.bat status                                   # pool status
run_manager.bat get-address --crypto btc                 # get address
run_sweep.bat <cold_wallet_address>                      # sweep to cold
```

## Private RPC (Helios Light Client)

**Problem:** Public RPCs (Infura, Alchemy) log your IP, addresses, and transactions.

**Solution:** Helios light client verifies ALL responses cryptographically. Even if the bootstrap RPC lies, Helios detects it via proofs.

### Unified startup

```
tools\start_all_services.bat
```

1. Checks Tor (9150 or 9050) — opens Tor Browser if needed
2. Checks Docker — if available, starts Helios (trustless)
3. If no Docker — falls back to `eth_rpc_proxy.py` (via Tor)
4. Starts Bitcoin Core (if configured)

### Helios vs Proxy Fallback

| Aspect | Helios (Docker) | Proxy Fallback |
|---------|----------------|----------------|
| Verification | Cryptographic (proofs) | None (trusts RPC) |
| IP privacy | Yes (via Tor) | Yes (via Tor) |
| Requirement | Docker Desktop | Python only |
| Storage | ~100 MB | 0 |

### Initial setup (once)

```
rpc\setup-first-time.bat   (as Admin)
```

Configures firewall, disables UPnP, creates config, pulls Docker image.

### MetaMask with privacy

1. Open Tor Browser (keep open, port 9150)
2. Start proxy: `tools\start_rpc_proxy.bat`
3. In MetaMask, add custom network:
   - RPC URL: `http://127.0.0.1:8545`
   - Chain ID: 1
   - Symbol: ETH

## Ports

| Service | Port |
|---------|------|
| Tor Browser SOCKS | 9150 |
| Docker Tor SOCKS | 9050 |
| RPC ETH (Helios or Proxy) | 8545 |
| Bitcoin Core RPC | 8332 |

## Key Scripts

| Script | Function | Admin? |
|--------|----------|:------:|
| `cold_wallets\gerar.bat` | Generate wallets offline | Yes |
| `cold_wallets\enviar_btc.bat` | Send-all BTC (fee by type + Tor) | Yes |
| `cold_wallets\enviar_eth.bat` | Send-all ETH (EIP-1559 + Tor) | Yes |
| `cold_wallets\assinar_btc.bat` | Sign BTC offline | Yes |
| `cold_wallets\assinar_eth.bat` | Sign ETH offline | Yes |
| `tools\start_all_services.bat` | Start Tor + Helios/Proxy + Bitcoin | No |
| `tools\stop_all_services.bat` | Stop Helios + Proxy | No |
| `tools\status.bat` | Check all services | No |
| `tools\check_tor.bat` | Verify Tor connection | No |
| `rpc\setup-first-time.bat` | Initial hardening + setup | Yes |

## Privacy Model

| Operation | Protection |
|-----------|-----------|
| Wallet generation | Internet physically disabled |
| Transaction signing | Internet physically disabled |
| Balance/nonce lookup | Via Tor |
| TX broadcast | Via Tor |
| MetaMask RPC | Via local Tor proxy |
| Bitcoin Core | Tor-only connections (`onlynet=onion`) |

## Security

- **Private keys** are stored in `generated/` and `address_pool/` — NEVER committed, GITIGNORED
- **RPC credentials** stored ONLY in `F:\BitcoinData\bitcoin.conf` — NEVER in docs or code
- **CORS** on RPC proxy restricted to localhost and Chrome extensions
- All monetary values use `Decimal` (never `float`)
- Address validation (EIP-55 checksum for ETH, base58/bech32 for BTC) before every send
- `except Exception:` only (never bare `except:`)

## RPC Documentation

Detailed docs for the Helios RPC subsystem:

- [Quickstart](rpc/docs/quickstart.md) — setup in 5 minutes
- [Threat Model](rpc/docs/threat-model.md) — security guarantees and attack analysis
- [Runbook](rpc/docs/runbook.md) — operational procedures, updates, incident response
- [Security Checklist](rpc/CHECKLIST.md) — pre/post deployment validation

## Lint

```bash
C:\Python314\python.exe -m ruff check --select=E,W,F cold_wallets/ tools/
```
