"""Google Sheets integration for Finance Tracker v2.

Auth: google-client.json + finance-tracker-token.json from ~/.openclaw/credentials/
ALL tab references use numeric sheetId, NEVER tab names.
Cherry-picked gspread connection from v1, adapted to sheetId-based access.
"""

import json
import time
from pathlib import Path

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from . import config as C
from .errors import FinanceError, ErrorCode

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_CLIENT = None
_SPREADSHEET = None

CREDS_DIR = Path.home() / ".openclaw" / "credentials"
CLIENT_JSON = CREDS_DIR / "google-client.json"
TOKEN_JSON = CREDS_DIR / "finance-tracker-token.json"

# Tab definitions with headers
TAB_DEFS = {
    "transactions": {
        "title": "Transactions",
        "headers": [
            "date", "amount", "merchant", "category", "subcategory", "card",
            "input_method", "confidence", "matched", "source", "notes",
            "timestamp", "month", "receipt_id", "receipt_number", "store_address",
            "tax_deductible", "tax_category", "type", "business_id",
        ],
    },
    "budget": {
        "title": "Budget",
        "headers": ["category", "type", "monthly_limit", "threshold", "current_spent", "pct_used"],
    },
    "payment_calendar": {
        "title": "Payment Calendar",
        "headers": ["name", "amount", "due_day", "frequency", "account", "autopay", "apr", "promo_expiry", "next_due"],
    },
    "monthly_summary": {
        "title": "Monthly Summary",
        "headers": ["month", "total_income", "total_expenses", "total_fixed", "total_variable",
                     "surplus", "savings_contrib", "debt_payments", "deductible_total"],
    },
    "debt_tracker": {
        "title": "Debt Tracker",
        "headers": ["name", "type", "balance", "apr", "minimum_payment", "monthly_payment",
                     "payoff_date_est", "total_interest_est", "notes"],
    },
    "rules": {
        "title": "Rules",
        "headers": ["merchant_pattern", "category", "subcategory", "requires_line_items",
                     "confidence", "times_used", "last_used", "created_by"],
    },
    "reconciliation_log": {
        "title": "Reconciliation Log",
        "headers": ["date", "amount", "merchant_bank", "merchant_receipt", "status",
                     "receipt_row", "csv_row", "resolved_by", "notes"],
    },
    "cashflow_ledger": {
        "title": "Cashflow Ledger",
        "headers": ["date", "account", "merchant", "amount_signed", "flow_type",
                     "category", "subcategory", "notes", "source", "timestamp", "month"],
    },
    "businesses": {
        "title": "Businesses",
        "headers": ["business_id", "name", "type", "schedule", "rulepack_id", "active", "created_at"],
    },
    "savings_goals": {
        "title": "Savings Goals",
        "headers": ["goal", "target", "saved", "deadline", "daily_required", "status"],
    },
}


def get_credentials() -> Credentials:
    """Load Google OAuth credentials from openclaw credentials dir."""
    if not CLIENT_JSON.exists():
        raise FinanceError(ErrorCode.GOG_AUTH_MISSING,
                           f"Missing {CLIENT_JSON}. Set up Google OAuth first.")
    if not TOKEN_JSON.exists():
        raise FinanceError(ErrorCode.GOG_AUTH_MISSING,
                           f"Missing {TOKEN_JSON}. Run OAuth flow first.")

    client_data = json.loads(CLIENT_JSON.read_text())
    token_data = json.loads(TOKEN_JSON.read_text())

    # Build credentials from client + token
    installed = client_data.get("installed", client_data.get("web", {}))
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        client_id=installed.get("client_id"),
        client_secret=installed.get("client_secret"),
        token_uri=installed.get("token_uri", "https://oauth2.googleapis.com/token"),
        scopes=SCOPES,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Save refreshed token
        token_data["token"] = creds.token
        C.save_json(TOKEN_JSON, token_data)
    return creds


def get_client() -> gspread.Client:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = gspread.authorize(get_credentials())
    return _CLIENT


def get_spreadsheet(spreadsheet_id: str) -> gspread.Spreadsheet:
    global _SPREADSHEET
    if _SPREADSHEET is None:
        _SPREADSHEET = get_client().open_by_key(spreadsheet_id)
    return _SPREADSHEET


