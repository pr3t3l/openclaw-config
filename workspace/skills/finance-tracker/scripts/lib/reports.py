"""Daily/weekly/monthly report generators for Finance Tracker v2.

Each report is bilingual (EN/ES) and outputs structured JSON.
Cherry-picked report structure from v1 analyst.py + budget.py.
"""

import json
from datetime import date, timedelta

from . import config as C
from . import ai_parser as AI
from .budget import get_budget_status
from .cashflow import safe_to_spend, format_cashflow
from .payments import get_upcoming_payments, check_due_soon, sinking_fund_summary


def daily_cashflow_report() -> dict:
    """Morning report: safe-to-spend + upcoming 3d + budget brief + savings."""
    lang = C.get_language()
    name = C.get_owner_name()

    sts = safe_to_spend()
    alerts = check_due_soon(days=3)
    budget = get_budget_status()
    savings = C.get_savings()
    sinking = sinking_fund_summary()

    # Budget brief: only categories with spending or alerts
    budget_lines = []
    for cat in budget["categories"]:
        if cat["spent"] > 0 or cat["status"] != "ok":
            pct = cat["pct"]
            icon = {"ok": "+", "warning": "!", "critical": "!!", "over": "X"}.get(cat["status"], " ")
            budget_lines.append(f"  [{icon}] {cat['category']}: ${cat['spent']:,.0f}/${cat['budget']:,.0f} ({pct:.0f}%)")

    # Savings progress
    savings_lines = []
    today = date.today()
    for g in savings:
        remaining = g.get("target", 0) - g.get("saved", 0)
        if remaining > 0:
            deadline = g.get("deadline", "")
            try:
                dl = date.fromisoformat(deadline)
                days_left = (dl - today).days
                daily_need = remaining / max(days_left, 1)
                savings_lines.append(f"  {g['goal']}: ${g['saved']:,.0f}/${g['target']:,.0f} "
                                     f"(${daily_need:.2f}/day needed, {days_left}d left)")
            except (ValueError, TypeError):
                savings_lines.append(f"  {g['goal']}: ${g.get('saved', 0):,.0f}/${g.get('target', 0):,.0f}")

    # Build report
    if lang == "es":
        greeting = f"Buenos días {name}!"
        header = "Resumen Financiero del Día"
    else:
        greeting = f"Good morning {name}!"
        header = "Daily Financial Snapshot"

    lines = [f"{greeting}\n{header}\n"]
    lines.append(f"Safe to spend today: ${sts['safe_to_spend_daily']:.2f}")
    if sts["risk"] != "comfortable":
        risk_msgs = {
            "caution": "Watch spending" if lang == "en" else "Cuidado con gastos",
            "tight": "TIGHT — essentials only" if lang == "en" else "APRETADO",
            "negative": "NOT ENOUGH" if lang == "en" else "NO ALCANZA",
        }
        lines.append(f"  {risk_msgs.get(sts['risk'], '')}")

    if alerts:
        lines.append(f"\nUpcoming ({('Próximos' if lang == 'es' else 'Next')} 3 days):")
        for a in alerts:
            lines.append(f"  {a['message']}")

    if budget_lines:
        lines.append(f"\nBudget:")
        lines.extend(budget_lines)

    if savings_lines:
        lines.append(f"\nSavings:")
        lines.extend(savings_lines)

    if sinking["sinking_funds"]:
        lines.append(f"\nSinking funds: ${sinking['total_daily_provision']:.2f}/day reserved")

    report_text = "\n".join(lines)
    return {
        "report": "daily_cashflow",
        "date": today.isoformat(),
        "safe_to_spend": sts["safe_to_spend_daily"],
        "risk": sts["risk"],
        "alerts_count": len(alerts),
        "_formatted": report_text,
    }


def weekly_review() -> dict:
    """Weekly review: spending breakdown, budget vs actual, upcoming, optimization."""
    lang = C.get_language()
    name = C.get_owner_name()
    today = date.today()
    week_start = today - timedelta(days=7)
    month = today.strftime("%Y-%m")

    budget = get_budget_status(month)
    upcoming = get_upcoming_payments(days=7)

    # Deductible expenses
    deductible_total = 0
    try:
        from . import sheets
        deductions = sheets.get_tax_deductions(month=month)
        deductible_total = sum(float(d.get("amount", 0)) for d in deductions)
    except Exception:
        pass

    # Over-budget categories (variable only for suggestions)
    over_budget = [c for c in budget["categories"]
                   if c["status"] in ("warning", "critical", "over") and c["type"] == "variable"]

    # Build report
    lines = []
    if lang == "es":
        lines.append(f"Resumen Semanal — {name}")
        lines.append(f"Semana: {week_start.isoformat()} a {today.isoformat()}\n")
    else:
        lines.append(f"Weekly Review — {name}")
        lines.append(f"Week: {week_start.isoformat()} to {today.isoformat()}\n")

    lines.append(f"Month spending: ${budget['total_spent']:,.2f} / ${budget['total_budget']:,.2f}")

    # Category breakdown
    lines.append(f"\nBy Category:")
    for cat in budget["categories"]:
        if cat["budget"] <= 0 and cat["spent"] <= 0:
            continue
        icon = {"ok": "+", "warning": "!", "critical": "!!", "over": "X"}.get(cat["status"], " ")
        lines.append(f"  [{icon}] {cat['category']}: ${cat['spent']:,.2f}/${cat['budget']:,.2f} ({cat['pct']:.0f}%)")

    if deductible_total > 0:
        lines.append(f"\nDeductible expenses: ${deductible_total:,.2f}")

    if upcoming:
        lines.append(f"\nUpcoming bills (7d):")
        for p in upcoming:
            lines.append(f"  {p['name']}: ${p['amount']:,.2f} (in {p['days_until']}d)")

    if over_budget:
        lines.append(f"\nOptimization suggestions:")
        for cat in over_budget[:3]:
            over_by = cat["spent"] - cat["budget"]
            if lang == "es":
                lines.append(f"  - {cat['category']}: ${over_by:,.2f} sobre presupuesto")
            else:
                lines.append(f"  - {cat['category']}: ${over_by:,.2f} over budget. Consider reducing.")

    report_text = "\n".join(lines)
    return {
        "report": "weekly_review",
        "week_start": week_start.isoformat(),
        "week_end": today.isoformat(),
        "total_spent": budget["total_spent"],
        "deductible_total": deductible_total,
        "over_budget_count": len(over_budget),
        "_formatted": report_text,
    }


