"""First-run setup wizard — AI-powered configuration."""

import json
from datetime import datetime
from pathlib import Path

from . import config as C


def run_setup_wizard(answers: dict = None) -> dict:
    """Run the setup wizard. Returns the created config.

    Reads name and language automatically from workspace USER.md.
    Only requires: cards, currency, tax type (+ tax_description if applicable).

    Non-interactive mode (pass JSON):
      finance.py setup '{"cards":"Chase Visa,Discover,Cash","currency":"USD","tax":"none"}'

    With tax:
      finance.py setup '{"cards":"Chase,Cash","currency":"USD","tax":"rental","tax_description":"Airbnb house"}'
    """
    interactive = answers is None
    if answers is None:
        answers = {}

    print("=" * 50)
    print("Finance Tracker — Setup")
    print("=" * 50)
    print()

    # Auto-detect name and language from workspace USER.md
    user_md = C.read_user_md()
    name = answers.get("name") or user_md.get("name") or "User"
    language = answers.get("language") or user_md.get("language") or "en"
    print(f"Name: {name} (from USER.md)")
    print(f"Language: {language}")

    # Cards — must be provided
    if "cards" in answers:
        cards_raw = answers["cards"]
        if isinstance(cards_raw, list):
            cards = cards_raw
        else:
            cards = [c.strip() for c in cards_raw.split(",")]
    elif interactive:
        print(f"\nWhat bank cards/accounts do you use? (comma-separated)")
        print(f"  Example: Chase Visa, Discover, Cash")
        cards_input = input("→ ").strip()
        cards = [c.strip() for c in cards_input.split(",")] if cards_input else ["Card 1", "Cash"]
    else:
        cards = ["Card 1", "Cash"]
    print(f"Cards: {', '.join(cards)}")

    # Currency — must be provided
    if "currency" in answers:
        currency = answers["currency"].upper()
    elif interactive:
        print(f"\nCurrency code (e.g. USD, EUR, GBP)?")
        currency = input("→ ").strip().upper() or "USD"
    else:
        currency = "USD"
    print(f"Currency: {currency}")

    # Spreadsheet name — auto-generated
    year = datetime.now().year
    sheet_name = answers.get("spreadsheet_name", f"{name} Finance {year}")

    # Save base config
    config = {
        "user": {
            "name": name,
            "language": language,
            "spreadsheet_name": sheet_name,
            "currency": currency,
            "cards": cards,
            "setup_complete": True,
            "created_at": datetime.now().isoformat(),
        },
        "categories": {
            "Groceries": {"monthly": 300, "threshold": 0.8},
            "Restaurants": {"monthly": 150, "threshold": 0.8},
            "Gas": {"monthly": 100, "threshold": 0.8},
            "Shopping": {"monthly": 200, "threshold": 0.8},
            "Entertainment": {"monthly": 75, "threshold": 0.8},
            "Subscriptions": {"monthly": 100, "threshold": 0.9},
            "Home": {"monthly": 150, "threshold": 0.8},
            "Personal": {"monthly": 75, "threshold": 0.8},
            "Travel": {"monthly": None, "threshold": None},
            "Work_Tools": {"monthly": 100, "threshold": 0.8},
            "Health": {"monthly": 75, "threshold": 0.8},
            "Other": {"monthly": 50, "threshold": 0.8},
        },
        "balance": {
            "available": 0,
            "last_updated": None,
            "pay_schedule": "biweekly",
            "pay_dates": [1, 15],
            "expected_paycheck": 0,
        },
        "tax": {
            "enabled": False,
            "business_type": None,
            "schedule_type": None,
            "business_name": None,
            "tax_categories": [],
            "ask_rules": [],
            "never_ask": [],
        },
        "payments": [],
        "savings": [],
    }
    C.save_json(C.CONFIG_DIR / "tracker_config.json", config)
    print(f"\n✅ Profile saved: {name}, {language}, {currency}")

    # Tax profile
    print("\n" + "=" * 50)
    print("Tax Deduction Setup")
    print("=" * 50)
    print()

    tax_type_map = {"none": "1", "rental": "2", "freelancer": "3", "business": "4", "other": "5"}

    if "tax" in answers:
        tax_type = answers["tax"].lower()
        biz_choice = tax_type_map.get(tax_type, "1")
    elif interactive:
        print("Do you have a business or side income where")
        print("some purchases might be tax-deductible?")
        print()
        print("  1. No — personal finance only")
        print("  2. Yes — rental property (Airbnb, VRBO, long-term)")
        print("  3. Yes — freelancer / contractor")
        print("  4. Yes — small business / side hustle")
        print("  5. Yes — other (I'll describe it)")
        print()
        biz_choice = input("→ ").strip()
    else:
        biz_choice = "1"

    if biz_choice == "1":
        tax_profile = {
            "enabled": False,
            "business_type": None,
            "schedule_type": None,
            "business_name": None,
            "tax_categories": [],
            "ask_rules": [],
            "never_ask": [],
            "generated_by": "setup_wizard",
            "generated_at": datetime.now().isoformat(),
        }
        config["tax"] = tax_profile
        C.save_json(C.CONFIG_DIR / "tracker_config.json", config)
        C.invalidate_config_cache()
        print("✅ Tax tracking disabled. Enable later: finance.py new-tax-profile")
    else:
        # Auto-assign schedule based on type
        default_schedule = "Schedule E" if biz_choice == "2" else "Schedule C"

        if "tax_description" in answers:
            biz_description = answers["tax_description"]
            biz_name = answers.get("tax_business_name") or None
            schedule = answers.get("tax_schedule", default_schedule)
        elif interactive:
            prompts = {
                "2": "Describe your rental property (e.g., 'Airbnb beach house in Florida'):",
                "3": "What kind of freelance/contract work? (e.g., 'web developer', 'consultant'):",
                "4": "Describe your business (e.g., 'Etsy candle shop', 'photography studio'):",
                "5": "Describe your business or income source:",
            }
            biz_description = input(f"\n{prompts.get(biz_choice, prompts['5'])}\n→ ").strip()
            biz_name = input(f"\nBusiness name (optional, Enter to skip):\n→ ").strip() or None
            schedule = default_schedule
        else:
            biz_description = "general business"
            biz_name = None
            schedule = default_schedule

        print(f"Tax: {biz_description} ({schedule})")
        print(f"\nGenerating tax deduction profile with AI...")
        tax_profile = _ai_generate_tax_profile(biz_description, schedule, biz_name)

        if tax_profile:
            config["tax"] = tax_profile
            C.save_json(C.CONFIG_DIR / "tracker_config.json", config)
            C.invalidate_config_cache()
            print(f"\n✅ Tax profile: {len(tax_profile['ask_rules'])} deduction rules")
            for rule in tax_profile["ask_rules"]:
                print(f"   • {rule['trigger']} ({len(rule['keywords'])} keywords)")
        else:
            print("\n⚠️ AI failed. Basic profile created — update later: finance.py new-tax-profile")
            tax_profile = _basic_tax_profile(biz_description, schedule, biz_name)
            config["tax"] = tax_profile
            C.save_json(C.CONFIG_DIR / "tracker_config.json", config)
            C.invalidate_config_cache()

    # Telegram / Cron configuration
    print("\n" + "=" * 50)
    print("Telegram & Scheduled Reports")
    print("=" * 50)
    print()

    tg_config = {}
    if "bot_token" in answers and "chat_id" in answers:
        tg_config["bot_token"] = answers["bot_token"]
        tg_config["chat_id"] = answers["chat_id"]
        tg_config["timezone"] = answers.get("timezone", "America/New_York")
    elif interactive:
        print("The Finance Tracker can send you automatic reports via Telegram:")
        print("  • Daily cashflow summary (weekday mornings)")
        print("  • Payment reminders")
        print("  • Weekly spending summary")
        print("  • Monthly tax report")
        print()
        print("To enable this, you need your Telegram Bot Token and Chat ID.")
        print("  Bot Token: get it from @BotFather when you create your bot")
        print("  Chat ID: send a message to @userinfobot to get yours")
        print()
        bot_token = input("Bot Token (Enter to skip, configure later):\n→ ").strip()
        if bot_token:
            chat_id = input("Chat ID:\n→ ").strip()
            if chat_id:
                tg_config["bot_token"] = bot_token
                tg_config["chat_id"] = chat_id
                print("\nWhat timezone are you in? (e.g. America/New_York, America/Chicago, Europe/London)")
                tz = input("→ ").strip() or "America/New_York"
                tg_config["timezone"] = tz
            else:
                print("⚠️ Skipped — no Chat ID. Configure later: finance.py setup-telegram")
        else:
            print("⚠️ Skipped. Configure later: finance.py setup-telegram")
    else:
        pass  # Non-interactive without telegram config — skip

    if tg_config.get("bot_token") and tg_config.get("chat_id"):
        config["telegram"] = tg_config
        C.save_json(C.CONFIG_DIR / "tracker_config.json", config)
        print(f"✅ Telegram configured (TZ: {tg_config.get('timezone', 'America/New_York')})")
        print(f"   Run: bash setup_crons.sh to install scheduled reports")
    else:
        config["telegram"] = {"bot_token": "", "chat_id": "", "timezone": "America/New_York"}
        C.save_json(C.CONFIG_DIR / "tracker_config.json", config)

    print("\n" + "=" * 50)
    print("✅ Setup complete!")
    print(f"   Spreadsheet: {sheet_name}")
    print("=" * 50)

    # Telemetry notice (legal requirement: inform user on first run)
    print()
    print("📊 Anonymous Usage Analytics")
    print("   This tool collects anonymous usage statistics (commands used,")
    print("   success/failure, timing) to improve the product.")
    print("   No personal information, financial data, or file contents")
    print("   are ever collected. Data cannot be linked back to you.")
    print("   Disable anytime: finance.py telemetry off")
    print("   Details: finance.py telemetry info")
    print()

    # Track setup completion
    from . import telemetry as T
    import time as _time
    T.track_install()
    T.track_setup_complete()
    # Track what setup received (no personal data — only structure)
    T.track_event("setup_input", {
        "cards_count": len(cards),
        "currency": currency,
        "tax_type": answers.get("tax", "none") if answers else "interactive",
        "had_tax_description": bool(answers.get("tax_description")) if answers else False,
        "source": "json" if answers else "interactive",
    })
    _time.sleep(1)  # Let telemetry threads finish before process exits

    return config


