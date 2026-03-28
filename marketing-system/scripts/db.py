"""
Marketing System DB Wrapper v2.1
PostgreSQL abstraction layer for schema marketing.*
"""

import json
from contextlib import contextmanager
from datetime import date, datetime, timedelta

import psycopg2
import psycopg2.extras

DATABASE_URL = "postgresql://litellm:litellm-local-2026@localhost:5432/litellm_db"

psycopg2.extras.register_default_jsonb(globally=True, loads=json.loads)


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def close_conn(conn):
    if conn and not conn.closed:
        conn.close()


@contextmanager
def _cursor():
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        cur.close()
    finally:
        close_conn(conn)


def _one(cur):
    row = cur.fetchone()
    return dict(row) if row else None


def _all(cur):
    return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def upsert_project(project_id, project_name, project_type, **kw):
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.projects (project_id, project_name, project_type, description, website_url, config)
            VALUES (%(project_id)s, %(project_name)s, %(project_type)s, %(description)s, %(website_url)s, %(config)s)
            ON CONFLICT (project_id) DO UPDATE SET
                project_name = EXCLUDED.project_name,
                project_type = EXCLUDED.project_type,
                description  = COALESCE(EXCLUDED.description, marketing.projects.description),
                website_url  = COALESCE(EXCLUDED.website_url, marketing.projects.website_url),
                config       = COALESCE(EXCLUDED.config, marketing.projects.config),
                updated_at   = now()
            RETURNING *
        """, dict(project_id=project_id, project_name=project_name, project_type=project_type,
                  description=kw.get('description'), website_url=kw.get('website_url'),
                  config=json.dumps(kw.get('config', {}))))
        return _one(cur)


def get_project(project_id):
    with _cursor() as cur:
        cur.execute("SELECT * FROM marketing.projects WHERE project_id = %s", (project_id,))
        return _one(cur)


# ---------------------------------------------------------------------------
# Strategy Versions
# ---------------------------------------------------------------------------

def create_strategy_version(project_id, version, **kw):
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.strategy_versions (project_id, version, status, description)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (project_id, version) DO UPDATE SET updated_at = now()
            RETURNING *
        """, (project_id, version, kw.get('status', 'draft'), kw.get('description')))
        return _one(cur)


def get_strategy_version(project_id, version):
    with _cursor() as cur:
        cur.execute("SELECT * FROM marketing.strategy_versions WHERE project_id = %s AND version = %s",
                    (project_id, version))
        return _one(cur)


def approve_strategy_version(project_id, version):
    with _cursor() as cur:
        cur.execute("""
            UPDATE marketing.strategy_versions SET status = 'approved', approved_at = now(), updated_at = now()
            WHERE project_id = %s AND version = %s RETURNING *
        """, (project_id, version))
        return _one(cur)


def get_active_strategy(project_id):
    with _cursor() as cur:
        cur.execute("""
            SELECT * FROM marketing.strategy_versions
            WHERE project_id = %s AND status = 'approved'
            ORDER BY version DESC LIMIT 1
        """, (project_id,))
        return _one(cur)


# ---------------------------------------------------------------------------
# Strategy Outputs
# ---------------------------------------------------------------------------

def save_strategy_output(project_id, version, output_type, data, **kw):
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.strategy_outputs (project_id, version, output_type, title, data)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (project_id, version, output_type) DO UPDATE SET
                data = EXCLUDED.data, title = COALESCE(EXCLUDED.title, marketing.strategy_outputs.title),
                updated_at = now()
            RETURNING id
        """, (project_id, version, output_type, kw.get('title'), json.dumps(data)))
        return _one(cur)['id']


def get_strategy_output(project_id, version, output_type):
    with _cursor() as cur:
        cur.execute("""
            SELECT * FROM marketing.strategy_outputs
            WHERE project_id = %s AND version = %s AND output_type = %s
        """, (project_id, version, output_type))
        return _one(cur)


def get_all_strategy_outputs(project_id, version):
    with _cursor() as cur:
        cur.execute("SELECT * FROM marketing.strategy_outputs WHERE project_id = %s AND version = %s",
                    (project_id, version))
        return _all(cur)


# ---------------------------------------------------------------------------
# Buyer Segments
# ---------------------------------------------------------------------------

def upsert_buyer_segment(project_id, segment_id, segment_name, priority, use_case, profile, **kw):
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.buyer_segments
                (project_id, segment_id, version, segment_name, priority, use_case, profile, pain_points, messaging)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (project_id, segment_id) DO UPDATE SET
                segment_name = EXCLUDED.segment_name,
                priority     = EXCLUDED.priority,
                use_case     = EXCLUDED.use_case,
                profile      = EXCLUDED.profile,
                pain_points  = COALESCE(EXCLUDED.pain_points, marketing.buyer_segments.pain_points),
                messaging    = COALESCE(EXCLUDED.messaging, marketing.buyer_segments.messaging),
                version      = EXCLUDED.version,
                updated_at   = now()
            RETURNING id
        """, (project_id, segment_id, kw.get('version', 1), segment_name, priority, use_case,
              json.dumps(profile) if isinstance(profile, dict) else profile,
              json.dumps(kw.get('pain_points', [])),
              json.dumps(kw.get('messaging', {}))))
        return _one(cur)['id']


