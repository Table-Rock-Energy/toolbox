#!/usr/bin/env python3
"""Create the initial admin user in PostgreSQL.

Usage: cd backend && python3 -m scripts.create_admin
"""

from __future__ import annotations

import asyncio
import sys
from getpass import getpass

from sqlalchemy import select


async def main():
    from app.core.database import async_session_maker
    from app.core.security import get_password_hash
    from app.models.db_models import User

    password = getpass("Enter admin password: ")
    if len(password) < 8:
        print("Error: Password must be at least 8 characters")
        sys.exit(1)

    confirm = getpass("Confirm password: ")
    if password != confirm:
        print("Error: Passwords do not match")
        sys.exit(1)

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.email == "james@tablerocktx.com")
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.password_hash = get_password_hash(password)
            existing.role = "admin"
            existing.is_admin = True
            existing.is_active = True
            await session.commit()
            print("Admin user password updated: james@tablerocktx.com")
        else:
            user = User(
                email="james@tablerocktx.com",
                password_hash=get_password_hash(password),
                role="admin",
                is_admin=True,
                is_active=True,
                display_name="James",
            )
            session.add(user)
            await session.commit()
            print("Admin user created: james@tablerocktx.com")


if __name__ == "__main__":
    asyncio.run(main())
