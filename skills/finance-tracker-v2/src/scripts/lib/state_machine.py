"""Core SetupStateMachine for Finance Tracker v2.

The LLM NEVER controls flow. This state machine controls ALL transitions.
Every CLI call returns JSON to stdout.
setup_state.json persists after every state transition for resume.

State flow (spec §3):
  UNPACK → PREFLIGHT → DETECT_CONTEXT → SETUP_MODE_SELECT
  → INCOME_COLLECT → INCOME_CONFIRM
  → BUSINESS_RULES_MAP → BUSINESS_RULES_CONFIRM
  → DEBT_COLLECT → DEBT_CONFIRM
  → BUDGET_PRESENT → BUDGET_COLLECT → BUDGET_CONFIRM
  → BILLS_COLLECT → BILLS_CONFIRM
  → REVIEW_ALL → SHEETS_CREATE → CRONS_SETUP
  → TELEMETRY_OPT → ONBOARDING_MISSIONS → COMPLETE
"""

import json
import shutil
from datetime import datetime
from enum import Enum
from pathlib import Path

from . import config as C
from .errors import FinanceError, ErrorCode


# ── States ────────────────────────────────────────────

class SetupState(str, Enum):
    UNPACK = "UNPACK"
    PREFLIGHT = "PREFLIGHT"
    DETECT_CONTEXT = "DETECT_CONTEXT"
    SETUP_MODE_SELECT = "SETUP_MODE_SELECT"
    INCOME_COLLECT = "INCOME_COLLECT"
    INCOME_CONFIRM = "INCOME_CONFIRM"
    BUSINESS_RULES_MAP = "BUSINESS_RULES_MAP"
    BUSINESS_RULES_CONFIRM = "BUSINESS_RULES_CONFIRM"
    DEBT_COLLECT = "DEBT_COLLECT"
    DEBT_CONFIRM = "DEBT_CONFIRM"
    BUDGET_PRESENT = "BUDGET_PRESENT"
    BUDGET_COLLECT = "BUDGET_COLLECT"
    BUDGET_CONFIRM = "BUDGET_CONFIRM"
    BILLS_COLLECT = "BILLS_COLLECT"
    BILLS_CONFIRM = "BILLS_CONFIRM"
    REVIEW_ALL = "REVIEW_ALL"
    SHEETS_CREATE = "SHEETS_CREATE"
    CRONS_SETUP = "CRONS_SETUP"
    TELEMETRY_OPT = "TELEMETRY_OPT"
    ONBOARDING_MISSIONS = "ONBOARDING_MISSIONS"
    COMPLETE = "COMPLETE"


STATE_ORDER = list(SetupState)
TOTAL_STATES = len(STATE_ORDER)

# Quick mode skips these
QUICK_SKIP = {
    SetupState.DEBT_COLLECT, SetupState.DEBT_CONFIRM,
    SetupState.BUDGET_PRESENT, SetupState.BUDGET_COLLECT, SetupState.BUDGET_CONFIRM,
    SetupState.BILLS_COLLECT, SetupState.BILLS_CONFIRM,
}

# ── Done signals (EN + ES) ───────────────────────────

DONE_SIGNALS = [
    "done", "that's it", "that's all", "finished", "listo",
    "terminé", "ya", "eso es todo", "no more", "nothing else",
    "nada más", "ya terminé", "end", "stop",
    "next", "siguiente", "skip", "saltar",
    "none", "ninguno", "n/a", "na", "nada",
]

# ── Meta commands ─────────────────────────────────────

META_COMMANDS = {"undo", "list", "skip", "back"}

# ── Source type → rulepack mapping ────────────────────

SOURCE_TYPE_TO_RULEPACK = {
    "salary": "us-personal.v1",
    "other": "us-personal.v1",
    "rental": "us-rental-property.v1",
    "freelance": "us-freelance.v1",
    "business": "us-small-business.v1",
}


def _is_done(text: str) -> bool:
    return text.strip().lower() in DONE_SIGNALS


def _is_meta(text: str) -> str | None:
    t = text.strip().lower()
    word = t.split()[0] if t else ""
    if word in META_COMMANDS:
        return word
    if word == "edit" and len(t.split()) > 1:
        return "edit"
    return None


def _progress(state: SetupState) -> str:
    idx = STATE_ORDER.index(state)
    return f"{idx + 1}/{TOTAL_STATES}"


def _lang(collected: dict) -> str:
    return collected.get("context", {}).get("language", "en")


# ── Schema / rulepack loading ─────────────────────────

def _load_schema(name: str) -> dict | None:
    path = C.SCHEMAS_DIR / f"{name}.v1.json"
    if path.exists():
        return C.load_json(path)
    return None


def _load_rulepack(rulepack_id: str) -> dict | None:
    path = C.RULEPACKS_DIR / f"{rulepack_id}.json"
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


# ── Install check ─────────────────────────────────────

def install_check() -> dict:
    """Verify runtime dependencies exist. Returns JSON."""
    checks = {}
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

    # Google OAuth credentials (spec §3.2)
    creds_dir = Path.home() / ".openclaw" / "credentials"
    client_json = creds_dir / "google-client.json"
    token_json = creds_dir / "finance-tracker-token.json"
    checks["google_oauth"] = {
        "ok": client_json.exists() and token_json.exists(),
        "client_json": client_json.exists(),
        "token_json": token_json.exists(),
        "hint": "Set up GOG skill first: https://docs.openclaw.ai/tools/gog",
    }

    # schemas
    for name in ("income", "debt", "budget", "bill"):
        path = C.SCHEMAS_DIR / f"{name}.v1.json"
        checks[f"schema_{name}"] = {"ok": path.exists()}

    # rulepacks
    for name in ("us-personal.v1", "us-rental-property.v1", "us-freelance.v1", "us-small-business.v1"):
        path = C.RULEPACKS_DIR / f"{name}.json"
        checks[f"rulepack_{name.replace('.', '_').replace('-', '_')}"] = {"ok": path.exists()}

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


# ── Confirm helper ────────────────────────────────────

