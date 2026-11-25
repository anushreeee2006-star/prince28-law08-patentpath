from __future__ import annotations

import sys
import time

import httpx

from patentpath.config import Settings


def ping(
    name: str,
    base_url: str,
    api_key: str,
    model: str,
    timeout: float,
) -> bool:
    if not api_key:
        print(f"{name:<6} FAILED  API key is missing in .env")
        return False

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
        "temperature": 0,
        "max_tokens": 64,
    }

    started = time.perf_counter()

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()

        elapsed_ms = round((time.perf_counter() - started) * 1000)
        answer = data["choices"][0]["message"]["content"].strip()
        usage = data.get("usage") or {}
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)

        print(
            f"{name:<6} OK      {model} said "
            f"'{answer}' in {elapsed_ms} ms, "
            f"tokens in={tokens_in} out={tokens_out}"
        )
        return True

    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        if isinstance(exc, httpx.HTTPStatusError):
            detail = exc.response.text[:500].replace(api_key, "[REDACTED]")
            print(f"{name:<6} FAILED  HTTP {exc.response.status_code}: {detail}")
        else:
            print(f"{name:<6} FAILED  {type(exc).__name__}: {exc}")
        return False


def main() -> None:
    settings = Settings()

    results = [
        ping(
            "gemini",
            settings.llm_primary_base_url,
            settings.gemini_api_key,
            settings.llm_primary_model,
            settings.llm_timeout_seconds,
        ),
        ping(
            "groq",
            settings.llm_fallback_base_url,
            settings.groq_api_key,
            settings.llm_fallback_model,
            settings.llm_timeout_seconds,
        ),
    ]

    if not all(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
