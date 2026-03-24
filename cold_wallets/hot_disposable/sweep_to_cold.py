#!/usr/bin/env python3
"""
SWEEP PARA COLD WALLET
Transfere todos os fundos de enderecos descartaveis para cold wallet

DESLIGA A INTERNET AUTOMATICAMENTE durante a assinatura
Requer execucao como Administrador
"""

import json
import sys
import argparse
from decimal import Decimal
from datetime import datetime
from pathlib import Path

# Adiciona o diretorio pai ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from eth_account import Account
from bit import Key
from bit.network.meta import Unspent

from network_control import OfflineContext, require_admin, is_online
from address_validation import validate_btc_address, validate_eth_address


BASE_DIR = Path(__file__).parent / "address_pool"
FUNDED_DIR = BASE_DIR / "funded"
SPENT_DIR = BASE_DIR / "spent"
SIGNED_DIR = Path(__file__).parent.parent / "signed_transactions"


def get_funded_addresses(crypto=None):
    """Busca enderecos com saldo"""
    pattern = f"{crypto}_*.json" if crypto else "*.json"
    addresses = []

    for f in FUNDED_DIR.glob(pattern):
        with open(f) as fp:
            data = json.load(fp)
            data['_file'] = f
            addresses.append(data)

    return addresses


def collect_btc_sweep_data(addresses, destination):
    """Coleta dados para sweep BTC"""
    print("\n[BTC] Enderecos com saldo:")
    for i, addr in enumerate(addresses):
        print(f"  {i+1}. {addr['address']}")

    print("\n[!] Para cada endereco, informe os UTXOs")
    print("    (Use tools/fetch_tx_data.py para buscar via Tor)\n")

    all_utxos = []
    total_satoshi = 0

    for addr in addresses:
        print(f"\nEndereco: {addr['address']}")
        print("(deixe TXID vazio para pular este endereco)")

        while True:
            txid = input("  TXID: ").strip()
            if not txid:
                break

            try:
                vout = int(input("  VOUT: "))
                amount = int(input("  Valor (satoshi): "))
            except ValueError:
                print("  [ERRO] VOUT e valor devem ser numeros inteiros")
                continue

            script = input("  scriptPubKey (hex): ").strip()
            if not script:
                print("  [ERRO] scriptPubKey obrigatorio!")
                print("         Busque via blockstream.info/api/tx/<txid>")
                continue

            all_utxos.append({
                'address': addr['address'],
                'private_key_wif': addr['private_key_wif'],
                'txid': txid,
                'vout': vout,
                'amount_satoshi': amount,
                'script': script
            })
            total_satoshi += amount

            more = input("  Mais UTXOs para este endereco? (s/n): ").strip().lower()
            if more != 's':
                break

    if not all_utxos:
        print("\n[!] Nenhum UTXO informado. Cancelando.")
        return None

    # Estima fee por tipo de endereco e vsize
    n_inputs = len(all_utxos)
    # Detecta tipo do primeiro endereco de origem
    src_addr = all_utxos[0]['address']
    if src_addr.startswith("bc1q"):
        input_vsize = 68
    elif src_addr.startswith("bc1p"):
        input_vsize = 58
    elif src_addr.startswith("3"):
        input_vsize = 91
    else:
        input_vsize = 148

    # Detecta tipo do destino
    if destination.startswith("bc1q"):
        output_vsize = 31
    elif destination.startswith("bc1p"):
        output_vsize = 43
    elif destination.startswith("3"):
        output_vsize = 32
    else:
        output_vsize = 34

    estimated_vsize = 11 + (n_inputs * input_vsize) + output_vsize
    prompt = f"\nTaxa sat/vB [10] (vsize estimado: {estimated_vsize} vB): "
    fee_rate = int(input(prompt) or "10")
    estimated_fee = estimated_vsize * fee_rate

    fee = int(input(f"Taxa total (satoshi) [{estimated_fee}]: ") or str(estimated_fee))
    send_amount = total_satoshi - fee

    print("\n[RESUMO BTC]")
    print(f"  Total entrada: {total_satoshi} satoshi")
    print(f"  Taxa:          {fee} satoshi")
    print(f"  Enviar:        {send_amount} satoshi")
    print(f"  Destino:       {destination}")

    confirm = input("\nConfirmar? (s/n): ").strip().lower()
    if confirm != 's':
        return None

    return {
        'crypto': 'btc',
        'utxos': all_utxos,
        'destination': destination,
        'amount': send_amount,
        'fee': fee,
        'addresses': addresses
    }


