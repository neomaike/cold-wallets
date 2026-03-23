#!/usr/bin/env python3
"""
CONTROLE DE REDE - Desliga/Liga internet para operacoes offline
Requer execucao como Administrador no Windows
"""

import subprocess
import time


def get_network_adapters():
    """Lista todos os adaptadores de rede ativos"""
    result = subprocess.run(
        ['netsh', 'interface', 'show', 'interface'],
        capture_output=True,
        text=True,
        encoding='cp850'
    )

    adapters = []
    for line in result.stdout.split('\n'):
        if 'Connected' in line or 'Conectado' in line:
            parts = line.split()
            if len(parts) >= 4:
                # Nome do adaptador e as ultimas palavras
                name = ' '.join(parts[3:])
                adapters.append(name)

    return adapters


def disable_network():
    """Desabilita todos os adaptadores de rede"""
    adapters = get_network_adapters()
    disabled = []

    for adapter in adapters:
        try:
            result = subprocess.run(
                ['netsh', 'interface', 'set', 'interface', adapter, 'disable'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                disabled.append(adapter)
                print(f"  [OK] Desabilitado: {adapter}")
            else:
                print(f"  [!] Falha ao desabilitar: {adapter}")
        except Exception as e:
            print(f"  [!] Erro em {adapter}: {e}")

    return disabled


def enable_network(adapters=None):
    """Habilita adaptadores de rede"""
    if adapters is None:
        # Tenta habilitar adaptadores comuns
        adapters = ['Ethernet', 'Wi-Fi', 'Ethernet 2', 'Conexao Local']

    enabled = []
    for adapter in adapters:
        try:
            result = subprocess.run(
                ['netsh', 'interface', 'set', 'interface', adapter, 'enable'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                enabled.append(adapter)
                print(f"  [OK] Habilitado: {adapter}")
        except Exception as e:
            print(f"  [!] Falha ao habilitar {adapter}: {e}")

    return enabled


def is_online():
    """Verifica se ha conexao com a internet (check adapters + rota de rede)"""
    if len(get_network_adapters()) == 0:
        return False
    # Verifica se existe rota de rede funcional (ping localhost gateway)
    try:
        result = subprocess.run(
            ['ping', '-n', '1', '-w', '500', '8.8.8.8'],
            capture_output=True, text=True, timeout=3
        )
        return result.returncode == 0
    except Exception:
        # Se ping falha, verifica apenas se ha adaptadores com IP configurado
        try:
            result = subprocess.run(
                ['netsh', 'interface', 'ip', 'show', 'config'],
                capture_output=True, text=True, encoding='cp850'
            )
            return 'Default Gateway' in result.stdout or 'Gateway' in result.stdout
        except Exception:
            return len(get_network_adapters()) > 0


def verify_offline():
    """Verifica se esta realmente offline"""
    time.sleep(1)
    if is_online():
        print("\n  [ALERTA] Ainda ha conexao! Tentando novamente...")
        disable_network()
        time.sleep(2)
        if is_online():
            return False
    return True


def require_admin():
    """Verifica se esta rodando como administrador"""
    try:
        result = subprocess.run(
            ['net', 'session'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


class OfflineContext:
    """Context manager para operacoes offline"""

    def __init__(self, auto_reconnect=True):
        self.auto_reconnect = auto_reconnect
        self.disabled_adapters = []
        self.was_online = False

    def __enter__(self):
        self.was_online = is_online()

        if self.was_online:
            print("\n[*] Desabilitando conexoes de rede...")
            self.disabled_adapters = disable_network()

            if not verify_offline():
                raise RuntimeError("Falha ao desconectar da internet!")

            print("[+] OFFLINE - Conexao desabilitada com sucesso\n")
        else:
            print("[*] Ja esta offline\n")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.auto_reconnect and self.disabled_adapters:
            print("\n[*] Reconectando a internet...")
            enable_network(self.disabled_adapters)

            time.sleep(2)
            if is_online():
                print("[+] ONLINE - Conexao restaurada\n")
            else:
                print("[!] Reconexao pode levar alguns segundos...\n")

        return False


if __name__ == "__main__":
    print("\n=== TESTE DE CONTROLE DE REDE ===\n")

    if not require_admin():
        print("[ERRO] Execute como Administrador!")
        print("       Clique direito -> Executar como administrador")
        exit(1)

    print(f"Status atual: {'ONLINE' if is_online() else 'OFFLINE'}")

    print("\nAdaptadores ativos:")
    for a in get_network_adapters():
        print(f"  - {a}")

    print("\nTestando ciclo offline/online...")

    with OfflineContext(auto_reconnect=True):
        print(">>> EXECUTANDO OPERACAO OFFLINE <<<")
        print(f"    Verificando: {'OFFLINE' if not is_online() else 'AINDA ONLINE!'}")
        time.sleep(2)

    print(f"\nStatus final: {'ONLINE' if is_online() else 'OFFLINE'}")
