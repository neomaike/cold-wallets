#!/usr/bin/env python3
"""
BUSCADOR DE DADOS PARA TRANSACOES - VIA TOR
Este script busca informacoes necessarias para criar transacoes offline.

Para assinar uma transacao offline, voce precisa de:
- BITCOIN: UTXOs (saldos nao gastos), taxa atual
- ETHEREUM: Nonce, gas price atual

Este script busca essas informacoes via Tor e salva em arquivo
para voce transferir para o computador offline.
"""

import sys
import json
from decimal import Decimal
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    print("ERRO: requests nao instalado!")
    print("Execute: pip install requests[socks] PySocks")
    sys.exit(1)


TOR_PROXY_BROWSER = "socks5h://127.0.0.1:9150"
TOR_PROXY_DAEMON = "socks5h://127.0.0.1:9050"


def get_tor_session():
    """Retorna uma sessao requests configurada para usar Tor"""
    session = requests.Session()

    for proxy in [TOR_PROXY_BROWSER, TOR_PROXY_DAEMON]:
        try:
            session.proxies = {'http': proxy, 'https': proxy}
            response = session.get('https://check.torproject.org/api/ip', timeout=30)
            if response.json().get('IsTor'):
                print(f"[+] Conectado ao Tor! IP: {response.json().get('IP')}")
                return session
        except Exception as e:
            print(f"    [-] Tor proxy falhou: {e}")
            continue

    return None


def fetch_bitcoin_utxos(session, address):
    """Busca UTXOs de um endereco Bitcoin"""
    print(f"\n[*] Buscando UTXOs para {address}...")

    apis = [
        f"https://blockstream.info/api/address/{address}/utxo",
        f"https://mempool.space/api/address/{address}/utxo"
    ]

    for url in apis:
        try:
            response = session.get(url, timeout=60)
            if response.status_code == 200:
                utxos = response.json()
                print(f"    [+] Encontrados {len(utxos)} UTXOs")
                return utxos
        except Exception as e:
            print(f"    [-] Erro: {e}")

    return None


def fetch_bitcoin_fee(session):
    """Busca estimativa de taxa Bitcoin"""
    print("\n[*] Buscando taxa recomendada...")

    try:
        response = session.get(
            "https://mempool.space/api/v1/fees/recommended",
            timeout=30)
        if response.status_code == 200:
            fees = response.json()
            print(f"    [+] Taxa rapida: {fees.get('fastestFee')} sat/vB")
            print(f"    [+] Taxa media: {fees.get('halfHourFee')} sat/vB")
            print(f"    [+] Taxa economica: {fees.get('economyFee')} sat/vB")
            return fees
    except Exception as e:
        print(f"    [-] Erro: {e}")

    return None


ETH_RPCS = [
    "https://cloudflare-eth.com",
    "https://ethereum.publicnode.com",
    "https://eth.llamarpc.com",
]


