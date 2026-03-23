#!/usr/bin/env python3
"""
ASSINADOR ETHEREUM - OFFLINE, SEND-ALL + EIP-1559
DESLIGA A INTERNET AUTOMATICAMENTE durante a assinatura
Requer execucao como Administrador

- EIP-1559 (type 2) como padrao, legacy como fallback
- Sempre envia saldo total (value = balance - gas_cost)
- Usuario informa saldo para calculo offline
"""

import json
import sys
from decimal import Decimal, InvalidOperation
from datetime import datetime
from pathlib import Path
from eth_account import Account

from network_control import OfflineContext, require_admin, is_online
from address_validation import validate_eth_address


GWEI = Decimal(10**9)
WEI = Decimal(10**18)


def sign_eth_transaction(private_key, tx):
    """Assina transacao ETH (EIP-1559 ou legacy)"""
    signed = Account.sign_transaction(tx, private_key)
    return signed.raw_transaction.hex()


def collect_tx_data():
    """Coleta dados da transacao do usuario (modo offline — send-all)"""
    print("\n--- Dados da Transacao (Send-All) ---\n")

    private_key = input("Private Key (hex): ").strip()
    if not private_key.startswith("0x"):
        private_key = "0x" + private_key

    to = input("Endereco destino (0x...): ").strip()

    valid, msg = validate_eth_address(to)
    if not valid:
        print(f"[ERRO] Endereco invalido: {msg}")
        sys.exit(1)

    # Saldo (necessario para calcular send-all offline)
    print("\nSaldo da carteira (para calcular send-all):")
    balance_input = input("Saldo em ETH: ").strip()
    try:
        balance_eth = Decimal(balance_input)
    except InvalidOperation:
        print(f"[ERRO] Valor invalido: {balance_input}")
        sys.exit(1)
    balance_wei = int(balance_eth * WEI)

    try:
        nonce = int(input("Nonce: "))
        gas_limit = int(input("Gas limit [21000]: ") or "21000")
    except ValueError:
        print("[ERRO] Nonce e gas limit devem ser numeros inteiros")
        sys.exit(1)

    # Modo de fee
    print("\nModo de fee:")
    print("  1 = EIP-1559 (maxFeePerGas + maxPriorityFeePerGas)")
    print("  2 = Legacy (gasPrice)")
    fee_mode = input("Escolha [1]: ").strip() or "1"

    if fee_mode == "2":
        # Legacy
        gas_price_gwei = Decimal(
            input("Gas price (Gwei) [20]: ").strip() or "20")
        gas_price_wei = int(gas_price_gwei * GWEI)
        gas_cost_wei = gas_limit * gas_price_wei
        send_wei = balance_wei - gas_cost_wei

        if send_wei <= 0:
            gas_cost_eth = Decimal(gas_cost_wei) / WEI
            print("[ERRO] Saldo insuficiente para gas!")
            print(f"       Saldo:    {balance_eth:.6f} ETH")
            print(f"       Gas cost: {gas_cost_eth:.6f} ETH")
            sys.exit(1)

        send_eth = Decimal(send_wei) / WEI
        gas_cost_eth = Decimal(gas_cost_wei) / WEI

        print("\n  === RESUMO (SEND-ALL, LEGACY) ===")
        print(f"  Saldo:    {balance_eth:.6f} ETH")
        print(f"  Gas cost: {gas_cost_eth:.6f} ETH "
              f"({gas_limit} x {gas_price_gwei:.2f} Gwei)")
        print(f"  Enviar:   {send_eth:.6f} ETH")
        print(f"  Destino:  {to}")

        confirm = input("\n  Confirmar? (s/n): ").strip().lower()
        if confirm != "s":
            print("Cancelado.")
            sys.exit(0)

        tx = {
            'to': to,
            'value': send_wei,
            'gas': gas_limit,
            'gasPrice': gas_price_wei,
            'nonce': nonce,
            'chainId': 1
        }

        return {
            'private_key': private_key,
            'tx': tx,
            'to': to,
            'send_wei': send_wei,
            'gas_cost_wei': gas_cost_wei,
            'tx_type': 'legacy',
        }

    else:
        # EIP-1559
        max_fee_gwei = Decimal(
            input("maxFeePerGas (Gwei) [30]: ").strip() or "30")
        priority_gwei = Decimal(
            input("maxPriorityFeePerGas (Gwei) [2]: ").strip() or "2")
        max_fee_wei = int(max_fee_gwei * GWEI)
        priority_wei = int(priority_gwei * GWEI)
        gas_cost_wei = gas_limit * max_fee_wei
        send_wei = balance_wei - gas_cost_wei

        if send_wei <= 0:
            gas_cost_eth = Decimal(gas_cost_wei) / WEI
            print("[ERRO] Saldo insuficiente para gas!")
            print(f"       Saldo:    {balance_eth:.6f} ETH")
            print(f"       Gas cost: {gas_cost_eth:.6f} ETH")
            sys.exit(1)

        send_eth = Decimal(send_wei) / WEI
        gas_cost_eth = Decimal(gas_cost_wei) / WEI

        print("\n  === RESUMO (SEND-ALL, EIP-1559) ===")
        print(f"  Saldo:    {balance_eth:.6f} ETH")
        print(f"  Gas cost: {gas_cost_eth:.6f} ETH "
              f"({gas_limit} x {max_fee_gwei:.2f} Gwei)")
        print(f"  Enviar:   {send_eth:.6f} ETH")
        print(f"  Destino:  {to}")

        confirm = input("\n  Confirmar? (s/n): ").strip().lower()
        if confirm != "s":
            print("Cancelado.")
            sys.exit(0)

        tx = {
            'type': 2,
            'to': to,
            'value': send_wei,
            'gas': gas_limit,
            'maxFeePerGas': max_fee_wei,
            'maxPriorityFeePerGas': priority_wei,
            'nonce': nonce,
            'chainId': 1
        }

        return {
            'private_key': private_key,
            'tx': tx,
            'to': to,
            'send_wei': send_wei,
            'gas_cost_wei': gas_cost_wei,
            'tx_type': 'eip1559',
        }


