#!/usr/bin/env python3
"""Sends marketing emails via Resend API from generated email sequences.

Reads email_sequence_draft.json and sends via Resend with A/B subject testing.

Usage:
    python3 send_marketing_emails.py <product_id> <week> [--dry-run] [--test-email user@example.com]
    # --dry-run: shows what would be sent without sending
    # --test-email: sends only to this address (for testing)

Dependencies:
    pip install resend markdown --break-system-packages
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import markdown

PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")
SCRIPTS_DIR = Path(__file__).parent
CONFIG_DIR = SCRIPTS_DIR.parent / "config"
ENV_PATH = Path("/home/robotin/.openclaw/.env")


def load_env():
    """Load .env file into environment."""
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())


def md_to_html(body_markdown: str, footer_html: str, unsubscribe_url: str) -> str:
    """Convert markdown email body to styled HTML."""
    body_html = markdown.markdown(body_markdown)
    footer = footer_html.replace("{{unsubscribe_url}}", unsubscribe_url)
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin: 0; padding: 20px; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 0 auto; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #333; line-height: 1.6; background: #fff; padding: 30px; border-radius: 8px;">
        {body_html}
        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        {footer}
    </div>
</body>
</html>"""


def load_email_config() -> dict:
    """Load email configuration."""
    config_path = CONFIG_DIR / "email_config.json"
    if config_path.exists():
        return json.loads(config_path.read_text())
    # Default config
    return {
        "from_email": "cases@theclassifiedcases.shop",
        "from_name": "Declassified Cases",
        "reply_to": "support@theclassifiedcases.shop",
        "subscriber_lists": {"all": []},
        "ab_test_split": 0.5,
        "unsubscribe_url": "https://theclassifiedcases.shop/unsubscribe",
        "footer_html": "<p>Declassified Cases — theclassifiedcases.shop<br><a href='{{unsubscribe_url}}'>Unsubscribe</a></p>",
    }


def get_recipients(config: dict, persona_id: str, test_email: str = None) -> list:
    """Get recipient list for a persona."""
    if test_email:
        return [test_email]

    lists = config.get("subscriber_lists", {})
    # Try persona-specific list, fall back to 'all'
    recipients = lists.get(persona_id, lists.get("all", []))
    return recipients


