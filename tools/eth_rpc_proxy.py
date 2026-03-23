#!/usr/bin/env python3
"""
PROXY RPC ETHEREUM VIA TOR
Cria um servidor local que roteia chamadas RPC para a rede Ethereum via Tor.

Use no MetaMask:
- RPC URL: http://127.0.0.1:8545
- Chain ID: 1

Requer Tor rodando na porta 9050 ou 9150 (Tor Browser).
"""

import json
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    import requests
except ImportError:
    print("ERRO: requests nao instalado!")
    print("Execute: pip install requests[socks] PySocks")
    sys.exit(1)


# Configuracao
LOCAL_PORT = 8545
TOR_PROXIES = [
    "socks5h://127.0.0.1:9150",  # Tor Browser
    "socks5h://127.0.0.1:9050",  # Tor Daemon
]

# RPCs publicos para Ethereum (rotacionamos entre eles)
ETH_RPCS = [
    "https://cloudflare-eth.com",
    "https://ethereum.publicnode.com",
    "https://eth.llamarpc.com",
    "https://rpc.builder0x69.io",
]

current_rpc_index = 0
tor_session = None
tor_session_created = 0

# Origens permitidas (localhost e extensoes Chrome/Brave)
ALLOWED_ORIGINS = [
    "http://127.0.0.1",
    "http://localhost",
    "chrome-extension://",
]

# Renovar sessao Tor a cada 10 minutos
SESSION_MAX_AGE = 600


def get_tor_session():
    """Cria sessao requests com Tor"""
    global tor_session, tor_session_created

    # Reutiliza sessao se ainda valida
    if tor_session and (time.time() - tor_session_created) < SESSION_MAX_AGE:
        return tor_session

    tor_session = None
    session = requests.Session()

    for proxy in TOR_PROXIES:
        try:
            session.proxies = {'http': proxy, 'https': proxy}
            # Testa conexao
            response = session.get('https://check.torproject.org/api/ip', timeout=10)
            if response.json().get('IsTor'):
                print(f"[+] Conectado ao Tor via {proxy}")
                print(f"    IP de saida: {response.json().get('IP')}")
                tor_session = session
                tor_session_created = time.time()
                return session
        except Exception:
            continue

    print("[!] ERRO: Nao foi possivel conectar ao Tor!")
    print("    Abra o Tor Browser ou inicie o Tor daemon")
    return None


def forward_rpc_request(data):
    """Encaminha requisicao RPC para o proximo RPC publico via Tor"""
    global current_rpc_index

    session = get_tor_session()
    if not session:
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32000, "message": "Tor not connected"},
            "id": data.get("id"),
        }

    # Tenta cada RPC ate um funcionar
    for attempt in range(len(ETH_RPCS)):
        rpc_url = ETH_RPCS[current_rpc_index]
        current_rpc_index = (current_rpc_index + 1) % len(ETH_RPCS)

        try:
            response = session.post(
                rpc_url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code == 200:
                return response.json()

        except Exception as e:
            print(f"    [-] RPC {rpc_url} falhou: {e}")
            continue

    return {
        "jsonrpc": "2.0",
        "error": {"code": -32000, "message": "All RPCs failed"},
        "id": data.get("id"),
    }


def _is_origin_allowed(origin):
    """Verifica se a origem e permitida"""
    if not origin:
        # Sem Origin = chamada direta (curl, scripts locais)
        # Aceitar apenas de localhost - verificado pelo bind em 127.0.0.1
        return True
    for allowed in ALLOWED_ORIGINS:
        if origin.startswith(allowed):
            return True
    return False


def _get_cors_origin(origin):
    """Retorna a origem CORS permitida"""
    if not origin:
        return "http://127.0.0.1"
    for allowed in ALLOWED_ORIGINS:
        if origin.startswith(allowed):
            return origin
    return "http://127.0.0.1"


class RPCProxyHandler(BaseHTTPRequestHandler):
    """Handler HTTP para proxy RPC"""

    def log_message(self, format, *args):
        """Log customizado"""
        method = args[0].split()[0] if args else "?"
        print(f"    [{method}] {args[0]}" if args else "")

    def do_POST(self):
        """Processa requisicao POST (RPC)"""
        origin = self.headers.get('Origin', '')

        if not _is_origin_allowed(origin):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b'{"error": "Forbidden origin"}')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)

            # Log da requisicao (sem dados sensiveis)
            method = data.get('method', 'unknown')
            print(f"[>] {method}")

            # Encaminha via Tor
            result = forward_rpc_request(data)

            # Responde
            response_body = json.dumps(result).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response_body))
            self.send_header('Access-Control-Allow-Origin', _get_cors_origin(origin))
            self.end_headers()
            self.wfile.write(response_body)

        except Exception as e:
            print(f"[!] Erro: {e}")
            error = {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": str(e)},
                "id": None,
            }
            response_body = json.dumps(error).encode()
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(response_body)

    def do_OPTIONS(self):
        """CORS preflight"""
        origin = self.headers.get('Origin', '')
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', _get_cors_origin(origin))
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def main():
    print("""
    =====================================================
       PROXY RPC ETHEREUM VIA TOR
    =====================================================

    Este proxy roteia chamadas RPC do MetaMask via Tor.

    Configure no MetaMask:
      Rede: Ethereum (Privado)
      RPC URL: http://127.0.0.1:8545
      Chain ID: 1
      Simbolo: ETH

    """)

    # Testa conexao Tor
    session = get_tor_session()
    if not session:
        print("\n[!] Inicie o Tor Browser ou Tor daemon primeiro!")
        input("\nPressione Enter para sair...")
        return

    # Inicia servidor
    server = HTTPServer(('127.0.0.1', LOCAL_PORT), RPCProxyHandler)
    print(f"\n[+] Proxy RPC iniciado em http://127.0.0.1:{LOCAL_PORT}")
    print("[+] Todas as chamadas serao roteadas via Tor")
    print(f"[+] Sessao Tor renova a cada {SESSION_MAX_AGE}s")
    print("\n[*] Pressione Ctrl+C para parar\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Parando proxy...")
        server.shutdown()


if __name__ == "__main__":
    main()
