#!/usr/bin/env python3
import json, re, subprocess, tempfile, hashlib, sys
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path('/home/robotin/.openclaw/workspace-meta-planner')
RUN_DIR = WORKSPACE / 'runs' / 'strategy-runtime-1'
OUT_DIR = RUN_DIR / 'contracts_atomic'
OUT_DIR.mkdir(parents=True, exist_ok=True)
MODELS = json.loads((WORKSPACE / 'models.json').read_text())
CONFIG = json.loads((WORKSPACE / 'planner_config.json').read_text())
SKILL = (WORKSPACE / 'skills' / 'contract-designer' / 'SKILL.md').read_text(encoding='utf-8')
MODEL = MODELS['agents']['contract_designer']['model']
PROXY = MODELS['litellm_proxy']
API_KEY = MODELS.get('litellm_api_key', '')
MAX_TOKENS = 3500

base_parts = []
p = RUN_DIR / '03_data_flow_map.json'
if p.exists():
    base_parts.append(f"=== 03_data_flow_map.json ===\n{p.read_text(encoding='utf-8')}\n=== END 03_data_flow_map.json ===")
adj = RUN_DIR / 'gate_1_adjustments.json'
if adj.exists():
    data = json.loads(adj.read_text())
    base_parts.append(f"=== HUMAN ADJUSTMENTS FROM GATE #1 (mandatory) ===\n{data.get('adjustments','')}\n=== END ADJUSTMENTS ===")
base_parts.append("=== EXECUTION OVERRIDE ===\nDesign for ADVANCED scope. Generate ONLY the requested single contract/spec artifact in COMPACT MODE. Output ONLY valid JSON.\n\nFor each contract include ONLY:\n1. artifact_name\n2. schema_definition (pure JSON Schema: type, properties, required, items, enum, pattern, additionalProperties when needed)\n3. produced_by\n4. consumed_by\n5. validation_rules (short list, no prose)\n\nDo NOT include:\n- examples\n- estimated_size_tokens\n- prose explanations\n- long descriptions inside schema\n- defaults unless absolutely required\n- commentary before or after JSON\n\nIf sub-objects are needed, define them inline or with $ref-compatible structure, but keep it compact.\n=== END EXECUTION OVERRIDE ===")
BASE = '\n\n'.join(base_parts)

TASKS = [
    ('01_product_manifest', 'Generate ONLY the compact contract for product_manifest.json.'),
    ('02_strategy_manifest', 'Generate ONLY the compact contract for strategy_manifest.json.'),
    ('03_run_manifest', 'Generate ONLY the compact contract for run_manifest.json.'),
    ('04_growth_run_manifest', 'Generate ONLY the compact contract for growth_run_manifest.json.'),
    ('05_runtime_state', 'Generate ONLY the compact contract for runtime_state.json.'),
    ('06_market_analysis', 'Generate ONLY the compact contract for market_analysis.json.'),
    ('07_buyer_persona', 'Generate ONLY the compact contract for buyer_persona.json.'),
    ('08_brand_strategy', 'Generate ONLY the compact contract for brand_strategy.json.'),
    ('09_seo_architecture', 'Generate ONLY the compact contract for seo_architecture.json.'),
    ('10_channel_strategy', 'Generate ONLY the compact contract for channel_strategy.json.'),
    ('11_interface_contract_marketing_v1', 'Generate ONLY the compact contract for interface_contract_marketing_v1.json, including exact paths, required fields, and version pinning rules.'),
    ('12_gate_definitions', 'Generate ONLY the compact contract for gate_definitions.json covering S1 and S2, approve/reject/adjust, timeout, expiration behavior, and what is shown to the human.'),
    ('13_telegram_security', 'Generate ONLY the compact contract for telegram_security.json covering whitelist user_ids, auth rules, unauthorized handling, and allowed commands.'),
    ('14_invalidation_rules', 'Generate ONLY the compact contract for invalidation_rules.json covering hard/soft invalidation rules, triggers, and downstream effects.'),
    ('15_rollback_policy', 'Generate ONLY the compact contract for rollback_policy.json covering atomic rollback, complete/partial/failed definitions, hashes, audit, and observability fields.')
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


def call_model(prompt, suffix):
    payload = {'model': MODEL, 'max_tokens': MAX_TOKENS, 'messages': [{'role': 'system', 'content': SKILL}, {'role': 'user', 'content': prompt}]}
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
    except Exception:
        repair_script = WORKSPACE / 'scripts' / 'json_repair.py'
        repaired_path = OUT_DIR / f'{suffix}.json.repaired.tmp'
        repair = subprocess.run([sys.executable, str(repair_script), str(raw_path), str(repaired_path)], capture_output=True, text=True)
        if repair.returncode != 0:
            raise RuntimeError(f'{suffix} JSON parse failed and auto-repair failed: {repair.stderr.strip() or repair.stdout.strip()}; raw={raw_path}')
        parsed = json.loads(repaired_path.read_text(encoding='utf-8'))
        repaired_path.unlink(missing_ok=True)
    return parsed, resp.get('usage', {})

results = {}
usage_totals = {'prompt_tokens': 0, 'completion_tokens': 0}
for name, task in TASKS:
    prompt = BASE + '\n\n=== ARTIFACT TASK ===\n' + task + '\n=== END ARTIFACT TASK ==='
    parsed, usage = call_model(prompt, name)
    (OUT_DIR / f'{name}.json').write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding='utf-8')
    results[name] = parsed
    usage_totals['prompt_tokens'] += usage.get('prompt_tokens', 0)
    usage_totals['completion_tokens'] += usage.get('completion_tokens', 0)

final = {
    'project_name': 'Strategy Workflow + Runtime Orchestrator (Phase 1)',
    'scope_version': 'advanced',
    'compact_mode': True,
    'contract_units': results,
    'consolidation_notes': {
        'generated_by': 'generate_contracts_atomic.py',
        'strategy': 'one-contract-per-artifact then consolidated',
        'artifacts': [name for name, _ in TASKS]
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
    'model': f'{MODEL}|atomic-contracts-compact',
    'input_tokens': usage_totals['prompt_tokens'],
    'output_tokens': usage_totals['completion_tokens'],
    'cost_usd': None,
    'timestamp': now
}
manifest['last_modified'] = now
(RUN_DIR / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
print('OK: wrote consolidated 04_contracts.json from compact atomic contract files')
