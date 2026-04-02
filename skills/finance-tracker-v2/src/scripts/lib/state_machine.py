"""Core SetupStateMachine for Finance Tracker v2.

The LLM NEVER controls flow. This state machine controls ALL transitions.
Every CLI call returns JSON to stdout.
setup_state.json persists after every state transition for resume.
"""

import json
import shutil
from datetime import datetime
from enum import Enum
from pathlib import Path

from . import config as C
from .errors import FinanceError, ErrorCode, setup_incomplete, invalid_input


# ── States ────────────────────────────────────────────

class SetupState(str, Enum):
    UNPACK = "UNPACK"
    DETECT_USER = "DETECT_USER"
    CARDS = "CARDS"
    CURRENCY = "CURRENCY"
    INCOME = "INCOME"
    DEBTS = "DEBTS"
    BUDGETS = "BUDGETS"
    BILLS = "BILLS"
    TAX_CHECK = "TAX_CHECK"
    TAX_DESCRIBE = "TAX_DESCRIBE"
    REVIEW = "REVIEW"
    SHEETS = "SHEETS"
    COMPLETE = "COMPLETE"


# Ordered for progress calculation
STATE_ORDER = list(SetupState)
TOTAL_STATES = len(STATE_ORDER)

# Quick mode skips these optional states
QUICK_SKIP = {SetupState.INCOME, SetupState.DEBTS, SetupState.BUDGETS, SetupState.BILLS}

# ── Done signals ──────────────────────────────────────
# User says one of these to finish a multi-item collection state

DONE_SIGNALS = [
    "done", "listo", "ya", "that's it", "eso es todo", "no more",
    "no más", "finish", "next", "siguiente", "skip", "saltar",
    "none", "ninguno", "n/a", "na", "nada",
]

# ── Meta commands ─────────────────────────────────────

META_COMMANDS = {"undo", "list", "skip", "back"}


def _is_done(text: str) -> bool:
    return text.strip().lower() in DONE_SIGNALS


def _is_meta(text: str) -> str | None:
    """Return meta command name or None."""
    t = text.strip().lower()
    # "edit 2" -> "edit"
    word = t.split()[0] if t else ""
    if word in META_COMMANDS:
        return word
    if word == "edit" and len(t.split()) > 1:
        return "edit"
    return None


def _progress(state: SetupState) -> str:
    idx = STATE_ORDER.index(state)
    return f"{idx + 1}/{TOTAL_STATES}"


# ── Schema loading ────────────────────────────────────

def _load_schema(name: str) -> dict | None:
    path = C.SCHEMAS_DIR / f"{name}.v1.json"
    if path.exists():
        return C.load_json(path)
    return None


# ── Response builder ──────────────────────────────────

def _response(message: str, state: SetupState, done: bool = False,
              error: str | None = None, **extra) -> dict:
    r = {
        "message": message,
        "state": state.value,
        "progress": _progress(state),
        "done": done,
    }
    if error:
        r["error"] = error
    r.update(extra)
    return r


# ── Install check & preflight ────────────────────────

def install_check() -> dict:
    """Verify runtime dependencies exist. Returns JSON."""
    checks = {}

    # Python version
    import sys
    checks["python"] = {
        "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "ok": sys.version_info >= (3, 10),
    }

    # gspread
    try:
        import gspread  # noqa: F401
        checks["gspread"] = {"ok": True}
    except ImportError:
        checks["gspread"] = {"ok": False, "hint": "pip install gspread"}

    # google-auth
    try:
        import google.auth  # noqa: F401
        checks["google_auth"] = {"ok": True}
    except ImportError:
        checks["google_auth"] = {"ok": False, "hint": "pip install google-auth"}

    # curl
    checks["curl"] = {"ok": shutil.which("curl") is not None}

    # GOG credentials
    creds = Path.home() / ".openclaw" / "credentials" / "gog"
    checks["gog_auth"] = {"ok": creds.is_dir() and any(creds.iterdir())}

    # schemas
    for name in ("income", "debt", "budget", "bill"):
        path = C.SCHEMAS_DIR / f"{name}.v1.json"
        checks[f"schema_{name}"] = {"ok": path.exists()}

    all_ok = all(c["ok"] for c in checks.values())
    return {"install_check": True, "ok": all_ok, "checks": checks}


