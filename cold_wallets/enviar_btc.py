#!/usr/bin/env python3
"""
ENVIAR BITCOIN - SEND-ALL AUTOMATIZADO VIA TOR
1. Informa WIF -> detecta endereco com saldo via Tor
2. Estima fee por tipo de endereco (p2wkh/np2wkh/p2pkh)
3. Envia saldo TOTAL (amount = balance - fee, sem troco)
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
    from bit import Key
    from bit.network.meta import Unspent
except ImportError:
    print("[ERRO] Dependencias nao instaladas!")
    print("Execute: C:\\Python314\\python.exe -m pip install "
          "bit requests[socks] PySocks")
    sys.exit(1)

from network_control import OfflineContext, require_admin, is_online
from address_validation import validate_btc_address


# Configuracao Tor
TOR_PROXIES = [
    {"http": "socks5h://127.0.0.1:9150", "https": "socks5h://127.0.0.1:9150"},
    {"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"},
]

# vsize por tipo de input/output (em vBytes)
INPUT_VSIZE = {"p2wkh": 68, "np2wkh": 91, "p2pkh": 148, "p2tr": 58}
OUTPUT_VSIZE = {"p2wkh": 31, "np2wkh": 32, "p2pkh": 34, "p2tr": 43}

SAT = Decimal(100_000_000)


def detect_address_type(address):
    """Detecta tipo de endereco Bitcoin para calculo de fee"""
    if address.startswith("bc1q"):
        return "p2wkh"      # Native SegWit — 68 vB/input
    elif address.startswith("bc1p"):
        return "p2tr"       # Taproot — 58 vB/input
    elif address.startswith("3"):
        return "np2wkh"     # Nested SegWit — 91 vB/input
    elif address.startswith("1"):
        return "p2pkh"      # Legacy — 148 vB/input
    return "p2pkh"          # fallback conservador


def estimate_tx_vsize(n_inputs, input_type, dest_address):
    """Estima vsize da transacao (sem troco — send-all, 1 output)"""
    dest_type = detect_address_type(dest_address)
    overhead = 11  # ~10.5 arredondado (version + locktime + segwit marker)
    inputs = n_inputs * INPUT_VSIZE.get(input_type, 148)
    outputs = 1 * OUTPUT_VSIZE.get(dest_type, 34)
    return overhead + inputs + outputs


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


def fetch_utxos(session, address):
    """Busca UTXOs de um endereco via Tor"""
    apis = [
        f"https://blockstream.info/api/address/{address}/utxo",
        f"https://mempool.space/api/address/{address}/utxo",
    ]

    for url in apis:
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"    [-] API falhou ({url}): {e}")
            continue

    return None


def fetch_script_pubkey(session, txid, vout):
    """Busca scriptPubKey de um output especifico via Tor"""
    apis = [
        f"https://blockstream.info/api/tx/{txid}",
        f"https://mempool.space/api/tx/{txid}",
    ]
    for url in apis:
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200:
                tx = r.json()
                return tx["vout"][vout]["scriptpubkey"]
        except Exception:
            continue
    return None


def find_funded_address(session, key):
    """Busca UTXOs em todos os formatos de endereco da chave"""
    candidates = [
        (key.segwit_address, "np2wkh"),   # 3... (P2SH-wrapped SegWit)
        (key.address, "p2pkh"),            # 1... (legacy)
    ]
    # Native SegWit (bc1q) se disponivel na lib bit
    if hasattr(key, 'segwit_address_native'):
        candidates.insert(0, (key.segwit_address_native, "p2wkh"))
    else:
        try:
            from bit.format import public_key_to_segwit_address
            bc1_addr = public_key_to_segwit_address(key.public_key)
            candidates.insert(0, (bc1_addr, "p2wkh"))
        except (ImportError, Exception):
            pass  # lib bit sem suporte nativo bc1q
    for address, addr_type in candidates:
        utxos = fetch_utxos(session, address)
        if utxos:
            return address, addr_type, utxos
    return None, None, None


def build_unspents(session, utxos, address, addr_type):
    """Cria objetos Unspent com script correto (obrigatorio)"""
    unspents = []
    for u in utxos:
        script = fetch_script_pubkey(session, u["txid"], u["vout"])
        if not script:
            raise ValueError(
                f"Nao foi possivel buscar script para {u['txid']}:{u['vout']}")
        unspent = Unspent(
            amount=u["value"],
            confirmations=u.get("status", {}).get("block_height", 0) and 1 or 0,
            script=script,
            txid=u["txid"],
            txindex=u["vout"],
            type=addr_type
        )
        unspents.append(unspent)
    return unspents


def fetch_fee_rates(session):
    """Busca taxas recomendadas via mempool.space"""
    try:
        r = session.get("https://mempool.space/api/v1/fees/recommended", timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"    [-] Erro buscando taxas: {e}")
    return {"fastestFee": 20, "halfHourFee": 10, "hourFee": 5}


def broadcast_tx(session, raw_tx):
    """Envia transacao via Tor"""
    apis = [
        "https://blockstream.info/api/tx",
        "https://mempool.space/api/tx",
    ]

    for url in apis:
        try:
            headers = {"Content-Type": "text/plain"}
            r = session.post(url, data=raw_tx, headers=headers, timeout=60)
            if r.status_code == 200:
                return True, r.text
        except Exception as e:
            print(f"    [-] Broadcast falhou ({url}): {e}")
            continue

    return False, "Todas APIs falharam"


def main():
    print("""
    =====================================================
       ENVIAR BITCOIN - SEND-ALL VIA TOR
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
    wif = input("      Private Key (WIF): ").strip()

    try:
        key = Key(wif)
    except Exception as e:
        print(f"[ERRO] Chave invalida: {e}")
        input("\nPressione Enter para sair...")
        return

    print("      Buscando saldo via Tor...")
    address, addr_type, utxos = find_funded_address(session, key)

    if not utxos:
        print("[!] Nenhum saldo encontrado em nenhum formato de endereco")
        print(f"    Testados: {key.segwit_address} (np2wkh), {key.address} (p2pkh)")
        input("\nPressione Enter para sair...")
        return

    total_sats = sum(u.get("value", 0) for u in utxos)
    total_btc = Decimal(total_sats) / SAT

    print(f"\n      Endereco: {address}")
    print(f"      Tipo:     {addr_type}")
    print(f"      Saldo:    {total_btc:.8f} BTC ({total_sats} sat)")
    print(f"      UTXOs:    {len(utxos)}")

    if total_sats == 0:
        print("\n[!] Saldo zero - nada para enviar")
        input("\nPressione Enter para sair...")
        return

    # [3/5] Destino + fee estimation
    print("\n[3/5] Informe o destino")
    dest_address = input("      Endereco destino: ").strip()

    valid, msg = validate_btc_address(dest_address)
    if not valid:
        print(f"[ERRO] Endereco invalido: {msg}")
        input("\nPressione Enter para sair...")
        return

    # Busca fee rates
    print("\n      Buscando taxas recomendadas...")
    fees = fetch_fee_rates(session)
    print(f"      Rapida: {fees.get('fastestFee', 20)} sat/vB")
    print(f"      Media:  {fees.get('halfHourFee', 10)} sat/vB")
    print(f"      Lenta:  {fees.get('hourFee', 5)} sat/vB")

    fee_rate = input(
        f"\n      Taxa sat/vB [{fees.get('halfHourFee', 10)}]: ").strip()
    fee_rate = int(fee_rate) if fee_rate else fees.get('halfHourFee', 10)

    # Estima vsize por tipo de endereco
    vsize = estimate_tx_vsize(len(utxos), addr_type, dest_address)
    fee_sats = vsize * fee_rate
    send_sats = total_sats - fee_sats

    if send_sats <= 0:
        print("[ERRO] Saldo insuficiente para taxa!")
        print(f"       Saldo: {total_sats} sat")
        print(f"       Fee:   {fee_sats} sat (vsize={vsize} vB x {fee_rate} sat/vB)")
        input("\nPressione Enter para sair...")
        return

    send_btc = Decimal(send_sats) / SAT
    fee_btc = Decimal(fee_sats) / SAT

    print("\n      === RESUMO (SEND-ALL, SEM TROCO) ===")
    print(f"      Saldo:   {total_btc:.8f} BTC ({total_sats} sat)")
    print(f"      Fee:     {fee_btc:.8f} BTC ({fee_sats} sat)")
    print(f"      Enviar:  {send_btc:.8f} BTC ({send_sats} sat)")
    print(f"      vsize:   {vsize} vB ({addr_type}, {len(utxos)} inputs)")
    print(f"      Destino: {dest_address}")

    confirm = input("\n      Confirmar? (s/n): ").strip().lower()
    if confirm != "s":
        print("Cancelado.")
        return

    # [4/5] Busca scripts e assina OFFLINE
    print("\n[4/5] Preparando e assinando transacao...")
    print("      Buscando scriptPubKey dos UTXOs...")

    unspents = build_unspents(session, utxos, address, addr_type)
    print(f"      {len(unspents)} UTXOs preparados")

    def sign_transaction():
        """Assina a transacao offline"""
        key.unspents = unspents
        outputs = [(dest_address, send_sats, "satoshi")]
        raw_tx = key.create_transaction(
            outputs, fee=fee_sats, absolute_fee=True)
        return raw_tx

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
    filepath = output_dir / f"btc_signed_{timestamp}.json"

    with open(filepath, "w") as f:
        json.dump({
            "type": "bitcoin",
            "raw_transaction": raw_tx,
            "from": address,
            "from_type": addr_type,
            "to": dest_address,
            "amount_sats": send_sats,
            "fee_sats": fee_sats,
            "fee_rate": fee_rate,
            "vsize": vsize,
            "send_all": True,
            "signed_at": datetime.now().isoformat()
        }, f, indent=2)

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
        print(f"  TXID: {result}")
        print("\n  Acompanhe em:")
        print(f"  https://mempool.space/tx/{result}")
    else:
        print(f"\n[!] Erro no broadcast: {result}")
        print("    Transacao salva. Tente broadcast_tor.py depois.")

    input("\nPressione Enter para sair...")


if __name__ == "__main__":
    main()
