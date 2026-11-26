"""Compare classification prompt versions on the labelled test set.

Usage:
    uv run python scripts/compare_prompts.py
    uv run python scripts/compare_prompts.py --rpm 8
    uv run python scripts/compare_prompts.py --no-cache
"""

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

from patentpath.config import get_settings
from patentpath.llm.classify import LABELS, accuracy, classify, find_leaks
from patentpath.llm.gateway import LLMUnavailable, build_gateway
from patentpath.llm.prompts import read_prompt, versions

TESTSET = Path("eval/prompt_testset.jsonl")
CACHE = Path("eval/cache/classify.json")
NOTES = Path("NOTES.md")
START = "<!-- prompts:start -->"
END = "<!-- prompts:end -->"


def load_testset() -> tuple[list[dict], int]:
    """Return usable examples and the number of TODO rows."""
    examples = []
    todo = 0

    for number, line in enumerate(TESTSET.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue

        row = json.loads(line)
        if row["label"] not in LABELS:
            raise SystemExit(f"{TESTSET} line {number}: label must be one of {LABELS}")

        if "TODO" in row["question"]:
            todo += 1
        else:
            examples.append({"n": number, **row})

    return examples, todo


def write_table(rows: list[dict], total: int) -> None:
    """Write or replace the prompt comparison table in NOTES.md."""
    table = [
        START,
        "",
        "| Prompt version | Correct | Accuracy | Invalid replies | Avg tokens in |",
        "|---|---|---|---|---|",
    ]

    for row in rows:
        table.append(
            f"| {row['version']} | {row['correct']}/{total} "
            f"| {row['accuracy']:.0%} | {row['invalid']} "
            f"| {row['tokens_in']} |"
        )

    table.extend(["", END])
    block = "\n".join(table)

    text = NOTES.read_text(encoding="utf-8") if NOTES.exists() else "# Notes\n"

    if START in text and END in text:
        before = text[: text.index(START)]
        after = text[text.index(END) + len(END) :]
        text = before + block + after
    else:
        text = text.rstrip() + "\n\n## D09 - Prompt versions compared\n\n" + block + "\n"

    NOTES.write_text(text, encoding="utf-8")


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    examples, todo = load_testset()

    if todo:
        print(f"Note: {todo} TODO rows skipped; {len(examples)} usable examples.")

    if len(examples) < 5:
        print("Write at least 5 real examples in eval/prompt_testset.jsonl first.")
        return 1

    prompt_versions = versions(settings.prompts_dir, "classify")
    if not prompt_versions:
        print("No classify_v*.md prompt files found.")
        return 1

    gateway = build_gateway(settings)

    cache = {}
    if not args.no_cache and CACHE.exists():
        cache = json.loads(CACHE.read_text(encoding="utf-8"))

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    asked = 0

    try:
        for version in prompt_versions:
            prompt = read_prompt(settings.prompts_dir, version)

            if "TODO" in prompt:
                print(f"Skipped {version}: prompt still contains TODO.")
                continue

            leaks = find_leaks(prompt, [e["question"] for e in examples])
            for leak in leaks:
                print(f"LEAK in {version}: test question appears in prompt: {leak!r}")

            results = []
            print(f"\nEvaluating {version} ({len(examples)} questions)...")

            for example in examples:
                key = hashlib.sha256(f"{prompt}\n\n{example['question']}".encode()).hexdigest()

                if key not in cache:
                    got, reply = await classify(gateway, prompt, version, example["question"])

                    cache[key] = {
                        "got": got,
                        "reply": reply.text[:120],
                        "tokens_in": reply.tokens_in,
                    }

                    CACHE.write_text(
                        json.dumps(cache, ensure_ascii=False, indent=1),
                        encoding="utf-8",
                    )
                    asked += 1
                    await asyncio.sleep(60 / args.rpm)

                result = {**example, **cache[key]}
                results.append(result)

                print(
                    f"  {example['n']:02}/{len(examples)}: "
                    f"expected={example['label']} got={result['got']}"
                )

            for miss in (r for r in results if r["got"] != r["label"]):
                print(
                    f"{version} missed line {miss['n']}: "
                    f"wanted {miss['label']}, got {miss['got']} "
                    f"(reply {miss['reply'][:40]!r}) "
                    f"{miss['question'][:60]!r}"
                )

            rows.append(
                {
                    "version": version,
                    "correct": sum(r["got"] == r["label"] for r in results),
                    "accuracy": accuracy(results),
                    "invalid": sum(r["got"] == "invalid" for r in results),
                    "tokens_in": round(sum(r["tokens_in"] for r in results) / len(results)),
                }
            )

    except LLMUnavailable as error:
        print(f"\nStopped: no model can answer ({str(error)[:160]})")
        print("Wait for the rate limit to reset, then rerun. Cached answers will be reused.")
        return 1

    if not rows:
        print("No prompt version could be evaluated.")
        return 1

    write_table(rows, len(examples))

    print("\nComparison:")
    for row in rows:
        print(f"{row['version']:<14} {row['correct']:>2}/{len(examples)}  {row['accuracy']:.0%}")

    print(
        f"\nModel calls made now: {asked} (remaining answers came from cache) -> table in NOTES.md"
    )
    return 0


def main() -> int:
    sys.stdout.reconfigure(errors="replace")

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--rpm",
        type=float,
        default=8,
        help="model calls per minute (default 8)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="ignore cached answers and ask the model again",
    )
    args = parser.parse_args()

    if args.rpm <= 0:
        parser.error("--rpm must be greater than zero")

    if not TESTSET.exists():
        print(f"{TESTSET} not found")
        return 1

    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
