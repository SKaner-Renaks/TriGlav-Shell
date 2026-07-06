import os
import base64
import hashlib
import secrets


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


def xor_base64_encrypt(plaintext: str, key: str) -> str:
    data = plaintext.encode('utf-8')
    key_bytes = hashlib.sha256(key.encode('utf-8')).digest()
    encrypted = _xor_bytes(data, key_bytes)
    return base64.b64encode(encrypted).decode('ascii')


def xor_base64_decrypt(ciphertext: str, key: str) -> str:
    data = base64.b64decode(ciphertext)
    key_bytes = hashlib.sha256(key.encode('utf-8')).digest()
    decrypted = _xor_bytes(data, key_bytes)
    return decrypted.decode('utf-8')


METHODS = {
    'xor_base64': (xor_base64_encrypt, xor_base64_decrypt),
}


def encrypt(data: str, method: str, key: str) -> str:
    if method not in METHODS:
        raise NotImplementedError(f'Method "{method}" not implemented. Available: {list(METHODS.keys())}')
    encrypt_fn, _ = METHODS[method]
    return encrypt_fn(data, key)


def decrypt(data: str, method: str, key: str) -> str:
    if method not in METHODS:
        raise NotImplementedError(f'Method "{method}" not implemented. Available: {list(METHODS.keys())}')
    _, decrypt_fn = METHODS[method]
    return decrypt_fn(data, key)


def save_env(filepath: str, data: dict, method: str, key: str):
    lines = []
    for k, v in data.items():
        encrypted = encrypt(str(v), method, key)
        lines.append(f'{k}={encrypted}')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def load_env(filepath: str, method: str, key: str) -> dict:
    if not os.path.exists(filepath):
        return {}
    result = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                result[k.strip()] = decrypt(v.strip(), method, key)
    return result


def generate_key() -> str:
    return secrets.token_hex(32)
