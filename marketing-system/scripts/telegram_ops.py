"""
Telegram Operations Bot — Phase 4A (Read-only + Reports)
Long-polling bot for marketing system monitoring.
"""

import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Paths & Config
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import db

ENV_PATH = Path("/home/robotin/.openclaw/.env")
OFFSET_PATH = Path("/home/robotin/.openclaw/marketing-system/config/telegram_ops_offset.json")
SECURITY_PATH = Path("/home/robotin/.openclaw/marketing-system/config/telegram_security.json")

# ---------------------------------------------------------------------------
# Environment loading
# ---------------------------------------------------------------------------

def _load_env():
    """Load .env variables into os.environ."""
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"')
                if k and k not in os.environ:
                    os.environ[k] = v

_load_env()

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = None
ALLOWED_USERS = set()

def _load_security():
    """Load chat_id and allowed users from security config + env."""
    global CHAT_ID, ALLOWED_USERS
    # From security config file
    if SECURITY_PATH.exists():
        cfg = json.loads(SECURITY_PATH.read_text())
        ids = cfg.get("allowed_user_ids", [])
        if ids:
            CHAT_ID = str(ids[0])
            ALLOWED_USERS = {str(i) for i in ids}
    # Merge from env
    env_users = os.environ.get("TELEGRAM_ALLOWED_USERS", "")
    if env_users:
        for u in env_users.split(","):
            u = u.strip()
            if u:
                ALLOWED_USERS.add(u)
                if not CHAT_ID:
                    CHAT_ID = u

_load_security()

# ---------------------------------------------------------------------------
# Offset persistence
# ---------------------------------------------------------------------------

def load_offset():
    if OFFSET_PATH.exists():
        try:
            return json.loads(OFFSET_PATH.read_text()).get("offset", 0)
        except Exception:
            pass
    return 0


def save_offset(offset):
    OFFSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_PATH.write_text(json.dumps({"offset": offset}))

# ---------------------------------------------------------------------------
# Telegram API helpers
# ---------------------------------------------------------------------------

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def poll_updates(offset, timeout=30):
    try:
        r = requests.get(f"{API_BASE}/getUpdates",
                         params={"offset": offset, "timeout": timeout},
                         timeout=timeout + 10)
        data = r.json()
        if data.get("ok"):
            return data.get("result", [])
    except Exception:
        time.sleep(5)
    return []


def send_message(text, chat_id=None, parse_mode="Markdown"):
    cid = chat_id or CHAT_ID
    if not cid:
        print("[ERROR] No chat_id configured")
        return False
    # Telegram limit 4096 chars
    if len(text) > 4000:
        text = text[:3990] + "\n...(truncado)"
    try:
        r = requests.post(f"{API_BASE}/sendMessage",
                          json={"chat_id": cid, "text": text, "parse_mode": parse_mode},
                          timeout=15)
        resp = r.json()
        if not resp.get("ok"):
            # Retry without parse_mode if markdown fails
            r = requests.post(f"{API_BASE}/sendMessage",
                              json={"chat_id": cid, "text": text},
                              timeout=15)
            resp = r.json()
        return resp.get("ok", False)
    except Exception as e:
        print(f"[ERROR] send_message: {e}")
        return False

# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_help(args):
    return (
        "*Marketing Operations Bot*\n\n"
        "*REPORTS:*\n"
        "  /status -- System overview\n"
        "  /strategy report <product\\_id> -- Active strategy\n"
        "  /week brief <product\\_id> <week> -- Weekly summary\n"
        "  /growth report <product\\_id> <week> -- Growth diagnosis\n\n"
        "*DATA:*\n"
        "  /db segments <product\\_id> -- Buyer segments\n"
        "  /db assets <product\\_id> [week] -- Assets with status\n"
        "  /db campaigns <product\\_id> -- Active campaigns\n"
        "  /db experiments <product\\_id> -- Experiments\n"
        "  /db kb <product\\_id> -- Knowledge base patterns\n"
        "  /db orders [days] -- Recent Stripe orders"
    )