def sign_and_save(tx_data):
    """Assina e salva a transacao"""
    raw_tx = sign_eth_transaction(
        tx_data['private_key'],
        tx_data['tx']
    )

    print("\n[+] Transacao assinada!")
    print(f"\nRaw TX (copie para broadcast):\n{raw_tx}")

    # Salva
    output_dir = Path(__file__).parent / "signed_transactions"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"eth_signed_{timestamp}.json"

    with open(filepath, 'w') as f:
        json.dump({
            "type": "ethereum",
            "raw_transaction": raw_tx,
            "to": tx_data['to'],
            "amount_wei": tx_data['send_wei'],
            "gas_cost_wei": tx_data['gas_cost_wei'],
            "tx_type": tx_data['tx_type'],
            "send_all": True,
            "signed_at": datetime.now().isoformat()
        }, f, indent=2)

    print(f"\nSalvo em: {filepath}")
    return filepath


def main():
    print("\n=== ASSINADOR ETHEREUM OFFLINE (SEND-ALL + EIP-1559) ===\n")

    # Verifica se e administrador
    if not require_admin():
        print("[ERRO] Execute como Administrador para controle de rede!")
        print("       Clique direito no terminal -> Executar como administrador")
        print("\n       Ou use --no-network-control para pular")
        if "--no-network-control" not in sys.argv:
            sys.exit(1)

    use_network_control = "--no-network-control" not in sys.argv

    # Coleta dados ANTES de desligar a rede
    print("[1] Primeiro, informe os dados da transacao")
    print("    (Busque nonce e fees via tools/fetch_tx_data.py se necessario)\n")

    tx_data = collect_tx_data()

    print("\n[2] Agora vamos assinar OFFLINE\n")

    if use_network_control:
        with OfflineContext(auto_reconnect=True):
            sign_and_save(tx_data)
    else:
        if is_online():
            print("[ALERTA] Voce esta ONLINE! Recomendado desconectar manualmente.")
            resp = input("Continuar mesmo assim? (s/n): ").strip().lower()
            if resp != 's':
                print("Cancelado.")
                sys.exit(0)
        sign_and_save(tx_data)

    print("\n[3] Use tools/broadcast_tor.py para enviar via Tor")


if __name__ == "__main__":
    main()
