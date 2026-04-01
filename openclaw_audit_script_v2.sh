#!/bin/bash
# ============================================
# OPENCLAW FULL SYSTEM AUDIT — v2.1
# Incorporates GPT + Gemini review (2 rounds)
# Run via Claude Code
# Outputs go to /tmp/ to avoid dirtying git
# DO NOT commit these files to git
# ============================================

REPORT="/tmp/openclaw_audit_report_$(date +%Y%m%d_%H%M%S).md"
SUMMARY="/tmp/openclaw_audit_summary_$(date +%Y%m%d_%H%M%S).json"

echo "# OpenClaw System Audit Report v2.1" > "$REPORT"
echo "## Generated: $(date -Iseconds)" >> "$REPORT"
echo "" >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 1: INFRASTRUCTURE
# ─────────────────────────────────────────
echo "## 1. Infrastructure" >> "$REPORT"

echo "### 1.1 WSL Config" >> "$REPORT"
echo '```' >> "$REPORT"
cat /etc/wsl.conf >> "$REPORT" 2>&1
echo '```' >> "$REPORT"

echo "### 1.2 systemd services" >> "$REPORT"
echo '```' >> "$REPORT"
systemctl is-active postgresql >> "$REPORT" 2>&1
systemctl is-active ssh >> "$REPORT" 2>&1
echo "--- user services (may not exist) ---" >> "$REPORT"
systemctl --user is-active openclaw-gateway >> "$REPORT" 2>&1 || echo "openclaw-gateway: not a user service" >> "$REPORT"
systemctl --user is-active litellm >> "$REPORT" 2>&1 || echo "litellm: not a user service" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 1.3 OpenClaw Version" >> "$REPORT"
echo '```' >> "$REPORT"
/home/robotin/.npm-global/bin/openclaw --version >> "$REPORT" 2>&1
echo '```' >> "$REPORT"

echo "### 1.4 start_all_services.sh (exists + line count)" >> "$REPORT"
echo '```' >> "$REPORT"
if [ -f ~/.openclaw/start_all_services.sh ]; then
    echo "EXISTS ($(wc -l < ~/.openclaw/start_all_services.sh) lines)" >> "$REPORT"
    cat ~/.openclaw/start_all_services.sh >> "$REPORT"
else
    echo "NOT FOUND" >> "$REPORT"
fi
echo '```' >> "$REPORT"

# NOTE: skipping sudo cat sudoers — can hang if password required
echo "### 1.5 Sudoers (existence check only)" >> "$REPORT"
echo '```' >> "$REPORT"
ls /etc/sudoers.d/robotin-services >> "$REPORT" 2>&1 && echo "EXISTS" >> "$REPORT" || echo "NOT FOUND" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 1.6 Windows Startup" >> "$REPORT"
echo '```' >> "$REPORT"
ls "/mnt/c/Users/robot/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/" >> "$REPORT" 2>&1
echo '```' >> "$REPORT"

echo "### 1.7 Logs directory" >> "$REPORT"
echo '```' >> "$REPORT"
ls ~/logs/ >> "$REPORT" 2>&1 || echo "~/logs/ not found" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 1.8 Tailscale" >> "$REPORT"
echo '```' >> "$REPORT"
tailscale status 2>/dev/null | head -5 >> "$REPORT" || echo "NOT RUNNING" >> "$REPORT"
tailscale serve status 2>/dev/null >> "$REPORT" || echo "serve not configured" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 1.9 tmux sessions" >> "$REPORT"
echo '```' >> "$REPORT"
tmux ls >> "$REPORT" 2>&1 || echo "No active tmux sessions" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 1.10 Service health (functional check)" >> "$REPORT"
echo '```' >> "$REPORT"
echo "OpenClaw Gateway:" >> "$REPORT"
curl -s -o /dev/null -w "HTTP %{http_code}" http://127.0.0.1:18789/ >> "$REPORT" 2>&1 || echo "NOT RESPONDING" >> "$REPORT"
echo "" >> "$REPORT"
echo "LiteLLM Proxy:" >> "$REPORT"
curl -s -o /dev/null -w "HTTP %{http_code}" -H "Authorization: Bearer sk-litellm-local" http://127.0.0.1:4000/health >> "$REPORT" 2>&1 || echo "NOT RESPONDING" >> "$REPORT"
echo "" >> "$REPORT"
echo "PostgreSQL:" >> "$REPORT"
pg_isready >> "$REPORT" 2>&1
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 2: OPENCLAW CONFIG
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 2. OpenClaw Configuration" >> "$REPORT"

echo "### 2.1 openclaw.json (full)" >> "$REPORT"
echo '```json' >> "$REPORT"
cat ~/.openclaw/openclaw.json | python3 -m json.tool >> "$REPORT" 2>&1
echo '```' >> "$REPORT"

echo "### 2.2 Workspace listing" >> "$REPORT"
echo '```' >> "$REPORT"
echo "--- Root (dirs + key files) ---" >> "$REPORT"
ls -la ~/.openclaw/ | grep -E "^d|workspace|\.json$|\.sh$|\.md$|\.env$" >> "$REPORT"
echo "" >> "$REPORT"
for ws in workspace workspace-declassified workspace-meta-planner; do
    echo "--- $ws/ ---" >> "$REPORT"
    ls ~/.openclaw/$ws/ >> "$REPORT" 2>&1 || echo "NOT FOUND" >> "$REPORT"
    echo "" >> "$REPORT"
