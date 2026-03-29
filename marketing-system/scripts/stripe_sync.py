#!/usr/bin/env python3
"""Stripe → PostgreSQL sync for marketing.orders.

Fetches successful payment_intents from Stripe and saves them to DB
via db.save_order(). Idempotent — uses order_id (pi_xxx) as key.

Usage:
    python3 stripe_sync.py <project_id> [--days 30]
    python3 stripe_sync.py misterio-semanal --days 60
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Load env
from dotenv import load_dotenv
env_path = Path("/home/robotin/.openclaw/.env")
if env_path.exists():
    load_dotenv(env_path)

import stripe
import db

stripe.api_key = os.environ.get("STRIPE_API_KEY")
if not stripe.api_key:
    print("ERROR: STRIPE_API_KEY not found in ~/.openclaw/.env")
    sys.exit(1)


def sync_orders(project_id: str, days: int = 30) -> dict:
    """Fetch Stripe payment_intents and save to DB."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    since_ts = int(since.timestamp())

    print(f"Fetching Stripe payments since {since.strftime('%Y-%m-%d')} ({days} days)...")

    created = 0
    updated = 0
    skipped = 0
    total = 0
    total_revenue = 0.0

    # Paginate through all payment_intents
    params = {
        "limit": 100,
        "created": {"gte": since_ts},
    }

    has_more = True
    starting_after = None

    while has_more:
        if starting_after:
            params["starting_after"] = starting_after

        response = stripe.PaymentIntent.list(**params)
        intents = response.data
        has_more = response.has_more

        if intents:
            starting_after = intents[-1].id

        for pi in intents:
            total += 1

            # Only process succeeded payments
            if pi.status != "succeeded":
                skipped += 1
                continue

            # Extract metadata for UTM attribution
            meta = pi.metadata or {}
            utm_source = meta.get("utm_source", meta.get("source"))
            utm_medium = meta.get("utm_medium", meta.get("medium"))
            utm_campaign = meta.get("utm_campaign", meta.get("campaign"))
            utm_content = meta.get("utm_content", meta.get("content"))

            # Amount is in cents
            amount_usd = pi.amount / 100.0
            currency = (pi.currency or "usd").upper()

            # Customer email from charges
            customer_email = None
            if pi.latest_charge:
                try:
                    charge = stripe.Charge.retrieve(pi.latest_charge)
                    customer_email = charge.billing_details.email or charge.receipt_email
                except Exception:
                    pass

            # Source platform heuristic from metadata
            source_platform = meta.get("platform", meta.get("source_platform"))
            source_campaign_name = meta.get("campaign_name", utm_campaign)

            # Build items from metadata if available
            items = []
            if meta.get("product_name"):
                items.append({
                    "product": meta.get("product_name"),
                    "sku": meta.get("sku", meta.get("product_id")),
                    "quantity": int(meta.get("quantity", 1)),
                })

            order_dict = {
                "order_id": pi.id,
                "stripe_payment_id": pi.id,
                "customer_email": customer_email,
                "amount": amount_usd,
                "currency": currency,
                "status": "completed",
                "source_platform": source_platform,
                "source_campaign": source_campaign_name,
                "utm_source": utm_source,
                "utm_medium": utm_medium,
                "utm_campaign": utm_campaign,
                "utm_content": utm_content,
                "items": items,
                "order_date": datetime.fromtimestamp(pi.created, tz=timezone.utc),
            }

            try:
                db_id = db.save_order(project_id, order_dict)
                total_revenue += amount_usd
                # Check if this was an insert or update by checking if id changed
                # (upsert always returns id, so we just count)
                created += 1
                print(f"  [{pi.id}] ${amount_usd:.2f} {currency} — {customer_email or 'no email'}"
                      f" — utm: {utm_source or '-'}/{utm_medium or '-'}/{utm_campaign or '-'}")
            except Exception as e:
                print(f"  ERROR saving {pi.id}: {e}")

    # Summary
    print(f"\n{'='*50}")
    print(f"STRIPE SYNC COMPLETE — {project_id}")
    print(f"{'='*50}")
    print(f"  Period: last {days} days")
    print(f"  Total payment_intents: {total}")
    print(f"  Succeeded (synced): {created}")
    print(f"  Skipped (not succeeded): {skipped}")
    print(f"  Total revenue: ${total_revenue:.2f}")

    return {
        "total_intents": total,
        "synced": created,
        "skipped": skipped,
        "total_revenue": total_revenue,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync Stripe orders to PostgreSQL")
    parser.add_argument("project_id", help="Project ID (e.g. misterio-semanal)")
    parser.add_argument("--days", type=int, default=30, help="Days to look back (default: 30)")
    args = parser.parse_args()

    result = sync_orders(args.project_id, args.days)