def get_sheet_by_id(spreadsheet_id: str, sheet_id: int) -> gspread.Worksheet:
    """Get a worksheet by its numeric sheetId (never by name)."""
    ss = get_spreadsheet(spreadsheet_id)
    for ws in ss.worksheets():
        if ws.id == sheet_id:
            return ws
    raise FinanceError(ErrorCode.SHEETS_ERROR, f"Sheet ID {sheet_id} not found")


# ── Create spreadsheet ────────────────────────────────

def create_spreadsheet(config: dict) -> dict:
    """Create the finance tracker workbook with 10 tabs.

    Returns sheets_config dict with spreadsheet_id, url, and tab sheetIds.
    Uses batch_update for all initial writes (one API call).
    """
    client = get_client()
    name = config["user"]["spreadsheet_name"]

    # Create spreadsheet
    ss = client.create(name)
    spreadsheet_id = ss.id
    spreadsheet_url = ss.url

    # Rename default Sheet1 to first tab
    first_tab_key = list(TAB_DEFS.keys())[0]
    first_ws = ss.sheet1
    first_ws.update_title(TAB_DEFS[first_tab_key]["title"])

    # Create remaining tabs
    tab_ids = {first_tab_key: {"sheet_id": first_ws.id, "schema_version": "v1.0"}}
    remaining_tabs = list(TAB_DEFS.keys())[1:]
    for tab_key in remaining_tabs:
        td = TAB_DEFS[tab_key]
        ws = ss.add_worksheet(title=td["title"], rows=1000, cols=len(td["headers"]))
        tab_ids[tab_key] = {"sheet_id": ws.id, "schema_version": "v1.0"}

    # Batch write all headers + initial data
    requests = []

    for tab_key, td in TAB_DEFS.items():
        sid = tab_ids[tab_key]["sheet_id"]
        # Write headers
        requests.append({
            "updateCells": {
                "range": {
                    "sheetId": sid,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(td["headers"]),
                },
                "rows": [{
                    "values": [
                        {"userEnteredValue": {"stringValue": h}} for h in td["headers"]
                    ]
                }],
                "fields": "userEnteredValue",
            }
        })

        # Format header row bold
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sid,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True},
                        "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                    }
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor)",
            }
        })

        # Freeze header row
        requests.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sid,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        })

    # Write initial budget data
    budget_sid = tab_ids["budget"]["sheet_id"]
    budget_rows = []
    for cat_name, cat_data in config.get("categories", {}).items():
        budget_rows.append({
            "values": [
                {"userEnteredValue": {"stringValue": cat_name}},
                {"userEnteredValue": {"stringValue": cat_data.get("type", "variable")}},
                {"userEnteredValue": {"numberValue": cat_data.get("monthly", 0)}},
                {"userEnteredValue": {"numberValue": cat_data.get("threshold", 0.8)}},
                {"userEnteredValue": {"numberValue": 0}},
                {"userEnteredValue": {"numberValue": 0}},
            ]
        })
    if budget_rows:
        requests.append({
            "updateCells": {
                "range": {
                    "sheetId": budget_sid,
                    "startRowIndex": 1,
                    "endRowIndex": 1 + len(budget_rows),
                    "startColumnIndex": 0,
                    "endColumnIndex": 6,
                },
                "rows": budget_rows,
                "fields": "userEnteredValue",
            }
        })

    # Write initial payment calendar data
    payments_sid = tab_ids["payment_calendar"]["sheet_id"]
    payment_rows = []
    for p in config.get("payments", []):
        payment_rows.append({
            "values": [
                {"userEnteredValue": {"stringValue": p.get("name", "")}},
                {"userEnteredValue": {"numberValue": p.get("amount", 0)}},
                {"userEnteredValue": {"numberValue": p.get("due_day", 1)}},
                {"userEnteredValue": {"stringValue": p.get("frequency", "monthly")}},
                {"userEnteredValue": {"stringValue": p.get("account", "Bank")}},
                {"userEnteredValue": {"boolValue": p.get("autopay", False)}},
                {"userEnteredValue": {"numberValue": p.get("apr", 0)}},
                {"userEnteredValue": {"stringValue": p.get("promo_expiry") or ""}},
                {"userEnteredValue": {"stringValue": ""}},
            ]
        })
    if payment_rows:
        requests.append({
            "updateCells": {
                "range": {
                    "sheetId": payments_sid,
                    "startRowIndex": 1,
                    "endRowIndex": 1 + len(payment_rows),
                    "startColumnIndex": 0,
                    "endColumnIndex": 9,
                },
                "rows": payment_rows,
                "fields": "userEnteredValue",
            }
        })

    # Write initial debt tracker data
    debt_sid = tab_ids["debt_tracker"]["sheet_id"]
    debt_rows = []
    for d in config.get("debts", []):
        debt_rows.append({
            "values": [
                {"userEnteredValue": {"stringValue": d.get("name", "")}},
                {"userEnteredValue": {"stringValue": d.get("type", "other")}},
                {"userEnteredValue": {"numberValue": d.get("balance", 0)}},
                {"userEnteredValue": {"numberValue": d.get("apr", 0)}},
                {"userEnteredValue": {"numberValue": d.get("minimum_payment", 0)}},
                {"userEnteredValue": {"numberValue": 0}},
                {"userEnteredValue": {"stringValue": ""}},
                {"userEnteredValue": {"numberValue": 0}},
                {"userEnteredValue": {"stringValue": d.get("notes", "")}},
            ]
        })
    if debt_rows:
        requests.append({
            "updateCells": {
                "range": {
                    "sheetId": debt_sid,
                    "startRowIndex": 1,
                    "endRowIndex": 1 + len(debt_rows),
                    "startColumnIndex": 0,
                    "endColumnIndex": 9,
                },
                "rows": debt_rows,
                "fields": "userEnteredValue",
            }
        })

    # Write business info
    biz_sid = tab_ids["businesses"]["sheet_id"]
    biz_rows = []
    for rp in config.get("tax", {}).get("rulepacks", []):
        btype = rp.replace("us-", "").replace(".v1", "").replace("-", "_")
        biz_rows.append({
            "values": [
                {"userEnteredValue": {"stringValue": btype}},
                {"userEnteredValue": {"stringValue": btype.replace("_", " ").title()}},
                {"userEnteredValue": {"stringValue": btype}},
                {"userEnteredValue": {"stringValue": "Schedule E" if "rental" in btype else "Schedule C"}},
                {"userEnteredValue": {"stringValue": rp}},
                {"userEnteredValue": {"boolValue": True}},
                {"userEnteredValue": {"stringValue": ""}},
            ]
        })
    if biz_rows:
        requests.append({
            "updateCells": {
                "range": {
                    "sheetId": biz_sid,
                    "startRowIndex": 1,
                    "endRowIndex": 1 + len(biz_rows),
                    "startColumnIndex": 0,
                    "endColumnIndex": 7,
                },
                "rows": biz_rows,
                "fields": "userEnteredValue",
            }
        })

    # Execute batch
    if requests:
        ss.batch_update({"requests": requests})

    # Build sheets_config
    from datetime import datetime
    sheets_config = {
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": spreadsheet_url,
        "tabs": tab_ids,
        "created_at": datetime.now().isoformat(),
        "last_validated": datetime.now().isoformat(),
    }

    # Save sheets_config.json
    C.save_json(C.get_config_dir() / "sheets_config.json", sheets_config)

    return sheets_config


# ── Schema validation ─────────────────────────────────

def validate_schema(spreadsheet_id: str, sheets_config: dict) -> dict:
    """Validate that sheet structure matches expected schema. Returns check results."""
    results = {}
    for tab_key, td in TAB_DEFS.items():
        tab_info = sheets_config.get("tabs", {}).get(tab_key)
        if not tab_info:
            results[tab_key] = {"ok": False, "error": "missing_from_config"}
            continue
        try:
            ws = get_sheet_by_id(spreadsheet_id, tab_info["sheet_id"])
            row1 = ws.row_values(1)
            expected = td["headers"]
            if row1[:len(expected)] == expected:
                results[tab_key] = {"ok": True}
            else:
                results[tab_key] = {
                    "ok": False, "error": "header_mismatch",
                    "expected": expected[:5], "got": row1[:5],
                }
        except Exception as e:
            results[tab_key] = {"ok": False, "error": str(e)}
    return results


# ── Convenience accessors ─────────────────────────────

def load_sheets_config() -> dict | None:
    path = C.get_config_dir() / "sheets_config.json"
    if path.exists():
        return C.load_json(path)
    return None