def get_buyer_segments(project_id, priority=None):
    with _cursor() as cur:
        if priority:
            cur.execute("SELECT * FROM marketing.buyer_segments WHERE project_id = %s AND priority = %s",
                        (project_id, priority))
        else:
            cur.execute("SELECT * FROM marketing.buyer_segments WHERE project_id = %s", (project_id,))
        return _all(cur)


def get_segment(project_id, segment_id):
    with _cursor() as cur:
        cur.execute("SELECT * FROM marketing.buyer_segments WHERE project_id = %s AND segment_id = %s",
                    (project_id, segment_id))
        return _one(cur)


# ---------------------------------------------------------------------------
# Product Catalog
# ---------------------------------------------------------------------------

def upsert_product(project_id, sku, product_name, price, **kw):
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.product_catalog
                (project_id, sku, product_name, price, description, currency, status, category, variants, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (project_id, sku) DO UPDATE SET
                product_name = EXCLUDED.product_name, price = EXCLUDED.price,
                description = COALESCE(EXCLUDED.description, marketing.product_catalog.description),
                status = COALESCE(EXCLUDED.status, marketing.product_catalog.status),
                category = COALESCE(EXCLUDED.category, marketing.product_catalog.category),
                variants = COALESCE(EXCLUDED.variants, marketing.product_catalog.variants),
                metadata = COALESCE(EXCLUDED.metadata, marketing.product_catalog.metadata),
                updated_at = now()
            RETURNING id
        """, (project_id, sku, product_name, price,
              kw.get('description'), kw.get('currency', 'USD'), kw.get('status', 'active'),
              kw.get('category'), json.dumps(kw.get('variants', [])), json.dumps(kw.get('metadata', {}))))
        return _one(cur)['id']


def get_products(project_id, status='active'):
    with _cursor() as cur:
        cur.execute("SELECT * FROM marketing.product_catalog WHERE project_id = %s AND status = %s",
                    (project_id, status))
        return _all(cur)


def get_product_by_sku(project_id, sku):
    with _cursor() as cur:
        cur.execute("SELECT * FROM marketing.product_catalog WHERE project_id = %s AND sku = %s",
                    (project_id, sku))
        return _one(cur)


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

def create_campaign(project_id, campaign_id, campaign_name, campaign_type, **kw):
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.campaigns
                (project_id, campaign_id, campaign_name, campaign_type, status, start_date, end_date, budget, goals, config)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (project_id, campaign_id) DO UPDATE SET
                campaign_name = EXCLUDED.campaign_name, campaign_type = EXCLUDED.campaign_type,
                status = COALESCE(EXCLUDED.status, marketing.campaigns.status),
                budget = COALESCE(EXCLUDED.budget, marketing.campaigns.budget),
                goals  = COALESCE(EXCLUDED.goals, marketing.campaigns.goals),
                updated_at = now()
            RETURNING id
        """, (project_id, campaign_id, campaign_name, campaign_type,
              kw.get('status', 'planned'), kw.get('start_date'), kw.get('end_date'),
              json.dumps(kw.get('budget', {})), json.dumps(kw.get('goals', {})),
              json.dumps(kw.get('config', {}))))
        return _one(cur)['id']


def get_campaign(project_id, campaign_id):
    with _cursor() as cur:
        cur.execute("SELECT * FROM marketing.campaigns WHERE project_id = %s AND campaign_id = %s",
                    (project_id, campaign_id))
        return _one(cur)


