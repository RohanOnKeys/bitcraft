"""Bitcoin address encoding for synthetic wallets.

Produces correctly formatted mainnet addresses (valid checksums) from random
key hashes: base58check for P2PKH (1...) and P2SH (3...), bech32 for P2WPKH
(bc1q...), bech32m for P2TR (bc1p...). The keys are random bytes, so no
address belongs to anyone.
"""

from __future__ import annotations

import hashlib
import random

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BECH32 = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32M_CONST = 0x2BC830A3

SCRIPT_TYPES = ("p2pkh", "p2sh", "p2wpkh", "p2tr")


def _base58check(version: int, payload: bytes) -> str:
    raw = bytes([version]) + payload
    checksum = hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
    num = int.from_bytes(raw + checksum, "big")
    out = ""
    while num:
        num, rem = divmod(num, 58)
        out = _B58[rem] + out
    pad = len(raw + checksum) - len((raw + checksum).lstrip(b"\0"))
    return "1" * pad + out


def _polymod(values: list[int]) -> int:
    gen = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    chk = 1
    for v in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            chk ^= gen[i] if (top >> i) & 1 else 0
    return chk


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _convertbits(data: bytes, frombits: int, tobits: int) -> list[int]:
    acc = bits = 0
    out = []
    maxv = (1 << tobits) - 1
    for value in data:
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            out.append((acc >> bits) & maxv)
    if bits:
        out.append((acc << (tobits - bits)) & maxv)
    return out


def _segwit(version: int, program: bytes, hrp: str = "bc") -> str:
    data = [version] + _convertbits(program, 8, 5)
    const = 1 if version == 0 else _BECH32M_CONST
    polymod = _polymod(_hrp_expand(hrp) + data + [0] * 6) ^ const
    checksum = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(_BECH32[d] for d in data + checksum)


def make_address(script_type: str, rng: random.Random) -> str:
    """A fresh, well-formed mainnet address of the given script type."""
    if script_type == "p2pkh":
        return _base58check(0x00, rng.randbytes(20))
    if script_type == "p2sh":
        return _base58check(0x05, rng.randbytes(20))
    if script_type == "p2wpkh":
        return _segwit(0, rng.randbytes(20))
    if script_type == "p2tr":
        return _segwit(1, rng.randbytes(32))
    raise ValueError(f"unknown script type {script_type!r}")


def script_type_of(address: str) -> str:
    """Script type implied by an address's format."""
    if address.startswith("bc1q"):
        return "p2wpkh"
    if address.startswith("bc1p"):
        return "p2tr"
    if address.startswith("3"):
        return "p2sh"
    if address.startswith("1"):
        return "p2pkh"
    return "unknown"


def base58check_valid(address: str) -> bool:
    """True when a base58 address's checksum verifies."""
    num = 0
    for ch in address:
        if ch not in _B58:
            return False
        num = num * 58 + _B58.index(ch)
    pad = len(address) - len(address.lstrip("1"))
    raw = b"\0" * pad + num.to_bytes((num.bit_length() + 7) // 8, "big")
    payload, checksum = raw[:-4], raw[-4:]
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] == checksum


def bech32_valid(address: str) -> bool:
    """True when a bech32/bech32m segwit address's checksum verifies."""
    hrp, _, data_part = address.rpartition("1")
    if not hrp or any(c not in _BECH32 for c in data_part):
        return False
    data = [_BECH32.index(c) for c in data_part]
    const = _polymod(_hrp_expand(hrp) + data)
    return const == (1 if data[0] == 0 else _BECH32M_CONST)
