"""Ask PatentPath a question through the chat API."""

import argparse
import json

import httpx


def main() -> None:
    """Send a question and print the response."""
    parser = argparse.ArgumentParser(description="Ask PatentPath a question.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="PatentPath API base URL",
    )
    parser.add_argument(
        "--message",
        help="Question to ask; if omitted, you will be prompted",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Receive the complete answer instead of streaming",
    )
    args = parser.parse_args()

    message = args.message or input("Ask PatentPath: ").strip()
    if not message:
        parser.error("A question is required.")

    url = f"{args.base_url.rstrip('/')}/v1/chat"
    payload = {"message": message, "stream": not args.no_stream}

    try:
        with httpx.Client(timeout=120.0) as client:
            if args.no_stream:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                print(data["answer"])
                print(f"\nModel: {data['summary']['provider']} / {data['summary']['model']}")
                return

            with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue

                    event = json.loads(line[6:])
                    if "text" in event:
                        print(event["text"], end="", flush=True)
                    elif "summary" in event:
                        print(
                            f"\n\nModel: {event['summary']['provider']} / "
                            f"{event['summary']['model']}"
                        )
                    elif "message" in event:
                        print(f"\nError: {event['message']}")

                print()

    except httpx.HTTPError as exc:
        print(f"Could not reach PatentPath API: {exc}")


if __name__ == "__main__":
    main()