def collect_eth_sweep_data(addresses, destination):
    """Coleta dados para sweep ETH"""
    print("\n[ETH] Enderecos com saldo:")
    for i, addr in enumerate(addresses):
        print(f"  {i+1}. {addr['address']}")

    print("\n[!] Para cada endereco, informe os dados")
    print("    (Use tools/fetch_tx_data.py para buscar nonce via Tor)\n")

    all_txs = []
    total_wei = 0

    for addr in addresses:
        print(f"\nEndereco: {addr['address']}")

        balance_str = input("  Saldo (ETH, 0 para pular): ").strip()
        if not balance_str or balance_str == "0":
            continue

        balance_wei = int(Decimal(balance_str) * Decimal(10**18))
        try:
            nonce = int(input("  Nonce: "))
        except ValueError:
            print("  [ERRO] Nonce deve ser numero inteiro")
            continue

        all_txs.append({
            'address': addr['address'],
            'private_key': addr['private_key'],
            'balance_wei': balance_wei,
            'nonce': nonce
        })
        total_wei += balance_wei

    if not all_txs:
        print("\n[!] Nenhum saldo informado. Cancelando.")
        return None

    print("\nModo de fee:")
    print("  1 = EIP-1559 (maxFeePerGas + maxPriorityFeePerGas)")
    print("  2 = Legacy (gasPrice)")
    fee_mode = input("Escolha [1]: ").strip() or "1"

    gas_limit = int(input("Gas limit [21000]: ") or "21000")

    if fee_mode == "2":
        gas_price_gwei = Decimal(input("Gas price (Gwei) [20]: ").strip() or "20")
        gas_price_wei = int(gas_price_gwei * Decimal(10**9))
        gas_cost_wei = gas_price_wei * gas_limit * len(all_txs)
        use_eip1559 = False
        max_fee_wei = None
        priority_fee_wei = None
    else:
        max_fee_gwei = Decimal(input("maxFeePerGas (Gwei) [30]: ").strip() or "30")
        priority_gwei = Decimal(
            input("maxPriorityFeePerGas (Gwei) [2]: ").strip() or "2")
        max_fee_wei = int(max_fee_gwei * Decimal(10**9))
        priority_fee_wei = int(priority_gwei * Decimal(10**9))
        gas_price_wei = max_fee_wei
        gas_cost_wei = max_fee_wei * gas_limit * len(all_txs)
        use_eip1559 = True

    WEI = Decimal(10**18)
    print("\n[RESUMO ETH]")
    print(f"  Total entrada:  {Decimal(total_wei) / WEI:.6f} ETH")
    print(f"  Gas total:      {Decimal(gas_cost_wei) / WEI:.6f} ETH"
          f" ({len(all_txs)} txs)")
    print(f"  Destino:        {destination}")

    confirm = input("\nConfirmar? (s/n): ").strip().lower()
    if confirm != 's':
        return None

    return {
        'crypto': 'eth',
        'txs': all_txs,
        'destination': destination,
        'gas_price_wei': gas_price_wei,
        'gas_limit': gas_limit,
        'use_eip1559': use_eip1559,
        'max_fee_wei': max_fee_wei,
        'priority_fee_wei': priority_fee_wei,
        'addresses': addresses
    }


