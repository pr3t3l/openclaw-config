"""PII / Secret detection scanner — blocking gate before content goes to providers.

Python-based regex scanner with smart triage (high/low confidence).
Human is the final authority on what is sensitive.
See spec.md §7.5 (PII / Secret Detection).
"""

import re
from dataclasses import dataclass, field
from typing import Optional

# High confidence patterns — block until human decision
HIGH_CONFIDENCE_PATTERNS = [
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI API key"),
    (r"AIza[a-zA-Z0-9_-]{35}", "Google API key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub PAT"),
    (r"ghs_[a-zA-Z0-9]{36}", "GitHub App token"),
    (r"glpat-[a-zA-Z0-9_-]{20,}", "GitLab PAT"),
    (r"(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token)\s*[=:]\s*['\"]?[a-zA-Z0-9_-]{16,}['\"]?", "API key assignment"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "SSN-like pattern"),
    (r"(?i)password\s*[=:]\s*['\"]?[^\s'\"]{6,}['\"]?", "Password assignment"),
]

# Low confidence patterns — show as warning, allow to continue
LOW_CONFIDENCE_PATTERNS = [
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "Email address"),
    (r"(?i)(api[_-]?key|token|secret)\b", "Sensitive keyword (variable name)"),
    (r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b", "Possible card number"),
]

_HIGH_RE = [(re.compile(p), desc) for p, desc in HIGH_CONFIDENCE_PATTERNS]
_LOW_RE = [(re.compile(p), desc) for p, desc in LOW_CONFIDENCE_PATTERNS]


@dataclass
class ScanHit:
    """A single scanner match."""
    line_number: int
    line_content: str
    pattern_description: str
    confidence: str  # "HIGH" or "LOW"
    matched_text: str


@dataclass
class ScanResult:
    """Result of scanning content for PII/secrets."""
    clean: bool
    high_confidence_hits: list[ScanHit] = field(default_factory=list)
    low_confidence_hits: list[ScanHit] = field(default_factory=list)

    @property
    def has_blockers(self) -> bool:
        return len(self.high_confidence_hits) > 0

    @property
    def total_hits(self) -> int:
        return len(self.high_confidence_hits) + len(self.low_confidence_hits)


def scan(content: str) -> ScanResult:
    """Scan content for potential secrets and PII.

    Args:
        content: Text to scan.

    Returns:
        ScanResult with categorized hits.
    """
    high_hits: list[ScanHit] = []
    low_hits: list[ScanHit] = []

    lines = content.split("\n")
    for i, line in enumerate(lines, start=1):
        # Skip comments and code fence markers
        stripped = line.strip()
        if stripped.startswith("<!--") or stripped.startswith("-->"):
            continue
        if stripped.startswith("```"):
            continue

        # Check high confidence patterns
        for regex, desc in _HIGH_RE:
            for match in regex.finditer(line):
                high_hits.append(ScanHit(
                    line_number=i,
                    line_content=_redact_line(line, match),
                    pattern_description=desc,
                    confidence="HIGH",
                    matched_text=_partial_redact(match.group()),
                ))

        # Check low confidence patterns (only if no high hit on same line)
        if not any(h.line_number == i for h in high_hits):
            for regex, desc in _LOW_RE:
                for match in regex.finditer(line):
                    low_hits.append(ScanHit(
                        line_number=i,
                        line_content=line.strip(),
                        pattern_description=desc,
                        confidence="LOW",
                        matched_text=match.group(),
                    ))

    return ScanResult(
        clean=len(high_hits) == 0 and len(low_hits) == 0,
        high_confidence_hits=high_hits,
        low_confidence_hits=low_hits,
    )


def classify_confidence(hit: ScanHit) -> str:
    """Return the confidence level of a hit."""
    return hit.confidence


def format_results(result: ScanResult) -> str:
    """Format scan results for human review via Telegram.

    Returns:
        Formatted string ready for Telegram display.
    """
    if result.clean:
        return "✅ PII scan clean — no secrets detected."

    lines = ["🔒 PII/Secret Scan Results:\n"]

    if result.high_confidence_hits:
        lines.append(f"🔴 **{len(result.high_confidence_hits)} HIGH confidence** (blocking):\n")
        for h in result.high_confidence_hits:
            lines.append(f"  Line {h.line_number}: {h.pattern_description}")
            lines.append(f"    Matched: `{h.matched_text}`\n")

    if result.low_confidence_hits:
        lines.append(f"🟡 **{len(result.low_confidence_hits)} LOW confidence** (warning):\n")
        for h in result.low_confidence_hits[:10]:  # Limit display
            lines.append(f"  Line {h.line_number}: {h.pattern_description}")
        if len(result.low_confidence_hits) > 10:
            lines.append(f"  ... and {len(result.low_confidence_hits) - 10} more")

    if result.has_blockers:
        lines.append("\n⚠️ HIGH confidence hits must be resolved before proceeding.")
        lines.append("Options: redact / skip file / approve as-is")

    return "\n".join(lines)


def _redact_line(line: str, match: re.Match) -> str:
    """Redact the matched portion of a line for safe display."""
    start, end = match.span()
    matched = match.group()
    if len(matched) > 8:
        redacted = matched[:4] + "****" + matched[-4:]
    else:
        redacted = "****"
    return line[:start] + redacted + line[end:]


def _partial_redact(text: str) -> str:
    """Partially redact a matched string for display."""
    if len(text) > 8:
        return text[:4] + "..." + text[-4:]
    return text[:2] + "..."
