#!/usr/bin/env python3
"""Morning Intelligence Report

- Reads sources from morning_report_sources.json
- Fetches a handful of items via RSS when possible
- Falls back to web_fetch via simple HTTP GET + title parsing for non-RSS pages (best-effort)
- Produces a Spanish summary script and sends an audio (TTS) via OpenClaw message pipeline.

NOTE: This is designed to be run by cron at 06:00 America/New_York.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import feedparser
import pytz
import requests

TZ = pytz.timezone("America/New_York")

CONFIG_PATH = Path(__file__).with_name("morning_report_sources.json")
STATE_DIR = Path(os.environ.get("OPENCLAW_STATE_DIR", str(Path.home() / ".openclaw" / "workspace" / "state")))
OUT_DIR = STATE_DIR / "morning_intelligence_report"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def now_local() -> datetime:
    return datetime.now(tz=TZ)


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def dow_key(dt: datetime) -> str:
    return dt.strftime("%a")  # Mon/Tue/...


def safe_get(url: str, timeout: int = 20) -> str:
    # WSL rule: keep requests short.
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text


def extract_title(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, flags=re.I | re.S)
    if not m:
        return "(sin título)"
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    return title[:200]


@dataclass
class Item:
    section: str
    source: str
    title: str
    url: str
    published: Optional[datetime] = None


def parse_rss(url: str) -> List[Item]:
    feed = feedparser.parse(url)
    items: List[Item] = []
    for e in feed.entries[:10]:
        link = getattr(e, "link", url)
        title = getattr(e, "title", "(sin título)")
        published = None
        if getattr(e, "published_parsed", None):
            published = datetime.fromtimestamp(time.mktime(e.published_parsed), tz=pytz.UTC).astimezone(TZ)
        items.append(Item(section="", source=feed.feed.get("title", url), title=title, url=link, published=published))
    return items


def within_24h(item: Item, ref: datetime) -> bool:
    if not item.published:
        return False
    return item.published >= (ref - timedelta(hours=24))


def collect_items(config: dict) -> Dict[str, List[Item]]:
    today = now_local()
    dow = dow_key(today)

    buckets: Dict[str, List[Item]] = {
        "critical_changes": [],
        "strategic_ai": [],
        "macro_finance": [],
        "opportunities": [],
        "other_weekly": [],
    }

    def add_from_source(category: str, name: str, url: str, typ: str = "web"):
        try:
            if typ == "rss" or url.endswith(".xml") or "rss" in url:
                parsed = parse_rss(url)
                for it in parsed:
                    it.section = category
                    it.source = name
                return parsed
            html = safe_get(url)
            title = extract_title(html)
            return [Item(section=category, source=name, title=title, url=url, published=None)]
        except Exception:
            return []

    tiers = config.get("tiers", {})

    # Tier 1 daily
    t1 = tiers.get("tier1_daily", {}).get("sources", [])
    for block in t1:
        category = block.get("category", "")
        items = block.get("items", [])
        for s in items:
            typ = s.get("type", "web")
            got = add_from_source(category, s.get("name", ""), s.get("url", ""), typ=typ)
            # Heuristic bucket mapping
            if "Changelog" in category or "Changelogs" in category:
                buckets["critical_changes"].extend(got)
            elif "Macro" in category:
                buckets["macro_finance"].extend(got)
            else:
                buckets["strategic_ai"].extend(got)

    # Tier 2 M/W/F
    t2 = tiers.get("tier2_mwf", {})
    if dow in set(t2.get("schedule", [])):
        for block in t2.get("sources", []):
            category = block.get("category", "")
            for s in block.get("items", []):
                typ = s.get("type", "web")
                got = add_from_source(category, s.get("name", ""), s.get("url", ""), typ=typ)
                buckets["opportunities"].extend(got)

    # Tier 3 weekly Monday
    t3 = tiers.get("tier3_weekly_mon", {})
    if dow in set(t3.get("schedule", [])):
        for block in t3.get("sources", []):
            category = block.get("category", "")
            for s in block.get("items", []):
                typ = s.get("type", "web")
                got = add_from_source(category, s.get("name", ""), s.get("url", ""), typ=typ)
                buckets["other_weekly"].extend(got)

    # Deduplicate by URL
    for k in list(buckets.keys()):
        seen = set()
        uniq = []
        for it in buckets[k]:
            if it.url in seen:
                continue
            seen.add(it.url)
            uniq.append(it)
        buckets[k] = uniq

    return buckets


def build_script(items: Dict[str, List[Item]]) -> str:
    ref = now_local()

    # Critical Changes: only if published within 24h (RSS). Otherwise say none.
    critical_recent = [it for it in items.get("critical_changes", []) if within_24h(it, ref)]

    lines: List[str] = []
    lines.append(f"Morning Intelligence Report — {ref.strftime('%A %d %b %Y, %H:%M')} (ET)")
    lines.append("")

    lines.append("1. Critical Changes")
    if not critical_recent:
        lines.append("Sin cambios críticos hoy.")
    else:
        for it in critical_recent[:8]:
            lines.append(f"- {it.source}: {it.title}")
    lines.append("")

    lines.append("2. Strategic AI News")
    strategic = items.get("strategic_ai", [])
    if not strategic:
        lines.append("- (sin items hoy)")
    else:
        for it in strategic[:5]:
            lines.append(f"- {it.source}: {it.title}")
    lines.append("")

    lines.append("3. Macro & Finanzas")
    macro = items.get("macro_finance", [])
    if not macro:
        lines.append("- (sin items hoy)")
    else:
        for it in macro[:5]:
            lines.append(f"- {it.source}: {it.title}")
    lines.append("")

    lines.append("4. Oportunidades / Tools (MWF)")
    opp = items.get("opportunities", [])
    if not opp:
        lines.append("- (no aplica hoy)")
    else:
        for it in opp[:5]:
            lines.append(f"- {it.source}: {it.title}")
    lines.append("")

    lines.append("5. Weekly (Mondays)")
    wk = items.get("other_weekly", [])
    if not wk:
        lines.append("- (no aplica hoy)")
    else:
        for it in wk[:6]:
            lines.append(f"- {it.source}: {it.title}")

    # Keep it short for audio
    script = "\n".join(lines)
    return script[:6000]


def main() -> int:
    cfg = load_config()
    items = collect_items(cfg)
    script = build_script(items)

    out_txt = OUT_DIR / f"morning_report_{now_local().strftime('%Y%m%d_%H%M')}.txt"
    out_txt.write_text(script, encoding="utf-8")

    # Print script to stdout for the caller to send via OpenClaw
    print(script)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