def sign_btc_sweep(sweep_data):
    """Assina transacoes BTC"""
    print("\n[*] Assinando transacoes BTC...")

    signed_txs = []

    # Agrupa UTXOs por chave privada
    by_key = {}
    for utxo in sweep_data['utxos']:
        key = utxo['private_key_wif']
        if key not in by_key:
            by_key[key] = []
        by_key[key].append(utxo)

    for private_key_wif, utxos in by_key.items():
        key = Key(private_key_wif)

        # Configura UTXOs
        unspents = []
        for u in utxos:
            unspent = Unspent(
                amount=u['amount_satoshi'],
                confirmations=0,
                script=u['script'],
                txid=u['txid'],
                txindex=u['vout']
            )
            unspents.append(unspent)

        key.unspents = unspents

        # Calcula valor a enviar deste grupo
        total = sum(u['amount_satoshi'] for u in utxos)
        # Proporcao da taxa
        total_all = sum(
            u['amount_satoshi'] for u in sweep_data['utxos'])
        fee_prop = int(sweep_data['fee'] * (total / total_all))
        send = total - fee_prop

        if send > 0:
            outputs = [(sweep_data['destination'], send, 'satoshi')]
            raw_tx = key.create_transaction(outputs, fee=fee_prop, absolute_fee=True)
            signed_txs.append({
                'from': utxos[0]['address'],
                'raw_tx': raw_tx,
                'amount': send
            })
            print(f"  [+] Assinado: {utxos[0]['address'][:20]}... -> {send} sat")

    return signed_txs


def sign_eth_sweep(sweep_data):
    """Assina transacoes ETH"""
    print("\n[*] Assinando transacoes ETH...")

    signed_txs = []

    for tx_data in sweep_data['txs']:
        # Calcula valor a enviar (saldo - gas)
        gas_cost = sweep_data['gas_price_wei'] * sweep_data['gas_limit']
        send_amount = tx_data['balance_wei'] - gas_cost

        if send_amount <= 0:
            print(f"  [!] Saldo insuficiente para gas: {tx_data['address'][:20]}...")
            continue

        if sweep_data.get('use_eip1559'):
            tx = {
                'type': 2,
                'to': sweep_data['destination'],
                'value': send_amount,
                'gas': sweep_data['gas_limit'],
                'maxFeePerGas': sweep_data['max_fee_wei'],
                'maxPriorityFeePerGas': sweep_data['priority_fee_wei'],
                'nonce': tx_data['nonce'],
                'chainId': 1
            }
        else:
            tx = {
                'to': sweep_data['destination'],
                'value': send_amount,
                'gas': sweep_data['gas_limit'],
                'gasPrice': sweep_data['gas_price_wei'],
                'nonce': tx_data['nonce'],
                'chainId': 1
            }

        signed = Account.sign_transaction(tx, tx_data['private_key'])
        raw_tx = signed.raw_transaction.hex()

        signed_txs.append({
            'from': tx_data['address'],
            'raw_tx': raw_tx,
            'amount_wei': send_amount
        })
        eth_val = Decimal(send_amount) / Decimal(10**18)
        print(f"  [+] Assinado: {tx_data['address'][:20]}"
              f"... -> {eth_val:.6f} ETH")

    return signed_txs


def save_signed_txs(signed_txs, crypto):
    """Salva transacoes assinadas"""
    SIGNED_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sweep_{crypto}_{timestamp}.json"
    filepath = SIGNED_DIR / filename

    data = {
        'type': f'sweep_{crypto}',
        'created_at': datetime.now().isoformat(),
        'transactions': signed_txs
    }

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n[+] Salvo em: {filepath}")
    return filepath


def move_to_spent(addresses):
    """Move enderecos para spent"""
    for addr in addresses:
        if '_file' in addr:
            src = addr['_file']
            dst = SPENT_DIR / src.name

            addr['status'] = 'spent'
            addr['spent_at'] = datetime.now().isoformat()
            del addr['_file']

            with open(dst, 'w') as f:
                json.dump(addr, f, indent=2)

            src.unlink()
            print(f"  Movido para spent: {addr['address'][:30]}...")