def get_active_campaigns(project_id):
    with _cursor() as cur:
        cur.execute("SELECT * FROM marketing.campaigns WHERE project_id = %s AND status = 'active'",
                    (project_id,))
        return _all(cur)


def update_campaign_status(project_id, campaign_id, status):
    with _cursor() as cur:
        cur.execute("""
            UPDATE marketing.campaigns SET status = %s, updated_at = now()
            WHERE project_id = %s AND campaign_id = %s
        """, (status, project_id, campaign_id))


def add_campaign_product(campaign_id, product_id):
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.campaign_products (campaign_id, product_id) VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (campaign_id, product_id))


def add_campaign_segment(campaign_id, buyer_segment_id):
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.campaign_target_segments (campaign_id, buyer_segment_id) VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (campaign_id, buyer_segment_id))


# ---------------------------------------------------------------------------
# Campaign Runs
# ---------------------------------------------------------------------------

def create_run(campaign_id, project_id, week_start_date, **kw):
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.campaign_runs (campaign_id, project_id, week_start_date, status, theme, config)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (campaign_id, week_start_date) DO UPDATE SET
                status = COALESCE(EXCLUDED.status, marketing.campaign_runs.status),
                theme  = COALESCE(EXCLUDED.theme, marketing.campaign_runs.theme),
                updated_at = now()
            RETURNING id
        """, (campaign_id, project_id, week_start_date,
              kw.get('status', 'planned'), kw.get('theme'), json.dumps(kw.get('config', {}))))
        return _one(cur)['id']


def get_run(campaign_id, week_start_date):
    with _cursor() as cur:
        cur.execute("SELECT * FROM marketing.campaign_runs WHERE campaign_id = %s AND week_start_date = %s",
                    (campaign_id, week_start_date))
        return _one(cur)


def update_run_status(run_id, status):
    with _cursor() as cur:
        cur.execute("UPDATE marketing.campaign_runs SET status = %s, updated_at = now() WHERE id = %s",
                    (status, run_id))


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

def save_asset(run_id, project_id, campaign_id, creative_id, asset_type, content, **kw):
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.assets
                (run_id, project_id, campaign_id, creative_id, asset_type, platform, persona_id,
                 title, content, status, angle_id, hook_type, week_start_date, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (creative_id) DO UPDATE SET
                content    = EXCLUDED.content,
                status     = COALESCE(EXCLUDED.status, marketing.assets.status),
                metadata   = COALESCE(EXCLUDED.metadata, marketing.assets.metadata),
                updated_at = now()
            RETURNING id
        """, (run_id, project_id, campaign_id, creative_id, asset_type,
              kw.get('platform'), kw.get('persona_id'), kw.get('title'),
              json.dumps(content) if isinstance(content, dict) else content,
              kw.get('status', 'draft'), kw.get('angle_id'), kw.get('hook_type'),
              kw.get('week_start_date'), json.dumps(kw.get('metadata', {}))))
        return _one(cur)['id']


def get_assets(project_id, week_start_date=None, asset_type=None, persona_id=None):
    with _cursor() as cur:
        q = "SELECT * FROM marketing.assets WHERE project_id = %s"
        params = [project_id]
        if week_start_date:
            q += " AND week_start_date = %s"; params.append(week_start_date)
        if asset_type:
            q += " AND asset_type = %s"; params.append(asset_type)
        if persona_id:
            q += " AND persona_id = %s"; params.append(persona_id)
        q += " ORDER BY created_at DESC"
        cur.execute(q, params)
        return _all(cur)


def get_asset_by_creative_id(creative_id):
    with _cursor() as cur:
        cur.execute("SELECT * FROM marketing.assets WHERE creative_id = %s", (creative_id,))
        return _one(cur)


def update_asset_status(asset_id, status):
    with _cursor() as cur:
        cur.execute("UPDATE marketing.assets SET status = %s, updated_at = now() WHERE id = %s",
                    (status, asset_id))


# ---------------------------------------------------------------------------
# Asset Metrics
# ---------------------------------------------------------------------------