def send_email_via_resend(from_addr: str, to_list: list, subject: str,
                          html_body: str, reply_to: str, tags: list,
                          dry_run: bool = False) -> dict:
    """Send email via Resend API. Returns result dict."""
    if dry_run:
        return {
            "status": "dry_run",
            "resend_id": "dry_run",
            "recipients_count": len(to_list),
        }

    if not to_list:
        return {
            "status": "skipped",
            "resend_id": None,
            "recipients_count": 0,
            "error": "No recipients",
        }

    import resend

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return {
            "status": "failed",
            "resend_id": None,
            "recipients_count": 0,
            "error": "RESEND_API_KEY not found in .env. Create account at resend.com, verify your domain, and add the key.",
        }

    resend.api_key = api_key

    try:
        response = resend.Emails.send({
            "from": from_addr,
            "to": to_list,
            "subject": subject,
            "html": html_body,
            "reply_to": reply_to,
            "tags": tags,
        })

        resend_id = response.get("id", "") if isinstance(response, dict) else str(response)
        return {
            "status": "sent",
            "resend_id": resend_id,
            "recipients_count": len(to_list),
        }

    except Exception as e:
        return {
            "status": "failed",
            "resend_id": None,
            "recipients_count": len(to_list),
            "error": str(e)[:300],
        }


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 send_marketing_emails.py <product_id> <week> [--dry-run] [--test-email user@example.com]")
        sys.exit(1)

    product_id = sys.argv[1]
    week = sys.argv[2]
    dry_run = "--dry-run" in sys.argv
    test_email = None
    if "--test-email" in sys.argv:
        idx = sys.argv.index("--test-email")
        if idx + 1 < len(sys.argv):
            test_email = sys.argv[idx + 1]

    load_env()
    config = load_email_config()

    # Check for API key early
    if not dry_run and not test_email:
        api_key = os.environ.get("RESEND_API_KEY")
        if not api_key:
            print("⚠️  RESEND_API_KEY not found in .env")
            print("   Create account at resend.com, verify your domain, and add:")
            print("   RESEND_API_KEY=re_xxxxxxxx")
            print("\n   Use --dry-run to preview without sending, or --test-email to test.")
            sys.exit(1)

    product_dir = PRODUCTS_DIR / product_id
    run_dir = product_dir / "weekly_runs" / week

    # Try approved first, then drafts
    approved_path = run_dir / "approved" / "email_sequence_draft.json"
    drafts_path = run_dir / "drafts" / "email_sequence_draft.json"
    email_path = approved_path if approved_path.exists() else drafts_path

    if not email_path.exists():
        print(f"Error: No email_sequence_draft.json found in {run_dir}")
        sys.exit(1)

    email_data = json.loads(email_path.read_text())
    sequences = email_data.get("sequences", [])

    from_name = config.get("from_name", "Declassified Cases")
    from_email = config.get("from_email", "cases@theclassifiedcases.shop")
    from_addr = f"{from_name} <{from_email}>"
    reply_to = config.get("reply_to", from_email)
    footer_html = config.get("footer_html", "")
    unsubscribe_url = config.get("unsubscribe_url", "")
    ab_split = config.get("ab_test_split", 0.5)

    mode = "dry_run" if dry_run else ("test" if test_email else "live")

    print(f"\n{'='*50}")
    print(f"EMAIL SENDING — {product_id} ({week})")
    print(f"Mode: {mode}")
    if test_email:
        print(f"Test email: {test_email}")
    print(f"Source: {email_path}")
    print(f"Sequences: {len(sequences)}")
    print(f"{'='*50}")

    report_emails = []
    total_sent = 0
    total_failed = 0
    variant_a_count = 0
    variant_b_count = 0

    for seq in sequences:
        seq_id = seq.get("sequence_id", "unknown")
        print(f"\n  Sequence: {seq_id}")

        for email in seq.get("emails", []):
            email_id = email.get("email_id", "")
            persona_id = email.get("persona_id", "")
            subject_a = email.get("subject_line_a", email.get("subject", ""))
            subject_b = email.get("subject_line_b", "")
            body_md = email.get("body_markdown", "")

            recipients = get_recipients(config, persona_id, test_email)
            html_body = md_to_html(body_md, footer_html, unsubscribe_url)

            has_ab = bool(subject_b and subject_b != subject_a)

            if has_ab and len(recipients) > 1 and not test_email:
                # A/B split
                split_point = int(len(recipients) * ab_split)
                recipients_a = recipients[:split_point]
                recipients_b = recipients[split_point:]
            else:
                recipients_a = recipients
                recipients_b = []

            # Send variant A
            tags_a = [
                {"name": "product_id", "value": product_id},
                {"name": "week", "value": week},
                {"name": "email_id", "value": email_id},
                {"name": "persona_id", "value": persona_id},
                {"name": "variant", "value": "A"},
            ]

            print(f"    {email_id} (variant A): \"{subject_a[:50]}\" → {len(recipients_a)} recipients")
            result_a = send_email_via_resend(from_addr, recipients_a, subject_a,
                                              html_body, reply_to, tags_a, dry_run)

            report_emails.append({
                "email_id": email_id,
                "sequence_id": seq_id,
                "subject_variant": "A",
                "subject": subject_a,
                "recipients_count": result_a["recipients_count"],
                "resend_id": result_a.get("resend_id"),
                "status": result_a["status"],
                "error": result_a.get("error"),
            })

            if result_a["status"] in ("sent", "dry_run"):
                total_sent += 1
                variant_a_count += result_a["recipients_count"]
            else:
                total_failed += 1

            # Send variant B if A/B test
            if recipients_b:
                tags_b = [t if t["name"] != "variant" else {"name": "variant", "value": "B"} for t in tags_a]
                print(f"    {email_id} (variant B): \"{subject_b[:50]}\" → {len(recipients_b)} recipients")
                result_b = send_email_via_resend(from_addr, recipients_b, subject_b,
                                                  html_body, reply_to, tags_b, dry_run)

                report_emails.append({
                    "email_id": email_id,
                    "sequence_id": seq_id,
                    "subject_variant": "B",
                    "subject": subject_b,
                    "recipients_count": result_b["recipients_count"],
                    "resend_id": result_b.get("resend_id"),
                    "status": result_b["status"],
                    "error": result_b.get("error"),
                })

                if result_b["status"] in ("sent", "dry_run"):
                    total_sent += 1
                    variant_b_count += result_b["recipients_count"]
                else:
                    total_failed += 1

    # Save report
    report = {
        "product_id": product_id,
        "week": week,
        "sent_at": datetime.now().isoformat(),
        "mode": mode,
        "test_email": test_email,
        "emails_sent": report_emails,
        "total_sent": total_sent,
        "total_failed": total_failed,
        "ab_test_split": {
            "variant_a_count": variant_a_count,
            "variant_b_count": variant_b_count,
        },
    }
    report_path = run_dir / "email_send_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print(f"\n{'='*50}")
    print(f"Done: {total_sent} sent, {total_failed} failed")
    print(f"A/B: {variant_a_count} variant A, {variant_b_count} variant B")
    print(f"Report: {report_path}")
    print(f"{'='*50}")

    # Telegram notification
    try:
        sys.path.insert(0, str(SCRIPTS_DIR))
        from telegram_sender import send_message
        send_message(
            f"📧 Emails enviados — {week}\n"
            f"{'✅' if total_failed == 0 else '⚠️'} {total_sent}/{total_sent + total_failed} emails enviados\n"
            f"📊 A/B test: {variant_a_count} con subject A, {variant_b_count} con subject B\n"
            f"Mode: {mode}"
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()
