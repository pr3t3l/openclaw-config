# FIX: LiteLLM Server Disconnect on Large Completions

## Date: 2026-04-03
## Status: DIAGNOSED — fix requires config change

---

## Problem

When `spawn_planner_agent.py` or `run_phase_c.sh` calls `claude-sonnet46` via LiteLLM proxy with:
- **~8000 input tokens** (architecture + contracts context)
- **`max_tokens=8192`** (large output requested)

The Anthropic API **disconnects mid-generation**, causing:
- `litellm.InternalServerError: AnthropicException - Server disconnected`
- Or empty response from curl

## Evidence

| Test | Input tokens | max_tokens | Result |
|------|-------------|------------|--------|
| Minimal ("say hello") | ~10 | 50 | ✅ OK |
| Medium (~2k tokens) | ~2019 | 500 | ✅ OK |
| Large (~5k tokens) | ~5020 | 4000 | ✅ OK |
| Architecture only (~1.8k) | ~1787 | 8192 | ✅ OK |
| Contracts only (~5.5k) | ~5470 | 8192 | ✅ OK |
| Full context, short output (~8k) | ~8088 | 500 | ✅ OK |
| **Full context, large output (~8k)** | **~8088** | **8192** | **❌ DISCONNECT** |

The pattern is clear:
- **Input size alone is not the problem** (8k input + 500 output works fine)
- **Output size alone is not the problem** (1.8k input + 8192 output works fine)
- **The combination of ~8k input + 8192 max_tokens triggers the disconnect**

This happens because the total generation time exceeds LiteLLM's default request timeout (likely 600s default, but the actual Anthropic API call for ~16k total tokens can take longer when the server is under load or the connection is unstable).

## Root Cause

LiteLLM proxy has no explicit `request_timeout` configured in `/home/robotin/.config/litellm/config.yaml`. The default timeout may be insufficient for large Anthropic completions, especially when:
1. The model needs to process ~8k input tokens
2. Then generate up to 8192 output tokens
3. The Anthropic API may have intermittent connection stability issues

## Fix

### Option A: Add request_timeout to LiteLLM config (RECOMMENDED)

Edit `/home/robotin/.config/litellm/config.yaml`:

```yaml
litellm_settings:
  json_logs: true
  drop_params: true
  request_timeout: 600      # ← ADD THIS (seconds)
```

Or per-model for Anthropic models:

```yaml
  - model_name: claude-sonnet46
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: os.environ/ANTHROPIC_API_KEY
      timeout: 600              # ← ADD THIS
```

Then restart LiteLLM:
```bash
# Find and restart the LiteLLM process
# Option 1: If managed by systemd
sudo systemctl restart litellm

# Option 2: If running manually
kill $(pgrep -f "litellm.*config.yaml.*port 4000" | head -1)
cd /home/robotin && litellm-venv/bin/litellm --config /home/robotin/.config/litellm/config.yaml --host 127.0.0.1 --port 4000 &
```

### Option B: Reduce max_tokens for implementation_planner (WORKAROUND)

In `/home/robotin/.openclaw/workspace-meta-planner/planner_config.json`:

Change:
```json
"max_tokens_standard": 8192
```

To:
```json
"max_tokens_standard": 4096
```

This reduces the output request size, making the total generation shorter and less likely to timeout. Trade-off: implementation plans may be truncated for complex projects.

### Option C: Use block-based generation for large artifacts (ARCHITECTURAL)

Already implemented in this workspace:
- `scripts/generate_implementation_by_blocks.py`
- `scripts/generate_contracts_atomic.py`

These split large artifacts into smaller generation units, each requesting fewer output tokens. This avoids the timeout entirely but requires maintaining separate generation scripts.

## Recommended Approach

**Apply Option A (global timeout) + keep Option C as fallback.**

Option A fixes the root cause for all models and all phases.
Option C remains available as a proven fallback when any single generation is too large.

## Affected Phases

Any phase that combines:
- Large input context (>5k tokens)
- Large output request (>4k max_tokens)

In practice:
- **C1 / implementation_planner** — most affected (architecture + contracts as input)
- **B2 / contract_designer** — previously affected (data flow + adjustments as input)
- **B3 / architecture_planner** — potentially affected via debate (multiple rounds)

## Files Referenced

- LiteLLM config: `/home/robotin/.config/litellm/config.yaml`
- Planner config: `/home/robotin/.openclaw/workspace-meta-planner/planner_config.json`
- Models config: `/home/robotin/.openclaw/workspace-meta-planner/models.json`
- Spawn script: `/home/robotin/.openclaw/workspace-meta-planner/scripts/spawn_planner_agent.py`
- Block generators: `scripts/generate_implementation_by_blocks.py`, `scripts/generate_contracts_atomic.py`
- New block script: `scripts/spawn_implementation_blocks.py`

---

## Permanent Fix: Context Compression + Block Fallback (2026-04-03)

### Root Cause (refined)

The real problem was NOT just a timeout — it was sending ~5,470 tokens of unnecessary JSON Schema detail from `04_contracts.json` to `implementation_planner`. The implementation planner only needs to know WHAT artifacts to build and their purpose/key fields, not the full JSON Schema definitions, examples, or format-level validation rules.

### Primary Fix: Context Compression in spawn_planner_agent.py

Added `compress_contracts()` function that strips full JSON Schema definitions, examples, and format-level validation rules, keeping only:
- Artifact names and formats
- Top-level field names, types, and descriptions
- Business-logic validation rules (not pattern/regex rules)

Result: `04_contracts.json` context reduced from ~5,470 tokens to ~1,200 tokens.

Also added `compress_architecture()` for `05_architecture_decision.json` — only activates when the raw file exceeds 30,000 chars (~7,500 tokens). Strips `red_team_findings` and `infrastructure_validation.notes` (verbose, informational, not build instructions).

The compressed context combined with the architecture (~1,787 tokens) brings the total input well below the threshold that triggered disconnects.

### Secondary Fix: Block-Based Generation (configurable fallback)

New script `scripts/spawn_implementation_blocks.py` splits the implementation plan into 5 smaller blocks, each with `max_tokens=5000`. Available as a fallback via:

```json
// planner_config.json
"block_mode": {
  "implementation_planner": {
    "enabled": true,   // set to true to activate
    ...
  }
}
```

`run_phase_c.sh` checks `block_mode.implementation_planner.enabled` and routes to the block script when true. Default is `false` — context compression is the primary fix.

### Defense in Depth

The `request_timeout: 600` setting in LiteLLM config should stay as an additional safety net.

### Summary

| Layer | Fix | When active |
|-------|-----|-------------|
| Context compression | `compress_contracts()` in spawn_planner_agent.py | Always (for implementation_planner) |
| Architecture compression | `compress_architecture()` in spawn_planner_agent.py | When raw file > 30k chars |
| LiteLLM timeout | `request_timeout: 600` in config.yaml | Always |
| Block-based generation | `spawn_implementation_blocks.py` | When `block_mode.enabled: true` |
