#!/usr/bin/env python3
"""
GERADOR DE ENDERECOS DESCARTAVEIS
Gera pool de enderecos para uso unico

DESLIGA A INTERNET AUTOMATICAMENTE durante a geracao
Requer execucao como Administrador
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Adiciona o diretorio pai ao path para importar network_control
sys.path.insert(0, str(Path(__file__).parent.parent))

from eth_account import Account
from bit import Key

from network_control import OfflineContext, require_admin, is_online


POOL_DIR = Path(__file__).parent / "address_pool" / "unused"


def generate_btc_addresses(count):
    """Gera enderecos Bitcoin descartaveis"""
    addresses = []
    for i in range(count):
        key = Key()
        addresses.append({
            "index": i,
            "crypto": "btc",
            "address": key.segwit_address,
            "address_legacy": key.address,
            "private_key_wif": key.to_wif(),
            "created_at": datetime.now().isoformat(),
            "status": "unused"
        })
    return addresses


def generate_eth_addresses(count):
    """Gera enderecos Ethereum descartaveis"""
    addresses = []
    for i in range(count):
        account = Account.create()
        addresses.append({
            "index": i,
            "crypto": "eth",
            "address": account.address,
            "private_key": account.key.hex(),
            "created_at": datetime.now().isoformat(),
            "status": "unused"
        })
    return addresses


def save_addresses(addresses, crypto):
    """Salva enderecos em arquivos individuais"""
    POOL_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved = []

    for addr in addresses:
        # Cria nome de arquivo unico
        filename = f"{crypto}_{timestamp}_{addr['index']:03d}.json"
        filepath = POOL_DIR / filename

        with open(filepath, 'w') as f:
            json.dump(addr, f, indent=2)

        saved.append(filepath)
        print(f"  [+] {addr['address'][:20]}... -> {filename}")

    return saved


def main():
    parser = argparse.ArgumentParser(description='Gera enderecos descartaveis')
    parser.add_argument('--count', '-c', type=int, default=10,
                        help='Quantidade de enderecos (default: 10)')
    parser.add_argument('--crypto', choices=['btc', 'eth', 'both'], default='both',
                        help='Tipo de crypto (default: both)')
    parser.add_argument('--no-network-control', action='store_true',
                        help='Nao desligar internet automaticamente')

    args = parser.parse_args()

    print("""
    =====================================================
       GERADOR DE ENDERECOS DESCARTAVEIS - OFFLINE
    =====================================================
    """)

    # Verifica admin se precisar de controle de rede
    if not args.no_network_control and not require_admin():
        print("[ERRO] Execute como Administrador para controle de rede!")
        print("       Ou use --no-network-control para pular")
        sys.exit(1)

    use_network_control = not args.no_network_control

    def generate():
        """Funcao de geracao"""
        all_addresses = []

        if args.crypto in ['btc', 'both']:
            print(f"\n[*] Gerando {args.count} enderecos Bitcoin...")
            btc = generate_btc_addresses(args.count)
            save_addresses(btc, 'btc')
            all_addresses.extend(btc)

        if args.crypto in ['eth', 'both']:
            print(f"\n[*] Gerando {args.count} enderecos Ethereum...")
            eth = generate_eth_addresses(args.count)
            save_addresses(eth, 'eth')
            all_addresses.extend(eth)

        return all_addresses

    if use_network_control:
        with OfflineContext(auto_reconnect=True):
            addresses = generate()
    else:
        if is_online():
            print("[ALERTA] Voce esta ONLINE! Recomendado desconectar manualmente.")
            resp = input("Continuar mesmo assim? (s/n): ").strip().lower()
            if resp != 's':
                print("Cancelado.")
                sys.exit(0)
        addresses = generate()

    # Resumo
    print("\n" + "="*60)
    print("  RESUMO")
    print("="*60)

    btc_count = len([a for a in addresses if a['crypto'] == 'btc'])
    eth_count = len([a for a in addresses if a['crypto'] == 'eth'])

    print(f"\n  Enderecos BTC gerados: {btc_count}")
    print(f"  Enderecos ETH gerados: {eth_count}")
    print(f"  Total: {len(addresses)}")
    print(f"\n  Salvos em: {POOL_DIR}")

    print("""
    USO:
    - Use disposable_manager.py para pegar enderecos
    - Cada endereco deve ser usado apenas UMA VEZ
    - Apos receber, faca sweep para cold wallet
    """)


if __name__ == "__main__":
    main()
