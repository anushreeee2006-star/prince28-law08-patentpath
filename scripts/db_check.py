import asyncio

from sqlalchemy import text

from patentpath.db.session import engine


async def main() -> None:
    async with engine.connect() as conn:
        database = await conn.scalar(text("SELECT current_database()"))
        version = await conn.scalar(text("SELECT version()"))

        print(f"Connected to database '{database}'")
        print(version)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