def cmd_status(args):
    lines = ["*SYSTEM STATUS*\n"]

    try:
        with db._cursor() as cur:
            cur.execute("SELECT project_id, project_name FROM marketing.projects")
            projects = db._all(cur)
    except Exception as e:
        return f"Error reading projects: {e}"

    for p in projects:
        pid = p["project_id"]

        # Strategy
        active = db.get_active_strategy(pid)
        strategy_info = f"v{active['version']} ({active['status']})" if active else "none"

        # Campaigns
        campaigns = db.get_active_campaigns(pid)
        campaign_info = campaigns[0]["campaign_name"] if campaigns else "none"

        # Assets count
        with db._cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM marketing.assets WHERE project_id=%s", (pid,))
            asset_count = db._one(cur)["cnt"]

        # KB
        kb = db.get_kb(pid)
        winning = sum(1 for e in kb if e.get("status") == "winning")
        losing = sum(1 for e in kb if e.get("status") == "losing")
        kb_info = f"{len(kb)} ({winning} winning, {losing} losing)" if kb else "empty"

        # Experiments
        exps = db.get_experiments(pid)
        exp_info = str(len(exps)) if exps else "0"

        lines.append(f"*{p['project_name']}* (`{pid}`)")
        lines.append(f"  Strategy: {strategy_info}")
        lines.append(f"  Campaign: {campaign_info}")
        lines.append(f"  Assets: {asset_count}")
        lines.append(f"  KB: {kb_info}")
        lines.append(f"  Experiments: {exp_info}")

    # Service checks
    lines.append("\n*SERVICES:*")

    # PostgreSQL
    try:
        conn = db.get_conn()
        db.close_conn(conn)
        lines.append("  PostgreSQL: OK")
    except Exception:
        lines.append("  PostgreSQL: OFFLINE")

    # LiteLLM
    try:
        r = requests.get("http://127.0.0.1:4000/health",
                         headers={"Authorization": f"Bearer {os.environ.get('LITELLM_API_KEY', 'sk-litellm-local')}"},
                         timeout=3)
        lines.append("  LiteLLM: OK" if r.status_code == 200 else "  LiteLLM: OFFLINE")
    except Exception:
        lines.append("  LiteLLM: OFFLINE")

    # Stripe
    stripe_key = os.environ.get("STRIPE_API_KEY", "")
    if stripe_key:
        try:
            r = requests.get("https://api.stripe.com/v1/balance",
                             headers={"Authorization": f"Bearer {stripe_key}"},
                             timeout=5)
            lines.append("  Stripe: OK" if r.status_code == 200 else "  Stripe: OFFLINE")
        except Exception:
            lines.append("  Stripe: OFFLINE")
    else:
        lines.append("  Stripe: not configured")

    return "\n".join(lines)


