"""Module 5: Monthly Analyst — month-end AI report."""

import calendar
import json
from datetime import datetime, date, timedelta

from . import config as C
from . import sheets


def monthly_report(month: str = None) -> str:
    """Generate the full monthly report."""
    if not month:
        today = date.today()
        first_of_month = today.replace(day=1)
        last_month = first_of_month - timedelta(days=1)
        month = f"{last_month.year}-{last_month.month:02d}"

    transactions = sheets.get_transactions_for_month(month)
    spending = sheets.get_all_month_spending(month)
    budgets = C.get_category_budgets()
    payments = C.get_payments()
    lang = C.get_language()
    name = C.get_owner_name()

    total_spent = sum(spending.values())

    # Category breakdown
    cat_lines = []
    for cat in C.get_categories():
        budget = budgets.get(cat, {}).get("monthly")
        spent = spending.get(cat, 0)
        if not budget and not spent:
            continue
        if budget:
            pct = spent / budget * 100
            status = "✔" if pct <= 100 else "🔴"
            cat_lines.append(f"  {cat}: ${spent:.0f}/${budget} ({pct:.0f}%) {status}")
        else:
            no_budget = "sin presupuesto" if lang == "es" else "no budget"
            cat_lines.append(f"  {cat}: ${spent:.0f} ({no_budget})")

    # Top 5 merchants
    merchant_totals: dict[str, float] = {}
    for tx in transactions:
        m = tx.get("merchant", "Unknown")
        merchant_totals[m] = merchant_totals.get(m, 0) + float(tx.get("amount", 0))
    top_merchants = sorted(merchant_totals.items(), key=lambda x: x[1], reverse=True)[:5]
    merchant_lines = [f"  {i+1}. {m}: ${a:.0f}" for i, (m, a) in enumerate(top_merchants)]

    # AI insights
    ai_analysis = _ai_monthly_analysis(spending, budgets, total_spent, name, lang)

    # Payment schedule next month
    next_month_total = sum(p["amount"] for p in payments)
    promo_warnings = []
    for p in payments:
        if p.get("promo_expiry"):
            promo_date = date.fromisoformat(p["promo_expiry"])
            days = (promo_date - date.today()).days
            if 0 < days <= 90:
                promo_warnings.append(f"  ⚠ {p['name']}: promo {p['apr']}% expires {p['promo_expiry']} ({days}d)")

    if lang == "es":
        lines = [
            f"📊 REPORTE MENSUAL — {month}",
            "",
            f"Total gastado: ${total_spent:,.0f}",
            "",
            "Por categoría:",
            *cat_lines,
            "",
            "Top 5 merchants:",
            *merchant_lines,
            "",
            f"Pagos fijos mensuales: ${next_month_total:,.0f}",
        ]
    else:
        lines = [
            f"📊 MONTHLY REPORT — {month}",
            "",
            f"Total spent: ${total_spent:,.0f}",
            "",
            "By category:",
            *cat_lines,
            "",
            "Top 5 merchants:",
            *merchant_lines,
            "",
            f"Fixed monthly payments: ${next_month_total:,.0f}",
        ]

    if promo_warnings:
        header = "Promos por vencer:" if lang == "es" else "Promos expiring:"
        lines += ["", header, *promo_warnings]

    # Tax deductions section
    tax_lines = _tax_deduction_summary(month)
    if tax_lines:
        lines += ["", *tax_lines]

    if ai_analysis:
        header = "💡 Análisis:" if lang == "es" else "💡 Analysis:"
        lines += ["", header, ai_analysis]

    return "\n".join(lines)


def _ai_monthly_analysis(spending: dict, budgets: dict, total: float, name: str, lang: str) -> str:
    lang_instruction = "Under 200 words. Spanish." if lang == "es" else "Under 200 words. English."
    prompt = f"""Analyze {name}'s monthly finances. Given the data, provide:
1) Categories over/under budget
2) Single biggest savings opportunity next month
3) Debt payoff progress
4) Motivational note where discipline was shown
{lang_instruction}

Spending: {json.dumps(spending)}
Budgets: {json.dumps({k: v.get('monthly') for k, v in budgets.items() if v.get('monthly')})}
Total: ${total:.0f}"""

    payload = {
        "model": C.ANALYSIS_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }

    return C.ai_extract_text(payload) or "(AI analysis unavailable)"


def _tax_deduction_summary(month: str) -> list[str]:
    """Generate tax deduction section for monthly report."""
    tax_profile = C.get_tax_profile()
    if not tax_profile.get("enabled"):
        return []

    deductions = sheets.get_tax_deductions(month=month)
    if not deductions:
        return []

    lang = C.get_language()
    groups: dict[str, list] = {}
    for d in deductions:
        cat = d.get("tax_category", "other")
        groups.setdefault(cat, []).append(d)

    header = "Deducciones este mes:" if lang == "es" else "Deductions this month:"
    lines = [header]
    for cat in tax_profile.get("tax_categories", []):
        items = groups.get(cat["id"], [])
        total = sum(float(i.get("amount", 0)) for i in items)
        if total > 0:
            lines.append(f"  {cat['label']}: ${total:,.2f} ({len(items)} items)")

    grand_total = sum(float(d.get("amount", 0)) for d in deductions)
    total_label = "Total deducible:" if lang == "es" else "Total deductible:"
    lines.append(f"  {total_label} ${grand_total:,.2f}")
    return lines