def save_asset_metrics(asset_id, platform, week_start_date, metrics_dict, **kw):
    m = metrics_dict
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.asset_metrics_base
                (asset_id, platform, week_start_date, impressions, reach, clicks, ctr, spend,
                 cpc, cpm, conversions, revenue, roas, engagement_rate, metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (idempotency_key)
            DO UPDATE SET
                impressions = EXCLUDED.impressions, reach = EXCLUDED.reach, clicks = EXCLUDED.clicks,
                ctr = EXCLUDED.ctr, spend = EXCLUDED.spend, cpc = EXCLUDED.cpc, cpm = EXCLUDED.cpm,
                conversions = EXCLUDED.conversions, revenue = EXCLUDED.revenue, roas = EXCLUDED.roas,
                engagement_rate = EXCLUDED.engagement_rate, updated_at = now()
            RETURNING id
        """, (asset_id, platform, week_start_date,
              m.get('impressions', 0), m.get('reach', 0), m.get('clicks', 0), m.get('ctr', 0),
              m.get('spend', 0), m.get('cpc', 0), m.get('cpm', 0), m.get('conversions', 0),
              m.get('revenue', 0), m.get('roas', 0), m.get('engagement_rate', 0),
              json.dumps(kw.get('metadata', {}))))
        return _one(cur)['id']


def save_video_metrics(metrics_base_id, video_metrics_dict):
    m = video_metrics_dict
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.asset_metrics_video
                (metrics_base_id, views, watch_time_sec, avg_watch_pct, likes, comments, shares, saves,
                 hook_rate_3s, retention_15s, retention_30s)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (metrics_base_id) DO UPDATE SET
                views = EXCLUDED.views, watch_time_sec = EXCLUDED.watch_time_sec,
                avg_watch_pct = EXCLUDED.avg_watch_pct, likes = EXCLUDED.likes,
                comments = EXCLUDED.comments, shares = EXCLUDED.shares, saves = EXCLUDED.saves,
                hook_rate_3s = EXCLUDED.hook_rate_3s, retention_15s = EXCLUDED.retention_15s,
                retention_30s = EXCLUDED.retention_30s
        """, (metrics_base_id, m.get('views', 0), m.get('watch_time_sec', 0), m.get('avg_watch_pct', 0),
              m.get('likes', 0), m.get('comments', 0), m.get('shares', 0), m.get('saves', 0),
              m.get('hook_rate_3s', 0), m.get('retention_15s', 0), m.get('retention_30s', 0)))


def save_email_metrics(metrics_base_id, email_metrics_dict):
    m = email_metrics_dict
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.asset_metrics_email
                (metrics_base_id, sent, delivered, opens, unique_opens, open_rate, click_rate,
                 unsubscribes, bounces, spam_reports)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (metrics_base_id) DO UPDATE SET
                sent = EXCLUDED.sent, delivered = EXCLUDED.delivered, opens = EXCLUDED.opens,
                unique_opens = EXCLUDED.unique_opens, open_rate = EXCLUDED.open_rate,
                click_rate = EXCLUDED.click_rate, unsubscribes = EXCLUDED.unsubscribes,
                bounces = EXCLUDED.bounces, spam_reports = EXCLUDED.spam_reports
        """, (metrics_base_id, m.get('sent', 0), m.get('delivered', 0), m.get('opens', 0),
              m.get('unique_opens', 0), m.get('open_rate', 0), m.get('click_rate', 0),
              m.get('unsubscribes', 0), m.get('bounces', 0), m.get('spam_reports', 0)))


def get_asset_metrics(asset_id):
    with _cursor() as cur:
        cur.execute("SELECT * FROM marketing.asset_metrics_base WHERE asset_id = %s ORDER BY week_start_date",
                    (asset_id,))
        return _all(cur)


def get_metrics_by_persona(project_id, persona_id, last_n_weeks=8):
    with _cursor() as cur:
        cur.execute("""
            SELECT m.* FROM marketing.asset_metrics_base m
            JOIN marketing.assets a ON a.id = m.asset_id
            WHERE a.project_id = %s AND a.persona_id = %s
              AND m.week_start_date >= CURRENT_DATE - INTERVAL '%s weeks'
            ORDER BY m.week_start_date DESC
        """, (project_id, persona_id, last_n_weeks))
        return _all(cur)


# ---------------------------------------------------------------------------
# Platform Metrics
# ---------------------------------------------------------------------------

def save_platform_metrics(project_id, campaign_id, week_start_date, platform, metrics_dict):
    m = metrics_dict
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.platform_metrics_weekly
                (project_id, campaign_id, platform, week_start_date, impressions, reach, clicks,
                 spend, conversions, revenue, roas, followers_gained, engagement_rate, metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (idempotency_key)
            DO UPDATE SET
                impressions = EXCLUDED.impressions, reach = EXCLUDED.reach, clicks = EXCLUDED.clicks,
                spend = EXCLUDED.spend, conversions = EXCLUDED.conversions, revenue = EXCLUDED.revenue,
                roas = EXCLUDED.roas, followers_gained = EXCLUDED.followers_gained,
                engagement_rate = EXCLUDED.engagement_rate, updated_at = now()
            RETURNING id
        """, (project_id, campaign_id, platform, week_start_date,
              m.get('impressions', 0), m.get('reach', 0), m.get('clicks', 0),
              m.get('spend', 0), m.get('conversions', 0), m.get('revenue', 0),
              m.get('roas', 0), m.get('followers_gained', 0), m.get('engagement_rate', 0),
              json.dumps(m.get('metadata', {}))))
        return _one(cur)['id']


