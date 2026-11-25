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
        default="http://127.0.0.1:8000",
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
    current_event = ""

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
                    if line.startswith("event: "):
                        current_event = line[7:].strip()
                        continue

                    if not line.startswith("data: "):
                        continue

                    event = json.loads(line[6:])

                    if current_event == "error":
                        print(f"\nError: {event.get('detail', 'Streaming failed')}")
                        continue

                    if current_event == "done":
                        total_time = time.perf_counter() - started

                        print("\n\n--- Usage ---")
                        print(f"Provider: {event.get('provider', 'unknown')}")
                        print(f"Model: {event.get('model', 'unknown')}")
                        print(f"Input tokens: {event.get('tokens_in', 0)}")
                        print(f"Output tokens: {event.get('tokens_out', 0)}")
                        print(f"Cost (INR): {event.get('cost_inr', 0)}")
                        print(f"Attempts: {event.get('attempts', 0)}")
                        print(f"Fallback used: {event.get('fallback_used', False)}")

                        if first_word_time is not None:
                            print(f"First-word latency: {first_word_time:.3f} sec")

                        print(f"Total time: {total_time:.3f} sec")
                        continue

                    if "delta" in event:
                        text = event["delta"]

                        if first_word_time is None and text.strip():
                            first_word_time = time.perf_counter() - started

                        print(text, end="", flush=True)

                    current_event = ""

                print()

    except httpx.HTTPError as exc:
        print(f"Could not reach PatentPath API: {exc}")


if __name__ == "__main__":
    main()