done
echo "--- archived_workspaces/ ---" >> "$REPORT"
ls ~/.openclaw/archived_workspaces/ >> "$REPORT" 2>&1 || echo "none" >> "$REPORT"
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 3: AGENT CONFIGURATIONS
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 3. Agent Configurations" >> "$REPORT"

echo "### 3.1 CEO AGENTS.md" >> "$REPORT"
echo '```' >> "$REPORT"
cat ~/.openclaw/workspace/AGENTS.md >> "$REPORT" 2>&1
echo '```' >> "$REPORT"

echo "### 3.2 CEO SOUL.md (first 30 lines)" >> "$REPORT"
echo '```' >> "$REPORT"
head -30 ~/.openclaw/workspace/SOUL.md >> "$REPORT" 2>&1
echo '```' >> "$REPORT"

echo "### 3.3 CEO MEMORY.md (first 30 lines)" >> "$REPORT"
echo '```' >> "$REPORT"
head -30 ~/.openclaw/workspace/MEMORY.md >> "$REPORT" 2>&1
echo '```' >> "$REPORT"

echo "### 3.4 CEO HEARTBEAT.md + IDENTITY.md + cost_baseline.md" >> "$REPORT"
echo '```' >> "$REPORT"
echo "--- HEARTBEAT.md ---" >> "$REPORT"
cat ~/.openclaw/workspace/HEARTBEAT.md >> "$REPORT" 2>&1 || echo "NOT FOUND" >> "$REPORT"
echo "" >> "$REPORT"
echo "--- IDENTITY.md (first 15 lines) ---" >> "$REPORT"
head -15 ~/.openclaw/workspace/IDENTITY.md >> "$REPORT" 2>&1 || echo "NOT FOUND" >> "$REPORT"
echo "" >> "$REPORT"
echo "--- cost_baseline.md existence ---" >> "$REPORT"
ls ~/.openclaw/workspace/cost_baseline.md >> "$REPORT" 2>&1 || echo "NOT FOUND" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 3.5 CEO memory/ directory" >> "$REPORT"
echo '```' >> "$REPORT"
ls ~/.openclaw/workspace/memory/ >> "$REPORT" 2>&1 || echo "NOT FOUND" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 3.6 Declassified AGENTS.md analysis" >> "$REPORT"
echo '```' >> "$REPORT"
wc -l ~/.openclaw/workspace-declassified/AGENTS.md >> "$REPORT" 2>&1
echo "sessions_spawn occurrences:" >> "$REPORT"
grep -c "sessions_spawn" ~/.openclaw/workspace-declassified/AGENTS.md >> "$REPORT" 2>&1
echo "spawn_agent occurrences:" >> "$REPORT"
grep -c "spawn_agent" ~/.openclaw/workspace-declassified/AGENTS.md >> "$REPORT" 2>&1
echo "spawn_narrative occurrences:" >> "$REPORT"
grep -c "spawn_narrative" ~/.openclaw/workspace-declassified/AGENTS.md >> "$REPORT" 2>&1
echo '```' >> "$REPORT"

echo "### 3.7 Declassified workspace core files" >> "$REPORT"
echo '```' >> "$REPORT"
for f in HEARTBEAT.md IDENTITY.md MEMORY.md SOUL.md TOOLS.md USER.md V9_PIPELINE_AUDIT_REPORT.md; do
    ls ~/.openclaw/workspace-declassified/$f >> "$REPORT" 2>&1 || echo "$f: NOT FOUND" >> "$REPORT"
done
echo '```' >> "$REPORT"

echo "### 3.8 Meta-Planner AGENTS.md (first 50 lines)" >> "$REPORT"
echo '```' >> "$REPORT"
head -50 ~/.openclaw/workspace-meta-planner/AGENTS.md >> "$REPORT" 2>&1
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 4: CREDENTIALS (NAMES ONLY — NO VALUES)
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 4. Credentials (names only, NO values)" >> "$REPORT"

echo "### 4.1 .env key names" >> "$REPORT"
echo '```' >> "$REPORT"
grep -E "^[A-Z_].*=" ~/.openclaw/.env 2>/dev/null | sed 's/=.*/=***/' | sort >> "$REPORT"
echo "" >> "$REPORT"
echo "Total keys: $(grep -cE '^[A-Z_].*=' ~/.openclaw/.env 2>/dev/null)" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 4.2 litellm.env key names" >> "$REPORT"
echo '```' >> "$REPORT"
grep -E "^[A-Z_].*=" ~/.config/litellm/litellm.env 2>/dev/null | sed 's/=.*/=***/' | sort >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 4.3 Credential files" >> "$REPORT"
echo '```' >> "$REPORT"
ls ~/.openclaw/credentials/ >> "$REPORT" 2>&1 || echo "no credentials/ dir" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 4.4 sync_keys.sh existence" >> "$REPORT"
echo '```' >> "$REPORT"
if [ -f ~/.openclaw/sync_keys.sh ]; then
    echo "EXISTS ($(wc -l < ~/.openclaw/sync_keys.sh) lines)" >> "$REPORT"
    # Show structure without values
    grep -E "^#|cp |source |echo " ~/.openclaw/sync_keys.sh >> "$REPORT" 2>&1