def get_platform_metrics(project_id, last_n_weeks=8):
    with _cursor() as cur:
        cur.execute("""
            SELECT * FROM marketing.platform_metrics_weekly
            WHERE project_id = %s AND week_start_date >= CURRENT_DATE - INTERVAL '%s weeks'
            ORDER BY week_start_date DESC, platform
        """, (project_id, last_n_weeks))
        return _all(cur)


# ---------------------------------------------------------------------------
# SEO Metrics
# ---------------------------------------------------------------------------

def save_seo_metrics(project_id, url, date_val, metrics_dict):
    m = metrics_dict
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.seo_metrics
                (project_id, url, date, query, impressions, clicks, ctr, avg_position, metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (idempotency_key)
            DO UPDATE SET
                impressions = EXCLUDED.impressions, clicks = EXCLUDED.clicks,
                ctr = EXCLUDED.ctr, avg_position = EXCLUDED.avg_position
            RETURNING id
        """, (project_id, url, date_val, m.get('query'),
              m.get('impressions', 0), m.get('clicks', 0), m.get('ctr', 0),
              m.get('avg_position'), json.dumps(m.get('metadata', {}))))
        return _one(cur)['id']


def get_seo_metrics(project_id, url=None, last_n_days=30):
    with _cursor() as cur:
        q = "SELECT * FROM marketing.seo_metrics WHERE project_id = %s AND date >= CURRENT_DATE - INTERVAL '%s days'"
        params = [project_id, last_n_days]
        if url:
            q += " AND url = %s"; params.append(url)
        q += " ORDER BY date DESC"
        cur.execute(q, params)
        return _all(cur)


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

def save_order(project_id, order_dict):
    o = order_dict
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.orders
                (project_id, order_id, stripe_payment_id, customer_email, amount, currency, status,
                 source_platform, source_campaign, utm_source, utm_medium, utm_campaign, utm_content, items, order_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (idempotency_key) DO UPDATE SET
                status = EXCLUDED.status, amount = EXCLUDED.amount
            RETURNING id
        """, (project_id, o['order_id'], o.get('stripe_payment_id'), o.get('customer_email'),
              o['amount'], o.get('currency', 'USD'), o.get('status', 'completed'),
              o.get('source_platform'), o.get('source_campaign'),
              o.get('utm_source'), o.get('utm_medium'), o.get('utm_campaign'), o.get('utm_content'),
              json.dumps(o.get('items', [])), o.get('order_date', datetime.now())))
        return _one(cur)['id']


def get_orders(project_id, last_n_days=30):
    with _cursor() as cur:
        cur.execute("""
            SELECT * FROM marketing.orders
            WHERE project_id = %s AND order_date >= now() - INTERVAL '%s days'
            ORDER BY order_date DESC
        """, (project_id, last_n_days))
        return _all(cur)


# ---------------------------------------------------------------------------
# Conversion Events
# ---------------------------------------------------------------------------

