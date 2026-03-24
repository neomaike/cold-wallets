#!/usr/bin/env python3
"""
ENVIAR ETHEREUM - SEND-ALL + EIP-1559 AUTOMATIZADO VIA TOR
1. Informa Private Key -> busca saldo automaticamente via Tor
2. Busca fees EIP-1559 (maxFeePerGas / maxPriorityFeePerGas)
3. Envia saldo TOTAL (value = balance - gas_cost)
4. Desliga internet, assina offline
5. Liga internet, broadcast via Tor
"""

import json
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    import requests
    from eth_account import Account
except ImportError:
    print("[ERRO] Dependencias nao instaladas!")
    print("Execute: C:\\Python314\\python.exe -m pip install "
          "eth-account requests[socks] PySocks")
    sys.exit(1)

from network_control import OfflineContext, require_admin, is_online
from address_validation import validate_eth_address


# Configuracao Tor
TOR_PROXIES = [
    {"http": "socks5h://127.0.0.1:9150", "https": "socks5h://127.0.0.1:9150"},
    {"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"},
]

# RPCs publicos
ETH_RPCS = [
    "https://cloudflare-eth.com",
    "https://ethereum.publicnode.com",
    "https://eth.llamarpc.com",
]

GWEI = Decimal(10**9)
WEI = Decimal(10**18)


def get_tor_session():
    """Conecta ao Tor"""
    session = requests.Session()

    for proxy in TOR_PROXIES:
        try:
            session.proxies = proxy
            r = session.get("https://check.torproject.org/api/ip", timeout=15)
            if r.json().get("IsTor"):
                print(f"[+] Conectado ao Tor - IP: {r.json().get('IP')}")
                return session
        except Exception as e:
            print(f"    [-] Tor proxy falhou: {e}")
            continue

    return None


def eth_rpc_call(session, method, params=None):
    """Faz chamada RPC Ethereum via Tor"""
    if params is None:
        params = []
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }

    for rpc in ETH_RPCS:
        try:
            r = session.post(rpc, json=payload, timeout=30)
            if r.status_code == 200:
                result = r.json()
                if "result" in result:
                    return result["result"]
        except Exception as e:
            print(f"    [-] RPC falhou ({rpc}): {e}")
            continue

    return None


def get_balance(session, address):
    """Busca saldo ETH"""
    result = eth_rpc_call(session, "eth_getBalance", [address, "latest"])
    if result:
        return int(result, 16)
    return None


def get_nonce(session, address):
    """Busca nonce"""
    result = eth_rpc_call(session, "eth_getTransactionCount",
                          [address, "latest"])
    if result:
        return int(result, 16)
    return None