def run_tax_setup(answers: dict = None) -> dict | None:
    """Run only the tax profile section. Returns updated config.

    Non-interactive: finance.py new-tax-profile '{"tax":"rental","tax_description":"Airbnb"}'
    """
    config = C._load_tracker_config()

    if answers:
        tax_type_map = {"rental": "1", "freelancer": "2", "business": "3", "other": "4"}
        tax_type = answers.get("tax", "other").lower()
        biz_choice = tax_type_map.get(tax_type, "4")
        biz_description = answers.get("tax_description", "general business")
        biz_name = answers.get("tax_business_name") or None
        default_schedule = "Schedule E" if biz_choice == "1" else "Schedule C"
        schedule = answers.get("tax_schedule", default_schedule)
    else:
        print("=" * 50)
        print("Tax Deduction Profile Setup")
        print("=" * 50)
        print()
        print("What type of business or side income do you have?")
        print()
        print("  1. Rental property (Airbnb, VRBO, long-term)")
        print("  2. Freelancer / contractor")
        print("  3. Small business / side hustle")
        print("  4. Other (I'll describe it)")
        print()
        biz_choice = input("→ ").strip()

        prompts = {
            "1": "Describe your rental property:",
            "2": "What kind of freelance/contract work?",
            "3": "Describe your business:",
            "4": "Describe your business or income source:",
        }
        biz_description = input(f"\n{prompts.get(biz_choice, prompts['4'])}\n→ ").strip()
        biz_name = input(f"\nBusiness name (optional, Enter to skip):\n→ ").strip() or None
        default_schedule = "Schedule E" if biz_choice == "1" else "Schedule C"
        schedule = default_schedule

    print(f"\nGenerating tax deduction profile for: {biz_description}...")
    tax_profile = _ai_generate_tax_profile(biz_description, schedule, biz_name)

    if not tax_profile:
        print("\n⚠️ AI failed. Basic profile created.")
        tax_profile = _basic_tax_profile(biz_description, schedule, biz_name)

    config["tax"] = tax_profile
    C.save_tracker_config(config)
    print(f"\n✅ Tax profile: {len(tax_profile.get('ask_rules', []))} deduction rules.")
    return config