def cmd_strategy_report(args):
    # /strategy report <product_id>
    if len(args) < 2 or args[0] != "report":
        return "Usage: /strategy report <product\\_id>"
    pid = args[1]

    project = db.get_project(pid)
    if not project:
        return f"Project `{pid}` not found."

    active = db.get_active_strategy(pid)
    if not active:
        return f"No approved strategy for `{pid}`."

    version = active["version"]
    outputs = db.get_all_strategy_outputs(pid, version)

    lines = [f"*STRATEGY REPORT* -- {pid} (v{version})\n"]

    for out in outputs:
        otype = out["output_type"]
        data = out.get("data", {})
        if not isinstance(data, dict):
            try:
                data = json.loads(data)
            except Exception:
                data = {}

        if otype == "market_analysis":
            competitors = data.get("competitors", [])
            if isinstance(competitors, list):
                comp_names = ", ".join(c if isinstance(c, str) else c.get("name", "?") for c in competitors[:5])
            else:
                comp_names = str(competitors)
            market_size = data.get("market_size", data.get("tam", "n/a"))
            lines.append("*MARKET ANALYSIS:*")
            lines.append(f"  Competitors: {comp_names}")
            lines.append(f"  Market size: {market_size}")

        elif otype == "buyer_segments":
            segments = data.get("segments", data.get("buyer_segments", []))
            if segments:
                lines.append(f"\n*BUYER SEGMENTS ({len(segments)}):*")
                icons = {"primary": "TARGET", "secondary": "PIN", "exploratory": "EXPLORE"}
                for s in segments:
                    prio = s.get("priority", "primary")
                    icon = icons.get(prio, "?")
                    sid = s.get("segment_id", s.get("id", "?"))
                    uc = s.get("use_case", s.get("description", ""))
                    lines.append(f"  [{icon}] {sid} -- {uc}")

        elif otype == "brand_positioning":
            pos = data.get("positioning_statement", data.get("statement", ""))
            angles = data.get("creative_angles", [])
            lines.append(f"\n*BRAND POSITIONING:*")
            if pos:
                lines.append(f'  "{pos}"')
            if angles:
                lines.append(f"  Creative angles: {len(angles)}")

        elif otype == "seo_keywords":
            keywords = data.get("keywords", [])
            urls = data.get("target_urls", data.get("urls", []))
            lines.append(f"\n*SEO:*")
            lines.append(f"  Keywords: {len(keywords)}")
            if urls:
                lines.append(f"  Target URLs: {len(urls)}")

        else:
            title = out.get("title", otype)
            lines.append(f"\n*{title.upper()}:*")
            # Show top-level keys as summary
            for k, v in list(data.items())[:5]:
                if isinstance(v, list):
                    lines.append(f"  {k}: {len(v)} items")
                elif isinstance(v, dict):
                    lines.append(f"  {k}: {len(v)} keys")
                else:
                    lines.append(f"  {k}: {v}")

    return "\n".join(lines) if len(lines) > 1 else f"No strategy outputs for `{pid}` v{version}."


def cmd_week(args):
    # /week brief <product_id> <week>
    if len(args) < 3 or args[0] != "brief":
        return "Usage: /week brief <product\\_id> <week>\nExample: /week brief misterio-semanal 2026-W17"
    pid = args[1]
    week = args[2]

    project = db.get_project(pid)
    if not project:
        return f"Project `{pid}` not found."

    # Convert week to date (Monday of that week)
    try:
        year, wk = week.split("-W")
        from datetime import datetime as dt
        week_date = dt.strptime(f"{year}-W{wk}-1", "%Y-W%W-%w").date()
    except Exception:
        return f"Invalid week format: `{week}`. Use YYYY-WNN (e.g. 2026-W17)."

    # Find campaign run for this week
    campaigns = db.get_active_campaigns(pid)
    # Also check all campaigns
    with db._cursor() as cur:
        cur.execute("SELECT * FROM marketing.campaigns WHERE project_id = %s", (pid,))
        all_campaigns = db._all(cur)

    run = None
    for c in all_campaigns:
        r = db.get_run(c["campaign_id"], week_date)
        if r:
            run = r
            break

    # Assets for this week
    assets = db.get_assets(pid, week_start_date=week_date)

    lines = [f"*WEEKLY BRIEF* -- {pid} {week}\n"]

    if run:
        lines.append(f"Status: {run.get('status', 'unknown')}")
        if run.get("theme"):
            lines.append(f"Theme: {run['theme']}")

    if assets:
        # Group by asset_type
        by_type = {}
        for a in assets:
            t = a.get("asset_type", "unknown")
            by_type.setdefault(t, []).append(a)

        lines.append(f"\n*ASSETS GENERATED:*")
        for atype, alist in sorted(by_type.items()):
            status = alist[0].get("status", "?")
            lines.append(f"  {atype}: {len(alist)} ({status})")

        lines.append(f"  ---")
        lines.append(f"  Total: {len(assets)} assets")

        # QA: check for quality_report assets
        qa_assets = [a for a in assets if a.get("asset_type") == "quality_report"]
        if qa_assets:
            lines.append(f"\n*QA:*")
            for qa in qa_assets:
                content = qa.get("content", {})
                if isinstance(content, str):
                    try:
                        content = json.loads(content)
                    except Exception:
                        content = {}
                if isinstance(content, dict):
                    criticals = content.get("criticals", content.get("critical_count", "?"))
                    warnings = content.get("warnings", content.get("warning_count", "?"))
                    lines.append(f"  Quality reviewer: {criticals} criticals, {warnings} warnings")
    else:
        lines.append("No assets found for this week.")

    if not run and not assets:
        lines.append("No data found for this week.")

    return "\n".join(lines)


