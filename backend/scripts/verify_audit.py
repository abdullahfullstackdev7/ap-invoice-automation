"""Verify the audit log's hash chain end to end. Exits 1 if broken."""

import asyncio
import sys

from app.db.session import async_session_factory
from app.services.audit import verify_chain


async def main() -> int:
    async with async_session_factory() as session:
        result = await verify_chain(session)

    if result.valid:
        print(f"OK: audit chain valid ({result.checked} entries checked)")
        return 0

    print(f"FAILED: audit chain broken at entry {result.broken_at_id}")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