def _ai_generate_tax_profile(business_description: str, schedule: str, business_name: str = None) -> dict | None:
    """Use AI to generate a tax deduction profile based on business description."""

    prompt = f"""I need you to create a tax deduction profile for a personal expense tracker.

Business: {business_description}
Tax schedule: {schedule}
{f'Business name: {business_name}' if business_name else ''}

Create a JSON profile with:
1. "business_type": one-line description of the business
2. "schedule_type": "{schedule}"
3. "business_name": "{business_name or 'null'}"
4. "tax_categories": array of 4-8 deduction category objects with "id" (snake_case) and "label" (human-readable)
5. "ask_rules": array of 4-8 rules, each with:
   - "trigger": human description of what to look for
   - "keywords": array of 15-25 lowercase keywords/phrases that appear on receipts or bank statements for items that MIGHT be tax-deductible for this business
   - "tax_category": matching one of the tax_categories ids
6. "never_ask": array of 15-20 keywords for items that are NEVER deductible (food, personal clothing, entertainment, medicine, etc.)

IMPORTANT:
- Keywords should be things that appear on actual receipts and bank statements (store names, product types, service names)
- Be specific to THIS business type
- Include both English and Spanish common terms where applicable
- The "ask" items are things that COULD be deductible but need user confirmation (could be personal too)
- The "never_ask" items should NEVER trigger the question

Respond ONLY with valid JSON, no markdown fences, no explanation."""

    payload = {
        "model": C.CLASSIFY_MODEL,
        "messages": [
            {"role": "system", "content": "You are a tax categorization expert. Output only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }

    ai_text = C.ai_extract_text(payload, timeout=60, _caller="tax-profile")
    if not ai_text:
        print(f"  AI error: empty response from {C.LITELLM_URL} (model: {C.CLASSIFY_MODEL})")
        _track_tax("ai_failed", schedule, 0)
        return None

    try:
        profile = json.loads(ai_text)
        profile["enabled"] = True
        profile["generated_by"] = "ai_setup_wizard"
        profile["generated_at"] = datetime.now().isoformat()
        _track_tax("ai_wizard", schedule, len(profile.get("ask_rules", [])))
        return profile
    except json.JSONDecodeError as e:
        print(f"  AI error: model returned invalid JSON: {e}")
        print(f"  Response: {ai_text[:300]}")
        _track_tax("ai_invalid_json", schedule, 0)
        return None


def _track_tax(method: str, schedule: str, rules_count: int):
    """Fire-and-forget tax profile telemetry."""
    try:
        from . import telemetry as T
        T.track_tax_profile(method, schedule, rules_count)
    except Exception:
        pass


def _basic_tax_profile(business_description: str, schedule: str, business_name: str = None) -> dict:
    """Fallback basic profile when AI fails."""
    _track_tax("basic_fallback", schedule, 1)
    return {
        "enabled": True,
        "business_type": business_description,
        "schedule_type": schedule,
        "business_name": business_name,
        "tax_categories": [
            {"id": "business_expense", "label": "General Business Expense"},
            {"id": "business_supplies", "label": "Business Supplies"},
        ],
        "ask_rules": [
            {
                "trigger": "Potential business purchase",
                "keywords": ["supply", "supplies", "equipment", "tool", "tools", "professional", "business"],
                "tax_category": "business_expense",
            }
        ],
        "never_ask": ["food", "groceries", "clothing", "medicine", "entertainment", "alcohol", "toys"],
        "generated_by": "basic_fallback",
        "generated_at": datetime.now().isoformat(),
    }