def _eth_rpc_call(session, method, params):
    """Faz chamada RPC Ethereum com fallback entre RPCs"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    for url in ETH_RPCS:
        try:
            response = session.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    return result["result"]
        except Exception as e:
            print(f"    [-] RPC falhou ({url}): {e}")
    return None


def fetch_ethereum_nonce(session, address):
    """Busca nonce de um endereco Ethereum"""
    print(f"\n[*] Buscando nonce para {address}...")

    result = _eth_rpc_call(
        session, "eth_getTransactionCount",
        [address, "latest"])
    if result:
        nonce = int(result, 16)
        print(f"    [+] Nonce atual: {nonce}")
        return nonce

    return None


def fetch_ethereum_balance(session, address):
    """Busca saldo de um endereco Ethereum"""
    print(f"\n[*] Buscando saldo para {address}...")

    result = _eth_rpc_call(
        session, "eth_getBalance", [address, "latest"])
    if result:
        balance_wei = int(result, 16)
        balance_eth = Decimal(balance_wei) / Decimal(10**18)
        print(f"    [+] Saldo: {balance_eth} ETH")
        return {"wei": balance_wei, "eth": str(balance_eth)}

    return None


def fetch_ethereum_gas_price(session):
    """Busca gas price atual"""
    print("\n[*] Buscando gas price...")

    result = _eth_rpc_call(session, "eth_gasPrice", [])
    if not result:
        return None

    gas_price_wei = int(result, 16)
    gas_price_gwei = Decimal(gas_price_wei) / Decimal(10**9)
    print(f"    [+] Gas Price: {gas_price_gwei:.2f} Gwei")

    # Busca EIP-1559 fees
    fee_result = _eth_rpc_call(
        session, "eth_feeHistory",
        ["0x5", "latest", [25, 50, 75]])
    if fee_result:
        base_fee = int(
            fee_result.get('baseFeePerGas', ['0x0'])[-1], 16)
        base_gwei = Decimal(base_fee) / Decimal(10**9)
        print(f"    [+] Base Fee: {base_gwei:.2f} Gwei")

        # Calcula maxFeePerGas usando percentil do feeHistory
        rewards = fee_result.get('reward', [])
        priority_fees = [int(r[1], 16) for r in rewards if r]
        if priority_fees:
            priority_fee = sorted(priority_fees)[len(priority_fees) // 2]
        else:
            priority_fee = int(2 * 10**9)
        suggested_max_fee = base_fee * 2 + priority_fee

        return {
            "gasPrice": gas_price_wei,
            "gasPriceGwei": str(gas_price_gwei),
            "baseFeePerGas": base_fee,
            "suggestedMaxFeePerGas": suggested_max_fee,
            "suggestedMaxPriorityFeePerGas": priority_fee
        }

    return {
        "gasPrice": gas_price_wei,
        "gasPriceGwei": str(gas_price_gwei)
    }


def save_tx_data(data, crypto_type, address):
    """Salva dados para transacao em arquivo"""
    output_dir = Path(__file__).parent.parent / "tx_data"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_addr = address[:8] + "..." + address[-6:]
    filename = f"{crypto_type}_txdata_{short_addr}_{timestamp}.json"
    filepath = output_dir / filename

    data['fetched_at'] = datetime.now().isoformat()
    data['address'] = address

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n[+] Dados salvos em: {filepath}")
    print("    Copie este arquivo para o computador offline!")

    return filepath


def main():
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║      BUSCADOR DE DADOS PARA TRANSACOES - VIA TOR             ║
    ║                                                               ║
    ║  Busca UTXOs, nonces e taxas para criar transacoes offline  ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)

    session = get_tor_session()

    if not session:
        print("\n[!] ERRO: Nao foi possivel conectar ao Tor!")
        print("    Abra o Tor Browser e tente novamente.")
        return

    print("\nOpcoes:")
    print("  1. Buscar dados para transacao Bitcoin")
    print("  2. Buscar dados para transacao Ethereum")
    print("  3. Sair")

    choice = input("\nEscolha uma opcao: ").strip()

    if choice == "1":
        from address_validation import validate_btc_address
        address = input("\nEndereco Bitcoin: ").strip()

        valid, msg = validate_btc_address(address)
        if not valid:
            print(f"[ERRO] Endereco invalido: {msg}")
            return

        utxos = fetch_bitcoin_utxos(session, address)
        fees = fetch_bitcoin_fee(session)

        if utxos is not None:
            # Calcula total disponivel
            total_sats = sum(u.get('value', 0) for u in utxos)
            total_btc = Decimal(total_sats) / Decimal(100000000)

            print("\n[*] RESUMO:")
            print(f"    Total disponivel: {total_btc} BTC ({total_sats} satoshis)")
            print(f"    UTXOs: {len(utxos)}")

            data = {
                "type": "bitcoin",
                "utxos": utxos,
                "total_satoshi": total_sats,
                "total_btc": str(total_btc),
                "recommended_fees": fees,
                "instructions": {
                    "1": "Copie este arquivo para o computador offline",
                    "2": "Use os UTXOs como inputs na transacao",
                    "3": "Escolha a taxa baseada na urgencia",
                    "4": "Assine a transacao offline",
                    "5": "Copie a transacao assinada de volta",
                    "6": "Use broadcast_tor.py para enviar"
                }
            }

            save_tx_data(data, "btc", address)

    elif choice == "2":
        from address_validation import validate_eth_address
        address = input("\nEndereco Ethereum (0x...): ").strip()

        valid, msg = validate_eth_address(address)
        if not valid:
            print(f"[ERRO] Endereco invalido: {msg}")
            return

        nonce = fetch_ethereum_nonce(session, address)
        balance = fetch_ethereum_balance(session, address)
        gas = fetch_ethereum_gas_price(session)

        if nonce is not None:
            print("\n[*] RESUMO:")
            print(f"    Nonce: {nonce}")
            if balance:
                print(f"    Saldo: {balance['eth']} ETH")
            if gas:
                print(f"    Gas Price: {gas['gasPriceGwei']} Gwei")

            data = {
                "type": "ethereum",
                "nonce": nonce,
                "balance": balance,
                "gas": gas,
                "chain_id": 1,
                "suggested_gas_limit_eth_transfer": 21000,
                "suggested_gas_limit_erc20": 100000,
                "instructions": {
                    "1": "Copie este arquivo para o computador offline",
                    "2": "Use o nonce exato (muito importante!)",
                    "3": "Use o gas price sugerido ou ajuste",
                    "4": "Assine a transacao offline",
                    "5": "Copie a transacao assinada de volta",
                    "6": "Use broadcast_tor.py para enviar"
                }
            }

            save_tx_data(data, "eth", address)

    else:
        print("Saindo...")


if __name__ == "__main__":
    main()
