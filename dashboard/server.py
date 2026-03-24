#!/usr/bin/env python3
"""
Cold Wallets Dashboard — lightweight API server
Serves index.html and exposes wallet operations as JSON API.
Binds to 127.0.0.1:8080 only. Uses ThreadingHTTPServer for concurrency.
"""

import json
import socket
import sys
import subprocess
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime

# Setup paths for imports
PROJECT_ROOT = Path(__file__).parent.parent
COLD_WALLETS = PROJECT_ROOT / "cold_wallets"
TOOLS_DIR = PROJECT_ROOT / "tools"

sys.path.insert(0, str(COLD_WALLETS))
sys.path.insert(0, str(COLD_WALLETS / "hot_disposable"))
sys.path.insert(0, str(COLD_WALLETS / "tools"))
sys.path.insert(0, str(TOOLS_DIR))

DASHBOARD_DIR = Path(__file__).parent
PORT = 8080

# Cache index.html in memory — it never changes at runtime
_HTML_CACHE = None


def _load_html():
    global _HTML_CACHE
    html_path = DASHBOARD_DIR / "index.html"
    _HTML_CACHE = html_path.read_bytes()


# --- Status cache (updated in background thread) ---

_status_cache = None
_status_lock = threading.Lock()


def _tcp_probe(host, port, timeout=0.3):
    """Fast TCP check — returns True if port is open"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        sock.close()
        return True
    except (ConnectionRefusedError, OSError, socket.timeout):
        return False


def check_import(module_name):
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def check_tor():
    """Check Tor — TCP probe then SOCKS verify"""
    for port in [9150, 9050]:
        if not _tcp_probe("127.0.0.1", port):
            continue
        # Port is open — verify via SOCKS
        try:
            import requests as req
            s = req.Session()
            s.proxies = {
                "http": f"socks5h://127.0.0.1:{port}",
                "https": f"socks5h://127.0.0.1:{port}",
            }
            r = s.get(
                "https://check.torproject.org/api/ip", timeout=10)
            d = r.json()
            if d.get("IsTor"):
                return {"connected": True,
                        "ip": d.get("IP", "unknown"),
                        "port": port}
        except Exception:
            # Port open but SOCKS failed — might be starting up
            return {"connected": False, "ip": None, "port": port}
    return {"connected": False, "ip": None, "port": None}


def check_docker():
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True, text=True, timeout=3,
            creationflags=0x08000000)  # CREATE_NO_WINDOW on Windows
        return result.returncode == 0
    except Exception:
        return False


def check_rpc():
    """Check if RPC on 8545 is responding"""
    if not _tcp_probe("127.0.0.1", 8545):
        return {"responding": False, "block": None}
    try:
        import requests
        r = requests.post(
            "http://127.0.0.1:8545",
            json={"jsonrpc": "2.0", "method": "eth_blockNumber",
                  "params": [], "id": 1},
            timeout=2)
        if r.status_code == 200 and "result" in r.json():
            block_hex = r.json()["result"]
            return {"responding": True, "block": int(block_hex, 16)}
    except Exception:
        pass
    return {"responding": False, "block": None}


def _build_status():
    """Build full system status (called from background thread)"""
    try:
        from network_control import get_network_adapters, is_online
        from network_control import require_admin
        adapters = get_network_adapters()
        online = is_online()
        admin = require_admin()
    except Exception:
        adapters = []
        online = True
        admin = False

    try:
        from disposable_manager import get_address_count
        disposable = get_address_count()
    except Exception:
        disposable = {"unused": 0, "active": 0, "funded": 0, "spent": 0}

    return {
        "tor": check_tor(),
        "online": online,
        "admin": admin,
        "adapters": adapters,
        "rpc": check_rpc(),
        "docker": check_docker(),
        "disposable": disposable,
        "python": sys.version.split()[0],
        "deps": {
            "eth_account": check_import("eth_account"),
            "bit": check_import("bit"),
            "requests": check_import("requests"),
            "PySocks": check_import("socks"),
        }
    }


def _status_refresh_loop():
    """Background thread: refresh status every 15s"""
    global _status_cache
    while True:
        try:
            new_status = _build_status()
            with _status_lock:
                _status_cache = new_status
        except Exception:
            pass
        time.sleep(15)


def get_system_status():
    """Return cached status (never blocks the HTTP handler)"""
    with _status_lock:
        if _status_cache is not None:
            return _status_cache
    # First call — build synchronously but fast
    # Skip slow checks on first load
    return {
        "tor": {"connected": False, "ip": None, "port": None},
        "online": True, "admin": False, "adapters": [],
        "rpc": {"responding": False, "block": None},
        "docker": False,
        "disposable": {"unused": 0, "active": 0,
                       "funded": 0, "spent": 0},
        "python": sys.version.split()[0],
        "deps": {
            "eth_account": check_import("eth_account"),
            "bit": check_import("bit"),
            "requests": check_import("requests"),
            "PySocks": check_import("socks"),
        },
        "_loading": True
    }


# --- API handlers ---

def api_generate_wallets(data):
    from generate_wallets import (
        generate_ethereum_wallets, generate_bitcoin_wallets)

    count = min(data.get("count", 3), 20)
    eth = generate_ethereum_wallets(count)
    btc = generate_bitcoin_wallets(count)

    output_dir = COLD_WALLETS / "generated"
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"cold_wallets_{timestamp}.json"

    with open(filepath, "w") as f:
        json.dump({
            "created_at": datetime.now().isoformat(),
            "ethereum": eth, "bitcoin": btc
        }, f, indent=2)

    return {
        "ethereum": [{"index": w["index"], "address": w["address"],
                      "private_key": w["private_key"]} for w in eth],
        "bitcoin": [{"index": w["index"], "address": w["address"],
                     "legacy": w["address_legacy"],
                     "wif": w["private_key_wif"]} for w in btc],
        "file": str(filepath),
    }


def api_generate_disposable(data):
    from generate_disposable import (
        generate_btc_addresses, generate_eth_addresses, save_addresses)

    count = min(data.get("count", 10), 50)
    crypto = data.get("crypto", "both")
    result = {"btc": 0, "eth": 0}

    if crypto in ["btc", "both"]:
        btc = generate_btc_addresses(count)
        save_addresses(btc, "btc")
        result["btc"] = len(btc)
    if crypto in ["eth", "both"]:
        eth = generate_eth_addresses(count)
        save_addresses(eth, "eth")
        result["eth"] = len(eth)

    return result


def api_disposable_list(data):
    from disposable_manager import (
        UNUSED_DIR, ACTIVE_DIR, FUNDED_DIR, SPENT_DIR, ensure_dirs)
    ensure_dirs()

    state = data.get("state", "all")
    crypto = data.get("crypto")
    pattern = f"{crypto}_*.json" if crypto else "*.json"

    dirs = {
        "unused": UNUSED_DIR, "active": ACTIVE_DIR,
        "funded": FUNDED_DIR, "spent": SPENT_DIR
    }
    states = (["unused", "active", "funded", "spent"]
              if state == "all" else [state])

    result = {}
    for s in states:
        if s not in dirs:
            continue
        entries = []
        for f in sorted(dirs[s].glob(pattern))[:20]:
            with open(f) as fp:
                addr_data = json.load(fp)
            entries.append({
                "crypto": addr_data.get("crypto"),
                "address": addr_data.get("address"),
                "status": addr_data.get("status"),
            })
        result[s] = entries

    return result


def api_disposable_get(data):
    from disposable_manager import (
        UNUSED_DIR, ACTIVE_DIR, ensure_dirs)
    ensure_dirs()

    crypto = data.get("crypto")
    pattern = f"{crypto}_*.json" if crypto else "*.json"
    available = sorted(UNUSED_DIR.glob(pattern))

    if not available:
        return {"error": "No addresses available. Generate more first."}

    addr_file = available[0]
    with open(addr_file) as f:
        addr_data = json.load(f)

    addr_data["status"] = "active"
    addr_data["activated_at"] = datetime.now().isoformat()

    new_path = ACTIVE_DIR / addr_file.name
    try:
        addr_file.rename(new_path)
    except OSError:
        with open(new_path, "w") as f:
            json.dump(addr_data, f, indent=2)
        addr_file.unlink()
    with open(new_path, "w") as f:
        json.dump(addr_data, f, indent=2)

    return {
        "crypto": addr_data["crypto"],
        "address": addr_data["address"],
        "warning": "Use this address ONLY ONCE."
    }


def api_prepare_btc(data):
    from enviar_btc import (
        get_tor_session, find_funded_address, fetch_fee_rates)
    from bit import Key

    wif = data.get("wif", "").strip()
    if not wif:
        return {"error": "WIF required"}
    try:
        key = Key(wif)
    except Exception as e:
        return {"error": f"Invalid key: {e}"}

    session = get_tor_session()
    if not session:
        return {"error": "Tor not connected. Open Tor Browser first."}

    address, addr_type, utxos = find_funded_address(session, key)
    if not utxos:
        return {"error": "No balance found", "tested": [
            key.segwit_address, key.address]}

    total_sats = sum(u.get("value", 0) for u in utxos)
    fees = fetch_fee_rates(session)

    return {
        "address": address, "type": addr_type,
        "balance_sats": total_sats, "utxos": len(utxos),
        "fees": fees,
    }


def api_prepare_eth(data):
    from enviar_eth import (
        get_tor_session, get_balance, get_nonce, get_eip1559_fees)
    from eth_account import Account
    from decimal import Decimal

    pk = data.get("private_key", "").strip()
    if not pk:
        return {"error": "Private key required"}
    if not pk.startswith("0x"):
        pk = "0x" + pk
    try:
        account = Account.from_key(pk)
    except Exception as e:
        return {"error": f"Invalid key: {e}"}

    session = get_tor_session()
    if not session:
        return {"error": "Tor not connected. Open Tor Browser first."}

    balance = get_balance(session, account.address)
    nonce = get_nonce(session, account.address)
    fees = get_eip1559_fees(session)

    if balance is None:
        return {"error": "Could not fetch balance via Tor"}

    WEI = Decimal(10**18)
    GWEI = Decimal(10**9)
    result = {
        "address": account.address,
        "balance_wei": balance,
        "balance_eth": str(Decimal(balance) / WEI),
        "nonce": nonce,
    }
    if fees:
        result["fees"] = {
            "baseFee_gwei": str(Decimal(fees["baseFee"]) / GWEI),
            "maxFee_gwei": str(
                Decimal(fees["maxFeePerGas"]) / GWEI),
            "priority_gwei": str(
                Decimal(fees["maxPriorityFeePerGas"]) / GWEI),
            "legacy": fees.get("legacy", False),
        }
    return result


def api_send_btc(data):
    from enviar_btc import (
        get_tor_session, find_funded_address, build_unspents,
        estimate_tx_vsize, broadcast_tx)
    from address_validation import validate_btc_address
    from bit import Key
    from decimal import Decimal

    wif = data.get("wif", "").strip()
    dest = data.get("destination", "").strip()
    fee_rate = data.get("fee_rate", 10)

    if not wif or not dest:
        return {"error": "WIF and destination required"}

    valid, msg = validate_btc_address(dest)
    if not valid:
        return {"error": f"Invalid destination: {msg}"}
    try:
        key = Key(wif)
    except Exception as e:
        return {"error": f"Invalid key: {e}"}

    session = get_tor_session()
    if not session:
        return {"error": "Tor not connected"}

    address, addr_type, utxos = find_funded_address(session, key)
    if not utxos:
        return {"error": "No balance found"}

    total_sats = sum(u.get("value", 0) for u in utxos)
    unspents = build_unspents(session, utxos, address, addr_type)

    vsize = estimate_tx_vsize(len(utxos), addr_type, dest)
    fee_sats = vsize * int(fee_rate)
    send_sats = total_sats - fee_sats

    if send_sats <= 0:
        return {"error": f"Insufficient balance. Need {fee_sats} sat "
                         f"for fee, have {total_sats} sat"}

    key.unspents = unspents
    outputs = [(dest, send_sats, "satoshi")]
    raw_tx = key.create_transaction(
        outputs, fee=fee_sats, absolute_fee=True)

    output_dir = COLD_WALLETS / "signed_transactions"
    output_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"btc_signed_{ts}.json"
    with open(filepath, "w") as f:
        json.dump({
            "type": "bitcoin", "raw_transaction": raw_tx,
            "from": address, "to": dest,
            "amount_sats": send_sats, "fee_sats": fee_sats,
            "send_all": True,
            "signed_at": datetime.now().isoformat()
        }, f, indent=2)

    success, result = broadcast_tx(session, raw_tx)

    SAT = Decimal(100_000_000)
    return {
        "success": success,
        "txid": result if success else None,
        "error": None if success else result,
        "amount_btc": str(Decimal(send_sats) / SAT),
        "fee_btc": str(Decimal(fee_sats) / SAT),
        "file": str(filepath),
    }


def api_send_eth(data):
    from enviar_eth import (
        get_tor_session, get_balance, get_nonce,
        get_eip1559_fees, broadcast_tx)
    from address_validation import validate_eth_address
    from eth_account import Account
    from decimal import Decimal

    pk = data.get("private_key", "").strip()
    dest = data.get("destination", "").strip()

    if not pk or not dest:
        return {"error": "Private key and destination required"}
    if not pk.startswith("0x"):
        pk = "0x" + pk

    valid, msg = validate_eth_address(dest)
    if not valid:
        return {"error": f"Invalid destination: {msg}"}
    try:
        account = Account.from_key(pk)
    except Exception as e:
        return {"error": f"Invalid key: {e}"}

    session = get_tor_session()
    if not session:
        return {"error": "Tor not connected"}

    balance_wei = get_balance(session, account.address)
    nonce = get_nonce(session, account.address)
    fee_data = get_eip1559_fees(session)

    if balance_wei is None or nonce is None or fee_data is None:
        return {"error": "Could not fetch on-chain data via Tor"}

    gas_limit = 21000
    gas_cost = gas_limit * fee_data["maxFeePerGas"]
    send_wei = balance_wei - gas_cost

    if send_wei <= 0:
        return {"error": "Insufficient balance for gas"}

    is_legacy = fee_data.get("legacy", False)
    if is_legacy:
        tx = {
            "to": dest, "value": send_wei, "gas": gas_limit,
            "gasPrice": fee_data["maxFeePerGas"],
            "nonce": nonce, "chainId": 1
        }
    else:
        tx = {
            "type": 2, "to": dest, "value": send_wei,
            "gas": gas_limit,
            "maxFeePerGas": fee_data["maxFeePerGas"],
            "maxPriorityFeePerGas": fee_data["maxPriorityFeePerGas"],
            "nonce": nonce, "chainId": 1
        }

    signed = Account.sign_transaction(tx, pk)
    raw_tx = signed.raw_transaction.hex()

    output_dir = COLD_WALLETS / "signed_transactions"
    output_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"eth_signed_{ts}.json"
    with open(filepath, "w") as f:
        json.dump({
            "type": "ethereum", "raw_transaction": raw_tx,
            "from": account.address, "to": dest,
            "amount_wei": send_wei, "gas_limit": gas_limit,
            "send_all": True,
            "signed_at": datetime.now().isoformat()
        }, f, indent=2)

    success, result = broadcast_tx(session, raw_tx)

    WEI = Decimal(10**18)
    return {
        "success": success,
        "txid": result if success else None,
        "error": None if success else result,
        "amount_eth": str(Decimal(send_wei) / WEI),
        "file": str(filepath),
    }


def api_tor_start(data):
    from tor_manager import start_tor, download_tor, status as tor_status
    s = tor_status()
    if s["running"]:
        return {"ok": True, "msg": f"Tor already running on port {s['port']}"}
    if not s["downloaded"]:
        ok, msg = download_tor(progress_cb=lambda m: None)
        if not ok:
            return {"ok": False, "msg": msg}
    ok, msg = start_tor()
    return {"ok": ok, "msg": msg}


def api_tor_stop(data):
    from tor_manager import stop_tor
    ok, msg = stop_tor()
    return {"ok": ok, "msg": msg}


def api_tor_download(data):
    from tor_manager import download_tor
    ok, msg = download_tor(progress_cb=lambda m: None)
    return {"ok": ok, "msg": msg}


# --- Route table ---

API_ROUTES = {
    "/api/status": lambda d: get_system_status(),
    "/api/generate-wallets": api_generate_wallets,
    "/api/generate-disposable": api_generate_disposable,
    "/api/disposable/list": api_disposable_list,
    "/api/disposable/get-address": api_disposable_get,
    "/api/check-tor": lambda d: check_tor(),
    "/api/tor/start": api_tor_start,
    "/api/tor/stop": api_tor_stop,
    "/api/tor/download": api_tor_download,
    "/api/prepare-btc": api_prepare_btc,
    "/api/prepare-eth": api_prepare_eth,
    "/api/send-btc": api_send_btc,
    "/api/send-eth": api_send_eth,
}


# --- HTTP Handler ---

class DashboardHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        if args and "/api/send" not in str(args[0]):
            msg = args[0] if args else ""
            print(f"  [{self.command}] {msg}")

    def _send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            if _HTML_CACHE is None:
                self.send_error(500, "index.html not loaded")
                return
            self.send_response(200)
            self.send_header(
                "Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(_HTML_CACHE))
            self.end_headers()
            self.wfile.write(_HTML_CACHE)
        elif self.path == "/api/status":
            self._send_json(get_system_status())
        elif self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self.send_error(404)

    def do_POST(self):
        handler = API_ROUTES.get(self.path)
        if not handler:
            self._send_json({"error": "Not found"}, 404)
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        try:
            result = handler(data)
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)


# --- Threading HTTP Server ---

class ThreadedHTTPServer(HTTPServer):
    """Handle each request in a new thread"""
    allow_reuse_address = True

    def process_request(self, request, client_address):
        t = threading.Thread(
            target=self.process_request_thread,
            args=(request, client_address), daemon=True)
        t.start()

    def process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


def main():
    _load_html()

    # Start background status refresh
    status_thread = threading.Thread(
        target=_status_refresh_loop, daemon=True)
    status_thread.start()

    server = ThreadedHTTPServer(
        ("127.0.0.1", PORT), DashboardHandler)
    print(f"[+] Dashboard running at http://127.0.0.1:{PORT}")
    print("[+] Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
