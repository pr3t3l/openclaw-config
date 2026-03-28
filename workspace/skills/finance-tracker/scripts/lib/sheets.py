"""Google Sheets client for the finance tracker."""

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from . import config as C

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_credentials(allow_interactive: bool = False) -> Credentials:
    creds = None
    if C.GOOGLE_TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(C.GOOGLE_TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif allow_interactive:
            flow = InstalledAppFlow.from_client_secrets_file(str(C.GOOGLE_CLIENT_FILE), SCOPES)
            # Use local server on fixed port — WSL forwards to Windows browser
            print("Opening OAuth flow on http://localhost:18900/")
            print("If browser doesn't open, copy the URL from the terminal.")
            creds = flow.run_local_server(port=18900, open_browser=False)
            C.GOOGLE_TOKEN_FILE.write_text(creds.to_json())
        else:
            raise RuntimeError(
                "Google Sheets not authenticated. Run: "
                "finance.py setup-sheets --auth to complete OAuth."
            )
    return creds


def get_client(allow_interactive: bool = False) -> gspread.Client:
    return gspread.authorize(get_credentials(allow_interactive))


def get_spreadsheet() -> gspread.Spreadsheet:
    return get_client().open(C.SPREADSHEET_NAME)


def get_sheet(tab_name: str) -> gspread.Worksheet:
    return get_spreadsheet().worksheet(tab_name)


def append_transaction(tx: dict):
    """Append a transaction row to the Transactions tab."""
    ws = get_sheet(C.TAB_TRANSACTIONS)
    row = [
        tx.get("date", ""),
        tx.get("amount", 0),
        tx.get("merchant", ""),
        tx.get("category", ""),
        tx.get("subcategory", ""),
        tx.get("card", ""),
        tx.get("input_method", ""),
        tx.get("confidence", 0),
        tx.get("matched", False),
        tx.get("source", "receipt"),
        tx.get("notes", ""),
        tx.get("timestamp", ""),
        tx.get("month", ""),
        tx.get("receipt_id", ""),
        tx.get("receipt_number", ""),
        tx.get("store_address", ""),
        tx.get("tax_deductible", False),
        tx.get("tax_category", "none"),
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")


def get_month_spending(category: str, month: str) -> float:
    """Sum spending for a category in a given month (YYYY-MM)."""
    ws = get_sheet(C.TAB_TRANSACTIONS)
    records = ws.get_all_records()
    return sum(
        float(r.get("amount", 0))
        for r in records
        if r.get("category") == category and r.get("month") == month
    )


def get_all_month_spending(month: str) -> dict[str, float]:
    """Return {category: total} for a given month."""
    ws = get_sheet(C.TAB_TRANSACTIONS)
    records = ws.get_all_records()
    totals: dict[str, float] = {}
    for r in records:
        if r.get("month") == month:
            cat = r.get("category", "Other")
            totals[cat] = totals.get(cat, 0) + float(r.get("amount", 0))
    return totals


def get_recent_transactions(days: int = 2) -> list[dict]:
    """Get transactions from the last N days for duplicate detection."""
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    ws = get_sheet(C.TAB_TRANSACTIONS)
    records = ws.get_all_records()
    return [r for r in records if r.get("date", "") >= cutoff]


def get_transactions_for_month(month: str) -> list[dict]:
    """Get all transactions for a specific month."""
    ws = get_sheet(C.TAB_TRANSACTIONS)
    records = ws.get_all_records()
    return [r for r in records if r.get("month") == month]


def get_tax_deductions(year: str = None, month: str = None) -> list[dict]:
    """Get tax-deductible transactions, optionally filtered by year or month."""
    ws = get_sheet(C.TAB_TRANSACTIONS)
    records = ws.get_all_records()
    results = []
    for r in records:
        if not r.get("tax_deductible") or str(r.get("tax_deductible")).upper() != "TRUE":
            continue
        if year and not r.get("date", "").startswith(year):
            continue
        if month and r.get("month") != month:
            continue
        results.append(r)
    return results


def get_budget_cell(cell: str):
    """Read a named cell from the Budget tab."""
    ws = get_sheet(C.TAB_BUDGET)
    return ws.acell(cell).value


def update_budget_cell(cell: str, value):
    """Update a named cell in the Budget tab."""
    ws = get_sheet(C.TAB_BUDGET)
    ws.update_acell(cell, value)


def append_reconciliation_row(row: dict):
    """Append a row to the Reconciliation_Log tab."""
    ws = get_sheet(C.TAB_RECONCILIATION)
    ws.append_row([
        row.get("date", ""),
        row.get("amount", 0),
        row.get("merchant_bank", ""),
        row.get("merchant_receipt", ""),
        row.get("status", ""),
        row.get("receipt_row", ""),
        row.get("csv_row", ""),
        row.get("resolved_by", ""),
        row.get("notes", ""),
    ], value_input_option="USER_ENTERED")
