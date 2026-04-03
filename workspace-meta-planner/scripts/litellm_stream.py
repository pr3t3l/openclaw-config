#!/usr/bin/env python3
"""
litellm_stream.py — Streaming LLM calls via LiteLLM proxy.

All scripts use this instead of non-streaming curl to avoid
Anthropic API disconnects on long generations (L-33).

Uses curl with stream:true and parses SSE chunks.
Never uses Python requests (TL-01).
"""

import json
import os
import subprocess
import tempfile


def call_litellm_stream(model, system_prompt, user_prompt, proxy_url, api_key="",
                         max_tokens=8192, curl_max_time=300, subprocess_buffer=50):
    """Call LiteLLM proxy with streaming enabled. Returns (content, usage_dict).

    Uses curl via subprocess (TL-01: never use Python requests in WSL).
    Parses SSE chunks to accumulate the full response.

    Returns:
        tuple: (content_str, {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int})

    Raises:
        Exception: on curl failure, empty response, or LiteLLM error
    """
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    payload_json = json.dumps(payload, ensure_ascii=True)

    with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
        f.write(payload_json.encode("utf-8"))
        tmp_path = f.name

    subprocess_timeout = curl_max_time + subprocess_buffer

    try:
        cmd = [
            "curl", "-s", "-S", "--max-time", str(curl_max_time),
            "-H", "Content-Type: application/json",
        ]
        if api_key:
            cmd.extend(["-H", f"Authorization: Bearer {api_key}"])
        cmd.extend(["--data-binary", f"@{tmp_path}", f"{proxy_url}/v1/chat/completions"])

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=subprocess_timeout
        )

        if result.returncode != 0:
            raise Exception(f"curl failed (rc={result.returncode}): {result.stderr[:300]}")

        raw_output = result.stdout.strip()
        if not raw_output:
            raise Exception(f"Empty response from LiteLLM. stderr: {result.stderr[:300]}")

        # Check if response is a non-streaming error (JSON object)
        if raw_output.startswith("{"):
            response = json.loads(raw_output)
            if "error" in response:
                raise Exception(f"LiteLLM error: {response['error']}")

        # Parse SSE chunks
        content_parts = []
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        for line in raw_output.split("\n"):
            line = line.strip()
            if not line or line == "data: [DONE]":
                continue
            if not line.startswith("data: "):
                continue

            try:
                chunk = json.loads(line[6:])  # strip "data: " prefix
            except json.JSONDecodeError:
                continue

            # Extract content from delta
            choices = chunk.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    content_parts.append(content)

            # Extract usage from final chunk (LiteLLM includes it with stream_options)
            if "usage" in chunk:
                u = chunk["usage"]
                usage["prompt_tokens"] = u.get("prompt_tokens", usage["prompt_tokens"])
                usage["completion_tokens"] = u.get("completion_tokens", usage["completion_tokens"])
                usage["total_tokens"] = u.get("total_tokens", usage["total_tokens"])

        full_content = "".join(content_parts)

        if not full_content:
            raise Exception("Streaming returned no content. Raw output (first 500): " + raw_output[:500])

        return full_content, usage

    finally:
        os.unlink(tmp_path)
