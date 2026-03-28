#!/usr/bin/env python3
import json, re, subprocess, sys, hashlib
from pathlib import Path
from datetime import datetime, timezone

W = Path('/home/robotin/.openclaw/workspace-meta-planner')
R = W / 'runs' / 'strategy-runtime-1'
RAW = R / 'debug_implementation_planner_response.txt'
OUT = R / '06_implementation_plan.json'

raw = RAW.read_text(encoding='utf-8')
# Try fenced first, then outer object.
m = re.search(r'```json\s*(.*?)```', raw, re.S)
text = m.group(1).strip() if m else raw.strip()
if not text.startswith('{'):
    s = text.find('{')
    e = text.rfind('}')
    if s >= 0 and e > s:
        text = text[s:e+1]

# Try direct parse, then repair.
try:
    data = json.loads(text)
except Exception:
    repair = subprocess.run([sys.executable, str(W/'scripts'/'json_repair.py'), str(RAW), str(OUT)], capture_output=True, text=True)
    if repair.returncode != 0:
        print(repair.stderr or repair.stdout)
        sys.exit(2)
    data = json.loads(OUT.read_text(encoding='utf-8'))
else:
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

subprocess.run([sys.executable, str(W/'scripts'/'validate_schema.py'), 'strategy-runtime-1', '06_implementation_plan'], check=True)
manifest = json.loads((R/'manifest.json').read_text(encoding='utf-8'))
file_hash = hashlib.md5(OUT.read_text(encoding='utf-8').encode()).hexdigest()[:8]
now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
manifest['artifacts']['06_implementation_plan'] = {
    'status':'fresh','hash':file_hash,'model':'claude-sonnet46|rescued-from-debug','input_tokens':None,'output_tokens':None,'cost_usd':None,'timestamp':now
}
manifest['last_modified']=now
(R/'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
print('OK rescued 06_implementation_plan.json')
