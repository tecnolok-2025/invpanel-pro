from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
import base64

def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")

priv = ec.generate_private_key(ec.SECP256R1())
pem = priv.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
pub = priv.public_key().public_numbers()
pub_bytes = b"\x04" + pub.x.to_bytes(32, "big") + pub.y.to_bytes(32, "big")

print("VAPID_PUBLIC_KEY=", b64url(pub_bytes))
print("VAPID_PRIVATE_KEY_PEM_B64=", base64.b64encode(pem).decode("ascii"))
