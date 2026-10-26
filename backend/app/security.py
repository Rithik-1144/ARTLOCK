import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password):
    return generate_password_hash(password, method="scrypt")


def verify_password(password_hash, password):
    return check_password_hash(password_hash, password)


def encrypt_bytes(data, configured_key):
    key = base64.urlsafe_b64decode(configured_key)
    if len(key) != 32:
        raise ValueError("ARTLOCK_ENCRYPTION_KEY must decode to exactly 32 bytes.")
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, data, None)
    return ciphertext, base64.urlsafe_b64encode(nonce).decode()


def decrypt_bytes(ciphertext, encoded_nonce, configured_key):
    key = base64.urlsafe_b64decode(configured_key)
    if len(key) != 32:
        raise ValueError("ARTLOCK_ENCRYPTION_KEY must decode to exactly 32 bytes.")
    nonce = base64.urlsafe_b64decode(encoded_nonce)
    return AESGCM(key).decrypt(nonce, ciphertext, None)


def digest(data):
    return hashlib.sha256(data).hexdigest()
