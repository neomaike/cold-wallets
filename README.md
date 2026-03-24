# Cold Wallets

Offline-first Bitcoin & Ethereum wallet toolkit with privacy by default.

All network operations routed through Tor. Transaction signing happens with the internet physically disabled (CLI mode) or online via dashboard. RPC queries verified cryptographically via Helios light client.

## Quick Start

Double-click **`start.bat`**. It automatically:
1. Requests administrator privileges (UAC prompt)
2. Checks Python and installs missing dependencies
3. Opens the dashboard at `http://127.0.0.1:8080`

From the dashboard:
- **Start Tor** with one click (downloads Tor Expert Bundle automatically, runs in background on port 9050)
- **Generate wallets** with private keys displayed (Show/Copy buttons)
- **Check balances** and **send BTC/ETH** via Tor
- **Manage disposable addresses** (generate pool, get address, track lifecycle)
- **Monitor system status** (Tor, Docker, RPC, dependencies)

For maximum security (offline signing with internet disabled), use the CLI scripts directly.

## Features

- **Dashboard** — visual interface at `127.0.0.1:8080`, threaded server, zero external dependencies
- **Automatic Tor** — downloads and runs `tor.exe` in background (no browser needed), SOCKS5 on port 9050
- **Auto-admin** — `start.bat` requests elevation via UAC on launch
- **Offline signing** — CLI scripts disable internet automatically during key generation and TX signing
- **Send-all** — always sends entire balance, no change output (BTC) or residual wei (ETH)
- **Tor-only networking** — all RPC calls, UTXO lookups, and broadcasts go through Tor
- **EIP-1559 fees** — ETH uses type 2 transactions with `eth_feeHistory` percentile-based estimation; legacy `gasPrice` as fallback
- **BTC fee by address type** — `detect_address_type()` + `estimate_tx_vsize()` for accurate fee calculation (p2wkh=68, np2wkh=91, p2pkh=148 vB/input)
- **Trustless RPC** — Helios light client verifies all Ethereum responses cryptographically via Docker
- **Disposable addresses** — hot address pool with lifecycle management (unused -> active -> funded -> spent)
- **MetaMask privacy** — local proxy routes MetaMask RPC calls through Tor

## Requirements

- **Python 3.14** — `C:\Python314\python.exe` (or any Python 3.10+ in PATH)
- **Windows 10/11** — administrator for network control
- **Internet** — for first-time dependency install and Tor download (~21MB)
- **Docker Desktop** — optional, for Helios light client

Dependencies are installed automatically by `start.bat`:
```
eth-account  bit  requests[socks]  PySocks
```

## Project Structure

```
Cold-Wallets/
|-- start.bat                   ONE-CLICK launcher (admin + deps + dashboard)
|
|-- dashboard/                  Visual interface
|   |-- server.py               Threaded API server (127.0.0.1:8080)
|   +-- index.html              Single-file dark UI (no external deps)
|
|-- cold_wallets/               Core: generate, sign, send crypto
|   |-- generate_wallets.py     Generate ETH + BTC wallets offline
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
|-- tools/                      Privacy & Tor management
|   |-- tor_manager.py          Download/start/stop Tor Expert Bundle
|   |-- check_tor.py            Verify Tor connection
|   |-- eth_rpc_proxy.py        RPC proxy for MetaMask (via Tor)
|   |-- start_all_services.bat  Unified startup: Tor + Helios/Proxy + Bitcoin
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
+-- audit_output/               Security audit patches (7 applied)
```

## Dashboard

The dashboard runs a threaded HTTP server on `127.0.0.1:8080` with background status updates every 15 seconds.

### Architecture
- **Backend**: Python `http.server` with `ThreadedHTTPServer` (each request in its own thread)
- **Frontend**: single HTML file with embedded CSS/JS, zero external dependencies
- **Status cache**: background thread polls Tor/Docker/RPC every 15s, API returns cached data instantly
- **Tor management**: downloads Tor Expert Bundle (~21MB), starts `tor.exe` as background process

