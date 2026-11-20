"""Smoke-test the live PatentPath API."""

import argparse
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test PatentPath API.")
    parser.add_argument("base_url", help="Base URL of the API")
    parser.add_argument("--expected-sha", help="Expected Git commit SHA")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    try:
        with httpx.Client(base_url=base_url, timeout=20.0) as client:
            health = client.get("/health")
            health.raise_for_status()
            health_data = health.json()

            assert health_data.get("status") == "ok", health_data
            actual_sha = health_data.get("git_sha")

            if args.expected_sha:
                assert actual_sha == args.expected_sha, (
                    f"Expected SHA {args.expected_sha}, got {actual_sha}"
                )

            print(f"ok /health -> {health.status_code}, version {actual_sha}")

            ready = client.get("/ready")
            ready.raise_for_status()
            ready_data = ready.json()

            assert ready_data.get("status") == "ready", ready_data
            assert ready_data.get("checks", {}).get("database") is True, ready_data

            print(f"ok /ready -> {ready.status_code} {ready_data}")

            documents = client.get("/v1/documents", params={"limit": 1})
            documents.raise_for_status()
            documents_data = documents.json()

            assert isinstance(documents_data.get("items"), list), documents_data

            print(f"ok /v1/documents?limit=1 -> {documents.status_code}")

        print("Smoke test passed")
        return 0

    except (httpx.HTTPError, AssertionError, ValueError) as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
