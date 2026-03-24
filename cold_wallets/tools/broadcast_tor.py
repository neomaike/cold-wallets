#!/usr/bin/env python3
"""
BROADCASTER DE TRANSACOES VIA TOR
Este script envia transacoes assinadas para a rede usando Tor.

PRE-REQUISITOS:
1. Tor instalado e rodando (porta 9050 ou Tor Browser na porta 9150)
2. Transacao ja assinada offline

PARA WINDOWS:
1. Instale o Tor Browser: https://www.torproject.org/download/
2. Abra o Tor Browser e mantenha-o aberto
3. Execute este script

PARA LINUX:
sudo apt install tor
sudo systemctl start tor
"""

import sys
import json
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERRO: requests nao instalado!")
    print("Execute: pip install requests[socks] PySocks")
    sys.exit(1)


# Configuracoes do Tor
TOR_PROXY_BROWSER = "socks5h://127.0.0.1:9150"  # Tor Browser
TOR_PROXY_DAEMON = "socks5h://127.0.0.1:9050"   # Tor Daemon

# APIs para broadcast (usam endpoints .onion quando possivel)
BITCOIN_BROADCAST_APIS = [
    {
        "name": "Blockstream (clearnet via Tor)",
        "url": "https://blockstream.info/api/tx",
        "method": "POST",
        "content_type": "text/plain"
    },
    {
        "name": "Mempool.space (clearnet via Tor)",
        "url": "https://mempool.space/api/tx",
        "method": "POST",
        "content_type": "text/plain"
    },
    {
        "name": "BlockCypher (clearnet via Tor)",
        "url": "https://api.blockcypher.com/v1/btc/main/txs/push",
        "method": "POST",
        "content_type": "application/json",
        "body_format": "json",
        "body_key": "tx"
    }
]

ETHEREUM_BROADCAST_APIS = [
    {
        "name": "Cloudflare ETH (clearnet via Tor)",
        "url": "https://cloudflare-eth.com",
        "method": "POST",
        "content_type": "application/json",
        "rpc": True
    },
    {
        "name": "PublicNode ETH (clearnet via Tor)",
        "url": "https://ethereum.publicnode.com",
        "method": "POST",
        "content_type": "application/json",
        "rpc": True
    }
]


def check_tor_connection(proxy):
    """Verifica se a conexao Tor esta funcionando"""
    try:
        session = requests.Session()
        session.proxies = {
            'http': proxy,
            'https': proxy
        }

        # Verifica IP via Tor
        response = session.get('https://check.torproject.org/api/ip', timeout=30)
        data = response.json()

        if data.get('IsTor'):
            print("[+] Conectado ao Tor!")
            print(f"    IP de saida: {data.get('IP')}")
            return True
        else:
            print("[-] Conectado, mas NAO via Tor!")
            return False

    except Exception:
        return False


def get_tor_session():
    """Retorna uma sessao requests configurada para usar Tor"""
    session = requests.Session()

    # Tenta primeiro o Tor Browser (9150)
    print("[*] Tentando conectar ao Tor Browser (porta 9150)...")
    if check_tor_connection(TOR_PROXY_BROWSER):
        session.proxies = {
            'http': TOR_PROXY_BROWSER,
            'https': TOR_PROXY_BROWSER
        }
        return session

    # Tenta o Tor Daemon (9050)
    print("[*] Tentando conectar ao Tor Daemon (porta 9050)...")
    if check_tor_connection(TOR_PROXY_DAEMON):
        session.proxies = {
            'http': TOR_PROXY_DAEMON,
            'https': TOR_PROXY_DAEMON
        }
        return session

    return None


def broadcast_bitcoin(session, raw_tx):
    """Envia transacao Bitcoin para a rede"""
    print("\n[*] Enviando transacao Bitcoin...")

    for api in BITCOIN_BROADCAST_APIS:
        print(f"\n    Tentando: {api['name']}")

        try:
            if api.get('body_format') == 'json':
                response = session.post(
                    api['url'],
                    json={api['body_key']: raw_tx},
                    timeout=60
                )
            else:
                response = session.post(
                    api['url'],
                    data=raw_tx,
                    headers={'Content-Type': api.get('content_type', 'text/plain')},
                    timeout=60
                )

            if response.status_code == 200:
                print("    [+] SUCESSO!")
                print(f"    Resposta: {response.text[:200]}")
                return True, response.text
            else:
                print(f"    [-] Falhou: {response.status_code}")
                print(f"    {response.text[:200]}")

        except Exception as e:
            print(f"    [-] Erro: {e}")

    return False, "Todas as APIs falharam"


