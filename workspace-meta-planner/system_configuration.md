# System Configuration — OpenClaw Infrastructure

## Platform
- OS: WSL2 Ubuntu on Windows 11
- User: robotin
- Home: /home/robotin
- OpenClaw version: v2026.3.13

## LiteLLM Proxy
- Endpoint: http://127.0.0.1:4000
- API Key: sk-litellm-local
- Format: OpenAI-compatible (all models use /v1/chat/completions)
- Auth: Bearer token in Authorization header
- Status: Running as systemd user service (litellm.service)

## Available Models (via LiteLLM)

| Model ID | Provider | Notes |
|----------|----------|-------|
| claude-sonnet46 | Anthropic | Primary for agents. $3/$15 per MTok |
| claude-sonnet46-thinking | Anthropic | Extended thinking variant |
| claude-opus46 | Anthropic | Premium. $15/$75 per MTok |
| claude-opus46-thinking | Anthropic | Extended thinking variant |
| gpt52-none | OpenAI | GPT-5.2 standard. $2/$10 per MTok |
| gpt52-medium | OpenAI | Medium reasoning |
| gpt52-thinking | OpenAI | Full reasoning |
| gpt52-xhigh | OpenAI | Max reasoning |
| gpt53-codex | OpenAI | GPT-5.3 code-optimized |
| gpt5-mini | OpenAI | Budget option |
| gpt41 | OpenAI | GPT-4.1 legacy |
| gemini31pro-none | Google | Gemini 3.1 Pro standard |
| gemini31pro-medium | Google | Medium reasoning |
| gemini31pro-thinking | Google | Full reasoning |
| gemini31lite-none | Google | Gemini 3.1 Lite (budget) |
| gemini31lite-low/medium/high | Google | Various reasoning levels |
| minimax-m27 | OpenRouter | MiniMax M2.7. $0.30/$1.20 per MTok (CEO primary) |
| step35-flash | OpenRouter | Step 3.5 Flash. $0.10/$0.30 per MTok (budget) |
| kimi-k25 | OpenRouter | Kimi K2.5 |

## Technical Constraints (MUST follow)
- **TL-01:** Python `requests` library FAILS in WSL for long calls (>30s). ALWAYS use `curl` via `subprocess`.
- **TL-04:** Never use `sessions_spawn` to write files. Use direct file I/O.
- **TL-05:** subprocess timeout MUST be > curl --max-time (add buffer from planner_config.json).
- **TL-09:** Always `mkdir -p` before writing any file.
- **TL-10:** ALL file paths must be absolute.

## Workspace Layout
- OpenClaw config: ~/.openclaw/
- CEO workspace: ~/.openclaw/workspace/
- Declassified pipeline: ~/.openclaw/workspace-declassified/
- Meta-planner: ~/.openclaw/workspace-meta-planner/
- Shared scripts: ~/.openclaw/shared/scripts/
- Git: Single unified repo (openclaw-config on GitHub)

## Spawn Pattern
All agents use the same pattern:
1. Build payload JSON (model, max_tokens, messages)
2. Write to tempfile (ensure_ascii=True)
3. Call `curl -s --max-time N -H "Authorization: Bearer sk-litellm-local" --data-binary @tempfile http://127.0.0.1:4000/v1/chat/completions`
4. Parse JSON response: choices[0].message.content
5. Extract structured output, validate against schema
6. Write artifact, update manifest

## Cost Tracking
- PostgreSQL spend tracking active via LiteLLM
- Dashboard: http://127.0.0.1:4000/ui/ (localhost only, no auth)
- Per-run cost tracked in manifest.json

## Image Generation
- DALL-E 3: $0.04/image (used by Declassified pipeline for POI portraits)
- Available via LiteLLM proxy
