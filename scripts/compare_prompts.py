"""Compare classification prompt versions on the labelled test set."""

import asyncio
import json
from pathlib import Path

from patentpath.config import get_settings
from patentpath.llm.classify import accuracy, classify
from patentpath.llm.gateway import build_gateway
from patentpath.llm.prompts import read_prompt, versions


async def main() -> None:
    """Evaluate each classification prompt and save the results."""
    settings = get_settings()
    testset_path = Path("eval/prompt_testset.jsonl")
    output_path = Path("eval/prompt_comparison.json")

    rows = [
        json.loads(line)
        for line in testset_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]

    prompt_versions = versions(settings.prompts_dir, "classify")
    if not prompt_versions:
        raise FileNotFoundError("No classify_v*.md prompt files found.")

    gateway = build_gateway(settings)
    results = []

    for version in prompt_versions:
        prompt = read_prompt(settings.prompts_dir, version)
        version_rows = []

        print(f"\nEvaluating {version} ({len(rows)} questions)...")

        for index, row in enumerate(rows, start=1):
            got, result = await classify(
                gateway,
                prompt,
                version,
                row["question"],
            )

            item = {
                "version": version,
                "question": row["question"],
                "label": row["label"],
                "got": got,
                "correct": got == row["label"],
                "provider": result.provider,
                "tokens_in": result.tokens_in,
                "tokens_out": result.tokens_out,
                "cost_inr": result.cost_inr,
            }
            version_rows.append(item)
            results.append(item)

            print(f"  {index:02}/{len(rows)}: expected={row['label']} got={got}")

        score = accuracy(version_rows)
        correct_count = sum(item["correct"] for item in version_rows)
        print(f"{version} accuracy: {score:.1%} ({correct_count}/{len(version_rows)})")

    output_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\nDetailed results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
