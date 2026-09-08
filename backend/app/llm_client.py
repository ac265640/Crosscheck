"""
Unified LLM client — wraps Groq.
Uses free-text mode so models return the exact JSON schema the prompt requests
(json_object mode forces a dict wrapper that breaks array responses).
"""
from __future__ import annotations

import re
import time
from typing import Optional

from groq import Groq

from backend.app.config import GROQ_API_KEY, GROQ_MODEL

_client: Optional[Groq] = None
_last_api_key: Optional[str] = None


def _get_client() -> Groq:
    global _client, _last_api_key
    # Re-initialise if the API key changed (e.g. rotated)
    if _client is None or _last_api_key != GROQ_API_KEY:
        _client = Groq(api_key=GROQ_API_KEY)
        _last_api_key = GROQ_API_KEY
    return _client


def _extract_json(text: str) -> str:
    """
    Extract the first JSON object or array from a free-text / fenced response.
    Priority: fenced ```json block → first [ array → first { object.
    """
    text = text.strip()

    # 1. Markdown fence  ```json ... ```
    m = re.search(r"```(?:json)?\s*([\[\{].*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # 2. Bare JSON — find first [ or { and balance brackets
    for start_ch, end_ch in [('[', ']'), ('{', '}')]:
        idx = text.find(start_ch)
        if idx == -1:
            continue
        depth = 0
        for i, ch in enumerate(text[idx:], start=idx):
            if ch == start_ch:
                depth += 1
            elif ch == end_ch:
                depth -= 1
                if depth == 0:
                    return text[idx:i + 1]

    return text  # fallback: return as-is and let caller handle parse error


def call_llm(
    system_prompt: str,
    user_message: str,
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_retries: int = 3,
    max_tokens: int = 1500,  # cap output to reduce TPM usage
) -> str:
    """
    Call Groq LLM in free-text mode. Returns extracted JSON text.
    Retries on rate limit (429) with exponential back-off.
    Raises on other errors.
    """
    client = _get_client()
    active_model = model or GROQ_MODEL
    last_error: Optional[str] = None

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=active_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            raw = response.choices[0].message.content or ""
            return _extract_json(raw)

        except Exception as e:
            last_error = str(e)
            err_lower = last_error.lower()

            if "429" in last_error or "rate_limit" in err_lower or "too many" in err_lower:
                wait = 4 * (attempt + 1)
                time.sleep(wait)
                continue

            raise  # Non-rate-limit errors bubble up immediately

    raise RuntimeError(f"LLM call failed after {max_retries} attempts: {last_error}")
