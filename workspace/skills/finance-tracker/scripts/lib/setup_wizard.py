"""First-run setup wizard — AI-powered configuration."""

import json
from datetime import datetime
from pathlib import Path

from . import config as C


def run_setup_wizard(interactive: bool = True) -> dict:
    """Run the setup wizard. Returns the created config.

    Steps:
    1. Ask user's name
    2. Ask preferred language (en/es)
    3. Ask what cards/accounts they use
    4. Ask if they have a business for tax deductions
    5. If yes: ask business type -> AI generates tax profile
    6. Save everything to tracker_config.json
    7. Create Google Sheet with the right name
    """
    print("=" * 50)
    print("Finance Tracker — First Time Setup")
    print("=" * 50)
    print()

    # Step 1: Name
    name = input("What's your first name? → ").strip() or "User"

    # Step 2: Language
    print("\nPreferred language?")
    print("  1. English")
    print("  2. Español")
    lang_choice = input("→ ").strip()
    language = "es" if lang_choice == "2" else "en"

    # Step 3: Currency
    print(f"\nCurrency code (default: USD)?")
    currency = input("→ ").strip().upper() or "USD"

    # Step 4: Cards
    print(f"\nWhat bank cards/accounts do you use? (comma-separated)")
    print(f"  Example: Chase Visa, Discover, Cash")
    cards_input = input("→ ").strip()
    cards = [c.strip() for c in cards_input.split(",")] if cards_input else ["Card 1", "Cash"]

    # Step 5: Spreadsheet name
    year = datetime.now().year
    default_sheet = f"{name} Finance {year}"
    print(f"\nGoogle Sheets name (default: {default_sheet})?")
    sheet_name = input("→ ").strip() or default_sheet

    # Save everything to tracker_config.json (single file)
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

    # Step 6: Tax profile
    print("\n" + "=" * 50)
    print("Tax Deduction Setup")
    print("=" * 50)
    print()
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
        print("\n✅ Tax tracking disabled. You can enable it later with: finance.py new-tax-profile")
    else:
        if biz_choice == "2":
            biz_description = input("\nDescribe your rental property (e.g., 'Airbnb beach house in Florida'):\n→ ").strip()
            default_schedule = "Schedule E"
        elif biz_choice == "3":
            biz_description = input("\nWhat kind of freelance/contract work? (e.g., 'web developer', 'graphic designer', 'consultant'):\n→ ").strip()
            default_schedule = "Schedule C"
        elif biz_choice == "4":
            biz_description = input("\nDescribe your business (e.g., 'Etsy candle shop', 'auto repair', 'photography studio'):\n→ ").strip()
            default_schedule = "Schedule C"
        else:
            biz_description = input("\nDescribe your business or income source:\n→ ").strip()
            default_schedule = "Schedule C"

        biz_name = input(f"\nBusiness name (optional, press Enter to skip):\n→ ").strip() or None

        print(f"\nTax schedule (default: {default_schedule})?")
        print("  Schedule C = self-employment / business income")
        print("  Schedule E = rental property income")
        print("  Other = enter your own")
        schedule = input("→ ").strip() or default_schedule

        print(f"\nAI is generating your tax deduction profile for: {biz_description}...")
        tax_profile = _ai_generate_tax_profile(biz_description, schedule, biz_name)

        if tax_profile:
            config["tax"] = tax_profile
            C.save_json(C.CONFIG_DIR / "tracker_config.json", config)
            C.invalidate_config_cache()
            print(f"\n✅ Tax profile created with {len(tax_profile['ask_rules'])} deduction rules:")
            for rule in tax_profile["ask_rules"]:
                print(f"   • {rule['trigger']} ({len(rule['keywords'])} keywords)")
            print(f"\n   Items that will NEVER be asked: {', '.join(tax_profile['never_ask'][:5])}...")
            print(f"\n   You can update this anytime: finance.py update-tax-profile")
        else:
            print("\n⚠️ AI generation failed. Creating basic profile — update later with: finance.py new-tax-profile")
            tax_profile = _basic_tax_profile(biz_description, schedule, biz_name)
            config["tax"] = tax_profile
            C.save_json(C.CONFIG_DIR / "tracker_config.json", config)
            C.invalidate_config_cache()

    print("\n" + "=" * 50)
    print("✅ Setup complete!")
    print(f"   Spreadsheet: {sheet_name}")
    print(f"   Next: run 'finance.py setup-sheets' to create the Google Sheet")
    print("=" * 50)

    # Track setup completion
    from . import telemetry as T
    T.track_install()
    T.track_setup_complete()

    return config


def run_tax_setup() -> dict | None:
    """Run only the tax profile section of the wizard. Returns updated config."""
    config = C._load_tracker_config()

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

    if biz_choice == "1":
        biz_description = input("\nDescribe your rental property:\n→ ").strip()
        default_schedule = "Schedule E"
    elif biz_choice == "2":
        biz_description = input("\nWhat kind of freelance/contract work?\n→ ").strip()
        default_schedule = "Schedule C"
    elif biz_choice == "3":
        biz_description = input("\nDescribe your business:\n→ ").strip()
        default_schedule = "Schedule C"
    else:
        biz_description = input("\nDescribe your business or income source:\n→ ").strip()
        default_schedule = "Schedule C"

    biz_name = input(f"\nBusiness name (optional, press Enter to skip):\n→ ").strip() or None

    print(f"\nTax schedule (default: {default_schedule})?")
    schedule = input("→ ").strip() or default_schedule

    print(f"\nAI is generating your tax deduction profile for: {biz_description}...")
    tax_profile = _ai_generate_tax_profile(biz_description, schedule, biz_name)

    if not tax_profile:
        print("\n⚠️ AI generation failed. Creating basic profile.")
        tax_profile = _basic_tax_profile(biz_description, schedule, biz_name)

    config["tax"] = tax_profile
    C.save_tracker_config(config)
    print(f"\n✅ Tax profile created with {len(tax_profile.get('ask_rules', []))} deduction rules.")
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

    ai_text = C.ai_extract_text(payload, timeout=60)
    if not ai_text:
        print(f"  AI error: empty response from {C.LITELLM_URL} (model: {C.CLASSIFY_MODEL})")
        return None

    try:
        profile = json.loads(ai_text)
        profile["enabled"] = True
        profile["generated_by"] = "ai_setup_wizard"
        profile["generated_at"] = datetime.now().isoformat()
        return profile
    except json.JSONDecodeError as e:
        print(f"  AI error: model returned invalid JSON: {e}")
        print(f"  Response: {ai_text[:300]}")
        return None


def _basic_tax_profile(business_description: str, schedule: str, business_name: str = None) -> dict:
    """Fallback basic profile when AI fails."""
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