def save_conversion_event(project_id, event_dict):
    e = event_dict
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.conversion_events
                (project_id, event_type, event_date, source_platform, source_campaign,
                 customer_id, value, currency, idempotency_key, metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (project_id, idempotency_key) DO UPDATE SET
                value = EXCLUDED.value, metadata = EXCLUDED.metadata
            RETURNING id
        """, (project_id, e['event_type'], e.get('event_date', datetime.now()),
              e.get('source_platform'), e.get('source_campaign'),
              e.get('customer_id'), e.get('value'), e.get('currency', 'USD'),
              e['idempotency_key'], json.dumps(e.get('metadata', {}))))
        return _one(cur)['id']


def get_conversion_events(project_id, event_type=None, last_n_days=30):
    with _cursor() as cur:
        q = "SELECT * FROM marketing.conversion_events WHERE project_id = %s AND event_date >= now() - INTERVAL '%s days'"
        params = [project_id, last_n_days]
        if event_type:
            q += " AND event_type = %s"; params.append(event_type)
        q += " ORDER BY event_date DESC"
        cur.execute(q, params)
        return _all(cur)


# ---------------------------------------------------------------------------
# Growth Analyses
# ---------------------------------------------------------------------------

def save_growth_analysis(project_id, campaign_id, week_start_date, results_dict, **kw):
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.growth_analyses
                (project_id, campaign_id, week_start_date, analysis_type, results, recommendations)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (idempotency_key)
            DO UPDATE SET results = EXCLUDED.results, recommendations = EXCLUDED.recommendations
            RETURNING id
        """, (project_id, campaign_id, week_start_date,
              kw.get('analysis_type', 'weekly_review'),
              json.dumps(results_dict), json.dumps(kw.get('recommendations', []))))
        return _one(cur)['id']


def get_growth_history(project_id, last_n_weeks=8):
    with _cursor() as cur:
        cur.execute("""
            SELECT * FROM marketing.growth_analyses
            WHERE project_id = %s AND week_start_date >= CURRENT_DATE - INTERVAL '%s weeks'
            ORDER BY week_start_date DESC
        """, (project_id, last_n_weeks))
        return _all(cur)


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

def save_decision(project_id, week_start_date, decision_dict):
    d = decision_dict
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.decisions
                (project_id, week_start_date, decision_type, target_type, target_id, rationale, impact, decided_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (project_id, week_start_date, d['decision_type'],
              d.get('target_type'), d.get('target_id'), d.get('rationale'),
              json.dumps(d.get('impact', {})), d.get('decided_by', 'system')))
        return _one(cur)['id']


def get_decisions(project_id, last_n_weeks=8):
    with _cursor() as cur:
        cur.execute("""
            SELECT * FROM marketing.decisions
            WHERE project_id = %s AND week_start_date >= CURRENT_DATE - INTERVAL '%s weeks'
            ORDER BY week_start_date DESC
        """, (project_id, last_n_weeks))
        return _all(cur)


# ---------------------------------------------------------------------------
# Knowledge Base
# ---------------------------------------------------------------------------

def add_kb_entry(project_id, entry_dict):
    e = entry_dict
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.knowledge_base
                (project_id, pattern_id, category, title, description, evidence, status, confidence, metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (project_id, pattern_id) DO UPDATE SET
                title = EXCLUDED.title, description = EXCLUDED.description,
                evidence = EXCLUDED.evidence, confidence = EXCLUDED.confidence,
                status = EXCLUDED.status, updated_at = now()
            RETURNING id
        """, (project_id, e['pattern_id'], e.get('category'), e['title'],
              e.get('description'), json.dumps(e.get('evidence', [])),
              e.get('status', 'active'), e.get('confidence', 0.5),
              json.dumps(e.get('metadata', {}))))
        return _one(cur)['id']


def get_kb(project_id, status=None):
    with _cursor() as cur:
        if status:
            cur.execute("SELECT * FROM marketing.knowledge_base WHERE project_id = %s AND status = %s ORDER BY confidence DESC",
                        (project_id, status))
        else:
            cur.execute("SELECT * FROM marketing.knowledge_base WHERE project_id = %s ORDER BY confidence DESC",
                        (project_id,))
        return _all(cur)


def update_kb_status(project_id, pattern_id, status):
    with _cursor() as cur:
        cur.execute("""
            UPDATE marketing.knowledge_base SET status = %s, updated_at = now()
            WHERE project_id = %s AND pattern_id = %s
        """, (status, project_id, pattern_id))


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------

def save_experiment(project_id, experiment_dict):
    e = experiment_dict
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.experiments
                (project_id, experiment_id, experiment_name, hypothesis, status,
                 start_date, end_date, variants, results, conclusion, metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (project_id, experiment_id) DO UPDATE SET
                experiment_name = EXCLUDED.experiment_name, hypothesis = EXCLUDED.hypothesis,
                status = EXCLUDED.status, results = EXCLUDED.results,
                conclusion = EXCLUDED.conclusion, updated_at = now()
            RETURNING id
        """, (project_id, e['experiment_id'], e['experiment_name'],
              e.get('hypothesis'), e.get('status', 'planned'),
              e.get('start_date'), e.get('end_date'),
              json.dumps(e.get('variants', [])), json.dumps(e.get('results', {})),
              e.get('conclusion'), json.dumps(e.get('metadata', {}))))
        return _one(cur)['id']


