#!/usr/bin/env python3
"""
spawn_agent.py — Generic agent spawner via Claude Sonnet API

Reads any skill's SKILL.md + case files, calls Claude API via streaming
curl (TL-01), extracts JSON output files, and writes them to the case dir.

Usage:
  python3 spawn_agent.py <case_slug> <skill_name> "<instruction>"

Examples:
  python3 spawn_agent.py cyber-ghost art-director "Generate art_briefs.json and scene_descriptions.json"
  python3 spawn_agent.py cyber-ghost experience-designer "Generate experience_design.json"

The instruction tells the agent what to produce. The script auto-detects
JSON output files from the response and writes them to the case directory.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

WORKSPACE = Path('/home/robotin/.openclaw/workspace-declassified')
DEFAULT_MODEL = 'claude-sonnet-4-6'
MAX_TOKENS = 16384


def load_text(path):
    return Path(path).read_text(encoding='utf-8')


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_json_safe(path):
    """Load JSON if file exists, else return empty dict."""
    if Path(path).exists():
        return load_json(path)
    return {}


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


def extract_all_json_blocks(text):
    """Extract ALL JSON blocks from the response (multiple fenced blocks or bare objects).

    Returns list of (label, parsed_json) tuples. Label is derived from
    the line before the fence (e.g. "art_briefs.json:") or "block_N".
    """
    blocks = []

    # Find all code-fenced JSON blocks with optional label on preceding line
    pattern = r'(?:^|\n)([^\n]*?\n)?```json?\s*\n(.*?)(?:```|\Z)'
    for m in re.finditer(pattern, text, re.DOTALL):
        label_line = (m.group(1) or '').strip()
        candidate = m.group(2).strip()
        candidate = re.sub(r'```\s*$', '', candidate).strip()
        try:
            parsed = json.loads(candidate)
            # Try to extract a filename from the label line
            label = _extract_label(label_line, len(blocks))
            blocks.append((label, parsed))
        except json.JSONDecodeError:
            pass

    if blocks:
        return blocks

    # Fallback: find bare top-level JSON objects
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
                    parsed = json.loads(candidate)
                    blocks.append((f'block_{len(blocks)}', parsed))
                except json.JSONDecodeError:
                    pass
                start = None

    return blocks


def _extract_label(label_line, index):
    """Try to derive a filename from the label line before a JSON fence."""
    if not label_line:
        return f'block_{index}'
    # Look for patterns like "art_briefs.json:", "## art_briefs.json", "Output: art_briefs.json"
    m = re.search(r'(\w[\w-]*\.json)', label_line, re.IGNORECASE)
    if m:
        return m.group(1)
    return f'block_{index}'


def detect_output_files(blocks, instruction):
    """Map extracted JSON blocks to output filenames based on instruction and content.

    Returns list of (filename, parsed_json) tuples.
    """
    outputs = []

    # Extract expected filenames from instruction
    expected = re.findall(r'(\w[\w-]*\.json)', instruction, re.IGNORECASE)

    if len(blocks) == 1 and len(expected) == 1:
        # Simple case: one block, one expected file
        outputs.append((expected[0], blocks[0][1]))
        return outputs

    if len(blocks) == len(expected):
        # Same count: match by order
        for (label, parsed), fname in zip(blocks, expected):
            outputs.append((fname, parsed))
        return outputs

    # Try to match by label or content heuristics
    used = set()
    for label, parsed in blocks:
        fname = None
        # Check if label matches an expected filename
        if label in expected:
            fname = label
        else:
            # Content-based detection
            fname = _guess_filename(parsed, expected, used)
        if not fname:
            fname = label if label.endswith('.json') else f'{label}.json'
        outputs.append((fname, parsed))
        used.add(fname)

    return outputs


def _guess_filename(parsed, expected, used):
    """Guess filename from JSON content structure."""
    if not isinstance(parsed, dict):
        return None

    keys = set(parsed.keys())
    guesses = {
        'art_briefs.json': lambda k: 'briefs' in k or 'art_briefs' in k,
        'scene_descriptions.json': lambda k: 'scenes' in k or 'scene_descriptions' in k or 'descriptions' in k,
        'experience_design.json': lambda k: 'document_experience_map' in k or 'emotional_arc' in k,
        'case-plan.json': lambda k: 'culprit' in k and 'pois' in k,
        'clue_catalog.json': lambda k: 'documents' in k and 'culprit' not in k,
    }
    for fname, test in guesses.items():
        if fname in expected and fname not in used and test(keys):
            return fname
    return None


def extract_markdown_files(text):
    """Extract markdown content files from the response.

    Handles these patterns:
    1. ## A1_content.md / ### envelope_A/A1_content.md headers followed by content
    2. ```markdown fenced blocks with filename labels on the preceding line
    3. Filename: A1_content.md headers

    Returns list of (filepath, content) tuples where filepath is like
    "envelope_A/A1_content.md".
    """
    files = []
    seen = set()

    # Pattern 1: ```markdown fenced blocks with filename label
    fence_pattern = r'(?:^|\n)([^\n]*?_content\.md[^\n]*)\n```(?:markdown|md)?\s*\n(.*?)```'
    for m in re.finditer(fence_pattern, text, re.DOTALL):
        label_line = m.group(1).strip()
        content = m.group(2).strip()
        filepath = _resolve_md_filepath(label_line)
        if filepath and filepath not in seen and content:
            files.append((filepath, content))
            seen.add(filepath)

    if files:
        return files

    # Pattern 2: ## or ### headers containing _content.md, content runs until next header or EOF
    header_pattern = r'(?:^|\n)(#{1,4})\s+([^\n]*?_content\.md[^\n]*)\n'
    matches = list(re.finditer(header_pattern, text))
    for i, m in enumerate(matches):
        header_level = len(m.group(1))
        label_line = m.group(2).strip()
        start = m.end()
        # Content runs until the next header of same or higher level, or EOF
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text)
        content = text[start:end].strip()
        # Strip any leading/trailing code fences that wrap the whole content
        content = re.sub(r'^```(?:markdown|md)?\s*\n', '', content)
        content = re.sub(r'\n```\s*$', '', content)
        content = content.strip()
        filepath = _resolve_md_filepath(label_line)
        if filepath and filepath not in seen and content:
            files.append((filepath, content))
            seen.add(filepath)

    return files


