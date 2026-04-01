"""Module 3: Budget Monitor — real-time alerts and weekly summaries."""

import json
import subprocess
from datetime import datetime

from . import config as C
from . import sheets


def weekly_summary(year: int = None, month: int = None) -> str:
    """Generate the weekly spending summary."""
    now = datetime.now()
    month_str = f"{year or now.year}-{(month or now.month):02d}"
    spending = sheets.get_all_month_spending(month_str)
    budgets = C.get_category_budgets()
    lang = C.get_language()
    name = C.get_owner_name()

    lines = [f"WEEKLY SUMMARY — {now.strftime('%b %d, %Y')}"] if lang == "en" else [f"RESUMEN SEMANAL — {now.strftime('%b %d, %Y')}"]

    total = sum(spending.values())
    days_elapsed = now.day
    daily_avg = total / max(days_elapsed, 1)
    if lang == "es":
        lines.append(f"Gastaste ${total:.0f} este mes (${daily_avg:.0f}/día)")
    else:
        lines.append(f"Spent ${total:.0f} this month (${daily_avg:.0f}/day)")
    lines.append("")

    for cat in C.get_categories():
        budget = budgets.get(cat, {}).get("monthly")
        if not budget:
            continue
        spent = spending.get(cat, 0)
        pct = (spent / budget * 100) if budget else 0
        if pct >= 95:
            flag = "OVER" if pct >= 100 else "ALERT"
            if lang == "es":
                flag = "EXCEDIDO" if pct >= 100 else "ALERTA"
        elif pct >= 80:
            flag = "CAUTION" if lang == "en" else "CUIDADO"
        else:
            flag = "OK"
        lines.append(f"  {cat}: ${spent:.0f}/${budget} ({pct:.0f}%) [{flag}]")

    # Upcoming payments
    payments = C.get_payments()
    upcoming = _upcoming_payments(payments, days=7)
    if upcoming:
        lines.append("")
        for p in upcoming:
            if lang == "es":
                lines.append(f"Próximo pago: {p['name']} ${p['amount']} el día {p['due_day']} (en {p['days_until']} días)")
            else:
                lines.append(f"Upcoming payment: {p['name']} ${p['amount']} on day {p['due_day']} (in {p['days_until']} days)")

    # AI analysis
    analysis = _ai_weekly_analysis(spending, budgets, name, lang)
    if analysis:
        lines.append("")
        lines.append(analysis)

    return "\n".join(lines)


def budget_status_brief(month: str = None) -> str:
    """Short budget status for daily cashflow message."""
    now = datetime.now()
    month_str = month or f"{now.year}-{now.month:02d}"
    spending = sheets.get_all_month_spending(month_str)
    budgets = C.get_category_budgets()

    lines = ["Budget status:"]
    for cat in C.get_categories():
        budget = budgets.get(cat, {}).get("monthly")
        if not budget:
            continue
        spent = spending.get(cat, 0)
        pct = spent / budget * 100
        icon = "✔" if pct < 80 else ("⚠" if pct < 100 else "🔴")
        if spent > 0 or pct >= 50:
            lines.append(f"  {cat}: ${spent:.0f}/${budget} ({pct:.0f}%) {icon}")

    return "\n".join(lines)


def _upcoming_payments(payments: list, days: int = 7) -> list:
    now = datetime.now()
    current_day = now.day
    results = []
    for p in payments:
        due = p["due_day"]
        days_until = (due - current_day) % 30
        if 0 <= days_until <= days:
            results.append({**p, "days_until": days_until})
    results.sort(key=lambda x: x["days_until"])
    return results


def _ai_weekly_analysis(spending: dict, budgets: dict, name: str, lang: str) -> str:
    """Short AI analysis of weekly spending patterns."""
    lang_instruction = "Under 100 words. Spanish only." if lang == "es" else "Under 100 words. English only."
    prompt = f"""Analyze {name}'s spending this month. Provide 3-4 sentences:
- Unusual purchases or patterns
- Categories trending over budget
- One actionable tip

Spending: {json.dumps(spending)}
Budgets: {json.dumps({k: v.get('monthly') for k, v in budgets.items() if v.get('monthly')})}

{lang_instruction}"""

    payload = {
        "model": C.PARSE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }

    try:
        result = subprocess.run(
            ["curl", "-s", C.LITELLM_URL,
             "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {C.LITELLM_KEY}",
             "-d", json.dumps(payload)],
            capture_output=True, text=True, timeout=30
        )
        resp = json.loads(result.stdout)
        return resp["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""
