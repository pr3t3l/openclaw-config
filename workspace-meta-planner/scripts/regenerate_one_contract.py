#!/usr/bin/env python3
import json, re, subprocess, tempfile, sys
from pathlib import Path

WORKSPACE = Path('/home/robotin/.openclaw/workspace-meta-planner')
RUN_DIR = WORKSPACE / 'runs' / 'strategy-runtime-1'
OUT_DIR = RUN_DIR / 'contracts_atomic'
MODELS = json.loads((WORKSPACE / 'models.json').read_text())
CONFIG = json.loads((WORKSPACE / 'planner_config.json').read_text())
SKILL = (WORKSPACE / 'skills' / 'contract-designer' / 'SKILL.md').read_text(encoding='utf-8')
MODEL = MODELS['agents']['contract_designer']['model']
PROXY = MODELS['litellm_proxy']
API_KEY = MODELS.get('litellm_api_key', '')
MAX_TOKENS = 3500

TASK_MAP = {
    '04_growth_run_manifest': 'Generate ONLY the compact contract for growth_run_manifest.json.',
    '05_runtime_state': 'Generate ONLY the compact contract for runtime_state.json.',
    '06_market_analysis': 'Generate ONLY the compact contract for market_analysis.json.',
    '07_buyer_persona': 'Generate ONLY the compact contract for buyer_persona.json.',
    '08_brand_strategy': 'Generate ONLY the compact contract for brand_strategy.json.',
    '09_seo_architecture': 'Generate ONLY the compact contract for seo_architecture.json.',
    '10_channel_strategy': 'Generate ONLY the compact contract for channel_strategy.json.',
    '11_interface_contract_marketing_v1': 'Generate ONLY the compact contract for interface_contract_marketing_v1.json, including exact paths, required fields, and version pinning rules.',
    '12_gate_definitions': 'Generate ONLY the compact contract for gate_definitions.json covering S1 and S2, approve/reject/adjust, timeout, expiration behavior, and what is shown to the human.',
    '13_telegram_security': 'Generate ONLY the compact contract for telegram_security.json covering whitelist user_ids, auth rules, unauthorized handling, and allowed commands.',
    '14_invalidation_rules': 'Generate ONLY the compact contract for invalidation_rules.json covering hard/soft invalidation rules, triggers, and downstream effects.',
    '15_rollback_policy': 'Generate ONLY the compact contract for rollback_policy.json covering atomic rollback, complete/partial/failed definitions, hashes, audit, and observability fields.'
}

name = sys.argv[1]
if name not in TASK_MAP:
    print('Unknown contract key')
    sys.exit(1)

base_parts = []
p = RUN_DIR / '03_data_flow_map.json'
if p.exists():
    base_parts.append(f"=== 03_data_flow_map.json ===\n{p.read_text(encoding='utf-8')}\n=== END 03_data_flow_map.json ===")
adj = RUN_DIR / 'gate_1_adjustments.json'
if adj.exists():
    data = json.loads(adj.read_text())
    base_parts.append(f"=== HUMAN ADJUSTMENTS FROM GATE #1 (mandatory) ===\n{data.get('adjustments','')}\n=== END ADJUSTMENTS ===")
base_parts.append("=== EXECUTION OVERRIDE ===\nDesign for ADVANCED scope. Generate ONLY the requested single contract/spec artifact in COMPACT MODE. Output ONLY valid JSON. For each contract include ONLY artifact_name, schema_definition, produced_by, consumed_by, validation_rules. Do NOT include examples, prose, or long descriptions.\n=== END EXECUTION OVERRIDE ===")
prompt = '\n\n'.join(base_parts) + '\n\n=== ARTIFACT TASK ===\n' + TASK_MAP[name] + '\n=== END ARTIFACT TASK ==='

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
    print(res.stderr)
    sys.exit(1)
resp = json.loads(res.stdout)
content = resp['choices'][0]['message']['content']
raw_path = OUT_DIR / f'{name}.raw.txt'
raw_path.write_text(content, encoding='utf-8')

m = re.search(r'```json\s*(.*?)```', content, re.S)
text = m.group(1).strip() if m else content.strip()
if not text.startswith('{'):
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        text = text[start:end+1]
try:
    parsed = json.loads(text)
except Exception as e:
    print(f'PARSE_FAIL: {e}')
    sys.exit(2)

(OUT_DIR / f'{name}.json').write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding='utf-8')
print('OK')
