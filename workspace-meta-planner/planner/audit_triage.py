"""Audit triage — categorize findings, detect conflicts, format summary.

Opus filters 4 audit results. Categorizes by severity rubric.
Conflict Flag fires when auditors disagree on CRITICAL.
See spec.md §3 (Phase 3 triage + conflict rule).
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Severity rubric
SEVERITY_RUBRIC = {
    "CRITICAL": "Breaks architecture or violates spec. Must be resolved.",
    "IMPORTANT": "Affects quality significantly. Should be addressed.",
    "MINOR": "Style, editorial, or low-impact. Auto-fixable.",
    "NOISE": "Not applicable to project scope. Dismissed.",
}


@dataclass
class Finding:
    """A single audit finding."""
    severity: str
    section: str
    description: str
    suggestion: str
    source: str  # model_label: gpt_tech, gpt_arch, gemini_tech, gemini_arch


@dataclass
class ConflictFlag:
    """A disagreement between auditors on a CRITICAL finding."""
    description: str
    gpt_argument: str
    gemini_argument: str


@dataclass
class TriageResult:
    """Result of triaging all audit findings."""
    critical: list[Finding] = field(default_factory=list)
    important: list[Finding] = field(default_factory=list)
    minor: list[Finding] = field(default_factory=list)
    noise: list[Finding] = field(default_factory=list)
    conflicts: list[ConflictFlag] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0

    @property
    def critical_count(self) -> int:
        return len(self.critical)

    @property
    def auto_fix_count(self) -> int:
        return len(self.minor)

    @property
    def noise_count(self) -> int:
        return len(self.noise)


def triage(
    audit_results: list[dict],
    gateway: Optional[Any] = None,
    phase: str = "3",
    document: Optional[str] = None,
) -> TriageResult:
    """Triage audit results from all 4 calls.

    Args:
        audit_results: List of AuditCallResult-like dicts with content and model_label.
        gateway: ModelGateway for Opus triage call (optional — can parse locally).
        phase: Phase for cost tracking.
        document: Document for cost tracking.

    Returns:
        TriageResult with categorized findings and conflict flags.
    """
    all_findings: list[Finding] = []

    for result in audit_results:
        source = result.get("model_label", "unknown")
        content = result.get("content", "")
        findings = _parse_findings(content, source)
        all_findings.extend(findings)

    # Detect conflicts between models on CRITICAL findings
    conflicts = detect_conflicts(all_findings)

    # Categorize
    triage_result = TriageResult()
    for f in all_findings:
        if f.severity == "CRITICAL":
            triage_result.critical.append(f)
        elif f.severity == "IMPORTANT":
            triage_result.important.append(f)
        elif f.severity == "MINOR":
            triage_result.minor.append(f)
        else:
            triage_result.noise.append(f)

    triage_result.conflicts = conflicts

    logger.info(
        f"Triage: {triage_result.critical_count} critical, "
        f"{len(triage_result.important)} important, "
        f"{triage_result.auto_fix_count} minor, "
        f"{triage_result.noise_count} noise, "
        f"{len(conflicts)} conflicts"
    )

    return triage_result


def detect_conflicts(findings: list[Finding]) -> list[ConflictFlag]:
    """Detect when GPT and Gemini disagree on CRITICAL findings.

    A conflict is when one model flags something as CRITICAL and
    another model explicitly addresses the same topic differently.
    """
    conflicts: list[ConflictFlag] = []

    gpt_criticals = [f for f in findings if f.severity == "CRITICAL" and "gpt" in f.source]
    gemini_criticals = [f for f in findings if f.severity == "CRITICAL" and "gemini" in f.source]

    # Check for topic overlap where severity differs
    gpt_all = {f.description.lower()[:50]: f for f in findings if "gpt" in f.source}
    gemini_all = {f.description.lower()[:50]: f for f in findings if "gemini" in f.source}

    for gpt_f in gpt_criticals:
        key = gpt_f.description.lower()[:50]
        # Look for same topic in gemini with different severity
        for gem_key, gem_f in gemini_all.items():
            if _topics_overlap(gpt_f.description, gem_f.description) and gem_f.severity != "CRITICAL":
                conflicts.append(ConflictFlag(
                    description=gpt_f.description,
                    gpt_argument=f"[CRITICAL] {gpt_f.description}: {gpt_f.suggestion}",
                    gemini_argument=f"[{gem_f.severity}] {gem_f.description}: {gem_f.suggestion}",
                ))

    for gem_f in gemini_criticals:
        for gpt_key, gpt_f in gpt_all.items():
            if _topics_overlap(gem_f.description, gpt_f.description) and gpt_f.severity != "CRITICAL":
                # Avoid duplicate conflicts
                already = any(c.description == gem_f.description for c in conflicts)
                if not already:
                    conflicts.append(ConflictFlag(
                        description=gem_f.description,
                        gpt_argument=f"[{gpt_f.severity}] {gpt_f.description}: {gpt_f.suggestion}",
                        gemini_argument=f"[CRITICAL] {gem_f.description}: {gem_f.suggestion}",
                    ))

    return conflicts


def format_summary(triage_result: TriageResult) -> str:
    """Format triage result as human-readable summary."""
    lines = []

    if triage_result.critical:
        lines.append(f"🔴 {triage_result.critical_count} CRITICAL findings need your input:\n")
        for i, f in enumerate(triage_result.critical, 1):
            lines.append(f"{i}. [{f.severity}] ({f.source}): {f.description}")
            if f.suggestion:
                lines.append(f"   Suggestion: {f.suggestion}")

    if triage_result.has_conflicts:
        lines.append(f"\n⚠️ {len(triage_result.conflicts)} CONFLICT(s) detected:\n")
        for c in triage_result.conflicts:
            lines.append(f"Topic: {c.description}")
            lines.append(f"  GPT says: {c.gpt_argument}")
            lines.append(f"  Gemini says: {c.gemini_argument}")

    lines.append(f"\n{triage_result.auto_fix_count} minor issues (auto-fixable)")
    lines.append(f"{triage_result.noise_count} noise (dismissed)")

    return "\n".join(lines)


def _parse_findings(content: str, source: str) -> list[Finding]:
    """Parse findings from audit model output."""
    findings = []
    current: Optional[dict] = None

    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Match severity markers.
        # Supported formats:
        #   - "- CRITICAL: ..." (old)
        #   - "- **SEVERITY:** CRITICAL" (current model outputs)
        sev_match = re.match(r"[-*]\s*(CRITICAL|IMPORTANT|MINOR|NOISE)\s*:?\s*(.*)", line, re.IGNORECASE)
        if not sev_match:
            sev_match = re.match(
                r"[-*]\s*\*\*SEVERITY:\*\*\s*(CRITICAL|IMPORTANT|MINOR|NOISE)\s*(.*)",
                line,
                re.IGNORECASE,
            )
        if sev_match:
            if current:
                findings.append(_build_finding(current, source))
            current = {
                "severity": sev_match.group(1).upper(),
                "description": sev_match.group(2).strip().strip("-–—").strip(),
                "section": "",
                "suggestion": "",
            }
            continue

        if current:
            upper = line.upper()
            if upper.startswith("SECTION:"):
                current["section"] = line.split(":", 1)[1].strip()
            elif upper.startswith("SUGGESTION:") or upper.startswith("FIX:"):
                current["suggestion"] = line.split(":", 1)[1].strip()
            elif upper.startswith("DESCRIPTION:"):
                current["description"] = line.split(":", 1)[1].strip()
            else:
                current["description"] += " " + line

    if current:
        findings.append(_build_finding(current, source))

    return findings


def _build_finding(data: dict, source: str) -> Finding:
    return Finding(
        severity=data.get("severity", "MINOR"),
        section=data.get("section", ""),
        description=data.get("description", "").strip(),
        suggestion=data.get("suggestion", "").strip(),
        source=source,
    )


def _topics_overlap(desc1: str, desc2: str) -> bool:
    """Check if two finding descriptions are about the same topic."""
    words1 = set(w.lower() for w in desc1.split() if len(w) > 3)
    words2 = set(w.lower() for w in desc2.split() if len(w) > 3)
    if not words1 or not words2:
        return False
    overlap = words1 & words2
    return len(overlap) >= min(len(words1), len(words2)) * 0.4
