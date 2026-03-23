"""
Validacao de enderecos Bitcoin e Ethereum.
Previne envio para enderecos invalidos.

Uso:
    from address_validation import validate_eth_address, validate_btc_address

    valid, msg = validate_eth_address("0x...")
    if not valid:
        print(f"[ERRO] {msg}")
"""

import re


def validate_eth_address(address: str) -> tuple:
    """Valida endereco Ethereum (formato + checksum EIP-55)."""
    if not address:
        return False, "Endereco vazio"

    if not address.startswith("0x"):
        return False, "Endereco ETH deve comecar com 0x"

    if len(address) != 42:
        return False, f"Endereco ETH deve ter 42 caracteres (tem {len(address)})"

    if not re.match(r'^0x[0-9a-fA-F]{40}$', address):
        return False, "Endereco ETH contem caracteres invalidos"

    # Verifica checksum EIP-55 (se mixed case)
    addr_hex = address[2:]
    if addr_hex != addr_hex.lower() and addr_hex != addr_hex.upper():
        try:
            from eth_utils import is_checksum_address
            if not is_checksum_address(address):
                return False, "Checksum EIP-55 invalido"
        except ImportError:
            try:
                # EIP-55 usa Keccak-256 (nao SHA3-256)
                from eth_hash.auto import keccak
                addr_lower = addr_hex.lower()
                hash_hex = keccak(addr_lower.encode()).hex()
                for i, c in enumerate(addr_hex):
                    if c.isalpha():
                        expected_upper = int(hash_hex[i], 16) >= 8
                        if expected_upper and c.islower():
                            return False, "Checksum EIP-55 invalido"
                        if not expected_upper and c.isupper():
                            return False, "Checksum EIP-55 invalido"
            except ImportError:
                return False, ("Checksum mixed-case detectado mas "
                               "eth_utils/eth_hash nao instalado para validar. "
                               "Instale: pip install eth-utils")

    return True, "OK"


def validate_btc_address(address: str) -> tuple:
    """Valida endereco Bitcoin (base58check, bech32, bech32m)."""
    if not address:
        return False, "Endereco vazio"

    # Bech32/Bech32m (bc1...)
    if address.lower().startswith("bc1"):
        if len(address) < 14 or len(address) > 74:
            return False, f"Endereco bech32 com tamanho invalido ({len(address)})"
        bech32_chars = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
        hrp_data = address[4:]
        for c in hrp_data.lower():
            if c not in bech32_chars:
                return False, f"Caractere invalido em bech32: '{c}'"
        return True, "OK (bech32)"

    # Base58 - Legacy (1...) ou P2SH (3...)
    if address.startswith("1") or address.startswith("3"):
        if len(address) < 25 or len(address) > 34:
            return False, f"Endereco base58 com tamanho invalido ({len(address)})"
        base58_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        for c in address:
            if c not in base58_chars:
                return False, f"Caractere invalido em base58: '{c}'"
        return True, "OK (base58)"

    return False, "Endereco BTC deve comecar com 1, 3, ou bc1"
