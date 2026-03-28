#!/usr/bin/env python3
import json, re, subprocess, sys, tempfile, hashlib
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path('/home/robotin/.openclaw/workspace-meta-planner')
RUN_DIR = WORKSPACE / 'runs' / 'strategy-runtime-1'
MODELS = json.loads((WORKSPACE / 'models.json').read_text())
CONFIG = json.loads((WORKSPACE / 'planner_config.json').read_text())
SKILL = (WORKSPACE / 'skills' / 'contract-designer' / 'SKILL.md').read_text(encoding='utf-8')

parts = []
for artifact in ['03_data_flow_map']:
    p = RUN_DIR / f'{artifact}.json'
    if p.exists():
        parts.append(f"=== {artifact}.json ===\n{p.read_text(encoding='utf-8')}\n=== END {artifact}.json ===")
for fname in ['system_configuration.md']:
    p = WORKSPACE / fname
    if p.exists():
        parts.append(f"=== {fname} ===\n{p.read_text(encoding='utf-8')}\n=== END {fname} ===")
parts.append(f"=== models.json ===\n{(WORKSPACE/'models.json').read_text(encoding='utf-8')}\n=== END models.json ===")
adj = RUN_DIR / 'gate_1_adjustments.json'
if adj.exists():
    data = json.loads(adj.read_text())
    parts.append(f"=== HUMAN ADJUSTMENTS FROM GATE #1 (mandatory) ===\n{data.get('adjustments','')}\n=== END ADJUSTMENTS ===")
parts.append("=== EXECUTION OVERRIDE ===\nDesign for ADVANCED scope. This is mandatory. Do not emit MVP/Standard recommendation content. Prioritize complete precise contracts and schemas over brevity. Output ONLY valid JSON matching the contracts schema.\n=== END EXECUTION OVERRIDE ===")
user_prompt = '\n\n'.join(parts)

proxy_url = MODELS['litellm_proxy']
api_key = MODELS.get('litellm_api_key','')
model = MODELS['agents']['contract_designer']['model']
max_tokens = 12000

payload = {
    'model': model,
    'max_tokens': max_tokens,
    'messages': [
        {'role': 'system', 'content': SKILL},
        {'role': 'user', 'content': user_prompt},
    ],
}

with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=True)
    tmp = f.name

cmd = ['curl','-s','-S','--max-time',str(CONFIG['defaults']['curl_max_time']),'-H','Content-Type: application/json']
if api_key:
    cmd += ['-H', f'Authorization: Bearer {api_key}']
cmd += ['--data-binary', f'@{tmp}', f'{proxy_url}/v1/chat/completions']
res = subprocess.run(cmd, capture_output=True, text=True, timeout=CONFIG['defaults']['curl_max_time']+CONFIG['defaults']['subprocess_buffer'])
Path(tmp).unlink(missing_ok=True)
if res.returncode != 0:
    print(res.stderr)
    sys.exit(1)
resp = json.loads(res.stdout)
content = resp['choices'][0]['message']['content']
(RUN_DIR / 'debug_contract_designer_response_advanced.txt').write_text(content, encoding='utf-8')

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
    print(f'JSON parse failed: {e}')
    print('Raw saved to debug_contract_designer_response_advanced.txt')
    sys.exit(2)

out = RUN_DIR / '04_contracts.json'
out.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding='utf-8')
subprocess.run([sys.executable, str(WORKSPACE/'scripts'/'validate_schema.py'), 'strategy-runtime-1', '04_contracts'], check=True)
manifest = json.loads((RUN_DIR/'manifest.json').read_text())
usage = resp.get('usage', {})
file_hash = hashlib.md5(out.read_text(encoding='utf-8').encode()).hexdigest()[:8]
now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
manifest['artifacts']['04_contracts'] = {
  'status':'fresh','hash':file_hash,'model':model,
  'input_tokens': usage.get('prompt_tokens',0),
  'output_tokens': usage.get('completion_tokens',0),
  'cost_usd': None,
  'timestamp': now
}
manifest['last_modified'] = now
(RUN_DIR/'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
print('OK: wrote and validated 04_contracts.json')