def get_experiments(project_id, status=None):
    with _cursor() as cur:
        if status:
            cur.execute("SELECT * FROM marketing.experiments WHERE project_id = %s AND status = %s ORDER BY created_at DESC",
                        (project_id, status))
        else:
            cur.execute("SELECT * FROM marketing.experiments WHERE project_id = %s ORDER BY created_at DESC",
                        (project_id,))
        return _all(cur)


def update_experiment(project_id, experiment_id, updates):
    allowed = {'status', 'results', 'conclusion', 'end_date', 'variants'}
    sets, vals = [], []
    for k, v in updates.items():
        if k not in allowed:
            continue
        if k in ('results', 'variants'):
            v = json.dumps(v)
        sets.append(f"{k} = %s")
        vals.append(v)
    if not sets:
        return
    sets.append("updated_at = now()")
    vals.extend([project_id, experiment_id])
    with _cursor() as cur:
        cur.execute(f"UPDATE marketing.experiments SET {', '.join(sets)} WHERE project_id = %s AND experiment_id = %s",
                    vals)


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

def log_gate(project_id, gate_type, status, **kw):
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO marketing.gates (project_id, gate_type, status, context, decided_by, decided_at, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (project_id, gate_type, status,
              json.dumps(kw.get('context', {})), kw.get('decided_by'),
              kw.get('decided_at'), kw.get('notes')))
        return _one(cur)['id']


# ---------------------------------------------------------------------------
# Analytics Queries
# ---------------------------------------------------------------------------

def best_performing_assets(project_id, metric='ctr', persona_id=None, last_n_weeks=8):
    valid_metrics = {'ctr', 'roas', 'engagement_rate', 'conversions', 'clicks', 'impressions', 'revenue'}
    if metric not in valid_metrics:
        metric = 'ctr'
    with _cursor() as cur:
        q = f"""
            SELECT a.creative_id, a.asset_type, a.platform, a.title, a.angle_id,
                   AVG(m.{metric}) as avg_metric, COUNT(m.id) as data_points
            FROM marketing.assets a
            JOIN marketing.asset_metrics_base m ON m.asset_id = a.id
            WHERE a.project_id = %s AND m.week_start_date >= CURRENT_DATE - INTERVAL '%s weeks'
        """
        params = [project_id, last_n_weeks]
        if persona_id:
            q += " AND a.persona_id = %s"; params.append(persona_id)
        q += f" GROUP BY a.creative_id, a.asset_type, a.platform, a.title, a.angle_id ORDER BY avg_metric DESC LIMIT 20"
        cur.execute(q, params)
        return _all(cur)


def creative_decay_check(project_id, angle_id=None):
    with _cursor() as cur:
        q = """
            SELECT a.creative_id, a.angle_id, a.asset_type,
                   m.week_start_date, m.ctr, m.engagement_rate, m.roas
            FROM marketing.assets a
            JOIN marketing.asset_metrics_base m ON m.asset_id = a.id
            WHERE a.project_id = %s AND m.week_start_date >= CURRENT_DATE - INTERVAL '8 weeks'
        """
        params = [project_id]
        if angle_id:
            q += " AND a.angle_id = %s"; params.append(angle_id)
        q += " ORDER BY a.creative_id, m.week_start_date"
        cur.execute(q, params)
        return _all(cur)


def segment_performance(project_id, last_n_weeks=4):
    with _cursor() as cur:
        cur.execute("""
            SELECT bs.segment_id, bs.segment_name, bs.priority,
                   AVG(m.ctr) as avg_ctr, AVG(m.roas) as avg_roas,
                   SUM(m.spend) as total_spend, SUM(m.revenue) as total_revenue,
                   COUNT(DISTINCT a.id) as asset_count
            FROM marketing.buyer_segments bs
            JOIN marketing.assets a ON a.persona_id = bs.id
            JOIN marketing.asset_metrics_base m ON m.asset_id = a.id
            WHERE bs.project_id = %s AND m.week_start_date >= CURRENT_DATE - INTERVAL '%s weeks'
            GROUP BY bs.segment_id, bs.segment_name, bs.priority
            ORDER BY avg_roas DESC
        """, (project_id, last_n_weeks))
        return _all(cur)