def get_eip1559_fees(session):
    """Busca fees EIP-1559 via eth_feeHistory"""
    result = eth_rpc_call(session, "eth_feeHistory",
                          ["0x5", "latest", [25, 50, 75]])
    if result:
        base_fee = int(result["baseFeePerGas"][-1], 16)
        rewards = result.get("reward", [])
        priority_fees = [int(r[1], 16) for r in rewards if r]
        if priority_fees:
            priority_fee = sorted(priority_fees)[len(priority_fees) // 2]
        else:
            priority_fee = 2_000_000_000

        max_fee = base_fee * 2 + priority_fee
        return {
            "baseFee": base_fee,
            "maxPriorityFeePerGas": priority_fee,
            "maxFeePerGas": max_fee,
        }

    # Fallback para legacy gasPrice
    gas_price = eth_rpc_call(session, "eth_gasPrice", [])
    if gas_price:
        gp = int(gas_price, 16)
        return {
            "baseFee": gp,
            "maxPriorityFeePerGas": 2_000_000_000,
            "maxFeePerGas": gp,
            "legacy": True
        }
    return None


def broadcast_tx(session, raw_tx):
    """Envia transacao via Tor"""
    if not raw_tx.startswith("0x"):
        raw_tx = "0x" + raw_tx

    result = eth_rpc_call(session, "eth_sendRawTransaction", [raw_tx])
    if result:
        return True, result
    return False, "Todas APIs falharam"


def main():
    print("""
    =====================================================
       ENVIAR ETHEREUM - SEND-ALL + EIP-1559 VIA TOR
    =====================================================
    """)

    # Verifica admin para controle de rede
    is_admin = require_admin()
    if not is_admin:
        print("[!] Nao e admin - internet NAO sera desligada automaticamente")
        print("    Para seguranca maxima, execute como Administrador")
        print()

    # [1/5] Conecta ao Tor
    print("[1/5] Conectando ao Tor...")
    session = get_tor_session()
    if not session:
        print("[ERRO] Tor nao esta rodando!")
        print("       Abra o Tor Browser primeiro.")
        input("\nPressione Enter para sair...")
        return

    # [2/5] Chave e saldo
    print("\n[2/5] Informe a chave privada")
    private_key = input("      Private Key (hex): ").strip()

    if not private_key.startswith("0x"):
        private_key = "0x" + private_key

    try:
        account = Account.from_key(private_key)
    except Exception as e:
        print(f"[ERRO] Chave invalida: {e}")
        input("\nPressione Enter para sair...")
        return

    address = account.address
    print(f"      Endereco: {address}")

    print("      Buscando saldo, nonce e fees via Tor...")
    balance_wei = get_balance(session, address)
    nonce = get_nonce(session, address)
    fee_data = get_eip1559_fees(session)

    if balance_wei is None:
        print("[ERRO] Nao foi possivel buscar saldo")
        input("\nPressione Enter para sair...")
        return

    if nonce is None:
        print("[ERRO] Nao foi possivel buscar nonce")
        input("\nPressione Enter para sair...")
        return

    if fee_data is None:
        print("[ERRO] Nao foi possivel buscar fees")
        input("\nPressione Enter para sair...")
        return

    balance_eth = Decimal(balance_wei) / WEI
    base_gwei = Decimal(fee_data["baseFee"]) / GWEI
    max_fee_gwei = Decimal(fee_data["maxFeePerGas"]) / GWEI
    priority_gwei = Decimal(fee_data["maxPriorityFeePerGas"]) / GWEI
    is_legacy = fee_data.get("legacy", False)

    print("\n      === SALDO E FEES ===")
    print(f"      Saldo:    {balance_eth:.6f} ETH")
    print(f"      Nonce:    {nonce}")
    if is_legacy:
        print(f"      GasPrice: {max_fee_gwei:.2f} Gwei (fallback legacy)")
    else:
        print(f"      BaseFee:  {base_gwei:.2f} Gwei")
        print(f"      Priority: {priority_gwei:.2f} Gwei")
        print(f"      MaxFee:   {max_fee_gwei:.2f} Gwei")

    if balance_wei == 0:
        print("\n[!] Saldo zero - nada para enviar")
        input("\nPressione Enter para sair...")
        return

    # [3/5] Destino + calculo send-all
    print("\n[3/5] Informe o destino")
    dest_address = input("      Endereco destino (0x...): ").strip()

    valid, msg = validate_eth_address(dest_address)
    if not valid:
        print(f"[ERRO] Endereco invalido: {msg}")
        input("\nPressione Enter para sair...")
        return

    gas_limit = 21000
    gas_cost_wei = gas_limit * fee_data["maxFeePerGas"]
    send_wei = balance_wei - gas_cost_wei

    if send_wei <= 0:
        print("[ERRO] Saldo insuficiente para gas!")
        print(f"       Saldo:    {balance_eth:.6f} ETH")
        gas_cost_eth = Decimal(gas_cost_wei) / WEI
        print(f"       Gas cost: {gas_cost_eth:.6f} ETH")
        input("\nPressione Enter para sair...")
        return

    send_eth = Decimal(send_wei) / WEI
    gas_cost_eth = Decimal(gas_cost_wei) / WEI

    print("\n      === RESUMO (SEND-ALL) ===")
    print(f"      Saldo:    {balance_eth:.6f} ETH")
    print(f"      Gas cost: {gas_cost_eth:.6f} ETH "
          f"(21000 x {max_fee_gwei:.2f} Gwei)")
    print(f"      Enviar:   {send_eth:.6f} ETH")
    print(f"      Destino:  {dest_address}")
    if is_legacy:
        print("      Modo:     Legacy (gasPrice)")
    else:
        print("      Modo:     EIP-1559 (type 2)")

    confirm = input("\n      Confirmar? (s/n): ").strip().lower()
    if confirm != "s":
        print("Cancelado.")
        return

    # [4/5] Assina OFFLINE
    print("\n[4/5] Assinando transacao...")

    def sign_transaction():
        """Assina a transacao offline"""
        if is_legacy:
            tx = {
                "to": dest_address,
                "value": send_wei,
                "gas": gas_limit,
                "gasPrice": fee_data["maxFeePerGas"],
                "nonce": nonce,
                "chainId": 1
            }
        else:
            tx = {
                "type": 2,
                "to": dest_address,
                "value": send_wei,
                "gas": gas_limit,
                "maxFeePerGas": fee_data["maxFeePerGas"],
                "maxPriorityFeePerGas": fee_data["maxPriorityFeePerGas"],
                "nonce": nonce,
                "chainId": 1
            }

        signed = Account.sign_transaction(tx, private_key)
        return signed.raw_transaction.hex()

    if is_admin:
        print("      Desligando internet...")
        with OfflineContext(auto_reconnect=True):
            raw_tx = sign_transaction()
            print("      [OK] Transacao assinada OFFLINE!")
    else:
        print("      [ALERTA] Assinando ONLINE - internet NAO foi desligada!")
        print("      Para seguranca maxima, execute como Administrador.")
        confirm_online = input("      Continuar mesmo assim? (s/n): ").strip().lower()
        if confirm_online != "s":
            print("Cancelado.")
            return
        raw_tx = sign_transaction()
        print("      [OK] Transacao assinada (ONLINE - sem protecao de rede)!")

    # Salva
    output_dir = Path(__file__).parent / "signed_transactions"
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"eth_signed_{timestamp}.json"

    save_data = {
        "type": "ethereum",
        "raw_transaction": raw_tx,
        "from": address,
        "to": dest_address,
        "amount_wei": str(send_wei),
        "gas_limit": gas_limit,
        "send_all": True,
        "signed_at": datetime.now().isoformat()
    }
    if is_legacy:
        save_data["gasPrice"] = fee_data["maxFeePerGas"]
        save_data["tx_type"] = "legacy"
    else:
        save_data["maxFeePerGas"] = fee_data["maxFeePerGas"]
        save_data["maxPriorityFeePerGas"] = fee_data["maxPriorityFeePerGas"]
        save_data["tx_type"] = "eip1559"

    with open(filepath, "w") as f:
        json.dump(save_data, f, indent=2)

    print(f"      Salvo em: {filepath}")

    # [5/5] Broadcast
    print("\n[5/5] Enviando transacao via Tor...")

    if not is_online():
        time.sleep(3)

    session = get_tor_session()
    if not session:
        print("[!] Tor desconectado. Transacao salva em arquivo.")
        print("    Use broadcast_tor.py para enviar depois.")
        input("\nPressione Enter para sair...")
        return

    success, result = broadcast_tx(session, raw_tx)

    if success:
        print(f"\n{'='*60}")
        print("  TRANSACAO ENVIADA COM SUCESSO!")
        print(f"{'='*60}")
        print(f"  TX Hash: {result}")
        print("\n  Acompanhe em:")
        print(f"  https://etherscan.io/tx/{result}")
    else:
        print(f"\n[!] Erro no broadcast: {result}")
        print("    Transacao salva. Tente broadcast_tor.py depois.")

    input("\nPressione Enter para sair...")


if __name__ == "__main__":
    main()
