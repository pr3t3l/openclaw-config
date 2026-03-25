#!/usr/bin/env python3
"""
cost_tracker.py — Unified Cost Tracking for Declassified Cases V9

Tracks every LLM API call, image generation, and rendering cost across
all pipeline phases. Writes to manifest.json cost_tracking section.

Usage:
    from cost_tracker import CostTracker
    tracker = CostTracker(case_dir)
    tracker.log_agent_call('narrative_architect_2a', 'narrative-architect', 
                           'litellm/gpt52-thinking', 12500, 8200)
    tracker.log_render_call('A1', 'claude-sonnet46', 18500, 3200)
    tracker.log_image('nano-banana-2-gemini', count=5, failures=1)
    print(tracker.get_summary())
"""

import json
import os
from datetime import datetime
from pathlib import Path


# Pricing per 1M tokens (USD)
PRICING = {
    # GPT-5.2 family
    'litellm/gpt52-thinking': {'input': 3.00, 'output': 15.00},
    'litellm/gpt52-xhigh': {'input': 3.00, 'output': 15.00},
    'litellm/gpt52-medium': {'input': 0.75, 'output': 3.00},
    'litellm/gpt52-none': {'input': 0.75, 'output': 3.00},
    'gpt52-thinking': {'input': 3.00, 'output': 15.00},
    'gpt52-medium': {'input': 0.75, 'output': 3.00},
    # Gemini family
    'litellm/gemini31pro-thinking': {'input': 1.25, 'output': 10.00},
    'litellm/gemini31pro-medium': {'input': 0.15, 'output': 0.60},
    'litellm/gemini31pro-none': {'input': 0.15, 'output': 0.60},
    'litellm/gemini31lite-medium': {'input': 0.08, 'output': 0.30},
    'gemini31pro-thinking': {'input': 1.25, 'output': 10.00},
    'gemini31pro-medium': {'input': 0.15, 'output': 0.60},
    # Claude family
    'litellm/claude-sonnet46': {'input': 3.00, 'output': 15.00},
    'litellm/claude-sonnet46-thinking': {'input': 3.00, 'output': 15.00},
    'litellm/claude-opus46': {'input': 15.00, 'output': 75.00},
    'claude-sonnet46': {'input': 3.00, 'output': 15.00},
    'claude-sonnet-4-6': {'input': 3.00, 'output': 15.00},
    'claude-sonnet-4-6-20250514': {'input': 3.00, 'output': 15.00},
    # Image generation
    'nano-banana-2-gemini': {'per_image': 0.02},
    'dall-e-3': {'per_image': 0.04, 'per_image_hd': 0.08},
    'gemini-3.1-flash-image-preview': {'per_image': 0.02},
}

# Default pricing for unknown models
DEFAULT_PRICING = {'input': 1.00, 'output': 5.00}


