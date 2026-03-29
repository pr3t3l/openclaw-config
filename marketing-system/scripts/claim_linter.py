#!/usr/bin/env python3
"""Claim Linter — deterministic pre-check for marketing assets.

Verifies all draft assets against verified_facts, allowed_claims,
and forbidden_claims from product_brief.json BEFORE the quality reviewer.

Usage:
    python3 claim_linter.py <product_id> <week>
    python3 claim_linter.py misterio-semanal 2026-W17

Exit codes:
    0 = pass (no critical violations)
    1 = fail (critical violations found — hard block)
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

FABRICATION_PATTERNS = [
    # Testimonios fabricados
    (r'"[^"]{20,}".*(?:dijo|comentó|afirmó|según)', "fabricated_testimonial",
     "Cita larga atribuida a alguien — posible testimonial fabricado"),
    (r'(?:María|Juan|Carlos|Ana|Pedro|Laura|Sofía|Diego|Valentina|Camila|Andrés|Lucía)\s+(?:de|desde)\s+\w+.*(?:dice|comenta|afirma|cuenta)',
     "fabricated_testimonial", "Nombre + ciudad + verbo de declaración — posible testimonial fabricado"),
    (r'\d+\s*(?:estrellas|stars)', "fabricated_testimonial",
     "Rating con estrellas — no hay reviews verificadas"),
    (r'\d+%\s*(?:de\s+)?(?:jugadores|usuarios|clientes|personas|detectives|compradores)',
     "fabricated_testimonial", "Estadística de usuarios fabricada"),

    # Garantías fabricadas
    (r'garant[íi]a\s+de\s+(?:satisfacci[óo]n|devoluci[óo]n)', "fabricated_guarantee",
     "Garantía de satisfacción/devolución — no existe. Eliminar o usar placeholder"),
    (r'(?:dinero|money)\s+(?:back|devuelta)', "fabricated_guarantee",
     "Money-back — no hay política de devolución verificada"),
    (r'sin\s+riesgo', "fabricated_guarantee",
     "'Sin riesgo' implica garantía que no existe"),
    (r'prueba\s+gratis', "fabricated_guarantee",
     "No hay prueba gratis verificada"),
    (r'te\s+devolvemos\s+el\s+dinero', "fabricated_guarantee",
     "Promesa de devolución — no existe política verificada"),

    # Exclusividad no respaldada
    (r'(?:la\s+)?(?:única|primera|exclusiv)', "unverified_claim",
     "Claim de exclusividad sin evidencia — eliminar"),
    (r'(?:nunca\s+antes|por\s+primera\s+vez)', "unverified_claim",
     "Claim de novedad sin evidencia"),

    # Comparaciones engañosas
    (r'(?:mejor|superior)\s+que\s+(?:Hunt|Unsolved|escape\s+room)', "forbidden_claim",
     "Comparación directa con competidor — no respaldada con datos"),
    (r'(?:\d+x|\d+\s+veces)\s+(?:mejor|más)', "forbidden_claim",
     "Multiplicador comparativo sin fuente"),

    # Datos inventados sobre el producto
    (r'(?:caso|historia|crimen)\s+real', "forbidden_claim",
     "Los casos son ficción — no afirmar que son reales"),
    (r'informe\s+(?:policial|forense)\s+real', "forbidden_claim",
     "Los informes son ficticios — eliminar 'real'"),
    (r'evidencia\s+(?:real|auténtica|verdadera)', "forbidden_claim",
     "La evidencia es parte de la ficción — cuidado con 'real/auténtica'"),
    (r'basado\s+en\s+(?:hechos|casos|crímenes)\s+reales', "forbidden_claim",
     "No afirmar que está basado en hechos reales a menos que el case_brief lo diga"),
]

FACT_CLAIMS_TO_VERIFY = [
    # (regex, fact_key, category, validator_fn_name)
    (r'(\d+)\s*(?:archivos|documentos)', 'documents_per_case', 'document_count_claims'),
    (r'(\d+)\s*pistas', 'documents_per_case', 'document_count_claims'),
    (r'(\d+(?:[.,]\d+)?)\s*(?:horas|hours)\s+(?:de\s+)?(?:investigación|juego|entretenimiento|gameplay)', 'estimated_play_time', 'time_claims'),
    (r'\$\s*(\d+[.,]\d{2})', 'price_usd', 'price_claims'),
    (r'(\d+)\s*(?:jugadores|players|personas)', 'players', 'player_claims'),
    (r'(\d+)\s*(?:sobres|envelopes)', 'envelopes_per_case', 'envelope_claims'),
    (r'(\d+)\s*(?:casos?\s+disponibles)', 'total_cases_available', 'case_count_claims'),
]


# ---------------------------------------------------------------------------
# Fact verification
# ---------------------------------------------------------------------------

def _verify_number(found_str: str, fact_value, fact_key: str) -> tuple[bool, str]:
    """Check if a found number matches the verified fact."""
    try:
        found_num = float(found_str.replace(",", "."))
    except ValueError:
        return False, f"No se pudo parsear '{found_str}'"

    if fact_value is None:
        return False, f"No hay dato verificado para '{fact_key}' — no usar números"

    if isinstance(fact_value, (int, float)):
        if abs(found_num - fact_value) < 0.01:
            return True, ""
        return False, f"Encontrado {found_num}, verificado: {fact_value}"

    # String value like "14-21 documentos..." or "2-4 horas" or "1-6 jugadores..."
    if isinstance(fact_value, str):
        range_match = re.search(r'(\d+)-(\d+)', fact_value)
        if range_match:
            lo, hi = int(range_match.group(1)), int(range_match.group(2))
            if lo <= found_num <= hi:
                return True, ""
            return False, f"Encontrado {int(found_num)}, rango verificado: {lo}-{hi}"

        nums = re.findall(r'\d+', fact_value)
        if nums and str(int(found_num)) in nums:
            return True, ""
        return False, f"Encontrado {found_num}, verificado: '{fact_value}'"

    return True, ""


# ---------------------------------------------------------------------------
# Text extraction from asset JSONs
# ---------------------------------------------------------------------------

def _extract_texts(data: dict, filename: str) -> list[tuple[str, str]]:
    """Extract (text, asset_ref) pairs from a draft JSON."""
    texts = []

    if "scripts" in data:
        for script in data["scripts"]:
            sid = script.get("script_id", "?")
            for v in script.get("variants", []):
                ref = f"{sid}-{v.get('variant', '?')}"
                for field in ["hook", "body", "cta"]:
                    if field in v:
                        texts.append((v[field], ref))

    elif "ad_sets" in data:
        for ad_set in data["ad_sets"]:
            for v in ad_set.get("variants", []):
                ref = v.get("variant_id", "?")
                for field in ["headline", "primary_text", "description"]:
                    if field in v:
                        texts.append((v[field], ref))
    elif "ad_set" in data:
        for v in data["ad_set"].get("variants", []):
            ref = v.get("variant_id", "?")
            for field in ["headline", "primary_text", "description"]:
                if field in v:
                    texts.append((v[field], ref))

    elif "sequences" in data:
        for seq in data["sequences"]:
            for email in seq.get("emails", []):
                ref = email.get("email_id", "?")
                for field in ["subject", "preheader", "body_markdown", "body"]:
                    if field in email:
                        texts.append((email[field], ref))
                for subj in email.get("subject_variants", []):
                    if isinstance(subj, dict):
                        texts.append((subj.get("text", ""), ref))
                    elif isinstance(subj, str):
                        texts.append((subj, ref))
    elif "sequence" in data:
        for email in data["sequence"]:
            ref = email.get("email_id", "?")
            for field in ["subject", "preheader", "body_markdown", "body"]:
                if field in email:
                    texts.append((email[field], ref))

    elif "schedule" in data:
        for entry in data["schedule"]:
            ref = entry.get("content_ref", "?")
            for field in ["notes", "caption", "description"]:
                if field in entry:
                    texts.append((entry[field], ref))

    return texts


# ---------------------------------------------------------------------------
# Main linting logic
# ---------------------------------------------------------------------------

def lint_assets(product_id: str, week: str) -> dict:
    """Lint all draft assets for a weekly run."""
    product_dir = PRODUCTS_DIR / product_id
    brief = json.loads((product_dir / "product_brief.json").read_text())
    verified = brief.get("verified_facts", {})

    drafts_dir = product_dir / "weekly_runs" / week / "drafts"
    if not drafts_dir.exists():
        return {"error": f"No drafts directory: {drafts_dir}"}

    violations = []
    facts_verified = {}

    # Initialize fact categories
    for _, _, category in FACT_CLAIMS_TO_VERIFY:
        if category not in facts_verified:
            facts_verified[category] = {"found": 0, "correct": 0, "wrong": 0}

    draft_files = [f for f in drafts_dir.iterdir()
                   if f.suffix == ".json" and "quality_report" not in f.name
                   and "image_manifest" not in f.name]

    for draft_file in sorted(draft_files):
        try:
            data = json.loads(draft_file.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        texts = _extract_texts(data, draft_file.name)

        for text, asset_ref in texts:
            if not text or not isinstance(text, str):
                continue

            # Check fabrication patterns
            for pattern, vtype, suggestion in FABRICATION_PATTERNS:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    violations.append({
                        "asset_file": draft_file.name,
                        "asset_ref": asset_ref,
                        "violation_type": vtype,
                        "text_found": match.group(0)[:200],
                        "rule_matched": pattern[:100],
                        "severity": "critical",
                        "suggestion": suggestion,
                    })

            # Verify factual claims
            for pattern, fact_key, category in FACT_CLAIMS_TO_VERIFY:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    found_val = match.group(1)
                    facts_verified[category]["found"] += 1

                    ok, reason = _verify_number(found_val, verified.get(fact_key), fact_key)
                    if ok:
                        facts_verified[category]["correct"] += 1
                    else:
                        facts_verified[category]["wrong"] += 1
                        violations.append({
                            "asset_file": draft_file.name,
                            "asset_ref": asset_ref,
                            "violation_type": "fact_mismatch",
                            "text_found": match.group(0)[:200],
                            "rule_matched": f"{fact_key}: {reason}",
                            "severity": "critical",
                            "suggestion": f"Usar dato verificado: {verified.get(fact_key, 'NO DISPONIBLE')}",
                        })

    # Determine status
    critical_count = sum(1 for v in violations if v["severity"] == "critical")
    status = "fail" if critical_count > 0 else "pass"

    report = {
        "product_id": product_id,
        "week": week,
        "linted_at": datetime.now().isoformat(),
        "status": status,
        "total_violations": len(violations),
        "critical_violations": critical_count,
        "violations": violations,
        "facts_verified": facts_verified,
    }

    # Write report
    report_path = drafts_dir.parent / "claim_lint_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Report written: {report_path}")

    return report


def print_report(report: dict):
    """Print a human-readable summary."""
    print(f"\n{'='*60}")
    print(f"CLAIM LINTER — {report['product_id']} {report['week']}")
    print(f"{'='*60}")
    print(f"Status: {'✅ PASS' if report['status'] == 'pass' else '🛑 FAIL'}")
    print(f"Total violations: {report['total_violations']} ({report['critical_violations']} critical)")

    if report.get("facts_verified"):
        print(f"\nFact verification:")
        for category, counts in report["facts_verified"].items():
            if counts["found"] > 0:
                print(f"  {category}: {counts['correct']}/{counts['found']} correct, {counts['wrong']} wrong")

    if report["violations"]:
        print(f"\nViolations:")
        for i, v in enumerate(report["violations"], 1):
            print(f"  {i}. [{v['severity'].upper()}] {v['violation_type']}")
            print(f"     File: {v['asset_file']} | Ref: {v['asset_ref']}")
            print(f"     Found: {v['text_found'][:100]}")
            print(f"     Fix: {v['suggestion']}")
            print()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 claim_linter.py <product_id> <week>")
        sys.exit(1)

    product_id = sys.argv[1]
    week = sys.argv[2]

    report = lint_assets(product_id, week)
    if "error" in report:
        print(f"ERROR: {report['error']}")
        sys.exit(1)

    print_report(report)
    sys.exit(0 if report["status"] == "pass" else 1)
