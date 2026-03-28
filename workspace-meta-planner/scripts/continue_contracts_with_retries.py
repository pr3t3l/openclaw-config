#!/usr/bin/env python3
import subprocess, sys
from pathlib import Path

WORKSPACE = Path('/home/robotin/.openclaw/workspace-meta-planner')
OUT_DIR = WORKSPACE / 'runs' / 'strategy-runtime-1' / 'contracts_atomic'
SCRIPT = WORKSPACE / 'scripts' / 'regenerate_one_contract.py'

TASKS = [
    '08_brand_strategy',
    '09_seo_architecture',
    '10_channel_strategy',
    '11_interface_contract_marketing_v1',
    '12_gate_definitions',
    '13_telegram_security',
    '14_invalidation_rules',
    '15_rollback_policy',
]

for task in TASKS:
    json_path = OUT_DIR / f'{task}.json'
    if json_path.exists():
        print(f'SKIP {task} already exists')
        continue
    success = False
    for attempt in range(1, 4):
        print(f'RUN {task} attempt {attempt}/3')
        r = subprocess.run([sys.executable, str(SCRIPT), task], capture_output=True, text=True)
        print(r.stdout.strip())
        if r.returncode == 0 and json_path.exists():
            success = True
            break
        else:
            print((r.stderr or '').strip())
    if not success:
        print(f'FAIL_3X {task}')
        sys.exit(2)

print('ALL_REMAINING_OK')