else
    echo "NOT FOUND" >> "$REPORT"
fi
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 5: LITELLM
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 5. LiteLLM" >> "$REPORT"

echo "### 5.1 Version" >> "$REPORT"
echo '```' >> "$REPORT"
/home/robotin/litellm-venv/bin/pip show litellm 2>/dev/null | grep Version >> "$REPORT" || echo "not found in venv" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 5.2 All model names in config.yaml" >> "$REPORT"
echo '```' >> "$REPORT"
grep "model_name:" ~/.config/litellm/config.yaml >> "$REPORT" 2>&1
echo "" >> "$REPORT"
echo "Total models in config: $(grep -c 'model_name:' ~/.config/litellm/config.yaml 2>/dev/null)" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 5.3 Models actually healthy (via API)" >> "$REPORT"
echo '```' >> "$REPORT"
curl -s -H "Authorization: Bearer sk-litellm-local" http://127.0.0.1:4000/v1/models 2>/dev/null | python3 -c "
import sys,json
try:
    data = json.load(sys.stdin)
    models = sorted([m['id'] for m in data.get('data',[])])
    for m in models: print(f'  {m}')
    print(f'\nTotal active models: {len(models)}')
except Exception as e:
    print(f'Could not parse: {e}')
" >> "$REPORT" 2>&1 || echo "LiteLLM NOT RUNNING — cannot verify models" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 5.4 Codex/OAuth model config" >> "$REPORT"
echo '```' >> "$REPORT"
grep -B1 -A5 "codex\|chatgpt-gpt54" ~/.config/litellm/config.yaml 2>/dev/null | grep -v "api_key\|api_base.*key" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 5.5 OpenRouter model config" >> "$REPORT"
echo '```' >> "$REPORT"
grep -B1 -A3 "openrouter" ~/.config/litellm/config.yaml 2>/dev/null | grep -v "api_key" >> "$REPORT"
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 6: POSTGRESQL
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 6. PostgreSQL" >> "$REPORT"

echo "### 6.1 All marketing schema tables + row counts" >> "$REPORT"
echo '```' >> "$REPORT"
psql "postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db" -c "
SELECT tablename, n_live_tup as row_count
FROM pg_stat_user_tables
WHERE schemaname = 'marketing'
ORDER BY tablename;
" >> "$REPORT" 2>&1 || echo "DB NOT REACHABLE" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 6.2 Table count (bible says 24)" >> "$REPORT"
echo '```' >> "$REPORT"
psql "postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db" -c "
SELECT COUNT(*) as total_tables FROM pg_tables WHERE schemaname = 'marketing';
" >> "$REPORT" 2>&1 || echo "DB NOT REACHABLE" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 6.3 Foreign key constraints" >> "$REPORT"
echo '```' >> "$REPORT"
psql "postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db" -c "
SELECT COUNT(*) as fk_count FROM information_schema.table_constraints
WHERE constraint_schema = 'marketing' AND constraint_type = 'FOREIGN KEY';
" >> "$REPORT" 2>&1
echo '```' >> "$REPORT"

echo "### 6.4 CHECK constraints" >> "$REPORT"
echo '```' >> "$REPORT"
psql "postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db" -c "
SELECT COUNT(*) as check_count FROM information_schema.table_constraints
WHERE constraint_schema = 'marketing' AND constraint_type = 'CHECK';
" >> "$REPORT" 2>&1
echo '```' >> "$REPORT"

echo "### 6.5 verify_db_parity.py (functional test)" >> "$REPORT"
echo '```' >> "$REPORT"
if [ -f ~/.openclaw/marketing-system/scripts/verify_db_parity.py ]; then
    cd ~/.openclaw/marketing-system/scripts
    /home/robotin/litellm-venv/bin/python verify_db_parity.py >> "$REPORT" 2>&1
else
    echo "verify_db_parity.py NOT FOUND" >> "$REPORT"
fi
echo '```' >> "$REPORT"