class CostTracker:
    def __init__(self, case_dir):
        self.case_dir = Path(case_dir)
        self.manifest_path = self.case_dir / 'manifest.json'
        self._load()

    def _load(self):
        """Load manifest and ensure cost_tracking structure exists."""
        if self.manifest_path.exists():
            self.manifest = json.load(open(self.manifest_path, 'r', encoding='utf-8'))
        else:
            self.manifest = {}

        if 'cost_tracking' not in self.manifest:
            self.manifest['cost_tracking'] = {}

        ct = self.manifest['cost_tracking']
        if 'phases' not in ct:
            ct['phases'] = {}
        if 'images' not in ct:
            ct['images'] = {'generated': 0, 'failed': 0, 'total_cost': 0}
        if 'totals' not in ct:
            ct['totals'] = {
                'input_tokens': 0,
                'output_tokens': 0,
                'wasted_tokens_retries': 0,
                'images_generated': 0,
                'estimated_total_usd': 0,
                'api_calls': 0
            }

    def _save(self):
        """Write manifest back to disk."""
        with open(self.manifest_path, 'w', encoding='utf-8') as f:
            json.dump(self.manifest, f, indent=2, ensure_ascii=False)

    def _get_pricing(self, model):
        """Get pricing for a model, with fallback."""
        model_clean = model.strip()
        if model_clean in PRICING:
            return PRICING[model_clean]
        # Try without litellm/ prefix
        if model_clean.startswith('litellm/'):
            bare = model_clean[len('litellm/'):]
            if bare in PRICING:
                return PRICING[bare]
        return DEFAULT_PRICING

    def _ensure_phase(self, phase):
        """Ensure a phase entry exists."""
        phases = self.manifest['cost_tracking']['phases']
        if phase not in phases:
            phases[phase] = {
                'calls': [],
                'total_cost': 0,
                'total_input_tokens': 0,
                'total_output_tokens': 0
            }
        return phases[phase]

    def log_agent_call(self, phase, agent_name, model,
                       input_tokens, output_tokens,
                       doc_id=None, retry=False, notes=None):
        """
        Log a single LLM API call from any pipeline phase.

        Args:
            phase: Pipeline phase name (e.g. 'narrative_architect_2a')
            agent_name: Agent/skill name (e.g. 'narrative-architect')
            model: Model used (e.g. 'litellm/gpt52-thinking')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            doc_id: Optional document ID (e.g. 'A1') for per-doc tracking
            retry: Whether this was a retry attempt
            notes: Optional notes about the call
        """
        pricing = self._get_pricing(model)
        cost = (input_tokens * pricing.get('input', 1.0) +
                output_tokens * pricing.get('output', 5.0)) / 1_000_000

        entry = {
            'timestamp': datetime.now().isoformat(),
            'agent': agent_name,
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost_usd': round(cost, 4),
            'retry': retry
        }
        if doc_id:
            entry['doc_id'] = doc_id
        if notes:
            entry['notes'] = notes

        # Add to phase
        phase_data = self._ensure_phase(phase)
        phase_data['calls'].append(entry)
        phase_data['total_cost'] = round(phase_data['total_cost'] + cost, 4)
        phase_data['total_input_tokens'] += input_tokens
        phase_data['total_output_tokens'] += output_tokens

        # Update totals
        totals = self.manifest['cost_tracking']['totals']
        totals['input_tokens'] = (totals.get('input_tokens') or 0) + input_tokens
        totals['output_tokens'] = (totals.get('output_tokens') or 0) + output_tokens
        totals['estimated_total_usd'] = round(
            (totals.get('estimated_total_usd') or 0) + cost, 4)
        totals['api_calls'] = (totals.get('api_calls') or 0) + 1
        if retry:
            totals['wasted_tokens_retries'] = (totals.get('wasted_tokens_retries') or 0) + input_tokens + output_tokens

        self._save()
        return cost

    def log_render_call(self, doc_id, model, input_tokens, output_tokens):
        """Shortcut for logging a document rendering API call."""
        return self.log_agent_call(
            phase='document_rendering',
            agent_name='document-designer',
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            doc_id=doc_id
        )

    def log_image(self, model, count=1, failures=0):
        """Log image generation costs."""
        pricing = self._get_pricing(model)
        per_image = pricing.get('per_image', 0.02)
        cost = count * per_image

        images = self.manifest['cost_tracking']['images']
        images['generated'] = images.get('generated', 0) + count
        images['failed'] = images.get('failed', 0) + failures
        images['model'] = model
        images['total_cost'] = round(
            images.get('total_cost', 0) + cost, 4)

        totals = self.manifest['cost_tracking']['totals']
        totals['images_generated'] = totals.get('images_generated', 0) + count
        totals['estimated_total_usd'] = round(
            (totals.get('estimated_total_usd') or 0) + cost, 4)

        self._save()
        return cost

    def get_phase_cost(self, phase):
        """Get total cost for a specific phase."""
        phases = self.manifest['cost_tracking']['phases']
        if phase in phases:
            return phases[phase]['total_cost']
        return 0

    def get_total_cost(self):
        """Get total estimated cost."""
        return (self.manifest['cost_tracking']['totals'].get('estimated_total_usd') or 0)

    def get_summary(self):
        """Return a human-readable cost summary string."""
        ct = self.manifest['cost_tracking']
        totals = ct['totals']
        phases = ct['phases']
        images = ct['images']

        lines = []
        lines.append('=' * 50)
        lines.append('COST SUMMARY')
        lines.append('=' * 50)

        # Per-phase breakdown
        for phase_name in sorted(phases.keys()):
            phase = phases[phase_name]
            calls = len(phase.get('calls', []))
            cost = phase.get('total_cost', 0)
            inp = phase.get('total_input_tokens', 0)
            out = phase.get('total_output_tokens', 0)
            lines.append(
                f'  {phase_name:30s}  ${cost:6.2f}  '
                f'({calls} calls, {inp:,} in / {out:,} out)')

        # Images
        if images.get('generated', 0) > 0:
            lines.append(
                f'  {"images":30s}  ${images.get("total_cost", 0):6.2f}  '
                f'({images["generated"]} generated, {images.get("failed", 0)} failed)')

        # Totals
        lines.append('-' * 50)
        lines.append(
            f'  {"TOTAL":30s}  ${(totals.get("estimated_total_usd") or 0):6.2f}  '
            f'({totals.get("api_calls", 0)} API calls, '
            f'{(totals.get("images_generated") or 0)} images)')
        lines.append(
            f'  {"Tokens":30s}  '
            f'{(totals.get("input_tokens") or 0):,} in / {(totals.get("output_tokens") or 0):,} out')

        if totals.get('wasted_tokens_retries', 0) > 0:
            lines.append(
                f'  {"Wasted (retries)":30s}  '
                f'{(totals.get("wasted_tokens_retries") or 0):,} tokens')

        lines.append('=' * 50)
        return '\n'.join(lines)

    def get_summary_dict(self):
        """Return cost summary as a dict for programmatic use."""
        ct = self.manifest['cost_tracking']
        totals = ct['totals']
        return {
            'total_cost_usd': (totals.get('estimated_total_usd') or 0),
            'total_api_calls': (totals.get('api_calls') or 0),
            'total_images': (totals.get('images_generated') or 0),
            'total_input_tokens': (totals.get('input_tokens') or 0),
            'total_output_tokens': (totals.get('output_tokens') or 0),
            'phases': {
                name: {
                    'cost': data['total_cost'],
                    'calls': len(data.get('calls', []))
                }
                for name, data in ct['phases'].items()
            }
        }


# ── CLI usage ──
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 cost_tracker.py <case_dir> [summary]")
        sys.exit(1)

    case_dir = Path(sys.argv[1])
    tracker = CostTracker(case_dir)

    if len(sys.argv) > 2 and sys.argv[2] == 'summary':
        print(tracker.get_summary())
    else:
        print(f"Cost tracker loaded for: {case_dir}")
        print(f"Total cost so far: ${tracker.get_total_cost():.2f}")
        print(f"Run with 'summary' for full breakdown")