def campaign_roi(project_id, campaign_id=None):
    with _cursor() as cur:
        q = """
            SELECT c.campaign_id, c.campaign_name, c.campaign_type,
                   SUM(pm.spend) as total_spend, SUM(pm.revenue) as total_revenue,
                   CASE WHEN SUM(pm.spend) > 0 THEN SUM(pm.revenue) / SUM(pm.spend) ELSE 0 END as roi,
                   SUM(pm.conversions) as total_conversions
            FROM marketing.campaigns c
            JOIN marketing.platform_metrics_weekly pm ON pm.campaign_id = c.id
            WHERE c.project_id = %s
        """
        params = [project_id]
        if campaign_id:
            q += " AND c.campaign_id = %s"; params.append(campaign_id)
        q += " GROUP BY c.campaign_id, c.campaign_name, c.campaign_type ORDER BY roi DESC"
        cur.execute(q, params)
        return _all(cur)


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== db.py smoke test ===\n")

    # 1. Insert project
    p = upsert_project("test-smoke", "Smoke Test Project", "digital_experience",
                       description="Testing db.py wrapper")
    print(f"[OK] upsert_project: {p['project_id']} — {p['project_name']}")

    # 2. Strategy version
    sv = create_strategy_version("test-smoke", 1, description="Baseline strategy")
    print(f"[OK] create_strategy_version: v{sv['version']} status={sv['status']}")

    # 3. Strategy output
    so_id = save_strategy_output("test-smoke", 1, "market_analysis",
                                 {"competitors": ["A", "B"], "tam": 50000},
                                 title="Market Analysis v1")
    print(f"[OK] save_strategy_output: id={so_id}")

    so = get_strategy_output("test-smoke", 1, "market_analysis")
    print(f"[OK] get_strategy_output: title={so['title']}, data keys={list(so['data'].keys())}")

    # 4. Buyer segment
    bs_id = upsert_buyer_segment("test-smoke", "mystery-lover", "Mystery Lover",
                                 "primary", "Weekly mystery kits", {"age": "25-45"}, version=1)
    print(f"[OK] upsert_buyer_segment: id={bs_id}")

    # 5. Knowledge base
    kb_id = add_kb_entry("test-smoke", {
        "pattern_id": "hook-curiosity-gap",
        "category": "content",
        "title": "Curiosity gap hooks outperform direct hooks",
        "description": "3s hook rate 2x higher with open loops",
        "confidence": 0.85
    })
    print(f"[OK] add_kb_entry: id={kb_id}")

    # 6. Experiment
    exp_id = save_experiment("test-smoke", {
        "experiment_id": "exp-hook-types-001",
        "experiment_name": "Hook type A/B test",
        "hypothesis": "Curiosity hooks > direct hooks for CTR"
    })
    print(f"[OK] save_experiment: id={exp_id}")

    # 7. Gate
    gate_id = log_gate("test-smoke", "strategy_approval", "approved",
                       decided_by="robotin", notes="Smoke test gate")
    print(f"[OK] log_gate: id={gate_id}")

    # 8. Read back
    segs = get_buyer_segments("test-smoke")
    print(f"[OK] get_buyer_segments: {len(segs)} segment(s)")

    kb = get_kb("test-smoke")
    print(f"[OK] get_kb: {len(kb)} entries")

    exps = get_experiments("test-smoke")
    print(f"[OK] get_experiments: {len(exps)} experiments")

    # 9. Cleanup test data
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM marketing.gates WHERE project_id = 'test-smoke'")
    cur.execute("DELETE FROM marketing.experiments WHERE project_id = 'test-smoke'")
    cur.execute("DELETE FROM marketing.knowledge_base WHERE project_id = 'test-smoke'")
    cur.execute("DELETE FROM marketing.buyer_segments WHERE project_id = 'test-smoke'")
    cur.execute("DELETE FROM marketing.strategy_outputs WHERE project_id = 'test-smoke'")
    cur.execute("DELETE FROM marketing.strategy_versions WHERE project_id = 'test-smoke'")
    cur.execute("DELETE FROM marketing.projects WHERE project_id = 'test-smoke'")
    cur.close()
    close_conn(conn)
    print("\n[OK] Cleanup done — test data removed")
    print("\n=== All smoke tests passed ===")
