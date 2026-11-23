import asyncio
import csv

import httpx


async def main():
    with open("data/sources.csv", encoding="utf-8-sig", newline="") as f:
        rows = [
            r
            for r in csv.DictReader(line for line in f if line.strip() and not line.startswith("#"))
        ]

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=20,
        headers={"User-Agent": "PatentPath-Research/0.1 (academic project)"},
    ) as client:
        for row in rows:
            try:
                response = await client.head(row["url"])
                print(
                    response.status_code,
                    response.headers.get("content-type", "unknown"),
                    row["title"],
                )
            except httpx.HTTPError as exc:
                print("ERROR", type(exc).__name__, row["title"])


asyncio.run(main())