def cmd_growth_report(args):
    # /growth report <product_id> <week>
    if len(args) < 3 or args[0] != "report":
        return "Usage: /growth report <product\\_id> <week>\nExample: /growth report misterio-semanal 2026-W17"
    pid = args[1]
    week = args[2]

    project = db.get_project(pid)
    if not project:
        return f"Project `{pid}` not found."

    # Get growth analyses
    analyses = db.get_growth_history(pid)

    # Try to find matching week
    try:
        year, wk = week.split("-W")
        from datetime import datetime as dt
        week_date = dt.strptime(f"{year}-W{wk}-1", "%Y-W%W-%w").date()
    except Exception:
        return f"Invalid week format: `{week}`. Use YYYY-WNN."

    match = None
    for a in analyses:
        if a.get("week_start_date") and str(a["week_start_date"]) == str(week_date):
            match = a
            break

    if not match:
        return (f"*GROWTH REPORT* -- {pid} {week}\n\n"
                f"No growth data yet for {week}.")

    results = match.get("results", {})
    if isinstance(results, str):
        try:
            results = json.loads(results)
        except Exception:
            results = {}

    lines = [f"*GROWTH REPORT* -- {pid} {week}\n"]

    root_cause = results.get("root_cause", results.get("summary", ""))
    if root_cause:
        lines.append(f"ROOT CAUSE: {root_cause}")
    decision_level = results.get("decision_level", "")
    if decision_level:
        lines.append(f"DECISION LEVEL: {decision_level}")
    domain = results.get("problem_domain", "")
    if domain:
        lines.append(f"PROBLEM DOMAIN: {domain}")

    # Winning patterns
    winning = results.get("winning_patterns", [])
    if winning:
        lines.append(f"\n*WINNING PATTERNS:*")
        for w in winning:
            wid = w.get("pattern_id", "")
            desc = w.get("description", w.get("title", ""))
            lines.append(f"  + {wid}: {desc}")

    # Losing patterns
    losing = results.get("losing_patterns", [])
    if losing:
        lines.append(f"\n*LOSING PATTERNS:*")
        for l in losing:
            lid = l.get("pattern_id", "")
            desc = l.get("description", l.get("title", ""))
            lines.append(f"  - {lid}: {desc}")

    # Experiments
    experiments = results.get("experiments", [])
    if experiments:
        lines.append(f"\n*EXPERIMENTS:*")
        for e in experiments:
            eid = e.get("experiment_id", "")
            name = e.get("experiment_name", e.get("name", ""))
            status = e.get("status", "proposed")
            lines.append(f"  [{status}] {eid}: {name}")

    return "\n".join(lines)


def cmd_db(args):
    if not args:
        return "Usage: /db <segments|assets|campaigns|experiments|kb|orders> [product\\_id] [extra]"

    subcmd = args[0].lower()
    handlers = {
        "segments": _db_segments,
        "assets": _db_assets,
        "campaigns": _db_campaigns,
        "experiments": _db_experiments,
        "kb": _db_kb,
        "orders": _db_orders,
    }
    handler = handlers.get(subcmd)
    if not handler:
        return f"Unknown /db subcommand: `{subcmd}`\nAvailable: segments, assets, campaigns, experiments, kb, orders"
    return handler(args[1:])


