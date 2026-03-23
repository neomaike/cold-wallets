#!/usr/bin/env python3
"""
VERIFICADOR DE CONEXAO TOR
Verifica se o Tor esta funcionando e mostra o IP de saida.
Nunca expoe o IP real — toda verificacao passa pelo proxy Tor.
"""

import sys

try:
    import requests
except ImportError:
    print("ERRO: requests nao instalado!")
    print("Execute: pip install requests[socks] PySocks")
    sys.exit(1)


def check_tor():
    print("\n=== VERIFICADOR DE CONEXAO TOR ===\n")

    proxies_to_try = [
        ("Tor Browser (9150)", "socks5h://127.0.0.1:9150"),
        ("Tor Daemon (9050)", "socks5h://127.0.0.1:9050"),
    ]

    for name, proxy in proxies_to_try:
        print(f"[*] Testando {name}...")

        try:
            session = requests.Session()
            session.proxies = {'http': proxy, 'https': proxy}

            response = session.get(
                'https://check.torproject.org/api/ip', timeout=15
            )
            data = response.json()

            if data.get('IsTor'):
                print("    [OK] Conectado ao Tor!")
                print(f"    [+] IP de saida: {data.get('IP')}")
                print(f"    [+] Proxy: {proxy}")
                return True
            else:
                print("    [!] Conectado mas NAO via Tor")

        except requests.exceptions.ConnectionError:
            print("    [-] Nao conectado (porta fechada)")
        except Exception as e:
            print(f"    [-] Erro: {e}")

    print("\n[!] NENHUMA CONEXAO TOR ENCONTRADA!")
    print("\n    Solucoes:")
    print("    1. Abra o Tor Browser")
    print("    2. Ou inicie o Tor daemon")
    print("    3. Verifique firewall/antivirus")

    return False


if __name__ == "__main__":
    tor_ok = check_tor()

    print("\n" + "=" * 50)
    if tor_ok:
        print("  STATUS: TOR FUNCIONANDO")
        print("  Voce pode usar os scripts com privacidade.")
    else:
        print("  STATUS: TOR NAO CONECTADO")
        print("  Inicie o Tor Browser antes de continuar!")
    print("=" * 50 + "\n")

    input("Pressione Enter para sair...")