def main():
    parser = argparse.ArgumentParser(description='Sweep para cold wallet')
    parser.add_argument('destination', help='Endereco cold wallet destino')
    parser.add_argument('--crypto', '-c', choices=['btc', 'eth'],
                        help='Tipo de crypto (default: ambos)')
    parser.add_argument('--no-network-control', action='store_true',
                        help='Nao desligar internet automaticamente')
    parser.add_argument('--dry-run', action='store_true',
                        help='Simular sem assinar')

    args = parser.parse_args()

    print("""
    =====================================================
       SWEEP PARA COLD WALLET - OFFLINE
    =====================================================
    """)

    # Valida endereco de destino por tipo de crypto
    dest = args.destination
    is_eth_dest = dest.startswith("0x") or dest.startswith("0X")
    is_btc_dest = not is_eth_dest

    if is_eth_dest:
        valid, msg = validate_eth_address(dest)
        if not valid:
            print(f"[ERRO] Endereco ETH destino invalido: {msg}")
            sys.exit(1)
    if is_btc_dest:
        valid, msg = validate_btc_address(dest)
        if not valid:
            print(f"[ERRO] Endereco BTC destino invalido: {msg}")
            sys.exit(1)

    # Restringe crypto ao tipo do endereco de destino
    if args.crypto is None:
        if is_eth_dest:
            args.crypto = 'eth'
            print("[!] Endereco 0x detectado — sweep apenas ETH")
        elif is_btc_dest:
            args.crypto = 'btc'
            print("[!] Endereco BTC detectado — sweep apenas BTC")

    # Verifica admin
    if not args.no_network_control and not require_admin():
        print("[ERRO] Execute como Administrador para controle de rede!")
        print("       Ou use --no-network-control para pular")
        sys.exit(1)

    use_network_control = not args.no_network_control

    # Busca enderecos com saldo
    btc_funded = get_funded_addresses('btc') if args.crypto in [None, 'btc'] else []
    eth_funded = get_funded_addresses('eth') if args.crypto in [None, 'eth'] else []

    if not btc_funded and not eth_funded:
        print("[!] Nenhum endereco com saldo (funded) encontrado!")
        print("    Use disposable_manager.py mark-funded <endereco>")
        sys.exit(0)

    print(f"Encontrados: {len(btc_funded)} BTC, {len(eth_funded)} ETH com saldo")
    print(f"Destino: {args.destination}\n")

    sweep_data_list = []

    # Coleta dados BTC
    if btc_funded:
        data = collect_btc_sweep_data(btc_funded, args.destination)
        if data:
            sweep_data_list.append(data)

    # Coleta dados ETH
    if eth_funded:
        data = collect_eth_sweep_data(eth_funded, args.destination)
        if data:
            sweep_data_list.append(data)

    if not sweep_data_list:
        print("\nNenhuma transacao a assinar.")
        sys.exit(0)

    if args.dry_run:
        print("\n[DRY RUN] Simulacao - nenhuma assinatura feita")
        sys.exit(0)

    # Assina offline
    def sign_all():
        all_signed = []
        used_addresses = []

        for sweep_data in sweep_data_list:
            if sweep_data['crypto'] == 'btc':
                signed = sign_btc_sweep(sweep_data)
                if signed:
                    save_signed_txs(signed, 'btc')
                    all_signed.extend(signed)
                    used_addresses.extend(sweep_data['addresses'])
            else:
                signed = sign_eth_sweep(sweep_data)
                if signed:
                    save_signed_txs(signed, 'eth')
                    all_signed.extend(signed)
                    used_addresses.extend(sweep_data['addresses'])

        return all_signed, used_addresses

    print("\n[2] Assinando OFFLINE...")

    if use_network_control:
        with OfflineContext(auto_reconnect=True):
            signed, used = sign_all()
    else:
        if is_online():
            print("[ALERTA] Voce esta ONLINE!")
            resp = input("Continuar mesmo assim? (s/n): ").strip().lower()
            if resp != 's':
                sys.exit(0)
        signed, used = sign_all()

    # Move enderecos para spent
    if signed and used:
        print("\n[3] Movendo enderecos para 'spent'...")
        move_to_spent(used)

    print("\n" + "="*60)
    print("  SWEEP CONCLUIDO!")
    print("="*60)
    print(f"\n  Transacoes assinadas: {len(signed)}")
    print(f"  Enderecos marcados como spent: {len(used)}")
    print("\n  Use tools/broadcast_tor.py para enviar via Tor")


if __name__ == "__main__":
    main()
