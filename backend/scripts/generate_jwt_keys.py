"""Generate a dev RSA keypair for RS256 JWT signing.

Usage: python backend/scripts/generate_jwt_keys.py [output_dir]
Output defaults to backend/keys/ (gitignored) -- never commit these files.
"""

import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "keys"
    out_dir.mkdir(parents=True, exist_ok=True)

    private_path = out_dir / "jwt_private.pem"
    public_path = out_dir / "jwt_public.pem"

    if private_path.exists() or public_path.exists():
        print(f"Keys already exist in {out_dir}, skipping generation.")
        return

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    private_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"Wrote {private_path} and {public_path}")


if __name__ == "__main__":
    main()
