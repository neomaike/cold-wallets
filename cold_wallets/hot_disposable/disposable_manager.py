#!/usr/bin/env python3
"""
GERENCIADOR DE ENDERECOS DESCARTAVEIS
Gerencia ciclo de vida: unused -> active -> funded -> spent
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Adiciona o diretorio pai ao path
sys.path.insert(0, str(Path(__file__).parent.parent))


BASE_DIR = Path(__file__).parent / "address_pool"
UNUSED_DIR = BASE_DIR / "unused"
ACTIVE_DIR = BASE_DIR / "active"
FUNDED_DIR = BASE_DIR / "funded"
SPENT_DIR = BASE_DIR / "spent"
LOGS_DIR = Path(__file__).parent / "logs"


def ensure_dirs():
    """Garante que os diretorios existem"""
    for d in [UNUSED_DIR, ACTIVE_DIR, FUNDED_DIR, SPENT_DIR, LOGS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def get_address_count():
    """Conta enderecos em cada estado"""
    ensure_dirs()
    return {
        'unused': len(list(UNUSED_DIR.glob('*.json'))),
        'active': len(list(ACTIVE_DIR.glob('*.json'))),
        'funded': len(list(FUNDED_DIR.glob('*.json'))),
        'spent': len(list(SPENT_DIR.glob('*.json')))
    }


def cmd_status(args):
    """Mostra status do pool de enderecos"""
    counts = get_address_count()

    print("\n" + "="*50)
    print("  STATUS DO POOL DE ENDERECOS")
    print("="*50)

    print(f"\n  Nao usados (unused):  {counts['unused']}")
    print(f"  Ativos (active):      {counts['active']}")
    print(f"  Com saldo (funded):   {counts['funded']}")
    print(f"  Gastos (spent):       {counts['spent']}")
    print(f"\n  Total: {sum(counts.values())}")

    if counts['unused'] < 5:
        print("\n  [ALERTA] Pool baixo! Gere mais enderecos com generate_disposable.py")


def cmd_get_address(args):
    """Pega proximo endereco disponivel"""
    ensure_dirs()

    crypto = args.crypto
    pattern = f"{crypto}_*.json" if crypto else "*.json"

    # Busca enderecos disponiveis
    available = sorted(UNUSED_DIR.glob(pattern))

    if not available:
        tag = crypto.upper() if crypto else ''
        print(f"\n[ERRO] Nenhum endereco {tag} disponivel!")
        print("       Execute generate_disposable.py para criar mais")
        sys.exit(1)

    # Pega o primeiro
    addr_file = available[0]

    with open(addr_file) as f:
        addr_data = json.load(f)

    # Atualiza status
    addr_data['status'] = 'active'
    addr_data['activated_at'] = datetime.now().isoformat()

    # Move para active (atomico: rename ao inves de write+delete)
    new_path = ACTIVE_DIR / addr_file.name
    try:
        addr_file.rename(new_path)
    except OSError:
        # Fallback se rename falha (cross-device)
        with open(new_path, 'w') as f:
            json.dump(addr_data, f, indent=2)
        addr_file.unlink()
    # Reescreve com status atualizado
    with open(new_path, 'w') as f:
        json.dump(addr_data, f, indent=2)

    # Exibe
    print("\n" + "="*60)
    print("  ENDERECO PARA RECEBER")
    print("="*60)
    print(f"\n  Tipo:     {addr_data['crypto'].upper()}")
    print(f"  Endereco: {addr_data['address']}")
    print(f"\n  Arquivo:  {new_path}")
    print("\n  [!] Use este endereco apenas UMA VEZ!")
    print("  [!] Apos receber, marque como 'funded' e faca sweep")

    # Log
    log_action('get_address', addr_data)

    return addr_data


def cmd_mark_funded(args):
    """Marca endereco como com saldo"""
    ensure_dirs()

    address = args.address

    # Busca em active
    for addr_file in ACTIVE_DIR.glob('*.json'):
        with open(addr_file) as f:
            addr_data = json.load(f)

        if addr_data['address'] == address:
            # Atualiza
            addr_data['status'] = 'funded'
            addr_data['funded_at'] = datetime.now().isoformat()

            # Move para funded (atomico: rename ao inves de write+delete)
            new_path = FUNDED_DIR / addr_file.name
            try:
                addr_file.rename(new_path)
            except OSError:
                with open(new_path, 'w') as f:
                    json.dump(addr_data, f, indent=2)
                addr_file.unlink()
            # Reescreve com status atualizado
            with open(new_path, 'w') as f:
                json.dump(addr_data, f, indent=2)

            print("\n[+] Endereco marcado como FUNDED")
            print(f"    {address}")

            log_action('mark_funded', addr_data)
            return

    print("\n[ERRO] Endereco nao encontrado em 'active'")
    print(f"       {address}")


def cmd_list(args):
    """Lista enderecos em um estado"""
    ensure_dirs()

    state = args.state
    crypto = args.crypto

    dirs = {
        'unused': UNUSED_DIR,
        'active': ACTIVE_DIR,
        'funded': FUNDED_DIR,
        'spent': SPENT_DIR,
        'all': None
    }

    if state == 'all':
        states = ['unused', 'active', 'funded', 'spent']
    else:
        states = [state]

    print("\n" + "="*70)

    for s in states:
        d = dirs[s]
        pattern = f"{crypto}_*.json" if crypto else "*.json"
        files = sorted(d.glob(pattern))

        print(f"\n  [{s.upper()}] ({len(files)} enderecos)")
        print("-"*70)

        for f in files[:10]:  # Limita a 10 por estado
            with open(f) as fp:
                data = json.load(fp)
            print(f"  {data['crypto'].upper():4} {data['address']}")

        if len(files) > 10:
            print(f"  ... e mais {len(files) - 10}")


def cmd_show(args):
    """Mostra detalhes de um endereco"""
    address = args.address

    for d in [UNUSED_DIR, ACTIVE_DIR, FUNDED_DIR, SPENT_DIR]:
        for f in d.glob('*.json'):
            with open(f) as fp:
                data = json.load(fp)
            if data['address'] == address:
                print("\n" + "="*60)
                print("  DETALHES DO ENDERECO")
                print("="*60)
                print(json.dumps(data, indent=2))
                print(f"\n  Arquivo: {f}")
                return

    print(f"\n[ERRO] Endereco nao encontrado: {address}")


def log_action(action, addr_data):
    """Registra acao no log"""
    LOGS_DIR.mkdir(exist_ok=True)
    log_file = LOGS_DIR / "actions.log"

    entry = {
        'timestamp': datetime.now().isoformat(),
        'action': action,
        'crypto': addr_data['crypto'],
        'address': addr_data['address']
    }

    with open(log_file, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def main():
    parser = argparse.ArgumentParser(
        description='Gerenciador de enderecos descartaveis')
    subparsers = parser.add_subparsers(dest='command', help='Comandos')

    # status
    p_status = subparsers.add_parser('status', help='Mostra status do pool')
    p_status.set_defaults(func=cmd_status)

    # get-address
    p_get = subparsers.add_parser('get-address', help='Pega proximo endereco')
    p_get.add_argument('--crypto', '-c', choices=['btc', 'eth'],
                       help='Tipo de crypto')
    p_get.set_defaults(func=cmd_get_address)

    # mark-funded
    p_funded = subparsers.add_parser(
        'mark-funded', help='Marca endereco como com saldo')
    p_funded.add_argument('address', help='Endereco a marcar')
    p_funded.set_defaults(func=cmd_mark_funded)

    # list
    p_list = subparsers.add_parser('list', help='Lista enderecos')
    p_list.add_argument('--state', '-s', default='all',
                        choices=['unused', 'active', 'funded', 'spent', 'all'],
                        help='Estado dos enderecos')
    p_list.add_argument('--crypto', '-c', choices=['btc', 'eth'],
                        help='Filtrar por crypto')
    p_list.set_defaults(func=cmd_list)

    # show
    p_show = subparsers.add_parser('show', help='Mostra detalhes de um endereco')
    p_show.add_argument('address', help='Endereco a mostrar')
    p_show.set_defaults(func=cmd_show)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