def _resolve_md_filepath(label):
    """Extract a doc_id and resolve to envelope_X/XX_content.md path.

    Handles:
      "A1_content.md"
      "envelope_A/A1_content.md"
      "## A1_content.md"
      "### envelope_A/A1_content.md:"
      "Filename: A1_content.md"
    """
    # Find the _content.md filename
    m = re.search(r'(?:envelope_([A-Z])/)?([A-Z]\d+_content\.md)', label)
    if not m:
        return None
    envelope_from_path = m.group(1)
    filename = m.group(2)  # e.g. "A1_content.md"
    doc_id_letter = filename[0]  # First char = envelope letter
    envelope = envelope_from_path or doc_id_letter
    return f'envelope_{envelope}/{filename}'


def load_case_context(case_dir, config_dir):
    """Load all available case files as context for the agent."""
    context = {}

    # Case-level files
    for name in ['case_config.json', 'case-plan.json', 'clue_catalog.json',
                  'art_briefs.json', 'scene_descriptions.json',
                  'experience_design.json', 'manifest.json']:
        path = case_dir / name
        if path.exists():
            context[name] = load_json(path)

    # Config files
    for name in ['doc_type_catalog.json', 'tier_definitions.json',
                  'design_system.json', 'lessons_learned.json']:
        path = config_dir / name
        if path.exists():
            context[name] = load_json(path)

    return context


