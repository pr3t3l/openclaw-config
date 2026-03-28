"""Shared LLM caller via LiteLLM proxy. All marketing system LLM calls go through here."""

import json
import subprocess
import tempfile
import os

LITELLM_URL = "http://127.0.0.1:4000/v1/chat/completions"
LITELLM_KEY = "sk-litellm-local"


def call_llm(model: str, system_prompt: str, user_prompt: str,
             max_tokens: int = 8192, temperature: float = 0.3,
             timeout: int = 300) -> tuple[str, dict]:
    """Call LLM via LiteLLM proxy. Returns (text, usage_dict)."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f, ensure_ascii=False)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["curl", "-s", "-S", "--max-time", str(timeout),
             LITELLM_URL,
             "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {LITELLM_KEY}",
             "--data-binary", f"@{tmp_path}"],
            capture_output=True, text=True, timeout=timeout + 30
        )

        if result.returncode != 0:
            raise Exception(f"curl failed (rc={result.returncode}): {result.stderr[:300]}")

        resp = json.loads(result.stdout)

        if "error" in resp:
            raise Exception(f"LiteLLM error: {resp['error']}")

        text = resp["choices"][0]["message"]["content"]
        usage = resp.get("usage", {})

        return text, {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "model": model,
        }
    finally:
        os.unlink(tmp_path)


def extract_json_from_response(text: str) -> dict | list | None:
    """Extract JSON from LLM response (handles code fences)."""
    import re
    # Try fenced JSON block first
    match = re.search(r"```(?:json)?\s*\n([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try bare JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    return None
