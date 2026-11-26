"""Extract structured metadata from parsed PatentPath documents."""

import argparse
import asyncio

from patentpath.config import get_settings
from patentpath.db.llm_calls import make_recorder
from patentpath.db.session import AsyncSessionLocal
from patentpath.llm.extract import run
from patentpath.llm.gateway import build_gateway
from patentpath.llm.prompts import latest, read_prompt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--rpm", type=int, default=12)
    parser.add_argument("--chars", type=int, default=6000)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--schema", action="store_true")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    settings = get_settings()

    version = latest(settings.prompts_dir, "extract")
    prompt = read_prompt(settings.prompts_dir, version)
    gateway = build_gateway(
        settings,
        recorder=make_recorder(AsyncSessionLocal),
    )

    print(f"Prompt version: {version}")
    print(f"RPM: {args.rpm} | Character limit: {args.chars}")

    stats = await run(
        gateway,
        prompt,
        version,
        limit=args.limit,
        rpm=args.rpm,
        chars=args.chars,
        retry_failed=args.retry_failed,
        use_schema=args.schema,
    )

    print("\nMetadata extraction results")
    for key, value in stats.items():
        if key == "cost_inr":
            print(f"{key}: INR {value:.4f}")
        else:
            print(f"{key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
