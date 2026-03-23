#!/usr/bin/env python3
"""
ASSINADOR BITCOIN - OFFLINE, SEND-ALL
DESLIGA A INTERNET AUTOMATICAMENTE durante a assinatura
Requer execucao como Administrador

- Corrige bug do Unspent (script obrigatorio)
- Fee estimation por tipo de endereco (p2wkh/np2wkh/p2pkh)
- Sempre envia saldo total (sem troco)
"""

import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from bit import Key
from bit.network.meta import Unspent

from network_control import OfflineContext, require_admin, is_online
from address_validation import validate_btc_address


# vsize por tipo de input/output (em vBytes)
INPUT_VSIZE = {"p2wkh": 68, "np2wkh": 91, "p2pkh": 148, "p2tr": 58}
OUTPUT_VSIZE = {"p2wkh": 31, "np2wkh": 32, "p2pkh": 34, "p2tr": 43}

SAT = Decimal(100_000_000)


def detect_address_type(address):
    """Detecta tipo de endereco Bitcoin para calculo de fee"""
    if address.startswith("bc1q"):
        return "p2wkh"
    elif address.startswith("bc1p"):
        return "p2tr"
    elif address.startswith("3"):
        return "np2wkh"
    elif address.startswith("1"):
        return "p2pkh"
    return "p2pkh"


def estimate_tx_vsize(n_inputs, input_type, dest_address):
    """Estima vsize da transacao (sem troco — send-all, 1 output)"""
    dest_type = detect_address_type(dest_address)
    overhead = 11
    inputs = n_inputs * INPUT_VSIZE.get(input_type, 148)
    outputs = 1 * OUTPUT_VSIZE.get(dest_type, 34)
    return overhead + inputs + outputs


def sign_btc_transaction(private_key_wif, unspents, outputs, fee_satoshi):
    """
    Assina transacao Bitcoin com Unspents ja preparados.
    """
    key = Key(private_key_wif)
    key.unspents = unspents

    formatted_outputs = [(addr, amount, 'satoshi') for addr, amount in outputs]

    raw_tx = key.create_transaction(
        formatted_outputs, fee=fee_satoshi, absolute_fee=True)

    return raw_tx


def collect_tx_data():
    """Coleta dados da transacao do usuario (modo offline — send-all)"""
    print("\n--- Dados da Transacao (Send-All) ---\n")

    private_key = input("Private Key (WIF): ").strip()

    # Tipo de endereco de origem
    print("\nTipo do endereco de ORIGEM:")
    print("  1 = bc1q... (Native SegWit, 68 vB/input)")
    print("  2 = 3...    (Nested SegWit, 91 vB/input)")
    print("  3 = 1...    (Legacy, 148 vB/input)")
    type_choice = input("Escolha [1]: ").strip() or "1"
    type_map = {"1": "p2wkh", "2": "np2wkh", "3": "p2pkh"}
    addr_type = type_map.get(type_choice, "p2wkh")
    print(f"  -> {addr_type} ({INPUT_VSIZE[addr_type]} vB/input)")

    # UTXOs
    print("\n[UTXOs a gastar]")
    print("(Busque via tools/fetch_tx_data.py se necessario)")

    utxos = []
    total_sats = 0
    while True:
        print(f"\n  UTXO #{len(utxos) + 1}:")
        txid = input("  TXID: ").strip()
        if not txid:
            if utxos:
                break
            print("  [!] Informe pelo menos 1 UTXO")
            continue
        try:
            vout = int(input("  VOUT: "))
            amount = int(input("  Valor (satoshi): "))
        except ValueError:
            print("  [ERRO] VOUT e valor devem ser numeros inteiros")
            continue
        script = input("  scriptPubKey (hex): ").strip()
        if not script:
            print("  [ERRO] scriptPubKey e obrigatorio para Unspent!")
            print("         Busque via blockstream.info/api/tx/<txid>")
            sys.exit(1)

        utxos.append({
            "txid": txid, "vout": vout,
            "amount_satoshi": amount, "script": script
        })
        total_sats += amount

        more = input("  Mais UTXOs? (s/n) [n]: ").strip().lower()
        if more != "s":
            break

    total_btc = Decimal(total_sats) / SAT
    print(f"\n  Total: {total_btc:.8f} BTC ({total_sats} sat) em {len(utxos)} UTXO(s)")

    # Destino
    print("\n[Destino]")
    to_addr = input("Endereco destino: ").strip()

    valid, msg = validate_btc_address(to_addr)
    if not valid:
        print(f"[ERRO] Endereco invalido: {msg}")
        sys.exit(1)

    # Fee
    fee_rate = input("Taxa (sat/vB) [10]: ").strip()
    fee_rate = int(fee_rate) if fee_rate else 10

    vsize = estimate_tx_vsize(len(utxos), addr_type, to_addr)
    fee_sats = vsize * fee_rate
    send_sats = total_sats - fee_sats

    if send_sats <= 0:
        print("[ERRO] Saldo insuficiente para taxa!")
        print(f"       Total: {total_sats} sat")
        print(f"       Fee:   {fee_sats} sat (vsize={vsize} vB x {fee_rate} sat/vB)")
        sys.exit(1)

    send_btc = Decimal(send_sats) / SAT
    fee_btc = Decimal(fee_sats) / SAT

    print("\n  === RESUMO (SEND-ALL, SEM TROCO) ===")
    print(f"  Total:   {total_btc:.8f} BTC ({total_sats} sat)")
    print(f"  Fee:     {fee_btc:.8f} BTC ({fee_sats} sat)")
    print(f"  Enviar:  {send_btc:.8f} BTC ({send_sats} sat)")
    print(f"  vsize:   {vsize} vB ({addr_type}, {len(utxos)} inputs)")
    print(f"  Destino: {to_addr}")

    confirm = input("\n  Confirmar? (s/n): ").strip().lower()
    if confirm != "s":
        print("Cancelado.")
        sys.exit(0)

    # Monta Unspents com script correto
    unspents = []
    for u in utxos:
        unspent = Unspent(
            amount=u['amount_satoshi'],
            confirmations=0,
            script=u['script'],
            txid=u['txid'],
            txindex=u['vout'],
            type=addr_type
        )
        unspents.append(unspent)

    return {
        'private_key': private_key,
        'unspents': unspents,
        'outputs': [(to_addr, send_sats)],
        'fee': fee_sats,
        'to_addr': to_addr,
        'send_sats': send_sats,
        'addr_type': addr_type,
    }


def sign_and_save(tx_data):
    """Assina e salva a transacao"""
    raw_tx = sign_btc_transaction(
        tx_data['private_key'],
        tx_data['unspents'],
        tx_data['outputs'],
        tx_data['fee']
    )

    print("\n[+] Transacao assinada!")
    print(f"\nRaw TX (copie para broadcast):\n{raw_tx}")

    # Salva
    output_dir = Path(__file__).parent / "signed_transactions"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"btc_signed_{timestamp}.json"

    with open(filepath, 'w') as f:
        json.dump({
            "type": "bitcoin",
            "raw_transaction": raw_tx,
            "to": tx_data['to_addr'],
            "amount_sats": tx_data['send_sats'],
            "fee_sats": tx_data['fee'],
            "addr_type": tx_data['addr_type'],
            "send_all": True,
            "signed_at": datetime.now().isoformat()
        }, f, indent=2)

    print(f"\nSalvo em: {filepath}")
    return filepath


def main():
    print("\n=== ASSINADOR BITCOIN OFFLINE (SEND-ALL) ===\n")

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
