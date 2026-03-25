#!/usr/bin/env python3
"""
spawn_narrative.py — Spawn Narrative Architect via Claude Sonnet API

Reads SKILL.md + case configs, calls Claude API via streaming curl (TL-01),
extracts JSON from the response and writes it to disk.

Usage:
  python3 spawn_narrative.py <case_slug>                  # generates case-plan.json
  python3 spawn_narrative.py <case_slug> --phase plan     # generates case-plan.json
  python3 spawn_narrative.py <case_slug> --phase catalog  # generates clue_catalog.json (requires existing case-plan.json)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path('/home/robotin/.openclaw/workspace-declassified')
DEFAULT_MODEL = 'claude-sonnet-4-6'
MAX_TOKENS = 16384


def load_text(path):
    return Path(path).read_text(encoding='utf-8')


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_api_key():
    """Load ANTHROPIC_API_KEY from env or .env file."""
    key = os.environ.get('ANTHROPIC_API_KEY', '')
    if key:
        return key
    env_path = WORKSPACE.parent / '.env'
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith('ANTHROPIC_API_KEY='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    raise ValueError(
        'ANTHROPIC_API_KEY not set. Set it in environment or ~/.openclaw/.env'
    )


def call_claude(api_key, model, system_prompt, user_prompt, max_tokens=MAX_TOKENS):
    """Call Anthropic API with streaming via curl (TL-01: never use Python requests in WSL)."""
    payload = json.dumps({
        'model': model,
        'max_tokens': max_tokens,
        'stream': True,
        'system': system_prompt,
        'messages': [{'role': 'user', 'content': user_prompt}]
    }, ensure_ascii=True)

    with tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False) as f:
        f.write(payload.encode('utf-8'))
        tmp_path = f.name

    try:
        result = subprocess.run([
            'curl', '-s', '-S', '-N', '--max-time', '600',
            'https://api.anthropic.com/v1/messages',
            '-H', f'x-api-key: {api_key}',
            '-H', 'anthropic-version: 2023-06-01',
            '-H', 'content-type: application/json',
            '--data-binary', f'@{tmp_path}'
        ], capture_output=True, text=True, timeout=650)

        if result.returncode != 0:
            raise Exception(f'curl failed (rc={result.returncode}): {result.stderr[:200]}')

        if not result.stdout.strip():
            raise Exception(f'Empty response. stderr: {result.stderr[:200]}')

        # Parse SSE stream
        full_text = ''
        input_tokens = 0
        output_tokens = 0
        for line in result.stdout.split('\n'):
            if line.startswith('data: '):
                try:
                    event = json.loads(line[6:])
                    etype = event.get('type', '')
                    if etype == 'content_block_delta':
                        delta = event.get('delta', {})
                        if delta.get('type') == 'text_delta':
                            full_text += delta.get('text', '')
                    elif etype == 'message_delta':
                        usage = event.get('usage', {})
                        output_tokens = usage.get('output_tokens', output_tokens)
                    elif etype == 'message_start':
                        usage = event.get('message', {}).get('usage', {})
                        input_tokens = usage.get('input_tokens', 0)
                    elif etype == 'error':
                        err = event.get('error', {})
                        raise Exception(f'API error: {err.get("message", str(err))}')
                    elif etype == 'message_stop':
                        break  # Stream complete
                except json.JSONDecodeError:
                    pass

        if not full_text:
            raise Exception(f'No text in stream. Response starts: {result.stdout[:300]}')

        return full_text, {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': input_tokens + output_tokens
        }
    finally:
        os.unlink(tmp_path)


def extract_json(text):
    """Extract JSON object from Claude's response (may be in code fences or bare)."""
    # Try code-fenced JSON first (tolerate missing closing fence by taking everything after the opening fence)
    m = re.search(r'```json?\s*\n(.*?)(?:```|\Z)', text, re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        # Strip trailing fence remnants if any
        candidate = re.sub(r'```\s*$', '', candidate).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Try to find the outermost { ... } block
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                candidate = text[start:i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    start = None

    raise ValueError('Could not extract valid JSON from response')


def log_cost_to_manifest(case_dir, artifact_name, usage, cost):
    """Log a single API call's cost to manifest.json."""
    manifest_path = case_dir / 'manifest.json'
    if not manifest_path.exists():
        return
    try:
        manifest = load_json(manifest_path)
        if 'cost_tracking' not in manifest:
            manifest['cost_tracking'] = {'phases': {}, 'totals': {}, 'images': {}}
        ct = manifest['cost_tracking']
        phase = ct.setdefault('phases', {}).setdefault('narrative_architect', {
            'calls': [], 'total_cost': 0,
            'total_input_tokens': 0, 'total_output_tokens': 0
        })
        from datetime import datetime
        phase['calls'].append({
            'timestamp': datetime.now().isoformat(),
            'agent': 'narrative-architect',
            'model': DEFAULT_MODEL,
            'input_tokens': usage['input_tokens'],
            'output_tokens': usage['output_tokens'],
            'cost_usd': round(cost, 4),
            'artifact': artifact_name
        })
        phase['total_cost'] = round(phase['total_cost'] + cost, 4)
        phase['total_input_tokens'] += usage['input_tokens']
        phase['total_output_tokens'] += usage['output_tokens']
        totals = ct.setdefault('totals', {})
        totals['input_tokens'] = (totals.get('input_tokens') or 0) + usage['input_tokens']
        totals['output_tokens'] = (totals.get('output_tokens') or 0) + usage['output_tokens']
        totals['estimated_total_usd'] = round((totals.get('estimated_total_usd') or 0) + cost, 4)
        totals['api_calls'] = (totals.get('api_calls') or 0) + 1
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(f"  Cost logged to manifest.json")
    except Exception as e:
        print(f"  WARN: Could not update manifest cost tracking: {e}")


def generate_plan(slug, case_dir, config_dir, skill_md, case_config, tier, tier_constraints, available_types, lessons, api_key):
    """Generate case-plan.json (Phase 2a)."""
    system_prompt = f"""You are the Narrative Architect for Declassified Cases.

{skill_md}

=== CONTEXT PROVIDED BELOW ===
You have been given: case_config.json, tier_definitions for this tier, doc_type_catalog.json, and lessons_learned.json.
Generate ONLY case-plan.json. Output the complete JSON and nothing else (no explanation, no markdown outside the JSON fence).
"""

    user_prompt = f"""Generate case-plan.json for this case.

CASE CONFIG:
{json.dumps(case_config, indent=2)}

TIER: {tier}
TIER CONSTRAINTS:
{json.dumps(tier_constraints, indent=2)}

AVAILABLE DOCUMENT TYPES (from doc_type_catalog.json):
{json.dumps(available_types, indent=2)}
You may also use custom types not in this list — just add a design_hint field (>=30 chars) to those documents in clue_catalog.

LESSONS LEARNED (mistakes to avoid):
{json.dumps(lessons.get('anti_patterns', lessons.get('lessons', [])), indent=2, default=str)}

INSTRUCTION:
Generate the complete case-plan.json following the skeleton in your SKILL.md exactly.
Include: tier, slug, title, logline, setting, victim, culprit (with motive >=50 chars, method_steps >=3, the_almost, motive_specificity_test), pois (with ALL required fields), timeline (>=8 events), contradictions (>=1 resolving in C+), evidence_chain (6-12 steps), envelopes (with "docs" arrays), experiential_style, emotional_arc, trojan_horse_docs (>=2), social_media_plan.
Output ONLY the JSON wrapped in ```json fences. No other text."""

    print(f"\nCalling Claude API ({DEFAULT_MODEL}) for case-plan.json...")
    print(f"  This may take 1-3 minutes...")

    response_text, usage = call_claude(api_key, DEFAULT_MODEL, system_prompt, user_prompt)

    print(f"  Response received: {usage['input_tokens']:,} in / {usage['output_tokens']:,} out")
    cost = (usage['input_tokens'] * 3.0 + usage['output_tokens'] * 15.0) / 1_000_000
    print(f"  Estimated cost: ${cost:.4f}")

    print("\nExtracting case-plan.json...")
    try:
        case_plan = extract_json(response_text)
    except ValueError as e:
        debug_path = case_dir / 'debug_narrative_response.txt'
        debug_path.write_text(response_text, encoding='utf-8')
        print(f"ERROR: {e}")
        print(f"  Raw response saved to: {debug_path}")
        sys.exit(1)

    # Validate basic structure
    required_keys = ['culprit', 'pois', 'timeline', 'envelopes']
    missing = [k for k in required_keys if k not in case_plan]
    if missing:
        print(f"WARNING: case-plan.json missing keys: {missing}")

    # Write case-plan.json
    output_path = case_dir / 'case-plan.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(case_plan, f, indent=2, ensure_ascii=False)
    print(f"\nWrote: {output_path}")

    # Print summary
    pois = case_plan.get('pois', [])
    envelopes = case_plan.get('envelopes', {})
    total_docs = sum(len(v.get('docs', [])) for v in envelopes.values() if isinstance(v, dict))
    contradictions = case_plan.get('contradictions', [])
    timeline = case_plan.get('timeline', [])

    print(f"\n  Title: {case_plan.get('title', '?')}")
    print(f"  POIs: {len(pois)}")
    print(f"  Documents: {total_docs} across {len(envelopes)} envelopes")
    print(f"  Timeline events: {len(timeline)}")
    print(f"  Contradictions: {len(contradictions)}")
    print(f"  Culprit: {case_plan.get('culprit', {}).get('poi_id', '?')}")

    log_cost_to_manifest(case_dir, 'case-plan.json', usage, cost)
    return case_plan


def generate_catalog(slug, case_dir, config_dir, skill_md, case_config, tier, tier_constraints, available_types, lessons, api_key):
    """Generate clue_catalog.json (Phase 2b) by ENVELOPE chunks to avoid output truncation."""
    plan_path = case_dir / 'case-plan.json'
    if not plan_path.exists():
        print(f"ERROR: case-plan.json not found at {plan_path}")
        print(f"Run --phase plan first.")
        sys.exit(1)

    case_plan = load_json(plan_path)

    system_prompt = f"""You are the Narrative Architect for Declassified Cases.

{skill_md}

=== CONTEXT PROVIDED BELOW ===
You have been given: case_config.json, tier_definitions for this tier, doc_type_catalog.json, lessons_learned.json, and the already-generated case-plan.json.
You will be asked to generate clue_catalog documents in smaller batches (one envelope at a time).
Output the complete JSON and nothing else (no explanation, no markdown outside the JSON fence).
"""

    envs = case_plan.get('envelopes', {})
    envelope_order = [k for k in ['A', 'B', 'C', 'D', 'R'] if isinstance(envs.get(k), dict)]

    all_docs = []
    usage_sum = {'input_tokens': 0, 'output_tokens': 0}
    total_cost = 0.0

    for env_key in envelope_order:
        env_obj = envs.get(env_key, {})
        env_doc_ids = env_obj.get('docs', []) if isinstance(env_obj, dict) else []
        env_doc_ids = [d for d in env_doc_ids if isinstance(d, str)]
        if not env_doc_ids:
            continue

        user_prompt = f"""Generate clue_catalog JSON for ONLY envelope {env_key}.

CASE CONFIG:
{json.dumps(case_config, indent=2)}

TIER: {tier}
TIER CONSTRAINTS:
{json.dumps(tier_constraints, indent=2)}

AVAILABLE DOCUMENT TYPES (from doc_type_catalog.json):
{json.dumps(available_types, indent=2)}

LESSONS LEARNED (mistakes to avoid):
{json.dumps(lessons.get('anti_patterns', lessons.get('lessons', [])), indent=2, default=str)}

CASE-PLAN.JSON (source of truth for POIs/contradictions/timeline; do NOT invent new doc_ids):
{json.dumps(case_plan, indent=2)}

DOC IDS TO GENERATE (MUST ALL APPEAR EXACTLY ONCE in documents[*].doc_id):
{json.dumps(env_doc_ids, indent=2)}

INSTRUCTION:
Return JSON with this exact top-level shape:
{{
  "slug": "{slug}",
  "documents": [ ... ]
}}

Rules:
- Generate ONLY the documents for envelope {env_key} (doc_ids listed above). No extras.
- Each document must include ALL required fields + correct envelope and sequence_number.
- Use ONLY valid player_purpose values.
- Every reveals field must be >=30 chars and specific.
Output ONLY the JSON wrapped in ```json fences. No other text."""

        print(f"\nCalling Claude API ({DEFAULT_MODEL}) for clue_catalog envelope {env_key}...")
        response_text, usage = call_claude(api_key, DEFAULT_MODEL, system_prompt, user_prompt)
        usage_sum['input_tokens'] += usage.get('input_tokens', 0)
        usage_sum['output_tokens'] += usage.get('output_tokens', 0)
        cost = (usage.get('input_tokens', 0) * 3.0 + usage.get('output_tokens', 0) * 15.0) / 1_000_000
        total_cost += cost
        print(f"  Response received: {usage['input_tokens']:,} in / {usage['output_tokens']:,} out (est ${cost:.4f})")

        try:
            chunk = extract_json(response_text)
        except ValueError as e:
            debug_path = case_dir / f'debug_clue_catalog_{env_key}.txt'
            debug_path.write_text(response_text, encoding='utf-8')
            print(f"ERROR: {e}")
            print(f"  Raw response saved to: {debug_path}")
            sys.exit(1)

        docs_arr = chunk.get('documents', []) if isinstance(chunk, dict) else []
        if not isinstance(docs_arr, list) or not docs_arr:
            debug_path = case_dir / f'debug_clue_catalog_{env_key}.txt'
            debug_path.write_text(response_text, encoding='utf-8')
            print(f"ERROR: envelope {env_key} chunk missing non-empty documents array")
            print(f"  Raw response saved to: {debug_path}")
            sys.exit(1)

        # Coverage sanity
        got_ids = {d.get('doc_id') for d in docs_arr if isinstance(d, dict)}
        missing = [d for d in env_doc_ids if d not in got_ids]
        if missing:
            print(f"  WARNING: Envelope {env_key} missing doc_ids: {missing}")

        all_docs.extend(docs_arr)

    clue_catalog = {"slug": slug, "documents": all_docs}

    output_path = case_dir / 'clue_catalog.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(clue_catalog, f, indent=2, ensure_ascii=False)
    print(f"\nWrote: {output_path}")
    print(f"  Clue catalog documents: {len(all_docs)}")

    log_cost_to_manifest(case_dir, 'clue_catalog.json', usage_sum, total_cost)
    return clue_catalog


def main():
    parser = argparse.ArgumentParser(description='Spawn Narrative Architect via Claude API')
    parser.add_argument('slug', help='Case slug (e.g. the-last-livestream)')
    parser.add_argument('--phase', choices=['plan', 'catalog'], default='plan',
                        help='Which artifact to generate (default: plan)')
    args = parser.parse_args()

    slug = args.slug
    config_dir = WORKSPACE / 'cases' / 'config'
    case_dir = WORKSPACE / 'cases' / 'exports' / slug

    if not case_dir.exists():
        print(f"ERROR: Case directory not found: {case_dir}")
        print(f"Run start_new_case.sh first: bash cases/scripts/start_new_case.sh {slug} <TIER>")
        sys.exit(1)

    # Load shared inputs
    print(f"Loading inputs for case: {slug} (phase: {args.phase})")
    skill_md = load_text(WORKSPACE / 'skills' / 'narrative-architect' / 'SKILL.md')
    case_config = load_json(case_dir / 'case_config.json')
    tier_defs = load_json(config_dir / 'tier_definitions.json')
    doc_type_catalog = load_json(config_dir / 'doc_type_catalog.json')

    lessons_path = config_dir / 'lessons_learned.json'
    lessons = load_json(lessons_path) if lessons_path.exists() else {}

    tier = case_config.get('tier', 'NORMAL')
    tier_constraints = tier_defs.get(tier, {})
    idea = case_config.get('idea', case_config.get('description', ''))
    available_types = sorted(doc_type_catalog.get('types', {}).keys())

    print(f"  Tier: {tier}")
    print(f"  Idea: {idea[:100]}...")

    api_key = load_api_key()

    if args.phase == 'plan':
        generate_plan(slug, case_dir, config_dir, skill_md, case_config,
                      tier, tier_constraints, available_types, lessons, api_key)
    else:
        generate_catalog(slug, case_dir, config_dir, skill_md, case_config,
                         tier, tier_constraints, available_types, lessons, api_key)

    print("\nDone.")


if __name__ == '__main__':
    main()
