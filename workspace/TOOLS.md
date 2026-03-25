# TOOLS.md — CEO Local Notes

## System Management
- **LiteLLM proxy:** http://127.0.0.1:4000
- **LiteLLM dashboard:** http://127.0.0.1:4000/ui/ (spend tracking, logs, model status)
- **LiteLLM config:** ~/.config/litellm/config.yaml
- **LiteLLM restart:** `systemctl --user restart litellm.service`
- **Gateway restart:** `openclaw gateway restart`
- **Key sync:** `~/.openclaw/sync_keys.sh` (syncs .env → litellm.env)
- **Master .env:** `~/.openclaw/.env` (source of truth for all API keys)

## Git Repos
- `~/.openclaw/` → github.com/pr3t3l/openclaw-config (system config)
- `~/.openclaw/workspace-declassified/` → github.com/pr3t3l/declassified-cases-pipeline (pipeline)
- RULE: Never git add/commit/push inside workspace/ or workspace-declassified/ from this agent

## Models Available (via LiteLLM)
- **CEO primary:** minimax-m27 (MiniMax M2.7, $0.30/$1.20)
- GPT-5.2 variants: gpt52-none, gpt52-medium, gpt52-thinking, gpt52-xhigh
- GPT-5.3 Codex: gpt53-codex
- GPT-5 Mini: gpt5-mini, GPT-4.1: gpt41
- Gemini 3.1 Pro: gemini31pro-none/medium/thinking
- Gemini 3.1 Flash Lite: gemini31lite-none/low/medium/high
- Claude Sonnet 4.6: claude-sonnet46, claude-sonnet46-thinking
- Claude Opus 4.6: claude-opus46, claude-opus46-thinking
- Step 3.5 Flash: step35-flash ($0.10/$0.30)
- Kimi K2.5: kimi-k25 ($0.60/$3.00)

## Cost Monitoring
- Dashboard: http://127.0.0.1:4000/ui/ → Usage tab
- Spend logs API: `curl http://127.0.0.1:4000/spend/logs`
- Pipeline costs: manifest.json in each case export folder
- OpenAI dashboard: https://platform.openai.com/usage
- Anthropic dashboard: https://console.anthropic.com/settings/billing

## Environment
- WSL Ubuntu 24 on Windows (user: robotin, Windows: robot)
- Python 3.12, Node.js, Bun 1.3.11
- QMD 2.0.1 (memory search)
- Chromium headless (PDF rendering — pipeline only)
- Claude Code at ~/.openclaw/ scope
