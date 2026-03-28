"""Module 5: Monthly Analyst — month-end AI report."""

import json
import subprocess
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from . import config as C
from . import sheets


def monthly_report(month: str = None) -> str:
    """Generate the full monthly report."""
    if not month:
        last_month = date.today() - relativedelta(months=1)
        month = f"{last_month.year}-{last_month.month:02d}"

    transactions = sheets.get_transactions_for_month(month)
    spending = sheets.get_all_month_spending(month)
    budgets = C.load_budgets()["categories"]
    payments = C.load_payments()

    total_spent = sum(spending.values())

    # Category breakdown
    cat_lines = []
    for cat in C.CATEGORIES:
        budget = budgets.get(cat, {}).get("monthly")
        spent = spending.get(cat, 0)
        if not budget and not spent:
            continue
        if budget:
            pct = spent / budget * 100
            status = "✔" if pct <= 100 else "🔴"
            cat_lines.append(f"  {cat}: ${spent:.0f}/${budget} ({pct:.0f}%) {status}")
        else:
            cat_lines.append(f"  {cat}: ${spent:.0f} (sin presupuesto)")

    # Top 5 merchants
    merchant_totals: dict[str, float] = {}
    for tx in transactions:
        m = tx.get("merchant", "Unknown")
        merchant_totals[m] = merchant_totals.get(m, 0) + float(tx.get("amount", 0))
    top_merchants = sorted(merchant_totals.items(), key=lambda x: x[1], reverse=True)[:5]
    merchant_lines = [f"  {i+1}. {m}: ${a:.0f}" for i, (m, a) in enumerate(top_merchants)]

    # AI insights
    ai_analysis = _ai_monthly_analysis(spending, budgets, total_spent)

    # Payment schedule next month
    next_month_total = sum(p["amount"] for p in payments)
    promo_warnings = []
    for p in payments:
        if p.get("promo_expiry"):
            promo_date = date.fromisoformat(p["promo_expiry"])
            days = (promo_date - date.today()).days
            if 0 < days <= 90:
                promo_warnings.append(f"  ⚠ {p['name']}: promo {p['apr']}% expira {p['promo_expiry']} ({days}d)")

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

    if promo_warnings:
        lines += ["", "Promos por vencer:", *promo_warnings]

    # Tax deductions section
    tax_lines = _tax_deduction_summary(month)
    if tax_lines:
        lines += ["", *tax_lines]

    if ai_analysis:
        lines += ["", "💡 Análisis:", ai_analysis]

    return "\n".join(lines)


def _ai_monthly_analysis(spending: dict, budgets: dict, total: float) -> str:
    prompt = f"""Analyze Alfredo's monthly finances. Given the data, provide:
1) Categories over/under budget
2) Single biggest savings opportunity next month
3) Debt payoff progress
4) Motivational note where discipline was shown
Under 200 words. Spanish.

Spending: {json.dumps(spending)}
Budgets: {json.dumps({k: v.get('monthly') for k, v in budgets.items() if v.get('monthly')})}
Total: ${total:.0f}"""

    payload = {
        "model": C.ANALYSIS_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }

    try:
        result = subprocess.run(
            ["curl", "-s", C.LITELLM_URL,
             "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {C.LITELLM_KEY}",
             "-d", json.dumps(payload)],
            capture_output=True, text=True, timeout=60
        )
        resp = json.loads(result.stdout)
        return resp["choices"][0]["message"]["content"].strip()
    except Exception:
        return "(Análisis AI no disponible)"


def _tax_deduction_summary(month: str) -> list[str]:
    """Generate tax deduction section for monthly report."""
    deductions = sheets.get_tax_deductions(month=month)
    if not deductions:
        return []

    groups: dict[str, list] = {}
    for d in deductions:
        cat = d.get("tax_category", "other")
        groups.setdefault(cat, []).append(d)

    lines = ["Deducciones este mes:"]
    for cat_key, label in [
        ("airbnb_supplies", "Airbnb supplies"),
        ("airbnb_repair", "Airbnb repairs"),
        ("business_expense", "Work tools"),
    ]:
        items = groups.get(cat_key, [])
        total = sum(float(i.get("amount", 0)) for i in items)
        lines.append(f"  {label}: ${total:,.2f} ({len(items)} items)")

    grand_total = sum(float(d.get("amount", 0)) for d in deductions)
    lines.append(f"  Total deducible: ${grand_total:,.2f}")
    return lines