echo "### 6.6 LiteLLM spend data (cost baseline)" >> "$REPORT"
echo '```' >> "$REPORT"
psql "postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db" -c "
SELECT
    DATE_TRUNC('week', \"startTime\") as week,
    ROUND(SUM(spend)::numeric, 2) as total_spend,
    COUNT(*) as api_calls
FROM \"LiteLLM_SpendLogs\"
WHERE \"startTime\" > NOW() - INTERVAL '4 weeks'
GROUP BY 1 ORDER BY 1 DESC LIMIT 4;
" >> "$REPORT" 2>&1 || echo "SpendLogs table not found or empty" >> "$REPORT"
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 7: MARKETING SYSTEM
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 7. Marketing System" >> "$REPORT"

echo "### 7.1 Skills" >> "$REPORT"
echo '```' >> "$REPORT"
ls ~/.openclaw/marketing-system/skills/ >> "$REPORT" 2>&1
echo "Total: $(ls ~/.openclaw/marketing-system/skills/ 2>/dev/null | wc -l)" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 7.2 Scripts" >> "$REPORT"
echo '```' >> "$REPORT"
ls ~/.openclaw/marketing-system/scripts/*.py 2>/dev/null >> "$REPORT"
echo "Total scripts: $(ls ~/.openclaw/marketing-system/scripts/*.py 2>/dev/null | wc -l)" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 7.3 Weekly runs" >> "$REPORT"
echo '```' >> "$REPORT"
ls ~/.openclaw/products/misterio-semanal/weekly_runs/ >> "$REPORT" 2>&1
echo '```' >> "$REPORT"

echo "### 7.4 Strategy versions" >> "$REPORT"
echo '```' >> "$REPORT"
ls ~/.openclaw/products/misterio-semanal/strategies/ >> "$REPORT" 2>&1
echo '```' >> "$REPORT"

echo "### 7.5 telegram_ops.py" >> "$REPORT"
echo '```' >> "$REPORT"
if [ -f ~/.openclaw/marketing-system/scripts/telegram_ops.py ]; then
    echo "EXISTS ($(wc -l < ~/.openclaw/marketing-system/scripts/telegram_ops.py) lines)" >> "$REPORT"
    ps aux | grep telegram_ops | grep -v grep >> "$REPORT" 2>&1 || echo "Process: NOT RUNNING" >> "$REPORT"
    # Check if dedicated token exists (name only)
    grep -q "TELEGRAM_OPS_TOKEN" ~/.openclaw/.env 2>/dev/null && echo "TELEGRAM_OPS_TOKEN: configured" >> "$REPORT" || echo "TELEGRAM_OPS_TOKEN: NOT configured (uses shared bot token — conflict)" >> "$REPORT"
else
    echo "NOT FOUND" >> "$REPORT"
fi
echo '```' >> "$REPORT"

echo "### 7.6 claim_linter.py integration check" >> "$REPORT"
echo '```' >> "$REPORT"
if [ -f ~/.openclaw/marketing-system/scripts/claim_linter.py ]; then
    echo "claim_linter.py EXISTS ($(wc -l < ~/.openclaw/marketing-system/scripts/claim_linter.py) lines)" >> "$REPORT"
    # Check if marketing_runner.py calls it
    grep -n "claim_linter\|claim_lint" ~/.openclaw/marketing-system/scripts/marketing_runner.py >> "$REPORT" 2>&1 || echo "NOT referenced in marketing_runner.py" >> "$REPORT"
else
    echo "claim_linter.py NOT FOUND" >> "$REPORT"
fi
echo '```' >> "$REPORT"

echo "### 7.7 stripe_sync.py" >> "$REPORT"
echo '```' >> "$REPORT"
ls ~/.openclaw/marketing-system/scripts/stripe_sync.py >> "$REPORT" 2>&1 && echo "stripe_sync.py: EXISTS" >> "$REPORT" || echo "stripe_sync.py: NOT FOUND" >> "$REPORT"
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 8: DECLASSIFIED PIPELINE
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 8. Declassified Pipeline" >> "$REPORT"

echo "### 8.1 Skills" >> "$REPORT"
echo '```' >> "$REPORT"
ls ~/.openclaw/workspace-declassified/skills/ >> "$REPORT" 2>&1
echo "Total: $(ls ~/.openclaw/workspace-declassified/skills/ 2>/dev/null | wc -l)" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 8.2 Case exports (with manifest data)" >> "$REPORT"
echo '```' >> "$REPORT"
if [ -d ~/.openclaw/workspace-declassified/cases/exports/ ]; then
    for dir in ~/.openclaw/workspace-declassified/cases/exports/*/; do
        [ -d "$dir" ] || continue
        slug=$(basename "$dir")
        echo "--- $slug ---" >> "$REPORT"
        if [ -f "$dir/manifest.json" ]; then
            python3 -c "
import sys,json
try:
    d=json.load(open('$dir/manifest.json'))
    print(f'  Case name: {d.get(\"case_name\",\"unknown\")}')
    print(f'  Status: {d.get(\"status\",\"unknown\")}')
    ct = d.get('cost_tracking',{})
    print(f'  Tracked cost: \${ct.get(\"total_cost_usd\",\"unknown\")}')
    phases = d.get('phases',{})
    print(f'  Phases: {list(phases.keys()) if phases else \"not in manifest\"}')
except Exception as e: print(f'  manifest error: {e}')
" >> "$REPORT"
        else
            echo "  No manifest.json" >> "$REPORT"
            ls "$dir" | head -5 >> "$REPORT"
        fi
    done
else
    echo "exports/ NOT FOUND" >> "$REPORT"
fi
echo '```' >> "$REPORT"

echo "### 8.3 Config files" >> "$REPORT"
echo '```' >> "$REPORT"
ls ~/.openclaw/workspace-declassified/cases/config/ >> "$REPORT" 2>&1
echo '```' >> "$REPORT"

echo "### 8.4 Scripts" >> "$REPORT"
echo '```' >> "$REPORT"
ls ~/.openclaw/workspace-declassified/cases/scripts/ >> "$REPORT" 2>&1
echo '```' >> "$REPORT"

echo "### 8.5 doc_type_catalog.json (first 60 lines)" >> "$REPORT"
echo '```json' >> "$REPORT"
cat ~/.openclaw/workspace-declassified/cases/config/doc_type_catalog.json 2>/dev/null | python3 -m json.tool 2>/dev/null | head -60 >> "$REPORT" || echo "NOT FOUND" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 8.6 ai_render.py critical parameters" >> "$REPORT"
echo '```' >> "$REPORT"
if [ -f ~/.openclaw/workspace-declassified/cases/scripts/ai_render.py ]; then
    echo "File: $(wc -l < ~/.openclaw/workspace-declassified/cases/scripts/ai_render.py) lines" >> "$REPORT"
    echo "--- MAX_TOKENS ---" >> "$REPORT"
    grep -n "MAX_TOKENS\|max_tokens" ~/.openclaw/workspace-declassified/cases/scripts/ai_render.py >> "$REPORT" 2>&1
    echo "--- Timeouts ---" >> "$REPORT"
    grep -n "timeout\|max.time\|max-time" ~/.openclaw/workspace-declassified/cases/scripts/ai_render.py >> "$REPORT" 2>&1
    echo "--- Model ---" >> "$REPORT"
    grep -n "model\|claude" ~/.openclaw/workspace-declassified/cases/scripts/ai_render.py | head -5 >> "$REPORT" 2>&1
else
    echo "ai_render.py NOT FOUND" >> "$REPORT"
fi
echo '```' >> "$REPORT"

echo "### 8.7 validate_art.py (known bug)" >> "$REPORT"
echo '```' >> "$REPORT"
ls ~/.openclaw/workspace-declassified/cases/scripts/validate_art.py >> "$REPORT" 2>&1 && echo "EXISTS" >> "$REPORT" || echo "NOT FOUND" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 8.8 model_routing config (if exists)" >> "$REPORT"
echo '```' >> "$REPORT"
cat ~/.openclaw/workspace-declassified/cases/config/model_routing.json 2>/dev/null | python3 -m json.tool 2>/dev/null >> "$REPORT" || echo "No model_routing.json in config/" >> "$REPORT"
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 9: META-WORKFLOW PLANNER
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 9. Meta-Workflow Planner" >> "$REPORT"

echo "### 9.1 Structure" >> "$REPORT"
echo '```' >> "$REPORT"
echo "--- root ---" >> "$REPORT"
ls ~/.openclaw/workspace-meta-planner/ >> "$REPORT" 2>&1 || echo "NOT FOUND" >> "$REPORT"
for subdir in skills scripts schemas runs; do
    echo "--- $subdir/ ---" >> "$REPORT"
    ls ~/.openclaw/workspace-meta-planner/$subdir/ >> "$REPORT" 2>&1 || echo "NOT FOUND" >> "$REPORT"
done
echo '```' >> "$REPORT"

echo "### 9.2 planner_config.json" >> "$REPORT"
echo '```json' >> "$REPORT"
cat ~/.openclaw/workspace-meta-planner/planner_config.json 2>/dev/null | python3 -m json.tool 2>/dev/null >> "$REPORT" || echo "NOT FOUND" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 9.3 models.json" >> "$REPORT"
echo '```json' >> "$REPORT"
cat ~/.openclaw/workspace-meta-planner/models.json 2>/dev/null | python3 -m json.tool 2>/dev/null >> "$REPORT" || echo "NOT FOUND" >> "$REPORT"
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 10: FINANCE TRACKER
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 10. Finance Tracker" >> "$REPORT"

echo "### 10.1 Structure" >> "$REPORT"
echo '```' >> "$REPORT"
if [ -d ~/.openclaw/workspace/skills/finance-tracker ]; then
    ls ~/.openclaw/workspace/skills/finance-tracker/ >> "$REPORT"
    echo "--- scripts/lib/ ---" >> "$REPORT"
    ls ~/.openclaw/workspace/skills/finance-tracker/scripts/lib/ >> "$REPORT" 2>&1
    echo "--- config/ ---" >> "$REPORT"
    ls ~/.openclaw/workspace/skills/finance-tracker/config/ >> "$REPORT" 2>&1
else
    echo "finance-tracker skill NOT FOUND" >> "$REPORT"
fi
echo '```' >> "$REPORT"

echo "### 10.2 Google Sheets OAuth" >> "$REPORT"
echo '```' >> "$REPORT"
ls ~/.openclaw/credentials/finance-tracker-token.json >> "$REPORT" 2>&1 && echo "OAuth token: OK" >> "$REPORT" || echo "OAuth token: MISSING" >> "$REPORT"
ls ~/.openclaw/credentials/google_client_secret.json >> "$REPORT" 2>&1 && echo "Client secret: OK" >> "$REPORT" || echo "Client secret: MISSING" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 10.3 AGENTS.md reference" >> "$REPORT"
echo '```' >> "$REPORT"
grep -i "finance" ~/.openclaw/workspace/AGENTS.md >> "$REPORT" 2>&1 || echo "NOT referenced in CEO AGENTS.md" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 10.4 Functional smoke test" >> "$REPORT"
echo '```' >> "$REPORT"
if [ -f ~/.openclaw/workspace/skills/finance-tracker/scripts/finance.py ]; then
    cd ~/.openclaw/workspace/skills/finance-tracker/scripts
    /home/robotin/litellm-venv/bin/python finance.py parse-text '$15.50 uber ride' 2>&1 | head -10 >> "$REPORT"
else
    echo "finance.py NOT FOUND" >> "$REPORT"
fi
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 11: GIT
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 11. Git Repositories" >> "$REPORT"

echo "### 11.1 openclaw-config" >> "$REPORT"
echo '```' >> "$REPORT"
cd ~/.openclaw
echo "Remote:" >> "$REPORT"
git remote -v >> "$REPORT" 2>&1
echo "" >> "$REPORT"
echo "Branch: $(git branch --show-current 2>/dev/null)" >> "$REPORT"
echo "" >> "$REPORT"
echo "Status (after fetch):" >> "$REPORT"
git fetch --quiet 2>/dev/null
git status -sb >> "$REPORT" 2>&1
echo "" >> "$REPORT"
echo "Last 20 commits:" >> "$REPORT"
git log --oneline -20 >> "$REPORT" 2>&1
echo "" >> "$REPORT"
echo "Uncommitted changes: $(git diff --stat 2>/dev/null | tail -1)" >> "$REPORT"
echo "" >> "$REPORT"
echo "Stash:" >> "$REPORT"
git stash list >> "$REPORT" 2>&1 || echo "none" >> "$REPORT"
echo "" >> "$REPORT"
echo "Nested .git check:" >> "$REPORT"
ls ~/.openclaw/workspace/.git >> "$REPORT" 2>&1 && echo "WARNING: workspace has own .git" >> "$REPORT" || echo "workspace: clean (no nested .git)" >> "$REPORT"
echo '```' >> "$REPORT"

echo "### 11.2 declassifiedcase (web store)" >> "$REPORT"
echo '```' >> "$REPORT"
if [ -d ~/declassifiedcase ]; then
    cd ~/declassifiedcase
    echo "Remote:" >> "$REPORT"
    git remote -v >> "$REPORT" 2>&1
    echo "Branch: $(git branch --show-current 2>/dev/null)" >> "$REPORT"
    echo "Status (after fetch):" >> "$REPORT"
    git fetch --quiet 2>/dev/null
    git status -sb >> "$REPORT" 2>&1
    echo "Last 10 commits:" >> "$REPORT"
    git log --oneline -10 >> "$REPORT" 2>&1
else
    echo "NOT CLONED — run: cd ~ && git clone https://github.com/pr3t3l/declassifiedcase.git" >> "$REPORT"
fi
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 12: WEB STORE
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 12. Web Store (declassifiedcase)" >> "$REPORT"
echo '```' >> "$REPORT"
if [ -d ~/declassifiedcase/src ]; then
    echo "--- components/brand/ ---" >> "$REPORT"
    ls ~/declassifiedcase/src/components/brand/ >> "$REPORT" 2>&1
    echo "Brand components: $(ls ~/declassifiedcase/src/components/brand/*.tsx 2>/dev/null | wc -l)" >> "$REPORT"
    echo "" >> "$REPORT"
    echo "--- components/admin/ ---" >> "$REPORT"
    ls ~/declassifiedcase/src/components/admin/ >> "$REPORT" 2>&1
    echo "" >> "$REPORT"
    echo "--- pages/ ---" >> "$REPORT"
    ls ~/declassifiedcase/src/pages/ >> "$REPORT" 2>&1
    echo "" >> "$REPORT"
    echo "--- hooks/ ---" >> "$REPORT"
    ls ~/declassifiedcase/src/hooks/ >> "$REPORT" 2>&1
    echo "" >> "$REPORT"
    echo "--- assets/brand/ ---" >> "$REPORT"
    ls ~/declassifiedcase/src/assets/brand/ >> "$REPORT" 2>&1
    echo "" >> "$REPORT"
    echo "--- Persona landing pages check ---" >> "$REPORT"
    grep -rl "date-night\|game-night\|true-crime\|mystery-gift\|family-detective" ~/declassifiedcase/src/ --include="*.tsx" 2>/dev/null | head -10 >> "$REPORT" || echo "No persona pages found" >> "$REPORT"
    echo "" >> "$REPORT"
    echo "--- UTM tracking ---" >> "$REPORT"
    ls ~/declassifiedcase/src/hooks/useUtmTracking.ts >> "$REPORT" 2>&1 || echo "No UTM hook" >> "$REPORT"
else
    echo "REPO NOT CLONED" >> "$REPORT"
fi
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 13: SOCIAL MEDIA CONFIG (filesystem only)
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 13. Social Media Config (local files only)" >> "$REPORT"
echo '```' >> "$REPORT"
find ~/.openclaw/ -name "*social*" -o -name "*facebook*" -o -name "*instagram*" -o -name "*tiktok*" -o -name "*meta_*" 2>/dev/null | head -10 >> "$REPORT"
echo "(empty = no social config files exist locally yet)" >> "$REPORT"
echo "" >> "$REPORT"
echo "NOTE: Social media status requires manual verification:" >> "$REPORT"
echo "  FB Page: CREATED (confirmed by Alfredo)" >> "$REPORT"
echo "  IG Business: CREATED, connected to FB (confirmed)" >> "$REPORT"
echo "  FB Developer App: IN PROGRESS — Phase 3 (confirmed)" >> "$REPORT"
echo "  TikTok: PENDING" >> "$REPORT"
echo "  YouTube: PENDING" >> "$REPORT"
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 14: OPTIMIZATION PLAN
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 14. Optimization Plan" >> "$REPORT"
echo '```' >> "$REPORT"
if [ -f ~/.openclaw/OPTIMIZATION_PLAN.md ]; then
    echo "EXISTS ($(wc -l < ~/.openclaw/OPTIMIZATION_PLAN.md) lines)" >> "$REPORT"
    head -60 ~/.openclaw/OPTIMIZATION_PLAN.md >> "$REPORT"
else
    echo "NOT FOUND" >> "$REPORT"
fi
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 15: CLAUDE CODE
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 15. Claude Code" >> "$REPORT"
echo '```' >> "$REPORT"
claude --version >> "$REPORT" 2>&1 || echo "NOT INSTALLED" >> "$REPORT"
# Show settings structure, not values
cat ~/.claude/settings.json 2>/dev/null | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(json.dumps({k: type(v).__name__ for k,v in d.items()}, indent=2))
except: print('No parseable settings')
" >> "$REPORT" || echo "No settings" >> "$REPORT"
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 16: QMD + BUN
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 16. QMD + Bun" >> "$REPORT"
echo '```' >> "$REPORT"
which bun >> "$REPORT" 2>&1 && bun --version >> "$REPORT" 2>&1 || echo "bun: NOT FOUND" >> "$REPORT"
which qmd >> "$REPORT" 2>&1 && qmd --version >> "$REPORT" 2>&1 || echo "qmd: NOT FOUND" >> "$REPORT"
# Also check if qmd is in bun bin
ls ~/.bun/bin/qmd >> "$REPORT" 2>&1 || echo "qmd not in ~/.bun/bin/ either" >> "$REPORT"
echo "" >> "$REPORT"
echo "openclaw.json memory/compaction/heartbeat config:" >> "$REPORT"
cat ~/.openclaw/openclaw.json 2>/dev/null | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    for key in ['compaction','contextPruning','session']:
        if key in d: print(f'{key}: {json.dumps(d[key], indent=2)}')
except: pass
" >> "$REPORT"
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 17: BACKUP
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 17. Backup" >> "$REPORT"
echo '```' >> "$REPORT"
ls ~/.openclaw/safe_backup.sh >> "$REPORT" 2>&1 && echo "EXISTS" >> "$REPORT" || echo "NOT FOUND" >> "$REPORT"
echo "--- All cron jobs ---" >> "$REPORT"
crontab -l >> "$REPORT" 2>&1 || echo "No cron jobs configured for robotin" >> "$REPORT"
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 18: DISK USAGE
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 18. Disk Usage" >> "$REPORT"
echo '```' >> "$REPORT"
du -sh ~/.openclaw/ >> "$REPORT" 2>&1
du -sh ~/.openclaw/workspace/ >> "$REPORT" 2>&1
du -sh ~/.openclaw/workspace-declassified/ >> "$REPORT" 2>&1
du -sh ~/.openclaw/workspace-meta-planner/ >> "$REPORT" 2>&1
du -sh ~/.openclaw/marketing-system/ >> "$REPORT" 2>&1
du -sh ~/declassifiedcase/ >> "$REPORT" 2>&1 || echo "web repo not cloned" >> "$REPORT"
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SECTION 19: MANUAL EVIDENCE (not filesystem-verifiable)
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## 19. Manual Evidence (confirmed by Alfredo 2026-03-29)" >> "$REPORT"
echo '```' >> "$REPORT"
cat << 'MANUAL_EOF' >> "$REPORT"
These items were confirmed directly and cannot be verified via filesystem:

CONFIRMED ACTIVE:
  - IONOS email support@declassified.shop: ACTIVE
  - Resend domain (declassified.shop): VERIFIED, emails sending
  - Codex OAuth ($200/mo Pro): ACTIVE, $0/token for all GPT usage
  - Web redesign (declassified.shop): DEPLOYED AND LIVE
  - FB Page (Declassified Cases): CREATED
  - IG Business Account: CREATED, connected to FB Page

CONFIRMED IN PROGRESS:
  - FB Developer App: Phase 3 (not yet complete)

CONFIRMED NOT DONE:
  - DALL-E 3 via LiteLLM: NOT TESTED YET (proxy restart needed)
  - TikTok account: PENDING
  - YouTube channel: PENDING

REQUIRES BROWSER VERIFICATION:
  - declassified.shop live design (confirm new brand components visible)
  - Lovable Publish deployment pipeline
  - Stripe checkout flow end-to-end
MANUAL_EOF
echo '```' >> "$REPORT"

# ─────────────────────────────────────────
# SUMMARY JSON (structured facts for Bible v2)
# ─────────────────────────────────────────
echo "" >> "$REPORT"
echo "## AUDIT COMPLETE" >> "$REPORT"
echo "Report saved to: $REPORT" >> "$REPORT"

# Generate structured summary
python3 << 'PYSCRIPT' > "$SUMMARY" 2>&1
import json, subprocess, os

def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except:
        return "ERROR"

summary = {
    "audit_date": run("date -Iseconds"),
    "openclaw_version": run("/home/robotin/.npm-global/bin/openclaw --version 2>/dev/null"),

    "services": {
        "gateway_http": run("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/ 2>/dev/null"),
        "litellm_http": run("curl -s -o /dev/null -w '%{http_code}' -H 'Authorization: Bearer sk-litellm-local' http://127.0.0.1:4000/health 2>/dev/null"),
        "postgresql": run("pg_isready 2>/dev/null"),
        "systemd_enabled": "true" in run("grep systemd /etc/wsl.conf 2>/dev/null"),
        "tmux_sessions": run("tmux ls 2>/dev/null || echo 'none'"),
    },

    "litellm": {
        "model_count_config": run("grep -c 'model_name:' ~/.config/litellm/config.yaml 2>/dev/null"),
        "active_models": run("curl -s -H 'Authorization: Bearer sk-litellm-local' http://127.0.0.1:4000/v1/models 2>/dev/null | python3 -c \"import sys,json; [print(m['id']) for m in json.load(sys.stdin).get('data',[])]\" 2>/dev/null").split('\n') if run("curl -s -o /dev/null -w '%{http_code}' -H 'Authorization: Bearer sk-litellm-local' http://127.0.0.1:4000/health 2>/dev/null") == "200" else "NOT_RUNNING",
    },

    "postgresql": {
        "marketing_table_count": run("psql 'postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db' -t -c \"SELECT COUNT(*) FROM pg_tables WHERE schemaname='marketing'\" 2>/dev/null").strip(),
        "fk_count": run("psql 'postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db' -t -c \"SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema='marketing' AND constraint_type='FOREIGN KEY'\" 2>/dev/null").strip(),
        "check_count": run("psql 'postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db' -t -c \"SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema='marketing' AND constraint_type='CHECK'\" 2>/dev/null").strip(),
    },

    "verify_db_parity": run("cd ~/.openclaw/marketing-system/scripts && /home/robotin/litellm-venv/bin/python verify_db_parity.py 2>&1 | tail -3") if os.path.exists(os.path.expanduser("~/.openclaw/marketing-system/scripts/verify_db_parity.py")) else "SCRIPT_NOT_FOUND",

    "credentials": {
        "env_key_count": run("grep -cE '^[A-Z_].*=' ~/.openclaw/.env 2>/dev/null"),
        "env_key_names": run("grep -E '^[A-Z_].*=' ~/.openclaw/.env 2>/dev/null | sed 's/=.*//' | sort").split('\n'),
    },

    "marketing": {
        "skills_count": run("ls ~/.openclaw/marketing-system/skills/ 2>/dev/null | wc -l"),
        "scripts_count": run("ls ~/.openclaw/marketing-system/scripts/*.py 2>/dev/null | wc -l"),
        "weekly_runs": run("ls ~/.openclaw/products/misterio-semanal/weekly_runs/ 2>/dev/null").split(),
        "telegram_ops_exists": os.path.exists(os.path.expanduser("~/.openclaw/marketing-system/scripts/telegram_ops.py")),
        "telegram_ops_token_configured": "TELEGRAM_OPS_TOKEN" in run("grep -E '^[A-Z_].*=' ~/.openclaw/.env 2>/dev/null"),
        "stripe_sync_exists": os.path.exists(os.path.expanduser("~/.openclaw/marketing-system/scripts/stripe_sync.py")),
        "claim_linter_exists": os.path.exists(os.path.expanduser("~/.openclaw/marketing-system/scripts/claim_linter.py")),
    },

    "pipeline": {
        "skills_count": run("ls ~/.openclaw/workspace-declassified/skills/ 2>/dev/null | wc -l"),
        "case_exports": run("ls ~/.openclaw/workspace-declassified/cases/exports/ 2>/dev/null").split(),
        "ai_render_max_tokens": run("grep -oP 'MAX_TOKENS\\s*=\\s*\\d+' ~/.openclaw/workspace-declassified/cases/scripts/ai_render.py 2>/dev/null"),
    },

    "meta_planner": {
        "skills_count": run("ls ~/.openclaw/workspace-meta-planner/skills/ 2>/dev/null | wc -l"),
        "runs": run("ls ~/.openclaw/workspace-meta-planner/runs/ 2>/dev/null").split(),
    },

    "finance_tracker_exists": os.path.exists(os.path.expanduser("~/.openclaw/workspace/skills/finance-tracker/SKILL.md")),
    "web_store_cloned": os.path.isdir(os.path.expanduser("~/declassifiedcase/src")),

    "git": {
        "openclaw_branch": run("cd ~/.openclaw && git branch --show-current 2>/dev/null"),
        "openclaw_dirty_files": run("cd ~/.openclaw && git status --porcelain 2>/dev/null | wc -l"),
        "openclaw_last_commit": run("cd ~/.openclaw && git log --oneline -1 2>/dev/null"),
        "webstore_branch": run("cd ~/declassifiedcase && git branch --show-current 2>/dev/null") if os.path.isdir(os.path.expanduser("~/declassifiedcase")) else "NOT_CLONED",
    },

    "manual_confirmations": {
        "confirmed_date": "2026-03-29",
        "ionos_email": True,
        "resend_verified": True,
        "codex_oauth_active": True,
        "web_redesign_live": True,
        "dalle3_tested": False,
        "fb_dev_app_complete": False,
        "fb_page_created": True,
        "ig_business_created": True,
        "tiktok": False,
        "youtube": False,
    }
}

print(json.dumps(summary, indent=2))
PYSCRIPT

echo ""
echo "✅ Audit complete."
echo "📄 Full report: $REPORT"
echo "📊 Summary JSON: $SUMMARY"
echo ""
echo "⚠️  Files are in /tmp/ — they won't dirty git."
echo "    DO NOT commit these files. Only the sanitized Bible v2 gets committed."
echo ""
echo "Next: Show the FULL contents of audit_summary.json."
echo "From the report, show only sections with errors, NOT FOUND, or unexpected counts."