def monthly_report(month: str | None = None) -> dict:
    """Full month AI analysis: trends, breakdown, recommendations."""
    lang = C.get_language()
    name = C.get_owner_name()
    if not month:
        today = date.today()
        if today.day < 5:
            prev = today.replace(day=1) - timedelta(days=1)
            month = prev.strftime("%Y-%m")
        else:
            month = today.strftime("%Y-%m")

    budget = get_budget_status(month)
    config = C._load_tracker_config()
    debts = config.get("debts", [])
    savings = config.get("savings", [])
    payments = config.get("payments", [])
    income_list = config.get("income", [])

    # Estimate income
    total_income = sum(
        inc["amount"] * {"weekly": 4.33, "biweekly": 2.17, "monthly": 1, "irregular": 1}.get(inc.get("frequency", "monthly"), 1)
        for inc in income_list
    )

    total_debt = sum(d.get("balance", 0) for d in debts)
    total_debt_min = sum(d.get("minimum_payment", 0) for d in debts)
    total_fixed = sum(c["spent"] for c in budget["categories"] if c["type"] == "fixed")
    total_variable = sum(c["spent"] for c in budget["categories"] if c["type"] == "variable")
    surplus = total_income - budget["total_spent"] - total_debt_min

    # Build sections
    lines = []
    lines.append(f"MONTHLY REPORT — {month}")
    lines.append(f"{'='*40}\n")

    lines.append(f"INCOME: ${total_income:,.2f}/mo estimated")
    lines.append(f"SPENT: ${budget['total_spent']:,.2f}")
    lines.append(f"  Fixed: ${total_fixed:,.2f} | Variable: ${total_variable:,.2f}")
    lines.append(f"SURPLUS: ${surplus:,.2f}\n")

    lines.append("CATEGORY BREAKDOWN:")
    for cat in budget["categories"]:
        if cat["budget"] <= 0 and cat["spent"] <= 0:
            continue
        icon = "+" if cat["pct"] <= 100 else "X"
        lines.append(f"  [{icon}] {cat['category']}: ${cat['spent']:,.2f}/${cat['budget']:,.2f} ({cat['pct']:.0f}%)")

    if debts:
        lines.append(f"\nDEBTS: ${total_debt:,.2f} total, ${total_debt_min:,.2f}/mo minimum")
        for d in debts:
            lines.append(f"  {d['name']}: ${d['balance']:,.2f} @ {d['apr']}%")

    if savings:
        lines.append(f"\nSAVINGS:")
        for g in savings:
            pct = (g.get("saved", 0) / g["target"] * 100) if g.get("target") else 0
            lines.append(f"  {g['goal']}: ${g.get('saved', 0):,.2f}/${g['target']:,.2f} ({pct:.0f}%)")

    # AI analysis (if available)
    ai_analysis = _ai_monthly_analysis(budget, name, lang, total_income)
    if ai_analysis:
        lines.append(f"\nAI INSIGHTS:\n{ai_analysis}")

    report_text = "\n".join(lines)

    # Write summary to Sheets
    try:
        from . import sheets
        sheets.write_monthly_summary(month, {
            "total_income": total_income,
            "total_expenses": budget["total_spent"],
            "total_fixed": total_fixed,
            "total_variable": total_variable,
            "surplus": surplus,
            "savings_contrib": sum(g.get("saved", 0) for g in savings),
            "debt_payments": total_debt_min,
            "deductible_total": 0,
        })
    except Exception:
        pass

    return {
        "report": "monthly_report",
        "month": month,
        "total_income": round(total_income, 2),
        "total_spent": budget["total_spent"],
        "surplus": round(surplus, 2),
        "total_debt": round(total_debt, 2),
        "_formatted": report_text,
    }


def _ai_monthly_analysis(budget: dict, name: str, lang: str, total_income: float) -> str | None:
    """Generate AI monthly analysis. Returns text or None."""
    spending = {c["category"]: c["spent"] for c in budget["categories"] if c["spent"] > 0}
    budgets = {c["category"]: c["budget"] for c in budget["categories"] if c["budget"] > 0}

    if not spending:
        return None

    lang_instruction = "Respond in Spanish." if lang == "es" else "Respond in English."
    system = "You are a personal finance advisor. Be concise and actionable."
    user = f"""Analyze {name}'s monthly finances. Provide:
1) Categories over/under budget
2) Single biggest savings opportunity next month
3) Motivational note
{lang_instruction}
Under 150 words.

Spending: {json.dumps(spending)}
Budgets: {json.dumps(budgets)}
Income: ${total_income:.0f}
Total spent: ${budget['total_spent']:.0f}"""

    backend = AI._get_backend()
    if backend["backend"] == "none":
        return None

    payload = {
        "model": AI._get_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.7,
    }
    resp = AI.ai_call(payload, timeout=30)
    if resp:
        return resp["choices"][0]["message"]["content"].strip()
    return None
