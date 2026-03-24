# Cold Wallets

Offline-first Bitcoin & Ethereum wallet toolkit with privacy by default.

All network operations routed through Tor. Transaction signing happens with the internet physically disabled (CLI mode) or online via dashboard. RPC queries verified cryptographically via Helios light client.

## Quick Start

Double-click **`start.bat`**. It automatically:
1. Requests administrator privileges (UAC prompt)
2. Checks Python and installs missing dependencies (`eth-account`, `bit`, `requests`, `PySocks`)
3. Opens the dashboard at `http://127.0.0.1:8888`

From the dashboard:
- **Start Tor** with one click (downloads Tor Expert Bundle ~21MB, runs `tor.exe` in background on port 9050)
- **Start RPC Proxy** to route MetaMask/ETH queries through Tor (port 8545)
- **Generate wallets** — keys displayed in sidebar with Show/Copy, saved to file
- **Check balances** and **send BTC/ETH** via Tor (send-all pattern)
- **Manage disposable addresses** — generate pool, get one-time addresses, track lifecycle
- **Monitor system** — Tor, Docker, RPC, dependencies, network status

For maximum security (offline signing with internet disabled), use the CLI scripts directly.

## Features

- **One-click setup** — `start.bat` handles admin elevation, dependencies, and dashboard launch
- **Automatic Tor** — downloads and runs `tor.exe` in background (SOCKS5 port 9050, no browser needed)
- **Dashboard** — visual interface at `127.0.0.1:8888`, threaded server, zero external dependencies
- **Sidebar wallet viewer** — generated wallets persist in right sidebar, reopen anytime
- **Offline signing (CLI)** — internet disabled automatically during key generation and TX signing
- **Send-all** — always sends entire balance, no change output (BTC) or residual wei (ETH)
- **Tor-only networking** — all RPC calls, UTXO lookups, and broadcasts go through Tor
- **EIP-1559 fees** — ETH uses type 2 transactions with `eth_feeHistory` percentile-based estimation
- **BTC fee by address type** — native segwit (bc1q), wrapped segwit (3...), legacy (1...) with accurate vsize
- **Native SegWit (bc1q)** — manual bech32 derivation since `bit` library only supports P2SH-wrapped
- **Trustless RPC** — Helios light client verifies Ethereum responses cryptographically via Docker
- **Disposable addresses** — one-time address pool with lifecycle (unused -> active -> funded -> spent)
- **MetaMask privacy** — local proxy routes RPC calls through Tor on port 8545

## Requirements

- **Python 3.10+** — tested with 3.14 (`C:\Python314\python.exe`)
- **Windows 10/11** — administrator for network control
- **Internet** — for first-time dependency install and Tor download
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
|   |-- server.py               ThreadedHTTPServer API (127.0.0.1:8888)
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
|   |-- eth_rpc_proxy.py        RPC proxy for MetaMask (via Tor, port 8545)
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

The dashboard runs on `127.0.0.1:8888` with a threaded HTTP server and background status cache.

### Layout (no scroll, viewport-fit)
- **Top row:** System Status | Generate Wallets | Disposable Pool
- **Bottom row:** Send Bitcoin | Send Ethereum | RPC Status
- **Right sidebar:** Generated wallets with Show/Copy (persists until closed)

### Architecture
- **Backend**: `ThreadedHTTPServer` — each request in its own thread
- **Frontend**: single HTML file, embedded CSS/JS, zero external dependencies
- **Status cache**: background thread polls Tor/Docker/RPC every 15s, API returns cached data
- **Tor management**: downloads Tor Expert Bundle, starts `tor.exe` as background process
- **RPC proxy**: starts `eth_rpc_proxy.py` on port 8545 via Tor
- **Security**: bound to 127.0.0.1 only, HTML escaped, clipboard error handling, thread-safe RPC lock

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | / | Dashboard HTML (any non-API path serves HTML) |
| POST | /api/status | System status (cached) |
| POST | /api/generate-wallets | Generate cold wallets |
| POST | /api/generate-disposable | Generate disposable address pool |
| POST | /api/disposable/list | List addresses by state |
| POST | /api/disposable/get-address | Get next unused address (atomic) |
| POST | /api/check-tor | Check Tor connectivity |
| POST | /api/tor/start | Download + start Tor |
| POST | /api/tor/stop | Stop managed Tor |
| POST | /api/rpc/start | Start RPC proxy on :8545 |
| POST | /api/rpc/stop | Stop RPC proxy |
| POST | /api/prepare-btc | Check BTC balance via Tor |
| POST | /api/prepare-eth | Check ETH balance via Tor |
| POST | /api/send-btc | Sign and broadcast BTC |
| POST | /api/send-eth | Sign and broadcast ETH |

