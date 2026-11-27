"""Start and monitor PatentPath document ingestion."""

import argparse
import time

import httpx

from patentpath.config import get_settings


def show(progress: dict) -> str:
    """Format one progress update."""
    counts = progress.get("counts", {})
    line = (
        f"Status: {progress.get('status', 'unknown')} | "
        f"Queued: {counts.get('queued', 0)} | "
        f"Running: {counts.get('running', 0)} | "
        f"Done: {counts.get('done', 0)} | "
        f"Skipped: {counts.get('skipped', 0)} | "
        f"Failed: {counts.get('failed', 0)} | "
        f"Pages: {progress.get('pages', 0)} | "
        f"Elapsed: {progress.get('elapsed_seconds', 0):.1f}s"
    )
    return line


def watch(client: httpx.Client, job_id: str, every: float) -> int:
    """Poll a job until it finishes."""
    previous = None

    while True:
        response = client.get(f"/v1/ingest/{job_id}")

        if response.status_code != 200:
            print(f"Progress request failed: HTTP {response.status_code} {response.text}")
            return 1

        progress = response.json()
        current = show(progress)

        if current != previous:
            print(current)
            previous = current

        if progress.get("status") == "finished":
            failed = progress.get("dead_letter", [])
            if failed:
                print("\nDead-letter items:")
                for item in failed:
                    print(item)
            return 0

        time.sleep(every)


def main() -> int:
    """Parse arguments and start or monitor ingestion."""
    parser = argparse.ArgumentParser(description="Start and monitor PatentPath document ingestion.")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--source", default="")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--watch", metavar="JOB_ID")
    parser.add_argument("--every", type=float, default=3.0)
    args = parser.parse_args()

    if args.limit < 1 or args.every <= 0:
        parser.error("--limit must be positive and --every must be greater than zero")

    headers = {"X-Admin-Token": get_settings().admin_token}

    try:
        with httpx.Client(
            base_url=args.url.rstrip("/"),
            headers=headers,
            timeout=30.0,
        ) as client:
            if args.watch:
                return watch(client, args.watch, args.every)

            response = client.post(
                "/v1/ingest",
                json={
                    "limit": args.limit,
                    "source": args.source,
                    "retry_failed": args.retry_failed,
                },
            )

            if response.status_code not in (200, 202):
                print(f"Ingestion request failed: HTTP {response.status_code} {response.text}")
                return 1

            result = response.json()
            job_id = result.get("job_id")

            if not job_id:
                print(result.get("detail", "Nothing to ingest."))
                return 0

            print(
                f"HTTP {response.status_code} | Job: {job_id} | Queued: {result.get('queued', 0)}"
            )
            return watch(client, job_id, args.every)

    except httpx.TransportError as exc:
        print(f"Could not connect to the API. Is it running? {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
