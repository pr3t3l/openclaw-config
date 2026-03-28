#!/usr/bin/env python3
import json, re, subprocess, tempfile, sys, hashlib
from pathlib import Path
from datetime import datetime, timezone

W = Path('/home/robotin/.openclaw/workspace-meta-planner')
R = W / 'runs' / 'strategy-runtime-1'
OUT = R / 'implementation_blocks'
OUT.mkdir(parents=True, exist_ok=True)
MODELS = json.loads((W / 'models.json').read_text())
CONFIG = json.loads((W / 'planner_config.json').read_text())
SKILL = (W / 'skills' / 'implementation-planner' / 'SKILL.md').read_text(encoding='utf-8')
MODEL = MODELS['agents']['implementation_planner']['model']
PROXY = MODELS['litellm_proxy']
API_KEY = MODELS.get('litellm_api_key', '')
MAX_TOKENS = 5000

context = []
for name in ['00_intake_summary.json','01_gap_analysis.json','02_scope_decision.json','03_data_flow_map.json','04_contracts.json','05_architecture_decision.json']:
    p = R / name
    if p.exists():
        context.append(f"=== {name} ===\n{p.read_text(encoding='utf-8')}\n=== END {name} ===")
context.append("=== EXECUTION OVERRIDE ===\nDesign for ADVANCED scope. Generate implementation plan by block. Output ONLY valid JSON. Each block must match the implementation-plan style and contain phases[] plus optional deferred_to_v2[] only if relevant.\n=== END EXECUTION OVERRIDE ===")
BASE = '\n\n'.join(context)

BLOCKS = [
    ('01_foundation', 'Generate implementation phases ONLY for foundation/bootstrap: directory layout, config/constants, preflight_check.py, spawn_core.py, artifact_validator.py, state_lock_manager.py.'),
    ('02_strategy_execution', 'Generate implementation phases ONLY for strategy execution: market_analysis_agent, buyer_persona_agent, brand_strategy_agent, seo_architecture_agent, channel_strategy_agent, strategy_runner.py.'),
    ('03_gates_and_runtime', 'Generate implementation phases ONLY for gates and runtime: gate_summary_agent, gate_handler.py, runtime_orchestrator.py, rollback_executor.py, invalidation handling, state promotion.'),
    ('04_telegram_and_entrypoints', 'Generate implementation phases ONLY for Telegram and entrypoints: telegram_bot.py, run_strategy.sh, auth/whitelist handling, operator workflows.'),
    ('05_testing_and_e2e', 'Generate implementation phases ONLY for testing, integration tests, end-to-end validation, rollout sequencing, and deferred_to_v2 list.')
]


def extract_json(content):
    m = re.search(r'```json\s*(.*?)```', content, re.S)
    text = m.group(1).strip() if m else content.strip()
    if not text.startswith('{'):
        s = text.find('{')
        e = text.rfind('}')
        if s >= 0 and e > s:
            text = text[s:e+1]
    return json.loads(text)


def call_block(name, task):
    prompt = BASE + '\n\n=== BLOCK TASK ===\n' + task + '\n=== END BLOCK TASK ==='
    payload = {'model': MODEL, 'max_tokens': MAX_TOKENS, 'messages': [{'role':'system','content':SKILL},{'role':'user','content':prompt}]}
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
    raw_path = OUT / f'{name}.raw.txt'
    raw_path.write_text(content, encoding='utf-8')
    try:
        parsed = extract_json(content)
    except Exception:
        repair = subprocess.run([sys.executable, str(W/'scripts'/'json_repair.py'), str(raw_path), str(OUT/f'{name}.repaired.json')], capture_output=True, text=True)
        if repair.returncode != 0:
            raise RuntimeError(f'{name} failed parse and repair: {repair.stderr or repair.stdout}')
        parsed = json.loads((OUT/f'{name}.repaired.json').read_text(encoding='utf-8'))
    return parsed, resp.get('usage', {})

results = {}
usage_totals = {'prompt_tokens':0, 'completion_tokens':0}
for name, task in BLOCKS:
    ok = False
    for attempt in range(1,4):
        try:
            parsed, usage = call_block(name, task)
            (OUT/f'{name}.json').write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding='utf-8')
            results[name] = parsed
            usage_totals['prompt_tokens'] += usage.get('prompt_tokens',0)
            usage_totals['completion_tokens'] += usage.get('completion_tokens',0)
            ok = True
            break
        except Exception as e:
            print(f'RETRY {name} {attempt}/3 failed: {e}')
    if not ok:
        print(f'FAIL_3X {name}')
        sys.exit(2)

all_phases = []
deferred = []
for name, _ in BLOCKS:
    block = results[name]
    all_phases.extend(block.get('phases', []))
    deferred.extend(block.get('deferred_to_v2', []))
all_phases = sorted(all_phases, key=lambda x: x.get('phase_number', 999))
final = {
    'project_name': 'Strategy Workflow + Runtime Orchestrator (Phase 1)',
    'phases': all_phases,
    'deferred_to_v2': deferred,
    'total_estimated_hours': sum(float(p.get('estimated_effort_hours',0)) for p in all_phases),
    'red_team_findings': [],
    'red_team_merged': False
}
final_path = R / '06_implementation_plan.json'
final_path.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding='utf-8')
subprocess.run([sys.executable, str(W/'scripts'/'validate_schema.py'), 'strategy-runtime-1', '06_implementation_plan'], check=True)
manifest = json.loads((R/'manifest.json').read_text(encoding='utf-8'))
file_hash = hashlib.md5(final_path.read_text(encoding='utf-8').encode()).hexdigest()[:8]
now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
manifest['artifacts']['06_implementation_plan'] = {'status':'fresh','hash':file_hash,'model':f'{MODEL}|by-blocks|retries','input_tokens':usage_totals['prompt_tokens'],'output_tokens':usage_totals['completion_tokens'],'cost_usd':None,'timestamp':now}
manifest['last_modified']=now
(R/'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
print('OK_IMPLEMENTATION_BLOCKS')
