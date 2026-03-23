#!/usr/bin/env python3
"""
Cold Wallets Dashboard — lightweight API server
Serves index.html and exposes wallet operations as JSON API.
Binds to 127.0.0.1:8080 only.
"""

import json
import sys
import subprocess
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


def check_import(module_name):
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def check_tor():
    """Check Tor connectivity — fast TCP probe first, then verify"""
    import socket
    for port in [9150, 9050]:
        # Fast TCP check (100ms timeout) — skip if port closed
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.3)
        try:
            sock.connect(("127.0.0.1", port))
            sock.close()
        except (ConnectionRefusedError, OSError, socket.timeout):
            continue

        # Port is open — verify it's actually Tor
        try:
            import requests
            session = requests.Session()
            proxy = f"socks5h://127.0.0.1:{port}"
            session.proxies = {"http": proxy, "https": proxy}
            r = session.get(
                "https://check.torproject.org/api/ip", timeout=8)
            data = r.json()
            if data.get("IsTor"):
                return {
                    "connected": True,
                    "ip": data.get("IP", "unknown"),
                    "port": port
                }
        except Exception:
            continue

    return {"connected": False, "ip": None, "port": None}


def check_docker():
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True, text=True, timeout=3)
        return result.returncode == 0
    except Exception:
        return False


def check_rpc():
    """Check if RPC on 8545 is responding"""
    import socket
    # Fast TCP check first
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.3)
    try:
        sock.connect(("127.0.0.1", 8545))
        sock.close()
    except (ConnectionRefusedError, OSError, socket.timeout):
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
            block_num = int(block_hex, 16)
            return {"responding": True, "block": block_num}
    except Exception:
        pass
    return {"responding": False, "block": None}


def get_system_status():
    """Collect full system status"""
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


def api_generate_wallets(data):
    """Generate cold wallets"""
    from generate_wallets import (
        generate_ethereum_wallets, generate_bitcoin_wallets)

    count = data.get("count", 3)
    eth = generate_ethereum_wallets(count)
    btc = generate_bitcoin_wallets(count)

    # Save to file
    output_dir = COLD_WALLETS / "generated"
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"cold_wallets_{timestamp}.json"

    save_data = {
        "created_at": datetime.now().isoformat(),
        "ethereum": eth,
        "bitcoin": btc
    }
    with open(filepath, "w") as f:
        json.dump(save_data, f, indent=2)

    # Return addresses only (never expose private keys via HTTP)
    return {
        "ethereum": [{"index": w["index"], "address": w["address"]}
                     for w in eth],
        "bitcoin": [{"index": w["index"], "address": w["address"],
                     "legacy": w["address_legacy"]} for w in btc],
        "file": str(filepath),
        "warning": "Private keys saved to file only. "
                   "NEVER share this file. Delete after noting keys."
    }


def api_generate_disposable(data):
    """Generate disposable address pool"""
    from generate_disposable import (
        generate_btc_addresses, generate_eth_addresses, save_addresses)

    count = data.get("count", 10)
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
    """List disposable addresses"""
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

    if state == "all":
        states = ["unused", "active", "funded", "spent"]
    else:
        states = [state]

    result = {}
    for s in states:
        entries = []
        for f in sorted(dirs[s].glob(pattern))[:20]:
            with open(f) as fp:
                addr_data = json.load(fp)
            entries.append({
                "crypto": addr_data.get("crypto"),
                "address": addr_data.get("address"),
                "status": addr_data.get("status"),
                "created_at": addr_data.get("created_at"),
            })
        result[s] = entries

    return result


def api_disposable_get(data):
    """Get next available disposable address"""
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
    """Prepare BTC transaction — fetch balance and estimate fees"""
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
        return {"error": "Tor not connected"}

    address, addr_type, utxos = find_funded_address(session, key)
    if not utxos:
        return {"error": "No balance found", "tested": [
            key.segwit_address, key.address]}

    total_sats = sum(u.get("value", 0) for u in utxos)
    fees = fetch_fee_rates(session)

    return {
        "address": address,
        "type": addr_type,
        "balance_sats": total_sats,
        "utxos": len(utxos),
        "fees": fees,
    }


def api_prepare_eth(data):
    """Prepare ETH transaction — fetch balance and fees"""
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
        return {"error": "Tor not connected"}

    balance = get_balance(session, account.address)
    nonce = get_nonce(session, account.address)
    fees = get_eip1559_fees(session)

    if balance is None:
        return {"error": "Could not fetch balance"}

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
            "maxFee_gwei": str(Decimal(fees["maxFeePerGas"]) / GWEI),
            "priority_gwei": str(
                Decimal(fees["maxPriorityFeePerGas"]) / GWEI),
            "legacy": fees.get("legacy", False),
        }

    return result


def api_send_btc(data):
    """Sign and broadcast BTC transaction"""
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
        return {"error": "Insufficient balance for fee"}

    # Sign (ONLINE — dashboard cannot disable network)
    key.unspents = unspents
    outputs = [(dest, send_sats, "satoshi")]
    raw_tx = key.create_transaction(
        outputs, fee=fee_sats, absolute_fee=True)

    # Save
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

    # Broadcast
    success, result = broadcast_tx(session, raw_tx)

    SAT = Decimal(100_000_000)
    return {
        "success": success,
        "txid": result if success else None,
        "error": None if success else result,
        "amount_btc": str(Decimal(send_sats) / SAT),
        "fee_btc": str(Decimal(fee_sats) / SAT),
        "signed_online": True,
        "file": str(filepath),
    }


def api_send_eth(data):
    """Sign and broadcast ETH transaction"""
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
        return {"error": "Could not fetch on-chain data"}

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

    # Save
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
        "signed_online": True,
        "file": str(filepath),
    }


# Route table
API_ROUTES = {
    "/api/status": lambda d: get_system_status(),
    "/api/generate-wallets": api_generate_wallets,
    "/api/generate-disposable": api_generate_disposable,
    "/api/disposable/status": lambda d: {
        "counts": __import__(
            "disposable_manager").get_address_count()},
    "/api/disposable/list": api_disposable_list,
    "/api/disposable/get-address": api_disposable_get,
    "/api/check-tor": lambda d: check_tor(),
    "/api/prepare-btc": api_prepare_btc,
    "/api/prepare-eth": api_prepare_eth,
    "/api/send-btc": api_send_btc,
    "/api/send-eth": api_send_eth,
}


class DashboardHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Suppress default logging to avoid leaking sensitive data
        if args and "/api/send" not in str(args[0]):
            print(f"  [{self.command}] {args[0]}" if args else "")

    def _send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            html_path = DASHBOARD_DIR / "index.html"
            try:
                content = html_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", len(content))
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_error(404, "index.html not found")
        elif self.path == "/api/status":
            self._send_json(get_system_status())
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


def main():
    server = HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    print(f"[+] Dashboard running at http://127.0.0.1:{PORT}")
    print("[+] Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