Errors return HTTP 400 with `{"error": "message"}`. Invalid JSON returns 400.

### Ports

| Service | Port |
|---------|------|
| Dashboard | 8888 |
| Tor SOCKS (managed) | 9050 |
| Tor SOCKS (Browser) | 9150 |
| RPC ETH (Helios or Proxy) | 8545 |
| Bitcoin Core RPC | 8332 |

## CLI Scripts (Maximum Security)

For offline signing with internet physically disabled:

| Script | Function | Admin? |
|--------|----------|:------:|
| `start.bat` | Launch dashboard (auto-admin, auto-deps) | Yes |
| `cold_wallets\gerar.bat` | Generate wallets offline | Yes |
| `cold_wallets\enviar_btc.bat` | Send-all BTC (fee by type + Tor) | Yes |
| `cold_wallets\enviar_eth.bat` | Send-all ETH (EIP-1559 + Tor) | Yes |
| `cold_wallets\assinar_btc.bat` | Sign BTC offline | Yes |
| `cold_wallets\assinar_eth.bat` | Sign ETH offline | Yes |

## Privacy Model

| Operation | Dashboard | CLI |
|-----------|-----------|-----|
| Wallet generation | Online (keys in memory) | Internet disabled |
| Transaction signing | Online (via Tor) | Internet disabled |
| Balance/nonce lookup | Via Tor | Via Tor |
| TX broadcast | Via Tor | Via Tor |

## Security

- **Private keys** stored in `generated/` and `address_pool/` — GITIGNORED
- **Tor runtime** downloaded to `tools/tor_runtime/` — GITIGNORED
- **Dashboard** bound to `127.0.0.1` only — not accessible from network
- **HTML escaping** on all server data rendered in dashboard
- **Atomic file rename** for disposable address claiming (race-safe with retry loop)
- **Thread locks** on RPC proxy start/stop (`_rpc_lock`)
- **tar extraction** with path traversal filter (`filter='data'` Python 3.12+, manual member filter for older)
- **PID verification** checks process name (`tor.exe`) before killing
- **Sweep destination validation** — auto-detects crypto type from address, prevents BTC-to-ETH mismatch
- **scriptPubKey mandatory** — BTC sweep requires script field for valid SegWit transactions
- **Input bounds** — wallet count clamped 1-20, disposable count 1-50
- **Server error log** — stderr redirected to `dashboard/server.log`
- All monetary values use `Decimal` (never `float`), wei/sats serialized as strings in JSON
- Address validation (EIP-55 for ETH, base58/bech32 including 4th char for BTC) before every send
- ETH broadcast via Cloudflare + PublicNode (no API key required)
- `except Exception:` only (never bare `except:`)
- Clipboard errors caught and displayed

## RPC Documentation

- [Quickstart](rpc/docs/quickstart.md) — Helios setup in 5 minutes
- [Threat Model](rpc/docs/threat-model.md) — security guarantees and attack analysis
- [Runbook](rpc/docs/runbook.md) — operational procedures, updates, incident response
- [Security Checklist](rpc/CHECKLIST.md) — pre/post deployment validation

## QA Status

Last tested: 2026-03-24 | 25 commits | 2 code reviews completed

| Test | Result |
|------|--------|
| Python 3.14 runtime | PASS |
| Dependencies (4 packages) | PASS |
| Dashboard endpoints (17) | PASS |
| Tor manager CLI | PASS |
| RPC proxy start/stop | PASS |
| Lint (ruff E,W,F) | PASS |
| Module imports (14) | PASS |
| Error handling (HTTP 400) | PASS |
| Invalid JSON rejection | PASS |
| BTC sweep scriptPubKey | PASS (fixed) |
| Sweep destination validation | PASS (fixed) |
| Bech32 address validation | PASS (fixed) |
| Tar extraction safety | PASS (fixed) |

## Lint

```bash
C:\Python314\python.exe -m ruff check --select=E,W,F cold_wallets/ tools/ dashboard/
```