def _db_segments(args):
    if not args:
        return "Usage: /db segments <product\\_id>"
    pid = args[0]
    segments = db.get_buyer_segments(pid)
    if not segments:
        return f"No segments for `{pid}`."

    lines = [f"*BUYER SEGMENTS* -- {pid}\n"]
    icons = {"primary": "TARGET", "secondary": "PIN", "exploratory": "EXPLORE"}
    for i, s in enumerate(segments, 1):
        prio = s.get("priority", "primary")
        icon = icons.get(prio, "?")
        name = s.get("segment_name", s.get("segment_id", "?"))
        uc = s.get("use_case", "")
        lines.append(f"{i}. {name} [{icon}] ({prio})")
        if uc:
            lines.append(f'   "{uc}"')
    return "\n".join(lines)


def _db_assets(args):
    if not args:
        return "Usage: /db assets <product\\_id> [week]"
    pid = args[0]
    week_date = None
    week_label = ""

    if len(args) > 1:
        week = args[1]
        try:
            year, wk = week.split("-W")
            from datetime import datetime as dt
            week_date = dt.strptime(f"{year}-W{wk}-1", "%Y-W%W-%w").date()
            week_label = f" {week}"
        except Exception:
            return f"Invalid week format: `{args[1]}`. Use YYYY-WNN."

    assets = db.get_assets(pid, week_start_date=week_date)
    if not assets:
        return f"No assets for `{pid}`{week_label}."

    by_type = {}
    for a in assets:
        t = a.get("asset_type", "unknown")
        s = a.get("status", "?")
        by_type.setdefault(t, {"count": 0, "status": s})
        by_type[t]["count"] += 1

    lines = [f"*ASSETS* -- {pid}{week_label}\n"]
    total = 0
    for atype, info in sorted(by_type.items()):
        lines.append(f"  {atype}: {info['count']} ({info['status']})")
        total += info["count"]
    lines.append(f"  ---")
    lines.append(f"  Total: {total} assets")
    return "\n".join(lines)


def _db_campaigns(args):
    if not args:
        return "Usage: /db campaigns <product\\_id>"
    pid = args[0]

    with db._cursor() as cur:
        cur.execute("""
            SELECT * FROM marketing.campaigns
            WHERE project_id = %s ORDER BY created_at DESC
        """, (pid,))
        campaigns = db._all(cur)

    if not campaigns:
        return f"No campaigns for `{pid}`."

    lines = [f"*CAMPAIGNS* -- {pid}\n"]
    for i, c in enumerate(campaigns, 1):
        name = c.get("campaign_name", c.get("campaign_id", "?"))
        status = c.get("status", "?")
        budget = c.get("budget", {})
        spend = budget.get("spend", 0) if isinstance(budget, dict) else 0
        revenue = budget.get("revenue", 0) if isinstance(budget, dict) else 0
        lines.append(f"{i}. {name} -- {status}")

        # Count assets for this campaign
        with db._cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM marketing.assets WHERE campaign_id = %s",
                        (c["id"],))
            asset_count = db._one(cur)["cnt"]
        if asset_count:
            lines.append(f"   Assets: {asset_count}")
    return "\n".join(lines)


def _db_experiments(args):
    if not args:
        return "Usage: /db experiments <product\\_id>"
    pid = args[0]
    exps = db.get_experiments(pid)
    if not exps:
        return f"No experiments for `{pid}`."

    lines = [f"*EXPERIMENTS* -- {pid}\n"]
    for i, e in enumerate(exps, 1):
        name = e.get("experiment_name", e.get("experiment_id", "?"))
        status = e.get("status", "?")
        hyp = e.get("hypothesis", "")
        lines.append(f"{i}. {name} ({status})")
        if hyp:
            lines.append(f"   Hypothesis: {hyp}")
    return "\n".join(lines)