### Ports

| Service | Port |
|---------|------|
| Dashboard | 8080 |
| Tor SOCKS (managed) | 9050 |
| Tor SOCKS (Browser) | 9150 |
| RPC ETH (Helios or Proxy) | 8545 |
| Bitcoin Core RPC | 8332 |

## CLI Scripts (Maximum Security)

For offline signing with internet physically disabled, use the `.bat` scripts directly:

| Script | Function | Admin? |
|--------|----------|:------:|
| `start.bat` | Launch dashboard (auto-admin, auto-deps) | Yes |
| `cold_wallets\gerar.bat` | Generate wallets offline | Yes |
| `cold_wallets\enviar_btc.bat` | Send-all BTC (fee by type + Tor) | Yes |
| `cold_wallets\enviar_eth.bat` | Send-all ETH (EIP-1559 + Tor) | Yes |
| `cold_wallets\assinar_btc.bat` | Sign BTC offline | Yes |
| `cold_wallets\assinar_eth.bat` | Sign ETH offline | Yes |
| `tools\start_all_services.bat` | Start Tor + Helios/Proxy + Bitcoin | No |

### Generate wallets (CLI, offline)

```
cold_wallets\gerar.bat          (run as Admin)
```

1. Script disables internet automatically
2. Generates 3 ETH + 3 BTC wallets
3. Saves to `cold_wallets\generated\`
4. Script re-enables internet
5. **Write down the keys and DELETE the JSON file**

### Send Bitcoin (CLI, send-all)

```
cold_wallets\enviar_btc.bat     (run as Admin)
```

1. Enter WIF (private key)
2. Script detects funded address (tests bc1q, 3..., 1...) via Tor
3. Enter destination — fee calculated by address type
4. Sends TOTAL balance (amount = balance - fee, no change)
5. Disables internet, signs OFFLINE, re-enables, broadcasts via Tor

### Send Ethereum (CLI, send-all + EIP-1559)

```
cold_wallets\enviar_eth.bat     (run as Admin)
```

1. Enter private key (hex)
2. Script fetches balance/nonce/EIP-1559 fees via Tor
3. Enter destination — sends `balance - (21000 * maxFeePerGas)`
4. Disables internet, signs OFFLINE, re-enables, broadcasts via Tor

## Privacy Model

| Operation | Dashboard | CLI |
|-----------|-----------|-----|
| Wallet generation | Online (keys in memory) | Internet disabled |
| Transaction signing | Online (via Tor) | Internet disabled |
| Balance/nonce lookup | Via Tor | Via Tor |
| TX broadcast | Via Tor | Via Tor |
| MetaMask RPC | Via local Tor proxy | Via local Tor proxy |

## Security

- **Private keys** stored in `generated/` and `address_pool/` — NEVER committed, GITIGNORED
- **Tor runtime** downloaded to `tools/tor_runtime/` — GITIGNORED
- **RPC credentials** stored ONLY in `F:\BitcoinData\bitcoin.conf`
- **Dashboard** bound to `127.0.0.1` only — not accessible from network
- **CORS** on RPC proxy restricted to localhost and Chrome extensions
- All monetary values use `Decimal` (never `float`)
- Address validation (EIP-55 for ETH, base58/bech32 for BTC) before every send
- `except Exception:` only (never bare `except:`)

## RPC Documentation

- [Quickstart](rpc/docs/quickstart.md) — Helios setup in 5 minutes
- [Threat Model](rpc/docs/threat-model.md) — security guarantees and attack analysis
- [Runbook](rpc/docs/runbook.md) — operational procedures, updates, incident response
- [Security Checklist](rpc/CHECKLIST.md) — pre/post deployment validation

## Lint

```bash
C:\Python314\python.exe -m ruff check --select=E,W,F cold_wallets/ tools/ dashboard/
```
