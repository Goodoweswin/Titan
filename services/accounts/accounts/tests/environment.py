import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

key = Path("/tmp/titan-accounts-test-key.pem")
if not key.exists():
    key.write_bytes(
        rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    key.chmod(0o600)
os.environ.setdefault("ACCOUNTS_RSA_KEY_FILE", str(key))
os.environ.setdefault("ACCOUNTS_SECRET_KEY", "test-only-not-a-deployment-secret")
os.environ.setdefault("ACCOUNTS_SESSION_EPOCH", "test-epoch")
os.environ.setdefault("ACCOUNTS_ISSUER", "http://testserver")
os.environ.setdefault("ACCOUNTS_DEBUG", "1")