def _db_kb(args):
    if not args:
        return "Usage: /db kb <product\\_id>"
    pid = args[0]
    entries = db.get_kb(pid)
    if not entries:
        return f"No KB entries for `{pid}`."

    lines = [f"*KNOWLEDGE BASE* -- {pid}\n"]
    for i, e in enumerate(entries, 1):
        title = e.get("title", e.get("pattern_id", "?"))
        status = e.get("status", "active")
        conf = e.get("confidence", 0)
        icon = "+" if status == "winning" else ("-" if status == "losing" else "o")
        lines.append(f"{i}. [{icon}] {title}")
        lines.append(f"   Status: {status} | Confidence: {conf:.0%}")
    return "\n".join(lines)


def _db_orders(args):
    days = 30
    if args:
        try:
            days = int(args[0])
        except ValueError:
            return "Usage: /db orders [days]  (default 30)"

    # Get all projects to query orders
    with db._cursor() as cur:
        cur.execute("SELECT project_id FROM marketing.projects")
        projects = db._all(cur)

    all_orders = []
    for p in projects:
        orders = db.get_orders(p["project_id"], last_n_days=days)
        all_orders.extend(orders)

    if not all_orders:
        return f"No orders in last {days} days."

    lines = [f"*ORDERS* -- last {days} days\n"]
    total_amount = 0
    for i, o in enumerate(all_orders[:20], 1):
        oid = o.get("order_id", "?")
        amount = o.get("amount", 0)
        currency = o.get("currency", "USD")
        status = o.get("status", "?")
        date = o.get("order_date", "")
        if date:
            date = str(date)[:10]
        lines.append(f"{i}. {oid} -- ${amount} {currency} ({status}) {date}")
        total_amount += float(amount) if amount else 0

    lines.append(f"\nTotal: ${total_amount:.2f} ({len(all_orders)} orders)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command router
# ---------------------------------------------------------------------------

COMMANDS = {
    "/help": cmd_help,
    "/start": cmd_help,
    "/status": cmd_status,
    "/strategy": cmd_strategy_report,
    "/week": cmd_week,
    "/growth": cmd_growth_report,
    "/db": cmd_db,
}


def route_command(text):
    parts = text.strip().split()
    cmd = parts[0].lower()
    args = parts[1:]

    # Handle bot commands with @botname suffix
    if "@" in cmd:
        cmd = cmd.split("@")[0]

    handler = COMMANDS.get(cmd)
    if handler:
        return handler(args)
    return None


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    if not BOT_TOKEN:
        print("[FATAL] TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)
    if not CHAT_ID:
        print("[FATAL] No chat_id configured (check telegram_security.json or TELEGRAM_ALLOWED_USERS)")
        sys.exit(1)

    print(f"Telegram Ops Bot started.")
    print(f"  Chat ID: {CHAT_ID}")
    print(f"  Allowed users: {ALLOWED_USERS or 'any in chat'}")
    print(f"  Listening for commands...\n")

    offset = load_offset()

    while True:
        try:
            updates = poll_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                save_offset(offset)

                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                user_id = msg.get("from", {}).get("id")
                text = msg.get("text", "")

                # Security: only respond to allowed chat + user
                if str(chat_id) != CHAT_ID:
                    continue
                if ALLOWED_USERS and str(user_id) not in ALLOWED_USERS:
                    continue

                if text.startswith("/"):
                    print(f"[CMD] {text} (from user {user_id})")
                    try:
                        response = route_command(text)
                        if response:
                            send_message(response, chat_id=str(chat_id))
                    except Exception as e:
                        err_msg = f"Error: {e}"
                        print(f"[ERROR] {traceback.format_exc()}")
                        send_message(err_msg, chat_id=str(chat_id), parse_mode=None)

        except KeyboardInterrupt:
            print("\nBot stopped.")
            break
        except Exception as e:
            print(f"[ERROR] Main loop: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
