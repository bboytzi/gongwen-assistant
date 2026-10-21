import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from core.config import settings


def _get_key() -> bytes:
    """Convert hex string to 32-byte key."""
    return bytes.fromhex(settings.ENCRYPTION_KEY)


def encrypt_api_key(plaintext: str) -> str:
    """Encrypt an API key using AES-256-GCM. Returns hex string with nonce prepended."""
    if not plaintext:
        return ""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return (nonce + ciphertext).hex()


def decrypt_api_key(encrypted: str) -> str:
    """Decrypt an AES-256-GCM encrypted API key."""
    if not encrypted:
        return ""
    key = _get_key()
    data = bytes.fromhex(encrypted)
    nonce = data[:12]
    ciphertext = data[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