def log_cost_to_manifest(case_dir, skill_name, artifact_names, usage, cost):
    """Log API call cost to manifest.json."""
    manifest_path = case_dir / 'manifest.json'
    if not manifest_path.exists():
        return
    try:
        manifest = load_json(manifest_path)
        if 'cost_tracking' not in manifest:
            manifest['cost_tracking'] = {'phases': {}, 'totals': {}, 'images': {}}
        ct = manifest['cost_tracking']
        phase_key = skill_name.replace('-', '_')
        phase = ct.setdefault('phases', {}).setdefault(phase_key, {
            'calls': [], 'total_cost': 0,
            'total_input_tokens': 0, 'total_output_tokens': 0
        })
        phase['calls'].append({
            'timestamp': datetime.now().isoformat(),
            'agent': skill_name,
            'model': DEFAULT_MODEL,
            'input_tokens': usage['input_tokens'],
            'output_tokens': usage['output_tokens'],
            'cost_usd': round(cost, 4),
            'artifacts': artifact_names
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


def main():
    parser = argparse.ArgumentParser(
        description='Generic agent spawner via Claude API',
        epilog='Example: python3 spawn_agent.py cyber-ghost art-director '
               '"Generate art_briefs.json and scene_descriptions.json"'
    )
    parser.add_argument('slug', help='Case slug (e.g. cyber-ghost)')
    parser.add_argument('skill', help='Skill name (e.g. art-director, experience-designer)')
    parser.add_argument('instruction', help='What to generate (e.g. "Generate art_briefs.json and scene_descriptions.json")')
    parser.add_argument('--model', default=DEFAULT_MODEL, help=f'Model to use (default: {DEFAULT_MODEL})')
    parser.add_argument('--max-tokens', type=int, default=MAX_TOKENS, help=f'Max output tokens (default: {MAX_TOKENS})')
    parser.add_argument('--dry-run', action='store_true', help='Print prompts without calling API')
    args = parser.parse_args()

    slug = args.slug
    skill_name = args.skill
    config_dir = WORKSPACE / 'cases' / 'config'
    case_dir = WORKSPACE / 'cases' / 'exports' / slug
    skill_dir = WORKSPACE / 'skills' / skill_name

    # Validate paths
    if not case_dir.exists():
        print(f"ERROR: Case directory not found: {case_dir}")
        sys.exit(1)
    skill_path = skill_dir / 'SKILL.md'
    if not skill_path.exists():
        print(f"ERROR: Skill not found: {skill_path}")
        available = [d.name for d in (WORKSPACE / 'skills').iterdir() if d.is_dir() and (d / 'SKILL.md').exists()]
        print(f"  Available skills: {', '.join(sorted(available))}")
        sys.exit(1)

    # Load inputs
    print(f"Spawning agent: {skill_name}")
    print(f"  Case: {slug}")
    print(f"  Instruction: {args.instruction}")

    skill_md = load_text(skill_path)
    case_context = load_case_context(case_dir, config_dir)

    tier = case_context.get('case_config.json', {}).get('tier', 'NORMAL')

    # Build context section — include all available case files
    context_parts = []
    for name, data in sorted(case_context.items()):
        # Truncate very large files to avoid blowing context
        dumped = json.dumps(data, indent=2, default=str)
        if len(dumped) > 50000:
            dumped = dumped[:50000] + '\n... (truncated)'
        context_parts.append(f'### {name}\n```json\n{dumped}\n```')

    context_section = '\n\n'.join(context_parts)

    # Build system prompt
    system_prompt = f"""You are the {skill_name} agent for Declassified Cases, a physical detective mystery game.

{skill_md}

=== UNIVERSAL RULES ===
- WORKSPACE ROOT: {WORKSPACE}
- ALL file paths must be absolute.
- For JSON output: wrap in ```json fences. Label each with filename on the line before.
- For markdown content files (_content.md): use ## headers with the filename (e.g. "## A1_content.md") followed by the markdown content. Or use ```markdown fences with filename labels.
- If producing MULTIPLE files, output each in a SEPARATE section.
- No empty strings for required fields.
=== END UNIVERSAL RULES ===
"""

    # Build user prompt
    user_prompt = f"""{args.instruction}

CASE: {slug}
TIER: {tier}

=== CASE FILES (read these as context) ===

{context_section}

=== END CASE FILES ===

INSTRUCTION REMINDER: {args.instruction}
Output ONLY the JSON file(s) wrapped in ```json fences, each labeled with its filename."""

    if args.dry_run:
        print(f"\n=== SYSTEM PROMPT ({len(system_prompt)} chars) ===")
        print(system_prompt[:500] + '...')
        print(f"\n=== USER PROMPT ({len(user_prompt)} chars) ===")
        print(user_prompt[:500] + '...')
        print(f"\nDry run complete. Would call {args.model} with {len(system_prompt) + len(user_prompt)} chars.")
        return

    # Call Claude API
    api_key = load_api_key()
    print(f"\nCalling Claude API ({args.model})...")
    print(f"  This may take 1-3 minutes...")

    response_text, usage = call_claude(api_key, args.model, system_prompt, user_prompt, args.max_tokens)

    print(f"  Response received: {usage['input_tokens']:,} in / {usage['output_tokens']:,} out")
    cost = (usage['input_tokens'] * 3.0 + usage['output_tokens'] * 15.0) / 1_000_000
    print(f"  Estimated cost: ${cost:.4f}")

    # Determine if we should look for markdown files
    wants_markdown = ('_content.md' in args.instruction.lower()
                      or 'production engine' in args.instruction.lower()
                      or 'production-engine' in args.instruction.lower())

    # Extract JSON blocks
    print("\nExtracting output...")
    blocks = extract_all_json_blocks(response_text)
    md_files = []

    if wants_markdown or not blocks:
        md_files = extract_markdown_files(response_text)

    if not blocks and not md_files:
        debug_path = case_dir / f'debug_{skill_name}_response.txt'
        debug_path.write_text(response_text, encoding='utf-8')
        print(f"ERROR: No valid JSON or markdown files found in response")
        print(f"  Raw response saved to: {debug_path}")
        sys.exit(1)

    written = []

    # Write JSON output files
    if blocks:
        print(f"  Found {len(blocks)} JSON block(s)")
        outputs = detect_output_files(blocks, args.instruction)
        for fname, data in outputs:
            out_path = case_dir / fname
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            if isinstance(data, dict):
                top_keys = list(data.keys())[:5]
                size_info = f"keys: {top_keys}"
                for k in ['briefs', 'documents', 'scenes', 'descriptions']:
                    if k in data and isinstance(data[k], list):
                        size_info = f"{len(data[k])} {k}"
                        break
            else:
                size_info = f"type: {type(data).__name__}"

            print(f"  Wrote: {out_path} ({size_info})")
            written.append(fname)

    # Write markdown content files
    if md_files:
        print(f"  Found {len(md_files)} markdown file(s)")
        for filepath, content in md_files:
            out_path = case_dir / filepath
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding='utf-8')
            word_count = len(content.split())
            print(f"  Wrote: {out_path} ({word_count} words)")
            written.append(filepath)

    # Log cost
    log_cost_to_manifest(case_dir, skill_name, written, usage, cost)

    # Save debug response
    debug_path = case_dir / f'debug_{skill_name}_response.txt'
    debug_path.write_text(response_text, encoding='utf-8')

    print(f"\nDone. Wrote {len(written)} file(s): {', '.join(written)}")


if __name__ == '__main__':
    main()