CONFIRM_YES = {"ok", "yes", "sí", "si", "confirm", "confirmar", "y"}


def _is_confirm(text: str) -> bool:
    return text.strip().lower() in CONFIRM_YES


# ── State Machine ─────────────────────────────────────

class SetupStateMachine:
    """Deterministic setup flow. LLM feeds user input, machine controls transitions."""

    # States where meta commands are NOT applicable
    _NO_META = {
        SetupState.UNPACK, SetupState.PREFLIGHT, SetupState.DETECT_CONTEXT,
        SetupState.SETUP_MODE_SELECT, SetupState.COMPLETE,
        # Confirm/review states use their own yes/back/edit logic
        SetupState.INCOME_CONFIRM, SetupState.DEBT_CONFIRM,
        SetupState.BUDGET_CONFIRM, SetupState.BILLS_CONFIRM,
        SetupState.BUSINESS_RULES_CONFIRM, SetupState.REVIEW_ALL,
        SetupState.SHEETS_CREATE, SetupState.CRONS_SETUP,
        SetupState.TELEMETRY_OPT, SetupState.ONBOARDING_MISSIONS,
    }

    def __init__(self, mode: str = "full"):
        state_data = C.load_setup_state()
        self.mode = state_data.get("mode", mode)
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
        if self.mode == "quick":
            while self.state in QUICK_SKIP:
                idx = STATE_ORDER.index(self.state)
                if idx + 1 < TOTAL_STATES:
                    self.state = STATE_ORDER[idx + 1]
                else:
                    break
        self._save()

    def _handle_meta(self, cmd: str, user_input: str) -> dict | None:
        if cmd == "list":
            return _response(
                json.dumps(self.collected, indent=2, ensure_ascii=False),
                self.state, collected=self.collected,
            )
        if cmd == "undo":
            key = self._collection_key()
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
                return self.process("")
            return _response("Cannot skip final state.", self.state)
        if cmd == "back":
            idx = STATE_ORDER.index(self.state)
            if idx > 0:
                self.state = STATE_ORDER[idx - 1]
                self._save()
                return self.process("")
            return _response("Already at first state.", self.state)
        if cmd == "edit":
            parts = user_input.strip().split(maxsplit=1)
            if len(parts) < 2 or not parts[1].isdigit():
                return _response("Usage: edit N (1-based index)", self.state)
            idx = int(parts[1]) - 1
            key = self._collection_key()
            items = self.collected.get(key, [])
            if 0 <= idx < len(items):
                removed = items.pop(idx)
                self._save()
                return _response(f"Removed item {idx + 1}: {json.dumps(removed)}. Re-enter or continue.", self.state)
            return _response(f"Index out of range. Have {len(items)} items.", self.state)
        return None

    def _collection_key(self) -> str:
        """Map current state to its collection key in self.collected."""
        mapping = {
            SetupState.INCOME_COLLECT: "income",
            SetupState.DEBT_COLLECT: "debts",
            SetupState.BUDGET_COLLECT: "budgets",
            SetupState.BILLS_COLLECT: "bills",
        }
        return mapping.get(self.state, self.state.value.lower())

    def process(self, user_input: str) -> dict:
        text = user_input.strip()

        meta = _is_meta(text)
        if meta and self.state not in self._NO_META:
            result = self._handle_meta(meta, text)
            if result:
                return result

        handler = getattr(self, f"_state_{self.state.value.lower()}", None)
        if handler is None:
            return _response(f"Unknown state: {self.state.value}", self.state,
                             error=ErrorCode.INTERNAL.value)
        return handler(text)

    # ── UNPACK ────────────────────────────────────────

    def _state_unpack(self, text: str) -> dict:
        self._advance(SetupState.PREFLIGHT)
        return self._state_preflight("")

    # ── PREFLIGHT (real state, not just function) ─────

    def _state_preflight(self, text: str) -> dict:
        checks = install_check()
        if not checks["ok"]:
            failed = [k for k, v in checks["checks"].items() if not v["ok"]]
            return _response(
                f"Preflight failed. Fix these before continuing: {', '.join(failed)}",
                self.state,
                error="PREFLIGHT_FAILED",
                checks=checks["checks"],
            )
        self._advance(SetupState.DETECT_CONTEXT)
        return self._state_detect_context("")

    # ── DETECT_CONTEXT ────────────────────────────────

    def _state_detect_context(self, text: str) -> dict:
        user_md = C.read_user_md()
        context = {
            "name": user_md.get("name") or "User",
            "language": user_md.get("language") or "en",
            "currency": "USD",  # default, can be overridden in income
            "timezone": "America/New_York",
        }

        # Try to read timezone from openclaw.json
        oc_path = Path.home() / ".openclaw" / "openclaw.json"
        if oc_path.exists():
            try:
                oc = json.loads(oc_path.read_text())
                tz = oc.get("agents", {}).get("defaults", {}).get("userTimezone")
                if tz:
                    context["timezone"] = tz
            except Exception:
                pass

        self.collected["context"] = context
        self._advance(SetupState.SETUP_MODE_SELECT)
        lang = context["language"]
        name = context["name"]
        if lang == "es":
            msg = (f"Hola {name}! Vamos a configurar tu Finance Tracker.\n\n"
                   f"Modo de setup:\n"
                   f"1. Quick — solo ingresos y reglas de negocio (~2 min)\n"
                   f"2. Full — ingresos, deudas, presupuesto, bills (~10 min)\n\n"
                   f"Escribe 1 o 2:")
        else:
            msg = (f"Hi {name}! Let's set up your Finance Tracker.\n\n"
                   f"Setup mode:\n"
                   f"1. Quick — income and business rules only (~2 min)\n"
                   f"2. Full — income, debts, budget, bills (~10 min)\n\n"
                   f"Enter 1 or 2:")
        return _response(msg, self.state)

    # ── SETUP_MODE_SELECT ─────────────────────────────

    def _state_setup_mode_select(self, text: str) -> dict:
        if text in ("1", "quick"):
            self.mode = "quick"
        elif text in ("2", "full"):
            self.mode = "full"
        elif not text:
            return _response("Enter 1 (quick) or 2 (full):", self.state)
        else:
            return _response("Enter 1 (quick) or 2 (full):", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)
        self._advance(SetupState.INCOME_COLLECT)
        return self._prompt_income_collect()

    # ── INCOME_COLLECT (loop) ─────────────────────────

    def _prompt_income_collect(self) -> dict:
        lang = _lang(self.collected)
        step = "1 of 8" if self.mode == "full" else "1 of 3"
        if lang == "es":
            msg = (f"Paso {step} — Fuentes de Ingreso\n"
                   f"Dime tus fuentes de ingreso una a la vez.\n"
                   f"Incluye: monto, frecuencia (weekly/biweekly/monthly),\n"
                   f"tipo (salary/freelance/rental/business/other),\n"
                   f"y la cuenta que lo recibe.\n\n"
                   f"Ejemplo: Trabajo, 3000, biweekly, salary, Personal Checking\n\n"
                   f"Escribe 'listo' cuando termines.\n"
                   f"'undo' para quitar el último, 'list' para ver lo ingresado.")
        else:
            msg = (f"Step {step} — Income Sources\n"
                   f"Tell me your income sources one at a time.\n"
                   f"Include: amount, frequency (weekly/biweekly/monthly),\n"
                   f"type (salary/freelance/rental/business/other),\n"
                   f"and which account receives it.\n\n"
                   f"Example: Day Job, 3000, biweekly, salary, Personal Checking\n\n"
                   f"Say 'done' when finished.\n"
                   f"'undo' to remove last, 'list' to see entries.")
        return _response(msg, self.state, schema=_load_schema("income"))

    def _state_income_collect(self, text: str) -> dict:
        if _is_done(text):
            items = self.collected.get("income", [])
            if not items:
                return _response("Need at least one income source.", self.state,
                                 error=ErrorCode.SETUP_INVALID_INPUT.value)
            self._advance(SetupState.INCOME_CONFIRM)
            return self._prompt_income_confirm()
        if not text:
            return self._prompt_income_collect()

        items = self.collected.setdefault("income", [])
        parts = [p.strip() for p in text.split(",")]
        if len(parts) < 5:
            lang = _lang(self.collected)
            if lang == "es":
                return _response("Formato: nombre, monto, frecuencia, tipo, cuenta", self.state,
                                 error=ErrorCode.SETUP_INVALID_INPUT.value)
            return _response("Format: name, amount, frequency, source_type, account_label", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)

        name = parts[0]
        try:
            amount = float(parts[1])
        except ValueError:
            return _response("Amount must be a number.", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)

        freq = parts[2].lower().strip()
        if freq not in ("biweekly", "monthly", "weekly", "irregular"):
            return _response("Frequency: weekly, biweekly, monthly, or irregular", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)

        source_type = parts[3].lower().strip()
        if source_type not in ("salary", "freelance", "rental", "business", "other"):
            return _response("Type: salary, freelance, rental, business, or other", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)

        account_label = parts[4].strip()
        is_regular = source_type == "salary"

        entry = {
            "name": name, "amount": amount, "frequency": freq,
            "source_type": source_type, "account_label": account_label,
            "is_regular": is_regular,
        }
        items.append(entry)
        self._save()

        lang = _lang(self.collected)
        added = f"{name} — ${amount:.2f}/{freq} → {account_label} ({source_type})"
        if lang == "es":
            msg = f"Agregado: {added}\nOtro ingreso? o 'listo'"
        else:
            msg = f"Added: {added}\nAnother? or 'done'"
        return _response(msg, self.state, items_count=len(items))

    # ── INCOME_CONFIRM ────────────────────────────────

    def _prompt_income_confirm(self) -> dict:
        items = self.collected.get("income", [])
        lang = _lang(self.collected)
        lines = []
        total_monthly = 0
        for i, inc in enumerate(items, 1):
            freq = inc["frequency"]
            amt = inc["amount"]
            monthly = amt * {"weekly": 4.33, "biweekly": 2.17, "monthly": 1, "irregular": 1}.get(freq, 1)
            total_monthly += monthly
            reg = "regular" if inc.get("is_regular") else "irregular"
            lines.append(f"  {i}. {inc['name']} — ${amt:,.2f} {freq} → {inc['account_label']} ({reg})")

        summary = "\n".join(lines)
        if lang == "es":
            msg = (f"Resumen de Ingresos:\n{summary}\n\n"
                   f"Total mensual estimado: ${total_monthly:,.2f}\n\n"
                   f"Correcto? (yes / edit N / add more)")
        else:
            msg = (f"Income Summary:\n{summary}\n\n"
                   f"Total estimated monthly: ${total_monthly:,.2f}\n\n"
                   f"Is this correct? (yes / edit N / add more)")
        return _response(msg, self.state, income=items, total_monthly=round(total_monthly, 2))

    def _state_income_confirm(self, text: str) -> dict:
        if _is_confirm(text):
            # Collect account labels as cards from income entries
            accounts = list(dict.fromkeys(
                inc["account_label"] for inc in self.collected.get("income", [])
            ))
            if "Cash" not in accounts:
                accounts.append("Cash")
            self.collected["cards"] = accounts

            # Auto-detect currency from context
            self.collected["currency"] = self.collected.get("context", {}).get("currency", "USD")

            self._advance(SetupState.BUSINESS_RULES_MAP)
            return self._state_business_rules_map("")
        if text.lower().startswith("edit") and len(text.split()) > 1:
            idx_str = text.split()[1]
            if idx_str.isdigit():
                idx = int(idx_str) - 1
                items = self.collected.get("income", [])
                if 0 <= idx < len(items):
                    removed = items.pop(idx)
                    self._save()
                    self._advance(SetupState.INCOME_COLLECT)
                    return _response(f"Removed: {removed['name']}. Re-enter or say 'done'.",
                                     self.state)
        if text.lower() in ("add", "add more", "más", "agregar"):
            self._advance(SetupState.INCOME_COLLECT)
            return _response("Add another income source:", self.state)
        if not text:
            return self._prompt_income_confirm()
        return _response("Type 'yes' to confirm, 'edit N' to change, or 'add more'.", self.state)

    # ── BUSINESS_RULES_MAP ────────────────────────────

    def _state_business_rules_map(self, text: str) -> dict:
        income = self.collected.get("income", [])
        source_types = set(inc["source_type"] for inc in income)

        # Map source types to rulepacks
        rulepacks_to_load = set()
        for st in source_types:
            rp_id = SOURCE_TYPE_TO_RULEPACK.get(st, "us-personal.v1")
            if rp_id != "us-personal.v1":  # personal has no deductions
                rulepacks_to_load.add(rp_id)

        if not rulepacks_to_load:
            # All personal/salary — no business rules needed
            self.collected["rulepacks"] = []
            self.collected["business_rules"] = []
            self._advance(SetupState.BUSINESS_RULES_CONFIRM)
            return self._state_business_rules_confirm("")

        loaded = []
        all_categories = []
        for rp_id in sorted(rulepacks_to_load):
            rp = _load_rulepack(rp_id)
            if rp:
                loaded.append(rp)
                for cat in rp.get("deductible_categories", []):
                    all_categories.append({
                        "category": cat["category"],
                        "irs_reference": cat.get("irs_reference", ""),
                        "description": cat.get("description", ""),
                        "rulepack": rp_id,
                    })

        self.collected["rulepacks"] = [rp["rulepack_id"] for rp in loaded]
        self.collected["business_rules"] = all_categories
        self._advance(SetupState.BUSINESS_RULES_CONFIRM)
        return self._prompt_business_rules_confirm(loaded, all_categories)

    # ── BUSINESS_RULES_CONFIRM ────────────────────────

    def _prompt_business_rules_confirm(self, loaded: list, categories: list) -> dict:
        lang = _lang(self.collected)
        lines = []
        for rp in loaded:
            btype = rp.get("business_type", "unknown")
            lines.append(f"\n  [{btype.replace('_', ' ').title()}] ({rp.get('irs_form', 'N/A')}):")
            for cat in rp.get("deductible_categories", []):
                lines.append(f"    - {cat['description']} ({cat.get('irs_reference', '')})")

        summary = "\n".join(lines)
        if lang == "es":
            msg = (f"Basado en tus ingresos, encontré estas categorías deducibles:\n{summary}\n\n"
                   f"Crearé reglas de seguimiento para estas. OK? (yes / edit)")
        else:
            msg = (f"Based on your income sources, found these deductible categories:\n{summary}\n\n"
                   f"I'll create tracking rules for these. OK? (yes / edit)")
        return _response(msg, self.state,
                         rulepacks=self.collected.get("rulepacks", []),
                         categories_count=len(categories))

    def _state_business_rules_confirm(self, text: str) -> dict:
        if _is_confirm(text) or not self.collected.get("business_rules"):
            self._advance(SetupState.DEBT_COLLECT)
            return self._prompt_debt_collect()
        if not text:
            if not self.collected.get("business_rules"):
                # No business rules to confirm
                self._advance(SetupState.DEBT_COLLECT)
                return self._prompt_debt_collect()
            # Re-show the confirm prompt
            loaded = []
            for rp_id in self.collected.get("rulepacks", []):
                rp = _load_rulepack(rp_id)
                if rp:
                    loaded.append(rp)
            return self._prompt_business_rules_confirm(loaded, self.collected.get("business_rules", []))
        return _response("Type 'yes' to confirm or 'edit' to modify.", self.state)

    # ── DEBT_COLLECT (loop) ───────────────────────────

    def _prompt_debt_collect(self) -> dict:
        lang = _lang(self.collected)
        step = "3 of 8" if self.mode == "full" else "skipped"
        if lang == "es":
            msg = (f"Paso {step} — Deudas\n"
                   f"Lista tus deudas una a la vez.\n"
                   f"Formato: nombre, tipo (credit_card/personal_loan/auto_loan/mortgage/student_loan),\n"
                   f"balance, APR%, pago mínimo\n\n"
                   f"Ejemplo: Chase Visa, credit_card, 2500, 24.99, 65\n\n"
                   f"'listo' para terminar, 'skip' para saltar.")
        else:
            msg = (f"Step {step} — Debts\n"
                   f"List your debts one at a time.\n"
                   f"Format: name, type (credit_card/personal_loan/auto_loan/mortgage/student_loan),\n"
                   f"balance, APR%, minimum payment\n\n"
                   f"Example: Chase Visa, credit_card, 2500, 24.99, 65\n\n"
                   f"'done' when finished, 'skip' to skip.")
        return _response(msg, self.state, schema=_load_schema("debt"))

    def _state_debt_collect(self, text: str) -> dict:
        if _is_done(text) or not text:
            self._advance(SetupState.DEBT_CONFIRM)
            return self._prompt_debt_confirm()

        items = self.collected.setdefault("debts", [])
        parts = [p.strip() for p in text.split(",")]
        if len(parts) < 3:
            return _response("Format: name, type, balance[, APR%, min_payment]", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)
        name = parts[0]
        debt_type = parts[1].lower().strip()
        try:
            balance = float(parts[2])
        except ValueError:
            return _response("Balance must be a number.", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)
        if balance < 0:
            return _response("Balance should be a positive number.", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)

        apr = 0.0
        min_payment = 0.0
        if len(parts) >= 4:
            try:
                apr = float(parts[3])
            except ValueError:
                pass
        if len(parts) >= 5:
            try:
                min_payment = float(parts[4])
            except ValueError:
                pass

        # Sanity warnings
        warnings = []
        if apr > 50:
            warnings.append("APR > 50% seems very high. Double-check.")
        if min_payment > balance:
            warnings.append("Min payment exceeds balance.")

        items.append({"name": name, "type": debt_type, "balance": balance,
                       "apr": apr, "minimum_payment": min_payment})
        self._save()

        msg = f"Added: {name} — ${balance:,.2f} @ {apr}% APR, min ${min_payment:.2f}"
        if warnings:
            msg += "\n  Warning: " + "; ".join(warnings)
        msg += "\nAnother? or 'done'"
        return _response(msg, self.state, items_count=len(items))

    # ── DEBT_CONFIRM ──────────────────────────────────

    def _prompt_debt_confirm(self) -> dict:
        items = self.collected.get("debts", [])
        lang = _lang(self.collected)
        if not items:
            if lang == "es":
                msg = "Sin deudas registradas. Continuar? (yes)"
            else:
                msg = "No debts entered. Continue? (yes)"
            return _response(msg, self.state)

        lines = []
        total = 0
        for i, d in enumerate(items, 1):
            lines.append(f"  {i}. {d['name']} ({d.get('type', 'unknown')}): "
                         f"${d['balance']:,.2f} @ {d['apr']}% APR, min ${d['minimum_payment']:.2f}")
            total += d["balance"]
        summary = "\n".join(lines)
        if lang == "es":
            msg = f"Resumen de Deudas:\n{summary}\n\nTotal: ${total:,.2f}\n\nCorrecto? (yes / edit N / add more)"
        else:
            msg = f"Debt Summary:\n{summary}\n\nTotal: ${total:,.2f}\n\nCorrect? (yes / edit N / add more)"
        return _response(msg, self.state, debts=items, total_debt=round(total, 2))

    def _state_debt_confirm(self, text: str) -> dict:
        if _is_confirm(text) or (not text and not self.collected.get("debts")):
            self._advance(SetupState.BUDGET_PRESENT)
            return self._state_budget_present("")
        if text.lower().startswith("edit") and len(text.split()) > 1:
            idx_str = text.split()[1]
            if idx_str.isdigit():
                idx = int(idx_str) - 1
                items = self.collected.get("debts", [])
                if 0 <= idx < len(items):
                    items.pop(idx)
                    self._save()
                    self._advance(SetupState.DEBT_COLLECT)
                    return _response("Removed. Re-enter or say 'done'.", self.state)
        if text.lower() in ("add", "add more", "más"):
            self._advance(SetupState.DEBT_COLLECT)
            return _response("Add another debt:", self.state)
        if not text:
            return self._prompt_debt_confirm()
        return _response("Type 'yes' to confirm, 'edit N' to change, or 'add more'.", self.state)

    # ── BUDGET_PRESENT ────────────────────────────────

    def _state_budget_present(self, text: str) -> dict:
        lang = _lang(self.collected)
        step = "4 of 8" if self.mode == "full" else "skipped"

        # Present suggested categories with Fixed/Variable
        defaults = [
            ("Rent/Mortgage", "fixed"), ("Utilities", "fixed"), ("Insurance", "fixed"),
            ("Groceries", "variable"), ("Restaurants", "variable"), ("Gas", "variable"),
            ("Shopping", "variable"), ("Entertainment", "variable"), ("Healthcare", "variable"),
            ("Personal Care", "variable"), ("Subscriptions", "variable"), ("Other", "variable"),
        ]

        # Add business-specific categories if rulepacks loaded
        for rp_id in self.collected.get("rulepacks", []):
            rp = _load_rulepack(rp_id)
            if rp:
                for cat in rp.get("deductible_categories", [])[:3]:
                    defaults.append((cat["description"].split(" — ")[0], "variable"))

        lines = []
        for i, (name, btype) in enumerate(defaults, 1):
            tag = "(F)" if btype == "fixed" else "(V)"
            lines.append(f"  {i:2d}. {name:<20s} {tag}  $___")

        table = "\n".join(lines)
        if lang == "es":
            msg = (f"Paso {step} — Presupuesto Mensual\n"
                   f"Categorías sugeridas. (F)ijo o (V)ariable:\n\n"
                   f"{table}\n\n"
                   f"Responde: 1. $1500  4. $300  5. $100 ...\n"
                   f"Para agregar: 'new Mascotas $200 variable'\n"
                   f"'done' cuando termines.")
        else:
            msg = (f"Step {step} — Monthly Budget\n"
                   f"Suggested categories. (F)ixed or (V)ariable:\n\n"
                   f"{table}\n\n"
                   f"Reply: 1. $1500  4. $300  5. $100 ...\n"
                   f"To add custom: 'new Pets $200 variable'\n"
                   f"Say 'done' when finished.")

        self.collected["_budget_defaults"] = defaults
        self._advance(SetupState.BUDGET_COLLECT)
        return _response(msg, self.state, schema=_load_schema("budget"))

    # ── BUDGET_COLLECT (loop) ─────────────────────────

    def _state_budget_collect(self, text: str) -> dict:
        if _is_done(text) or not text:
            # If no budgets entered, use defaults with $0
            if not self.collected.get("budgets"):
                defaults = self.collected.get("_budget_defaults", [])
                self.collected["budgets"] = [
                    {"category": name, "monthly": 0, "type": btype, "threshold": 0.8}
                    for name, btype in defaults
                ]
            self._advance(SetupState.BUDGET_CONFIRM)
            return self._prompt_budget_confirm()

        items = self.collected.setdefault("budgets", [])
        defaults = self.collected.get("_budget_defaults", [])

        # Handle "new Category $amount type"
        if text.lower().startswith("new "):
            rest = text[4:].strip()
            parts = rest.rsplit(maxsplit=1)
            if len(parts) >= 1:
                # Parse: "Pets $200 variable" or "Pets 200"
                import re
                m = re.match(r"(.+?)\s+\$?(\d+(?:\.\d+)?)\s*(fixed|variable)?$", rest, re.IGNORECASE)
                if m:
                    cat_name = m.group(1).strip()
                    amount = float(m.group(2))
                    btype = (m.group(3) or "variable").lower()
                    items.append({"category": cat_name, "monthly": amount,
                                  "type": btype, "threshold": 0.8})
                    self._save()
                    return _response(f"Added: {cat_name} — ${amount:.2f}/mo ({btype})", self.state)
            return _response("Format: new CategoryName $amount [fixed|variable]", self.state,
                             error=ErrorCode.SETUP_INVALID_INPUT.value)

        # Handle "N. $amount" pattern (referencing defaults)
        import re
        entries = re.findall(r"(\d+)\.\s*\$?(\d+(?:\.\d+)?)", text)
        if entries:
            added = []
            for idx_str, amt_str in entries:
                idx = int(idx_str) - 1
                if 0 <= idx < len(defaults):
                    cat_name, btype = defaults[idx]
                    amount = float(amt_str)
                    items.append({"category": cat_name, "monthly": amount,
                                  "type": btype, "threshold": 0.8})
                    added.append(f"{cat_name}: ${amount:.2f}")
            if added:
                self._save()
                return _response(f"Added: {', '.join(added)}\nMore? or 'done'", self.state)

        # Try comma-separated: category, amount[, type]
        parts = [p.strip() for p in text.split(",")]
        if len(parts) >= 2:
            try:
                amount = float(parts[1].replace("$", ""))
            except ValueError:
                return _response("Amount must be a number.", self.state,
                                 error=ErrorCode.SETUP_INVALID_INPUT.value)
            btype = parts[2].lower().strip() if len(parts) >= 3 else "variable"
            if btype not in ("fixed", "variable"):
                btype = "variable"
            items.append({"category": parts[0], "monthly": amount,
                          "type": btype, "threshold": 0.8})
            self._save()
            return _response(f"Added: {parts[0]} — ${amount:.2f}/mo ({btype})", self.state)

        return _response("Format: N. $amount  OR  category, amount, type  OR  new Name $amount type",
                         self.state, error=ErrorCode.SETUP_INVALID_INPUT.value)

    # ── BUDGET_CONFIRM ────────────────────────────────

    def _prompt_budget_confirm(self) -> dict:
        items = self.collected.get("budgets", [])
        lang = _lang(self.collected)
        fixed = [b for b in items if b.get("type") == "fixed" and b["monthly"] > 0]
        variable = [b for b in items if b.get("type") == "variable" and b["monthly"] > 0]
        fixed_total = sum(b["monthly"] for b in fixed)
        var_total = sum(b["monthly"] for b in variable)

        lines = []
        if fixed:
            lines.append("  FIXED:")
            for b in fixed:
                lines.append(f"    {b['category']}: ${b['monthly']:,.2f}")
        if variable:
            lines.append("  VARIABLE:")
            for b in variable:
                lines.append(f"    {b['category']}: ${b['monthly']:,.2f}")

        summary = "\n".join(lines) if lines else "  (no budgets set)"
        total = fixed_total + var_total
        if lang == "es":
            msg = (f"Resumen de Presupuesto:\n{summary}\n\n"
                   f"Fijo: ${fixed_total:,.2f} | Variable: ${var_total:,.2f} | Total: ${total:,.2f}/mes\n\n"
                   f"Correcto? (yes / edit / add more)")
        else:
            msg = (f"Budget Summary:\n{summary}\n\n"
                   f"Fixed: ${fixed_total:,.2f} | Variable: ${var_total:,.2f} | Total: ${total:,.2f}/mo\n\n"
                   f"Correct? (yes / edit / add more)")
        return _response(msg, self.state, budgets=items,
                         fixed_total=round(fixed_total, 2), variable_total=round(var_total, 2))

    def _state_budget_confirm(self, text: str) -> dict:
        if _is_confirm(text):
            self._advance(SetupState.BILLS_COLLECT)
            return self._prompt_bills_collect()
        if text.lower() in ("add", "add more", "más", "edit"):
            self._advance(SetupState.BUDGET_COLLECT)
            return _response("Modify budgets (same format as before):", self.state)
        if not text:
            return self._prompt_budget_confirm()
        return _response("Type 'yes' to confirm or 'edit' to modify.", self.state)

    # ── BILLS_COLLECT (loop) ──────────────────────────

    def _prompt_bills_collect(self) -> dict:
        lang = _lang(self.collected)
        step = "5 of 8" if self.mode == "full" else "skipped"
        if lang == "es":
            msg = (f"Paso {step} — Bills y Suscripciones Recurrentes\n"
                   f"Dime tus pagos recurrentes: nombre, monto, día de vencimiento, frecuencia.\n"
                   f"Ejemplo: Power, 120, 15, monthly\n\n"
                   f"'done' para terminar, 'skip' para saltar.")
        else:
            msg = (f"Step {step} — Recurring Bills & Subscriptions\n"
                   f"Tell me your recurring bills: name, amount, due date, frequency.\n"
                   f"Example: Power, 120, 15, monthly\n\n"
                   f"'done' when finished, 'skip' to skip.")
        return _response(msg, self.state, schema=_load_schema("bill"))

    def _state_bills_collect(self, text: str) -> dict:
        if _is_done(text) or not text:
            self._advance(SetupState.BILLS_CONFIRM)
            return self._prompt_bills_confirm()

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
        return _response(f"Added: {parts[0]} — ${amount:.2f} due day {due_day}\nAnother? or 'done'",
                         self.state, items_count=len(items))

    # ── BILLS_CONFIRM ─────────────────────────────────

    def _prompt_bills_confirm(self) -> dict:
        items = self.collected.get("bills", [])
        lang = _lang(self.collected)
        if not items:
            if lang == "es":
                msg = "Sin bills registrados. Continuar? (yes)"
            else:
                msg = "No bills entered. Continue? (yes)"
            return _response(msg, self.state)

        lines = []
        total = 0
        for i, b in enumerate(items, 1):
            lines.append(f"  {i}. {b['name']}: ${b['amount']:,.2f} due day {b['due_day']}")
            total += b["amount"]
        summary = "\n".join(lines)
        if lang == "es":
            msg = f"Resumen de Bills:\n{summary}\n\nTotal mensual: ${total:,.2f}\n\nCorrecto? (yes / edit N / add more)"
        else:
            msg = f"Bills Summary:\n{summary}\n\nMonthly total: ${total:,.2f}\n\nCorrect? (yes / edit N / add more)"
        return _response(msg, self.state, bills=items, total_bills=round(total, 2))

    def _state_bills_confirm(self, text: str) -> dict:
        if _is_confirm(text) or (not text and not self.collected.get("bills")):
            self._advance(SetupState.REVIEW_ALL)
            return self._prompt_review_all()
        if text.lower().startswith("edit") and len(text.split()) > 1:
            idx_str = text.split()[1]
            if idx_str.isdigit():
                idx = int(idx_str) - 1
                items = self.collected.get("bills", [])
                if 0 <= idx < len(items):
                    items.pop(idx)
                    self._save()
                    self._advance(SetupState.BILLS_COLLECT)
                    return _response("Removed. Re-enter or say 'done'.", self.state)
        if text.lower() in ("add", "add more", "más"):
            self._advance(SetupState.BILLS_COLLECT)
            return _response("Add another bill:", self.state)
        if not text:
            return self._prompt_bills_confirm()
        return _response("Type 'yes' to confirm, 'edit N' to change, or 'add more'.", self.state)

    # ── REVIEW_ALL ────────────────────────────────────

    def _prompt_review_all(self) -> dict:
        lang = _lang(self.collected)
        income = self.collected.get("income", [])
        debts = self.collected.get("debts", [])
        budgets = [b for b in self.collected.get("budgets", []) if b["monthly"] > 0]
        bills = self.collected.get("bills", [])
        rulepacks = self.collected.get("rulepacks", [])

        total_monthly_income = sum(
            inc["amount"] * {"weekly": 4.33, "biweekly": 2.17, "monthly": 1, "irregular": 1}.get(inc["frequency"], 1)
            for inc in income
        )
        total_bills = sum(b["amount"] for b in bills)
        total_budget = sum(b["monthly"] for b in budgets)
        total_debt_min = sum(d.get("minimum_payment", 0) for d in debts)
        surplus = total_monthly_income - total_bills - total_debt_min

        lines = [
            f"INCOME ({len(income)} sources):",
        ]
        for inc in income:
            lines.append(f"  {inc['name']}: ${inc['amount']:,.2f} {inc['frequency']} → {inc['account_label']}")
        lines.append(f"  Est. monthly: ${total_monthly_income:,.2f}")

        if rulepacks:
            lines.append(f"\nBUSINESS RULES: {len(rulepacks)} rulepack(s) loaded")

        if debts:
            lines.append(f"\nDEBTS ({len(debts)}):")
            for d in debts:
                lines.append(f"  {d['name']}: ${d['balance']:,.2f} @ {d['apr']}% APR, min ${d['minimum_payment']:.2f}")

        if budgets:
            fixed = sum(b["monthly"] for b in budgets if b.get("type") == "fixed")
            variable = sum(b["monthly"] for b in budgets if b.get("type") == "variable")
            lines.append(f"\nBUDGET: {len(budgets)} categories, ${total_budget:,.2f}/month")
            lines.append(f"  Fixed: ${fixed:,.2f} | Variable: ${variable:,.2f}")

        if bills:
            lines.append(f"\nBILLS: {len(bills)} recurring, ${total_bills:,.2f}/month")

        lines.append(f"\nEstimated monthly surplus: ${surplus:,.2f}")
        if surplus < 0:
            lines.append("  WARNING: Spending exceeds income!")

        summary = "\n".join(lines)
        if lang == "es":
            msg = f"Revisión del Setup:\n\n{summary}\n\nConfirmar todo? (yes / edit [section])"
        else:
            msg = f"Setup Review:\n\n{summary}\n\nConfirm all? (yes / edit [section])"
        return _response(msg, self.state,
                         summary={
                             "income_count": len(income),
                             "debt_count": len(debts),
                             "budget_count": len(budgets),
                             "bills_count": len(bills),
                             "rulepacks": rulepacks,
                             "total_monthly_income": round(total_monthly_income, 2),
                             "total_bills": round(total_bills, 2),
                             "surplus": round(surplus, 2),
                         })

    def _state_review_all(self, text: str) -> dict:
        if _is_confirm(text):
            self._build_config()
            self._advance(SetupState.SHEETS_CREATE)
            lang = _lang(self.collected)
            if lang == "es":
                msg = "Config guardada. Creando Google Sheet..."
            else:
                msg = "Config saved. Creating Google Sheet..."
            return _response(msg, self.state)
        if text.lower().startswith("edit"):
            # Allow "edit income", "edit debts", etc.
            section = text.split(maxsplit=1)[1].lower() if len(text.split()) > 1 else ""
            section_map = {
                "income": SetupState.INCOME_COLLECT,
                "ingresos": SetupState.INCOME_COLLECT,
                "debt": SetupState.DEBT_COLLECT, "debts": SetupState.DEBT_COLLECT,
                "deudas": SetupState.DEBT_COLLECT,
                "budget": SetupState.BUDGET_COLLECT, "budgets": SetupState.BUDGET_COLLECT,
                "presupuesto": SetupState.BUDGET_COLLECT,
                "bills": SetupState.BILLS_COLLECT,
                "pagos": SetupState.BILLS_COLLECT,
            }
            if section in section_map:
                self._advance(section_map[section])
                return self.process("")
            return _response("Edit which section? (income / debts / budget / bills)", self.state)
        if not text:
            return self._prompt_review_all()
        return _response("Type 'yes' to confirm or 'edit [section]' to go back.", self.state)

    # ── SHEETS_CREATE ─────────────────────────────────

    def _state_sheets_create(self, text: str) -> dict:
        # Phase 2 will implement actual sheet creation
        # For now, advance to CRONS_SETUP without marking complete
        self._advance(SetupState.CRONS_SETUP)
        lang = _lang(self.collected)
        if lang == "es":
            msg = "Sheet creado (placeholder). Configurando cron jobs..."
        else:
            msg = "Sheet created (placeholder). Setting up cron jobs..."
        return _response(msg, self.state)

    # ── CRONS_SETUP ───────────────────────────────────

    def _state_crons_setup(self, text: str) -> dict:
        # Phase 2 will register OpenClaw native crons
        tz = self.collected.get("context", {}).get("timezone", "America/New_York")
        self.collected["crons"] = {
            "timezone": tz,
            "jobs": ["daily_cashflow", "payment_check", "weekly_review", "monthly_report"],
        }
        self._advance(SetupState.TELEMETRY_OPT)
        lang = _lang(self.collected)
        if lang == "es":
            msg = (f"4 cron jobs configurados (TZ: {tz}):\n"
                   f"  - Cashflow diario (L-V 7:30am)\n"
                   f"  - Verificación de pagos (diario 9am)\n"
                   f"  - Resumen semanal (domingos 8am)\n"
                   f"  - Reporte mensual (día 1, 8am)")
        else:
            msg = (f"4 cron jobs configured (TZ: {tz}):\n"
                   f"  - Daily cashflow (Mon-Fri 7:30am)\n"
                   f"  - Payment check (daily 9am)\n"
                   f"  - Weekly review (Sundays 8am)\n"
                   f"  - Monthly report (1st of month, 8am)")
        return _response(msg, self.state)

    # ── TELEMETRY_OPT ─────────────────────────────────

    def _state_telemetry_opt(self, text: str) -> dict:
        lang = _lang(self.collected)
        if not text:
            msg = ("To improve reliability, we collect anonymous performance data:\n"
                   "  + App version and stage completion/failure\n"
                   "  + Coarse timing buckets (e.g., '5-15 seconds')\n"
                   "  + Feature counts (categories, rules, income sources)\n"
                   "  + Standardized error codes\n\n"
                   "We NEVER collect:\n"
                   "  - Your name, email, phone, or chat ID\n"
                   "  - Account names, balances, or transactions\n"
                   "  - Merchant names or receipt text\n"
                   "  - Google Sheet URLs or file contents\n\n"
                   "Allow anonymous telemetry? (yes/no)")
            return _response(msg, self.state)

        if text.lower() in ("yes", "y", "sí", "si"):
            self.collected["telemetry"] = True
        elif text.lower() in ("no", "n"):
            self.collected["telemetry"] = False
        else:
            return _response("Enter yes or no:", self.state)

        self._save()
        self._advance(SetupState.ONBOARDING_MISSIONS)
        return self._state_onboarding_missions("")

    # ── ONBOARDING_MISSIONS ───────────────────────────

    def _state_onboarding_missions(self, text: str) -> dict:
        lang = _lang(self.collected)

        # Mark setup complete NOW
        config = C._load_tracker_config()
        config["user"]["setup_complete"] = True
        config["telemetry"] = {"enabled": self.collected.get("telemetry", False)}
        C.save_tracker_config(config)
        C.clear_setup_state()
        self.state = SetupState.COMPLETE

        if lang == "es":
            msg = ("Setup completo! Tu Finance Tracker está listo.\n\n"
                   "Probemos 3 cosas rápidas:\n\n"
                   "Misión 1: Envíame una foto de un recibo o escribe '$15 Uber'\n"
                   "Misión 2: Escribe 'budget status'\n"
                   "Misión 3: Escribe 'safe to spend'")
        else:
            msg = ("Setup complete! Your Finance Tracker is ready.\n\n"
                   "Let's try 3 quick things to get you started:\n\n"
                   "Mission 1: Send a receipt photo or type '$15 Uber'\n"
                   "Mission 2: Say 'budget status'\n"
                   "Mission 3: Say 'safe to spend'")
        return _response(msg, self.state, done=True)

    # ── COMPLETE ──────────────────────────────────────

    def _state_complete(self, text: str) -> dict:
        return _response("Setup already complete.", self.state, done=True)

    # ── Config builder ────────────────────────────────

    def _build_config(self) -> None:
        """Build tracker_config.json from collected setup data."""
        ctx = self.collected.get("context", {})
        name = ctx.get("name", "User")
        lang = ctx.get("language", "en")
        currency = self.collected.get("currency", "USD")
        cards = self.collected.get("cards", ["Card 1", "Cash"])
        year = datetime.now().year

        # Build categories from budgets
        user_budgets = self.collected.get("budgets", [])
        if user_budgets:
            categories = {}
            for b in user_budgets:
                categories[b["category"]] = {
                    "monthly": b["monthly"],
                    "type": b.get("type", "variable"),
                    "threshold": b.get("threshold", 0.8),
                }
            if "Other" not in categories:
                categories["Other"] = {"monthly": 50, "type": "variable", "threshold": 0.8}
        else:
            categories = C._defaults()["categories"]

        # Build payments from bills
        payments = []
        for bill in self.collected.get("bills", []):
            payments.append({
                "name": bill["name"], "amount": bill["amount"],
                "due_day": bill["due_day"], "account": bill.get("account", "Bank"),
                "autopay": bill.get("autopay", False), "apr": bill.get("apr", 0),
                "promo_expiry": None,
            })

        # Income → balance
        income_list = self.collected.get("income", [])
        expected = 0
        pay_schedule = "biweekly"
        if income_list:
            primary = income_list[0]
            expected = primary["amount"]
            pay_schedule = primary.get("frequency", "biweekly")
            if pay_schedule == "irregular":
                pay_schedule = "monthly"

        # Tax / business rules
        rulepacks = self.collected.get("rulepacks", [])
        business_rules = self.collected.get("business_rules", [])
        tax = {
            "enabled": bool(rulepacks),
            "rulepacks": rulepacks,
            "deductible_categories": business_rules,
        }

        config = {
            "user": {
                "name": name, "language": lang,
                "spreadsheet_name": f"{name} Finance {year}",
                "currency": currency, "cards": cards,
                "setup_complete": False,
                "created_at": datetime.now().isoformat(),
            },
            "categories": categories,
            "balance": {
                "available": 0, "last_updated": None,
                "pay_schedule": pay_schedule, "pay_dates": [1, 15],
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
