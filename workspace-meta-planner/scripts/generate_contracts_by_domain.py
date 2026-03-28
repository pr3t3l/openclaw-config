#!/usr/bin/env python3
import json, re, subprocess, tempfile, hashlib, sys
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path('/home/robotin/.openclaw/workspace-meta-planner')
RUN_DIR = WORKSPACE / 'runs' / 'strategy-runtime-1'
OUT_DIR = RUN_DIR / 'contracts_domains'
OUT_DIR.mkdir(parents=True, exist_ok=True)
MODELS = json.loads((WORKSPACE / 'models.json').read_text())
CONFIG = json.loads((WORKSPACE / 'planner_config.json').read_text())
SKILL = (WORKSPACE / 'skills' / 'contract-designer' / 'SKILL.md').read_text(encoding='utf-8')
MODEL = MODELS['agents']['contract_designer']['model']
PROXY = MODELS['litellm_proxy']
API_KEY = MODELS.get('litellm_api_key', '')
MAX_TOKENS = 9000

base_parts = []
for artifact in ['03_data_flow_map']:
    p = RUN_DIR / f'{artifact}.json'
    if p.exists():
        base_parts.append(f"=== {artifact}.json ===\n{p.read_text(encoding='utf-8')}\n=== END {artifact}.json ===")
adj = RUN_DIR / 'gate_1_adjustments.json'
if adj.exists():
    data = json.loads(adj.read_text())
    base_parts.append(f"=== HUMAN ADJUSTMENTS FROM GATE #1 (mandatory) ===\n{data.get('adjustments','')}\n=== END ADJUSTMENTS ===")
base_parts.append("=== EXECUTION OVERRIDE ===\nDesign for ADVANCED scope. Generate only the requested domain block. Output ONLY valid JSON. No prose before or after. Keep examples compact. If a block is still large, prefer concise schemas over verbose examples.\n=== END EXECUTION OVERRIDE ===")
BASE = '\n\n'.join(base_parts)

DOMAINS = [
    ('01a_product_strategy_manifests', 'Generate ONLY the contracts for: product_manifest.json and strategy_manifest.json. Include schema_definition, validation_rules, ownership/writer-consumer clarity, and only compact examples.'),
    ('01b_run_growth_manifests', 'Generate ONLY the contracts for: run_manifest.json and growth_run_manifest.json. Include schema_definition, validation_rules, complete/partial/failed fields where relevant, and compact examples.'),
    ('01c_runtime_state', 'Generate ONLY the contract for: runtime_state.json. Include exact states, gate tracking, locking/concurrency fields, invalidation references, and compact examples.'),
    ('02_strategic_artifacts', 'Generate ONLY the contracts for: market_analysis.json, buyer_persona.json, brand_strategy.json, seo_architecture.json, channel_strategy.json. Include exact required fields and validation rules.'),
    ('03_marketing_interface', 'Generate ONLY the contract for interface_contract_marketing_v1.json, including exact paths, required fields consumed by marketing-workflow-1, and version pinning rules.'),
    ('04_gates_telegram_security', 'Generate ONLY the contracts/specs for Gates S1 and S2, Telegram command payloads approve/reject/adjust, timeout/expiration behavior, whitelist user_ids, and unauthorized handling.'),
    ('05_invalidation_rollback_observability', 'Generate ONLY the contracts/specs for invalidation_log.json, complete/partial/failed criteria, atomic rollback, hashes, timestamps, audit trail, and observability metadata.')
]


def extract_json(content: str):
    m = re.search(r'```json\s*(.*?)```', content, re.S)
    text = m.group(1).strip() if m else content.strip()
    if not text.startswith('{'):
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            text = text[start:end+1]
    return json.loads(text)


def call_model(user_prompt, suffix):
    payload = {
        'model': MODEL,
        'max_tokens': MAX_TOKENS,
        'messages': [
            {'role': 'system', 'content': SKILL},
            {'role': 'user', 'content': user_prompt},
        ],
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=True)
        tmp = f.name
    cmd = ['curl','-s','-S','--max-time',str(CONFIG['defaults']['curl_max_time']),'-H','Content-Type: application/json']
    if API_KEY:
        cmd += ['-H', f'Authorization: Bearer {API_KEY}']
    cmd += ['--data-binary', f'@{tmp}', f'{PROXY}/v1/chat/completions']
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=CONFIG['defaults']['curl_max_time']+CONFIG['defaults']['subprocess_buffer'])
    Path(tmp).unlink(missing_ok=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr)
    resp = json.loads(res.stdout)
    content = resp['choices'][0]['message']['content']
    raw_path = OUT_DIR / f'{suffix}.raw.txt'
    raw_path.write_text(content, encoding='utf-8')
    try:
        parsed = extract_json(content)
    except Exception as e:
        raise RuntimeError(f'{suffix} JSON parse failed: {e}; raw={raw_path}')
    return parsed, resp.get('usage', {})

results = {}
usage_totals = {'prompt_tokens': 0, 'completion_tokens': 0}
for name, task in DOMAINS:
    prompt = BASE + '\n\n=== DOMAIN TASK ===\n' + task + '\n=== END DOMAIN TASK ==='
    parsed, usage = call_model(prompt, name)
    (OUT_DIR / f'{name}.json').write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding='utf-8')
    results[name] = parsed
    usage_totals['prompt_tokens'] += usage.get('prompt_tokens', 0)
    usage_totals['completion_tokens'] += usage.get('completion_tokens', 0)

final = {
    'project_name': 'Strategy Workflow + Runtime Orchestrator (Phase 1)',
    'scope_version': 'advanced',
    'domain_blocks': results,
    'consolidation_notes': {
        'generated_by': 'generate_contracts_by_domain.py',
        'strategy': 'split-by-domain then consolidated',
        'domains': [name for name, _ in DOMAINS]
    }
}
final_path = RUN_DIR / '04_contracts.json'
final_path.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding='utf-8')
subprocess.run([sys.executable, str(WORKSPACE / 'scripts' / 'validate_schema.py'), 'strategy-runtime-1', '04_contracts'], check=True)
manifest = json.loads((RUN_DIR / 'manifest.json').read_text())
file_hash = hashlib.md5(final_path.read_text(encoding='utf-8').encode()).hexdigest()[:8]
now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
manifest['artifacts']['04_contracts'] = {
    'status': 'fresh',
    'hash': file_hash,
    'model': f'{MODEL}|split-domains',
    'input_tokens': usage_totals['prompt_tokens'],
    'output_tokens': usage_totals['completion_tokens'],
    'cost_usd': None,
    'timestamp': now
}
manifest['last_modified'] = now
(RUN_DIR / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
print('OK: wrote consolidated 04_contracts.json from domain blocks')
