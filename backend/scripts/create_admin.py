"""Bootstrap the first ADMIN account.

ADMIN and UNDERWRITER accounts can't be created through the public OTP
signup flow (see VerifyOtp's SELF_ASSIGNABLE_ROLES check) -- that's the
whole point of closing the self-assigned-role gap. This script is the one
out-of-band path to create the very first admin, run once by whoever
operates the deployment. Every admin after that can be created through
`POST /admin/users` by an existing admin.

Usage: python -m scripts.create_admin --phone +254712345678 --name "Jane Admin"
(run from the backend/ directory, or inside the backend container)
"""

import argparse
import asyncio

from app.core.db import AsyncSessionLocal
from app.modules.identity.domain.entities import InvalidPhoneNumber
from app.modules.identity.infrastructure.repository import SqlUserRepository


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phone", required=True, help="E.164-ish phone number, e.g. +254712345678")
    parser.add_argument("--name", required=True, help="Full name")
    args = parser.parse_args()

    async with AsyncSessionLocal() as session:
        repo = SqlUserRepository(session)
        existing = await repo.get_by_phone_any_status(args.phone)
        if existing is not None:
            print(f"{args.phone} is already registered (role={existing.role}, active={existing.is_active}). Not creating a duplicate.")
            return

        try:
            user = await repo.create(phone_number=args.phone, full_name=args.name, role="ADMIN")
        except InvalidPhoneNumber as exc:
            print(f"Invalid phone number: {exc}")
            return
        await session.commit()
        print(f"Created ADMIN {user.full_name} ({user.phone_number}), id={user.id}")
        print("They can now log in through the normal OTP flow -- no role picker will be shown, since the role is already set.")


if __name__ == "__main__":
    asyncio.run(main())