def preflight() -> dict:
    """Check if setup can proceed. Returns JSON with current state."""
    state_data = C.load_setup_state()

    if C.is_setup_complete():
        return {
            "preflight": True,
            "setup_complete": True,
            "message": "Setup already complete. Use setup-reset to redo.",
        }

    current = state_data.get("current_state", SetupState.UNPACK.value)
    return {
        "preflight": True,
        "setup_complete": False,
        "current_state": current,
        "can_resume": bool(state_data),
        "message": f"Ready. Current state: {current}",
    }


# ── State Machine ─────────────────────────────────────

class SetupStateMachine:
    """Deterministic setup flow. LLM feeds user input, machine controls transitions."""

    def __init__(self, mode: str = "full"):
        self.mode = mode  # "quick" or "full"
        state_data = C.load_setup_state()
        self.state = SetupState(state_data.get("current_state", SetupState.UNPACK.value))
        self.collected = state_data.get("collected", {})

    def _save(self) -> None:
        C.save_setup_state({
            "current_state": self.state.value,
            "collected": self.collected,
            "mode": self.mode,
            "updated_at": datetime.now().isoformat(),
        })

    def _advance(self, next_state: SetupState) -> None:
        self.state = next_state
        # In quick mode, skip optional states
        if self.mode == "quick":
            while self.state in QUICK_SKIP:
                idx = STATE_ORDER.index(self.state)
                if idx + 1 < TOTAL_STATES:
                    self.state = STATE_ORDER[idx + 1]
                else:
                    break
        self._save()

    def _handle_meta(self, cmd: str, user_input: str) -> dict | None:
        """Handle meta commands. Returns response dict or None to continue."""
        if cmd == "list":
            return _response(
                json.dumps(self.collected, indent=2, ensure_ascii=False),
                self.state,
                collected=self.collected,
            )
        if cmd == "undo":
            # Remove last item from current collection
            key = self.state.value.lower()
            items = self.collected.get(key, [])
            if items:
                removed = items.pop()
                self._save()
                return _response(f"Removed: {json.dumps(removed)}", self.state)
            return _response("Nothing to undo.", self.state)
        if cmd == "skip":
            idx = STATE_ORDER.index(self.state)
            if idx + 1 < TOTAL_STATES:
                self._advance(STATE_ORDER[idx + 1])
                return self.process("")  # enter next state with empty input
            return _response("Cannot skip final state.", self.state)
        if cmd == "back":
            idx = STATE_ORDER.index(self.state)
            if idx > 0:
                self.state = STATE_ORDER[idx - 1]
                self._save()
                return self.process("")  # re-enter previous state
            return _response("Already at first state.", self.state)
        if cmd == "edit":
            parts = user_input.strip().split(maxsplit=1)
            if len(parts) < 2 or not parts[1].isdigit():
                return _response("Usage: edit N (1-based index)", self.state)
            idx = int(parts[1]) - 1
            key = self.state.value.lower()
            items = self.collected.get(key, [])
            if 0 <= idx < len(items):
                removed = items.pop(idx)
                self._save()
                return _response(
                    f"Removed item {idx + 1}: {json.dumps(removed)}. Re-enter it or continue.",
                    self.state,
                )
            return _response(f"Index out of range. Have {len(items)} items.", self.state)
        return None

    def process(self, user_input: str) -> dict:
        """Process user input for the current state. Returns JSON response."""
        text = user_input.strip()

        # Check for meta command first
        meta = _is_meta(text)
        if meta and self.state not in (SetupState.UNPACK, SetupState.DETECT_USER, SetupState.COMPLETE):
            result = self._handle_meta(meta, text)
            if result:
                return result

        handler = getattr(self, f"_state_{self.state.value.lower()}", None)
        if handler is None:
            return _response(f"Unknown state: {self.state.value}", self.state,
                             error=ErrorCode.INTERNAL.value)
        return handler(text)

    # ── State handlers ────────────────────────────────

    def _state_unpack(self, text: str) -> dict:
        """Initial state — auto-advance on any input."""
        self._advance(SetupState.DETECT_USER)
        return self._state_detect_user("")

    def _state_detect_user(self, text: str) -> dict:
        """Auto-detect user from USER.md, then ask for cards."""
        user_md = C.read_user_md()
        self.collected["user"] = {
            "name": user_md.get("name") or "User",
            "language": user_md.get("language") or "en",
        }
        self._advance(SetupState.CARDS)
        name = self.collected["user"]["name"]
        lang = self.collected["user"]["language"]
        if lang == "es":
            msg = (f"Hola {name}! Vamos a configurar tu Finance Tracker.\n"
                   f"Primero, que tarjetas o cuentas usas? (separadas por coma)\n"
                   f"Ejemplo: Chase Visa, Discover, Cash")
        else:
            msg = (f"Hi {name}! Let's set up your Finance Tracker.\n"
                   f"First, what bank cards/accounts do you use? (comma-separated)\n"
                   f"Example: Chase Visa, Discover, Cash")
        return _response(msg, self.state)

    def _state_cards(self, text: str) -> dict:
        if not text:
            return _response("Enter your cards (comma-separated):", self.state)
        cards = [c.strip() for c in text.split(",") if c.strip()]
        if not cards:
            return _response("Need at least one card/account.", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)
        self.collected["cards"] = cards
        self._advance(SetupState.CURRENCY)
        lang = self.collected.get("user", {}).get("language", "en")
        if lang == "es":
            msg = f"Tarjetas: {', '.join(cards)}\nMoneda? (USD, EUR, MXN...)"
        else:
            msg = f"Cards: {', '.join(cards)}\nCurrency code? (USD, EUR, GBP...)"
        return _response(msg, self.state)

    def _state_currency(self, text: str) -> dict:
        if not text:
            return _response("Enter currency code (e.g. USD):", self.state)
        currency = text.upper().strip()
        if len(currency) != 3 or not currency.isalpha():
            return _response("Currency must be a 3-letter code (e.g. USD).", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)
        self.collected["currency"] = currency
        self._advance(SetupState.INCOME)
        schema = _load_schema("income")
        lang = self.collected.get("user", {}).get("language", "en")
        if lang == "es":
            msg = ("Ahora tus fuentes de ingreso.\n"
                   "Formato: nombre, monto, frecuencia (biweekly/monthly/weekly)\n"
                   "Ejemplo: Trabajo, 3200, biweekly\n"
                   'Escribe "listo" cuando termines.')
        else:
            msg = ("Now your income sources.\n"
                   "Format: name, amount, frequency (biweekly/monthly/weekly)\n"
                   "Example: Day Job, 3200, biweekly\n"
                   'Type "done" when finished.')
        return _response(msg, self.state, schema=schema)

    def _state_income(self, text: str) -> dict:
        if _is_done(text) or not text:
            self._advance(SetupState.DEBTS)
            return self._prompt_debts()
        items = self.collected.setdefault("income", [])
        parts = [p.strip() for p in text.split(",")]
        if len(parts) < 3:
            return _response("Format: name, amount, frequency", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)
        try:
            amount = float(parts[1])
        except ValueError:
            return _response("Amount must be a number.", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)
        freq = parts[2].lower()
        if freq not in ("biweekly", "monthly", "weekly"):
            return _response("Frequency must be: biweekly, monthly, or weekly", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)
        items.append({"name": parts[0], "amount": amount, "frequency": freq})
        self._save()
        lang = self.collected.get("user", {}).get("language", "en")
        added = f"{parts[0]} — ${amount:.2f}/{freq}"
        if lang == "es":
            msg = f"Agregado: {added}\nOtro ingreso? o \"listo\""
        else:
            msg = f"Added: {added}\nAnother income? or \"done\""
        return _response(msg, self.state, items_count=len(items))

    def _prompt_debts(self) -> dict:
        schema = _load_schema("debt")
        lang = self.collected.get("user", {}).get("language", "en")
        if lang == "es":
            msg = ("Deudas (tarjetas de crédito, préstamos, etc.).\n"
                   "Formato: nombre, balance, APR%\n"
                   "Ejemplo: Chase Visa, 2500, 24.99\n"
                   'Escribe "listo" cuando termines o "skip" para saltar.')
        else:
            msg = ("Debts (credit cards, loans, etc.).\n"
                   "Format: name, balance, APR%\n"
                   "Example: Chase Visa, 2500, 24.99\n"
                   'Type "done" when finished or "skip" to skip.')
        return _response(msg, self.state, schema=schema)

    def _state_debts(self, text: str) -> dict:
        if _is_done(text) or not text:
            self._advance(SetupState.BUDGETS)
            return self._prompt_budgets()
        items = self.collected.setdefault("debts", [])
        parts = [p.strip() for p in text.split(",")]
        if len(parts) < 2:
            return _response("Format: name, balance[, APR%]", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)
        try:
            balance = float(parts[1])
        except ValueError:
            return _response("Balance must be a number.", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)
        apr = 0.0
        if len(parts) >= 3:
            try:
                apr = float(parts[2])
            except ValueError:
                pass
        items.append({"name": parts[0], "balance": balance, "apr": apr})
        self._save()
        return _response(f"Added: {parts[0]} — ${balance:.2f} @ {apr}% APR\nAnother? or \"done\"",
                         self.state, items_count=len(items))

    def _prompt_budgets(self) -> dict:
        schema = _load_schema("budget")
        lang = self.collected.get("user", {}).get("language", "en")
        if lang == "es":
            msg = ("Categorías de presupuesto mensual.\n"
                   "Formato: categoría, monto mensual\n"
                   "Ejemplo: Groceries, 300\n"
                   'Escribe "listo" para usar las predeterminadas o agrega las tuyas.')
        else:
            msg = ("Monthly budget categories.\n"
                   "Format: category, monthly amount\n"
                   "Example: Groceries, 300\n"
                   'Type "done" for defaults or add your own.')
        return _response(msg, self.state, schema=schema,
                         defaults=list(C._defaults()["categories"].keys()))

    def _state_budgets(self, text: str) -> dict:
        if _is_done(text) or not text:
            self._advance(SetupState.BILLS)
            return self._prompt_bills()
        items = self.collected.setdefault("budgets", [])
        parts = [p.strip() for p in text.split(",")]
        if len(parts) < 2:
            return _response("Format: category, monthly_amount", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)
        try:
            amount = float(parts[1])
        except ValueError:
            return _response("Amount must be a number.", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)
        items.append({"category": parts[0], "monthly": amount, "threshold": 0.8})
        self._save()
        return _response(f"Added: {parts[0]} — ${amount:.2f}/mo\nAnother? or \"done\"",
                         self.state, items_count=len(items))

    def _prompt_bills(self) -> dict:
        schema = _load_schema("bill")
        lang = self.collected.get("user", {}).get("language", "en")
        if lang == "es":
            msg = ("Pagos recurrentes (renta, servicios, suscripciones).\n"
                   "Formato: nombre, monto, día del mes\n"
                   "Ejemplo: Netflix, 15.99, 1\n"
                   'Escribe "listo" cuando termines.')
        else:
            msg = ("Recurring bills (rent, utilities, subscriptions).\n"
                   "Format: name, amount, due_day\n"
                   "Example: Netflix, 15.99, 1\n"
                   'Type "done" when finished.')
        return _response(msg, self.state, schema=schema)

    def _state_bills(self, text: str) -> dict:
        if _is_done(text) or not text:
            self._advance(SetupState.TAX_CHECK)
            return self._prompt_tax_check()
        items = self.collected.setdefault("bills", [])
        parts = [p.strip() for p in text.split(",")]
        if len(parts) < 3:
            return _response("Format: name, amount, due_day", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)
        try:
            amount = float(parts[1])
            due_day = int(parts[2])
        except ValueError:
            return _response("Amount must be number, due_day must be integer.", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)
        if not 1 <= due_day <= 28:
            return _response("Due day must be 1-28.", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)
        items.append({"name": parts[0], "amount": amount, "due_day": due_day,
                       "autopay": False, "apr": 0})
        self._save()
        return _response(f"Added: {parts[0]} — ${amount:.2f} due day {due_day}\nAnother? or \"done\"",
                         self.state, items_count=len(items))

    def _prompt_tax_check(self) -> dict:
        lang = self.collected.get("user", {}).get("language", "en")
        if lang == "es":
            msg = ("Tienes un negocio o ingreso extra donde algunas\n"
                   "compras podrían ser deducibles de impuestos?\n"
                   "1. No — finanzas personales solamente\n"
                   "2. Sí — propiedad de renta (Airbnb, VRBO)\n"
                   "3. Sí — freelancer / contratista\n"
                   "4. Sí — negocio pequeño\n"
                   "5. Sí — otro")
        else:
            msg = ("Do you have a business or side income where some\n"
                   "purchases might be tax-deductible?\n"
                   "1. No — personal finance only\n"
                   "2. Yes — rental property (Airbnb, VRBO)\n"
                   "3. Yes — freelancer / contractor\n"
                   "4. Yes — small business / side hustle\n"
                   "5. Yes — other")
        return _response(msg, self.state)

    def _state_tax_check(self, text: str) -> dict:
        choice = text.strip()
        if choice == "1" or choice.lower() in ("no", "none"):
            self.collected["tax"] = {"enabled": False}
            self._advance(SetupState.REVIEW)
            return self._prompt_review()
        if choice in ("2", "3", "4", "5"):
            type_map = {"2": "rental", "3": "freelancer", "4": "business", "5": "other"}
            self.collected["tax"] = {"enabled": True, "type": type_map[choice]}
            self._advance(SetupState.TAX_DESCRIBE)
            lang = self.collected.get("user", {}).get("language", "en")
            if lang == "es":
                msg = "Describe tu negocio o fuente de ingreso:"
            else:
                msg = "Describe your business or income source:"
            return _response(msg, self.state)
        return _response("Enter 1-5.", self.state, error=ErrorCode.SETUP_INVALID_INPUT.value)

    def _state_tax_describe(self, text: str) -> dict:
        if not text:
            return _response("Please describe your business:", self.state)
        self.collected["tax"]["description"] = text
        self._advance(SetupState.REVIEW)
        return self._prompt_review()

    def _prompt_review(self) -> dict:
        lang = self.collected.get("user", {}).get("language", "en")
        summary = {
            "user": self.collected.get("user", {}),
            "cards": self.collected.get("cards", []),
            "currency": self.collected.get("currency", "USD"),
            "income": self.collected.get("income", []),
            "debts": self.collected.get("debts", []),
            "budgets": self.collected.get("budgets", []),
            "bills": self.collected.get("bills", []),
            "tax": self.collected.get("tax", {}),
        }
        if lang == "es":
            msg = (f"Resumen de configuración:\n"
                   f"{json.dumps(summary, indent=2, ensure_ascii=False)}\n\n"
                   f"Escribe \"ok\" para confirmar o \"back\" para regresar.")
        else:
            msg = (f"Setup summary:\n"
                   f"{json.dumps(summary, indent=2, ensure_ascii=False)}\n\n"
                   f"Type \"ok\" to confirm or \"back\" to go back.")
        return _response(msg, self.state, summary=summary)

    def _state_review(self, text: str) -> dict:
        if text.lower() in ("ok", "yes", "sí", "si", "confirm", "confirmar"):
            # Build final config from collected data
            self._build_config()
            self._advance(SetupState.SHEETS)
            lang = self.collected.get("user", {}).get("language", "en")
            if lang == "es":
                msg = "Configuración guardada! Ahora crea la hoja de cálculo: finance.py setup-sheets"
            else:
                msg = "Config saved! Now create the spreadsheet: finance.py setup-sheets"
            return _response(msg, self.state)
        if not text:
            return self._prompt_review()
        return _response("Type \"ok\" to confirm or \"back\" to go back.", self.state)

    def _state_sheets(self, text: str) -> dict:
        # Sheets creation is handled by a separate command
        # Mark setup complete
        config = C._load_tracker_config()
        config["user"]["setup_complete"] = True
        C.save_tracker_config(config)
        C.clear_setup_state()
        self.state = SetupState.COMPLETE
        lang = self.collected.get("user", {}).get("language", "en")
        if lang == "es":
            msg = "Setup completo! Tu Finance Tracker está listo."
        else:
            msg = "Setup complete! Your Finance Tracker is ready."
        return _response(msg, self.state, done=True)

    def _state_complete(self, text: str) -> dict:
        return _response("Setup already complete.", self.state, done=True)

    # ── Config builder ────────────────────────────────

    def _build_config(self) -> None:
        """Build tracker_config.json from collected setup data."""
        user = self.collected.get("user", {})
        name = user.get("name", "User")
        lang = user.get("language", "en")
        currency = self.collected.get("currency", "USD")
        cards = self.collected.get("cards", ["Card 1", "Cash"])
        year = datetime.now().year

        # Build categories from user budgets or defaults
        user_budgets = self.collected.get("budgets", [])
        if user_budgets:
            categories = {}
            for b in user_budgets:
                categories[b["category"]] = {
                    "monthly": b["monthly"],
                    "threshold": b.get("threshold", 0.8),
                }
            if "Other" not in categories:
                categories["Other"] = {"monthly": 50, "threshold": 0.8}
        else:
            categories = C._defaults()["categories"]

        # Build payments from bills
        payments = []
        for bill in self.collected.get("bills", []):
            payments.append({
                "name": bill["name"],
                "amount": bill["amount"],
                "due_day": bill["due_day"],
                "account": bill.get("account", "Bank"),
                "autopay": bill.get("autopay", False),
                "apr": bill.get("apr", 0),
                "promo_expiry": None,
            })

        # Build balance from income
        income_list = self.collected.get("income", [])
        expected = 0
        pay_schedule = "biweekly"
        if income_list:
            primary = income_list[0]
            expected = primary["amount"]
            pay_schedule = primary.get("frequency", "biweekly")

        # Tax section
        tax_data = self.collected.get("tax", {})
        tax = {
            "enabled": tax_data.get("enabled", False),
            "business_type": tax_data.get("description"),
            "schedule_type": None,
            "business_name": None,
            "tax_categories": [],
            "ask_rules": [],
            "never_ask": [],
        }
        if tax_data.get("enabled"):
            tax_type = tax_data.get("type", "other")
            tax["schedule_type"] = "Schedule E" if tax_type == "rental" else "Schedule C"

        config = {
            "user": {
                "name": name,
                "language": lang,
                "spreadsheet_name": f"{name} Finance {year}",
                "currency": currency,
                "cards": cards,
                "setup_complete": False,  # Will be set True after sheets
                "created_at": datetime.now().isoformat(),
            },
            "categories": categories,
            "balance": {
                "available": 0,
                "last_updated": None,
                "pay_schedule": pay_schedule,
                "pay_dates": [1, 15],
                "expected_paycheck": expected,
            },
            "tax": tax,
            "payments": payments,
            "savings": [],
            "income": income_list,
            "debts": self.collected.get("debts", []),
        }
        C.save_tracker_config(config)


# ── Public API ────────────────────────────────────────

def setup_status() -> dict:
    """Return current setup status as JSON."""
    state_data = C.load_setup_state()
    if C.is_setup_complete():
        return {"setup_complete": True, "state": "COMPLETE", "progress": f"{TOTAL_STATES}/{TOTAL_STATES}"}
    if not state_data:
        return {"setup_complete": False, "state": "NOT_STARTED", "progress": "0/0"}
    return {
        "setup_complete": False,
        "state": state_data.get("current_state", "UNPACK"),
        "progress": _progress(SetupState(state_data.get("current_state", "UNPACK"))),
        "collected": state_data.get("collected", {}),
        "mode": state_data.get("mode", "full"),
    }
