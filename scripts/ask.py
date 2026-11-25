"""Ask PatentPath a question through the chat API."""

import argparse
import json
import time

import httpx


def main() -> None:
    """Send a question and print the response."""
    parser = argparse.ArgumentParser(description="Ask PatentPath a question.")
    parser.add_argument(
        "message",
        nargs="*",
        help="Question to ask PatentPath",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="PatentPath API base URL",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Return the complete response as JSON",
    )
    args = parser.parse_args()

    message = " ".join(args.message).strip()
    if not message:
        message = input("Ask PatentPath: ").strip()

    if not message:
        parser.error("A question is required.")

    url = f"{args.url.rstrip('/')}/v1/chat"
    payload = {"message": message, "stream": not args.json}

    started = time.perf_counter()
    first_word_time = None

    try:
        with httpx.Client(timeout=120.0) as client:
            if args.json:
                response = client.post(url, json=payload)
                response.raise_for_status()
                print(json.dumps(response.json(), indent=2, ensure_ascii=False))
                return

            with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()

                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue

                    event = json.loads(line[6:])

                    if "text" in event:
                        if first_word_time is None and event["text"].strip():
                            first_word_time = time.perf_counter() - started

                        print(event["text"], end="", flush=True)

                    elif "summary" in event:
                        summary = event["summary"]
                        total_time = time.perf_counter() - started

                        print("\n\n--- Usage ---")
                        print(f"Provider: {summary.get('provider', 'unknown')}")
                        print(f"Model: {summary.get('model', 'unknown')}")
                        print(f"Input tokens: {summary.get('tokens_in', 0)}")
                        print(f"Output tokens: {summary.get('tokens_out', 0)}")
                        print(f"Cost (INR): {summary.get('cost_inr', 0)}")
                        print(f"Fallback used: {summary.get('fallback_used', False)}")

                        if first_word_time is not None:
                            print(f"First-word latency: {first_word_time:.3f} sec")

                        print(f"Total time: {total_time:.3f} sec")

                    elif "message" in event:
                        print(f"\nError: {event['message']}")

                print()

    except httpx.HTTPError as exc:
        print(f"Could not reach PatentPath API: {exc}")


if __name__ == "__main__":
    main()
