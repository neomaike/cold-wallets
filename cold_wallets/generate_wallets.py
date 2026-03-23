#!/usr/bin/env python3
"""
GERADOR DE CARTEIRAS FRIAS - SIMPLES E DIRETO
Gera 3 carteiras Bitcoin + 3 carteiras Ethereum

DESLIGA A INTERNET AUTOMATICAMENTE durante a geracao
Requer execucao como Administrador
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from eth_account import Account
from bit import Key

from network_control import OfflineContext, require_admin, is_online


def generate_ethereum_wallets(count=3):
    """Gera carteiras Ethereum"""
    wallets = []
    for i in range(count):
        account = Account.create()
        wallets.append({
            "index": i + 1,
            "private_key": account.key.hex(),
            "address": account.address
        })
    return wallets


def generate_bitcoin_wallets(count=3):
    """Gera carteiras Bitcoin"""
    wallets = []
    for i in range(count):
        key = Key()
        wallets.append({
            "index": i + 1,
            "private_key_wif": key.to_wif(),
            "address": key.segwit_address,  # Use este para receber!
            "address_legacy": key.address   # Formato antigo (opcional)
        })
    return wallets


def main():
    print("""
    =====================================================
       GERADOR DE CARTEIRAS FRIAS - 100% OFFLINE
    =====================================================
    """)

    # Verifica se e administrador
    if not require_admin():
        print("[ERRO] Execute como Administrador para controle de rede!")
        print("       Clique direito no terminal -> Executar como administrador")
        print("\n       Ou use --no-network-control para pular")
        if "--no-network-control" not in sys.argv:
            sys.exit(1)

    use_network_control = "--no-network-control" not in sys.argv

    output_dir = Path(__file__).parent / "generated"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if use_network_control:
        # Executa com controle de rede (desliga internet)
        with OfflineContext(auto_reconnect=True):
            eth_wallets, btc_wallets, filepath = _generate_wallets(
                output_dir, timestamp)
    else:
        # Executa sem controle de rede
        if is_online():
            print("[ALERTA] Voce esta ONLINE! Recomendado desconectar manualmente.")
            resp = input("Continuar mesmo assim? (s/n): ").strip().lower()
            if resp != 's':
                print("Cancelado.")
                sys.exit(0)
        eth_wallets, btc_wallets, filepath = _generate_wallets(output_dir, timestamp)

    # Exibe resultados
    _display_wallets(eth_wallets, btc_wallets, filepath)


def _generate_wallets(output_dir, timestamp):
    """Gera e salva as carteiras"""
    print("[*] Gerando 3 carteiras Ethereum...")
    eth_wallets = generate_ethereum_wallets(3)

    print("[*] Gerando 3 carteiras Bitcoin...")
    btc_wallets = generate_bitcoin_wallets(3)

    # Salva
    data = {
        "created_at": datetime.now().isoformat(),
        "ethereum": eth_wallets,
        "bitcoin": btc_wallets
    }

    filepath = output_dir / f"cold_wallets_{timestamp}.json"
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

    return eth_wallets, btc_wallets, filepath


def _display_wallets(eth_wallets, btc_wallets, filepath):
    """Exibe as carteiras geradas"""
    print("\n" + "="*60)
    print("  ETHEREUM (enderecos comecam com 0x)")
    print("="*60)
    for w in eth_wallets:
        print(f"\n  Carteira #{w['index']}")
        print(f"  Address:     {w['address']}")
        print(f"  Private Key: {w['private_key']}")

    print("\n" + "="*60)
    print("  BITCOIN (use o Address para receber)")
    print("="*60)
    for w in btc_wallets:
        print(f"\n  Carteira #{w['index']}")
        print(f"  Address:     {w['address']}")  # SegWit - comeca com 3 ou bc1
        print(f"  Private WIF: {w['private_key_wif']}")

    print("\n" + "="*60)
    print(f"  Salvo em: {filepath}")
    print("="*60)

    print("""
    ENDERECOS BITCOIN:
    - Comecam com '3' ou 'bc1' (SegWit - taxas menores)
    - Comecam com '1' (Legacy - formato antigo)

    Para RECEBER: use o 'Address' mostrado acima
    Para ENVIAR: use o script sign_btc.py

    [!] IMPORTANTE: Anote as chaves e DELETE o arquivo JSON!
    """)


if __name__ == "__main__":
    main()
