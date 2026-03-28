#!/usr/bin/env python3
import json, sys
from pathlib import Path


def repair_text(text: str) -> str:
    # Prefer fenced JSON body if present
    if '```json' in text:
        start = text.find('```json') + 7
        end = text.rfind('```')
        if end > start:
            text = text[start:end]
    text = text.strip()
    # Trim to outermost object when possible
    s = text.find('{')
    e = text.rfind('}')
    if s >= 0 and e > s:
        text = text[s:e+1]
    # Balance quotes/brackets/braces heuristically
    unescaped_quotes = 0
    escaped = False
    for ch in text:
        if escaped:
            escaped = False
            continue
        if ch == '\\':
            escaped = True
            continue
        if ch == '"':
            unescaped_quotes += 1
    if unescaped_quotes % 2 == 1:
        text += '"'
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')
    if open_brackets > 0:
        text += (']' * open_brackets)
    if open_braces > 0:
        text += ('}' * open_braces)
    # Remove trailing commas before close tokens
    text = text.replace(',}', '}').replace(',]', ']')
    return text


def main():
    if len(sys.argv) != 3:
        print('Usage: json_repair.py <input_raw> <output_json>')
        sys.exit(1)
    raw = Path(sys.argv[1]).read_text(encoding='utf-8')
    repaired = repair_text(raw)
    data = json.loads(repaired)
    Path(sys.argv[2]).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    print('OK')

if __name__ == '__main__':
    main()