def broadcast_ethereum(session, raw_tx):
    """Envia transacao Ethereum para a rede"""
    print("\n[*] Enviando transacao Ethereum...")

    # Garante que tem prefixo 0x
    if not raw_tx.startswith('0x'):
        raw_tx = '0x' + raw_tx

    for api in ETHEREUM_BROADCAST_APIS:
        print(f"\n    Tentando: {api['name']}")

        try:
            if api.get('rpc'):
                # JSON-RPC
                payload = {
                    "jsonrpc": "2.0",
                    "method": "eth_sendRawTransaction",
                    "params": [raw_tx],
                    "id": 1
                }
                response = session.post(
                    api['url'],
                    json=payload,
                    timeout=60
                )
            elif api.get('params'):
                # Etherscan style
                params = api['params'].copy()
                params[api['body_key']] = raw_tx
                response = session.post(
                    api['url'],
                    data=params,
                    timeout=60
                )
            else:
                response = session.post(
                    api['url'],
                    data=raw_tx,
                    timeout=60
                )

            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    print(f"    [-] Erro: {result['error']}")
                else:
                    print("    [+] SUCESSO!")
                    tx_hash = result.get('result') or result.get('txHash')
                    print(f"    TX Hash: {tx_hash}")
                    return True, tx_hash
            else:
                print(f"    [-] Falhou: {response.status_code}")

        except Exception as e:
            print(f"    [-] Erro: {e}")

    return False, "Todas as APIs falharam"


def load_signed_transaction(filepath):
    """Carrega transacao assinada de arquivo"""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"[ERRO] Falha ao ler arquivo: {e}")
        sys.exit(1)

    if 'raw_transaction' not in data:
        print("[ERRO] Arquivo nao contem campo 'raw_transaction'")
        print(f"       Campos encontrados: {list(data.keys())}")
        sys.exit(1)

    if 'type' not in data:
        print("[ERRO] Arquivo nao contem campo 'type' (bitcoin/ethereum)")
        sys.exit(1)

    return data


def save_broadcast_result(tx_data, result, success):
    """Salva resultado do broadcast"""
    output_dir = Path(__file__).parent.parent / "broadcast_logs"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"broadcast_{tx_data['type']}_{timestamp}.json"
    filepath = output_dir / filename

    log_data = {
        "broadcast_at": datetime.now().isoformat(),
        "success": success,
        "type": tx_data['type'],
        "transaction_hash": tx_data.get('transaction_hash'),
        "result": result
    }

    with open(filepath, 'w') as f:
        json.dump(log_data, f, indent=2)

    return filepath


def main():
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║         BROADCASTER DE TRANSACOES VIA TOR                    ║
    ║                                                               ║
    ║  Envia transacoes assinadas para a rede de forma anonima     ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)

    print("[!] PRE-REQUISITOS:")
    print("    1. Tor Browser aberto OU Tor daemon rodando")
    print("    2. Transacao ja assinada offline\n")

    # Verifica conexao Tor
    session = get_tor_session()

    if not session:
        print("\n[!] ERRO: Nao foi possivel conectar ao Tor!")
        print("\n    WINDOWS: Abra o Tor Browser e mantenha-o aberto")
        print("    LINUX:   sudo systemctl start tor")
        return

    print("\nOpcoes:")
    print("  1. Enviar transacao de arquivo")
    print("  2. Enviar transacao manualmente (colar hex)")
    print("  3. Verificar conexao Tor")
    print("  4. Sair")

    choice = input("\nEscolha uma opcao: ").strip()

    if choice == "1":
        tx_file = input("Caminho do arquivo de transacao assinada (.json): ").strip()

        if not Path(tx_file).exists():
            print(f"ERRO: Arquivo nao encontrado: {tx_file}")
            return

        tx_data = load_signed_transaction(tx_file)

        print("\n[*] Transacao carregada:")
        print(f"    Tipo: {tx_data['type'].upper()}")
        if tx_data.get('signed_at'):
            print(f"    Assinada em: {tx_data['signed_at']}")
        if tx_data.get('transaction_hash'):
            print(f"    Hash esperado: {tx_data['transaction_hash']}")

        confirm = input("\nConfirma envio? (s/N): ").lower()
        if confirm != 's':
            print("Operacao cancelada.")
            return

        raw_tx = tx_data['raw_transaction']

        if tx_data['type'] == 'bitcoin':
            success, result = broadcast_bitcoin(session, raw_tx)
        elif tx_data['type'] == 'ethereum':
            success, result = broadcast_ethereum(session, raw_tx)
        else:
            print(f"Tipo de transacao desconhecido: {tx_data['type']}")
            return

        log_path = save_broadcast_result(tx_data, result, success)

        if success:
            print("\n[+] TRANSACAO ENVIADA COM SUCESSO!")
            print(f"[+] Log salvo em: {log_path}")
        else:
            print("\n[-] FALHA ao enviar transacao")
            print(f"[-] Log salvo em: {log_path}")

    elif choice == "2":
        tx_type = input("Tipo (bitcoin/ethereum): ").strip().lower()
        raw_tx = input("Raw transaction (hex): ").strip()

        if tx_type == "bitcoin":
            success, result = broadcast_bitcoin(session, raw_tx)
        elif tx_type == "ethereum":
            success, result = broadcast_ethereum(session, raw_tx)
        else:
            print("Tipo invalido!")
            return

        if success:
            print("\n[+] TRANSACAO ENVIADA!")
        else:
            print(f"\n[-] FALHA: {result}")

    elif choice == "3":
        print("\n[*] Verificando conexao Tor...")
        try:
            response = session.get('https://check.torproject.org/api/ip', timeout=30)
            data = response.json()
            print(f"    Esta usando Tor: {data.get('IsTor')}")
            print(f"    IP de saida: {data.get('IP')}")
        except Exception as e:
            print(f"    Erro: {e}")

    else:
        print("Saindo...")


if __name__ == "__main__":
    main()
