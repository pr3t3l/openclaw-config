-- =============================================================================
-- Marketing System Schema v2.1
-- Created: 2026-03-28
-- Database: litellm_db | Schema: marketing
-- =============================================================================

BEGIN;

-- Schema
CREATE SCHEMA IF NOT EXISTS marketing;

-- =============================================================================
-- Helper function: iso_week_text(DATE) → '2026-W13'
-- =============================================================================
CREATE OR REPLACE FUNCTION marketing.iso_week_text(d DATE)
RETURNS TEXT
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT TO_CHAR(d, 'IYYY') || '-W' || LPAD(TO_CHAR(d, 'IW'), 2, '0');
$$;

-- Helper: immutable date → text (ISO format, locale-independent)
CREATE OR REPLACE FUNCTION marketing.date_text(d DATE)
RETURNS TEXT
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT TO_CHAR(d, 'YYYY-MM-DD');
$$;

-- Helper: immutable int → text
CREATE OR REPLACE FUNCTION marketing.int_text(i INT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT i::TEXT;
$$;

-- =============================================================================
-- 1. projects — top-level business/brand
-- =============================================================================
CREATE TABLE marketing.projects (
    project_id   TEXT PRIMARY KEY,
    project_name TEXT NOT NULL,
    project_type TEXT NOT NULL CHECK (project_type IN ('digital_experience', 'physical_product', 'food', 'service')),
    description  TEXT,
    website_url  TEXT,
    config       JSONB DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 2. strategy_versions — versioned strategies per project
-- =============================================================================
CREATE TABLE marketing.strategy_versions (
    project_id  TEXT NOT NULL REFERENCES marketing.projects(project_id),
    version     INT  NOT NULL,
    status      TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'generating', 'awaiting_approval', 'approved', 'invalid', 'archived', 'superseded')),
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, version)
);

-- =============================================================================
-- 3. product_catalog — items with JSONB variants
-- =============================================================================
CREATE TABLE marketing.product_catalog (
    id          SERIAL PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES marketing.projects(project_id),
    sku         TEXT NOT NULL,
    product_name TEXT NOT NULL,
    description TEXT,
    price       NUMERIC(10,2),
    currency    TEXT DEFAULT 'USD',
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'draft', 'archived', 'seasonal')),
    category    TEXT,
    variants    JSONB DEFAULT '[]',
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, sku)
);

-- =============================================================================
-- 4. strategy_outputs — one row per artifact, FK to strategy_versions
-- =============================================================================
CREATE TABLE marketing.strategy_outputs (
    id          SERIAL PRIMARY KEY,
    project_id  TEXT NOT NULL,
    version     INT  NOT NULL,
    output_type TEXT NOT NULL CHECK (output_type IN ('market_analysis', 'buyer_persona', 'brand_strategy', 'seo_architecture', 'channel_strategy', 'strategy_report')),
    title       TEXT,
    data        JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (project_id, version) REFERENCES marketing.strategy_versions(project_id, version),
    UNIQUE (project_id, version, output_type)
);

-- =============================================================================
-- 5. buyer_segments — reusable segments, FK to strategy_versions
-- =============================================================================
CREATE TABLE marketing.buyer_segments (
    id           SERIAL PRIMARY KEY,
    project_id   TEXT NOT NULL,
    segment_id   TEXT NOT NULL,
    version      INT  NOT NULL,
    segment_name TEXT NOT NULL,
    priority     TEXT CHECK (priority IN ('primary', 'secondary', 'tertiary', 'exploratory')),
    use_case     TEXT,
    profile      JSONB DEFAULT '{}',
    pain_points  JSONB DEFAULT '[]',
    messaging    JSONB DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (project_id, version) REFERENCES marketing.strategy_versions(project_id, version),
    UNIQUE (project_id, segment_id)
);

-- =============================================================================
-- 6. campaigns — multi-week campaigns (NO target_segments TEXT[])
-- =============================================================================
CREATE TABLE marketing.campaigns (
    id             SERIAL PRIMARY KEY,
    campaign_id    TEXT NOT NULL,
    project_id     TEXT NOT NULL REFERENCES marketing.projects(project_id),
    campaign_name  TEXT NOT NULL,
    campaign_type  TEXT NOT NULL CHECK (campaign_type IN ('weekly_product', 'seasonal', 'launch', 'evergreen', 'promotion')),
    status         TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'active', 'paused', 'completed', 'cancelled')),
    start_date     DATE,
    end_date       DATE,
    budget         JSONB DEFAULT '{}',
    goals          JSONB DEFAULT '{}',
    config         JSONB DEFAULT '{}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, campaign_id)
);

-- =============================================================================
-- 7. campaign_products — join table campaign ↔ product
-- =============================================================================
CREATE TABLE marketing.campaign_products (
    campaign_id INT NOT NULL REFERENCES marketing.campaigns(id) ON DELETE CASCADE,
    product_id  INT NOT NULL REFERENCES marketing.product_catalog(id) ON DELETE CASCADE,
    PRIMARY KEY (campaign_id, product_id)
);

-- =============================================================================
-- 8. campaign_target_segments — join table campaign ↔ buyer_segment
-- =============================================================================
CREATE TABLE marketing.campaign_target_segments (
    campaign_id      INT  NOT NULL REFERENCES marketing.campaigns(id) ON DELETE CASCADE,
    buyer_segment_id INT  NOT NULL REFERENCES marketing.buyer_segments(id) ON DELETE CASCADE,
    PRIMARY KEY (campaign_id, buyer_segment_id)
);

-- =============================================================================
-- 9. campaign_runs — weekly execution with week_start_date + generated iso_week
-- =============================================================================
CREATE TABLE marketing.campaign_runs (
    id              SERIAL PRIMARY KEY,
    campaign_id     INT  NOT NULL REFERENCES marketing.campaigns(id),
    project_id      TEXT NOT NULL REFERENCES marketing.projects(project_id),
    week_start_date DATE NOT NULL,
    iso_week        TEXT GENERATED ALWAYS AS (marketing.iso_week_text(week_start_date)) STORED,
    status          TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'generating', 'review', 'approved', 'published', 'completed', 'failed')),
    theme           TEXT,
    config          JSONB DEFAULT '{}',
    results         JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (campaign_id, week_start_date)
);

-- =============================================================================
-- 10. assets — creative pieces with structural IDs
-- =============================================================================
CREATE TABLE marketing.assets (
    id            SERIAL PRIMARY KEY,
    run_id        INT  REFERENCES marketing.campaign_runs(id),
    project_id    TEXT NOT NULL REFERENCES marketing.projects(project_id),
    campaign_id   INT  REFERENCES marketing.campaigns(id),
    creative_id   TEXT NOT NULL,
    asset_type    TEXT NOT NULL CHECK (asset_type IN ('reel_script', 'meta_ad', 'email', 'video', 'image', 'calendar', 'blog_post', 'landing_page', 'report')),
    platform      TEXT CHECK (platform IN ('tiktok', 'instagram', 'facebook', 'meta_ads', 'email', 'youtube', 'pinterest', 'google', 'google_ads', 'organic_instagram', 'organic_tiktok', 'organic_youtube', 'website', 'landing_page')),
    persona_id    INT  REFERENCES marketing.buyer_segments(id),
    title         TEXT,
    content       JSONB NOT NULL DEFAULT '{}',
    status        TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'review', 'approved', 'published', 'archived', 'rejected')),
    angle_id      TEXT,
    hook_type     TEXT,
    week_start_date DATE,
    iso_week      TEXT GENERATED ALWAYS AS (marketing.iso_week_text(week_start_date)) STORED,
    metadata      JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (creative_id)
);

-- =============================================================================
-- 11. asset_metrics_base — universal metrics with idempotency key
-- =============================================================================
CREATE TABLE marketing.asset_metrics_base (
    id              SERIAL PRIMARY KEY,
    asset_id        INT  NOT NULL REFERENCES marketing.assets(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL,
    week_start_date DATE NOT NULL,
    iso_week        TEXT GENERATED ALWAYS AS (marketing.iso_week_text(week_start_date)) STORED,
    impressions     INT  DEFAULT 0,
    reach           INT  DEFAULT 0,
    clicks          INT  DEFAULT 0,
    ctr             NUMERIC(8,4) DEFAULT 0,
    spend           NUMERIC(10,2) DEFAULT 0,
    cpc             NUMERIC(10,2) DEFAULT 0,
    cpm             NUMERIC(10,2) DEFAULT 0,
    conversions     INT  DEFAULT 0,
    revenue         NUMERIC(12,2) DEFAULT 0,
    roas            NUMERIC(10,2) DEFAULT 0,
    engagement_rate NUMERIC(8,4) DEFAULT 0,
    idempotency_key TEXT GENERATED ALWAYS AS (marketing.int_text(asset_id) || '/' || platform || '/' || marketing.date_text(week_start_date)) STORED,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_asset_metrics_base_idempotency ON marketing.asset_metrics_base(idempotency_key);

-- =============================================================================
-- 12. asset_metrics_video — video-specific metrics (CASCADE from base)
-- =============================================================================
CREATE TABLE marketing.asset_metrics_video (
    metrics_base_id INT PRIMARY KEY REFERENCES marketing.asset_metrics_base(id) ON DELETE CASCADE,
    views           INT DEFAULT 0,
    watch_time_sec  NUMERIC(12,2) DEFAULT 0,
    avg_watch_pct   NUMERIC(8,4) DEFAULT 0,
    likes           INT DEFAULT 0,
    comments        INT DEFAULT 0,
    shares          INT DEFAULT 0,
    saves           INT DEFAULT 0,
    hook_rate_3s    NUMERIC(8,4) DEFAULT 0,
    retention_15s   NUMERIC(8,4) DEFAULT 0,
    retention_30s   NUMERIC(8,4) DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 13. asset_metrics_email — email-specific metrics (CASCADE from base)
-- =============================================================================
CREATE TABLE marketing.asset_metrics_email (
    metrics_base_id INT PRIMARY KEY REFERENCES marketing.asset_metrics_base(id) ON DELETE CASCADE,
    sent            INT DEFAULT 0,
    delivered       INT DEFAULT 0,
    opens           INT DEFAULT 0,
    unique_opens    INT DEFAULT 0,
    open_rate       NUMERIC(8,4) DEFAULT 0,
    click_rate      NUMERIC(8,4) DEFAULT 0,
    unsubscribes    INT DEFAULT 0,
    bounces         INT DEFAULT 0,
    spam_reports    INT DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 14. asset_metrics_search — Google Ads metrics (CASCADE from base)
-- =============================================================================
CREATE TABLE marketing.asset_metrics_search (
    metrics_base_id  INT PRIMARY KEY REFERENCES marketing.asset_metrics_base(id) ON DELETE CASCADE,
    quality_score    INT,
    avg_position     NUMERIC(6,2),
    search_impr_share NUMERIC(8,4),
    keyword_text     TEXT,
    match_type       TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 15. asset_metrics_landing — landing page metrics (CASCADE from base)
-- =============================================================================
CREATE TABLE marketing.asset_metrics_landing (
    metrics_base_id INT PRIMARY KEY REFERENCES marketing.asset_metrics_base(id) ON DELETE CASCADE,
    page_views      INT DEFAULT 0,
    unique_visitors INT DEFAULT 0,
    bounce_rate     NUMERIC(8,4) DEFAULT 0,
    avg_time_on_page NUMERIC(10,2) DEFAULT 0,
    scroll_depth_avg NUMERIC(8,4) DEFAULT 0,
    form_submissions INT DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 16. platform_metrics_weekly — aggregated per platform with idempotency
-- =============================================================================
CREATE TABLE marketing.platform_metrics_weekly (
    id              SERIAL PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES marketing.projects(project_id),
    campaign_id     INT  REFERENCES marketing.campaigns(id),
    platform        TEXT NOT NULL,
    week_start_date DATE NOT NULL,
    iso_week        TEXT GENERATED ALWAYS AS (marketing.iso_week_text(week_start_date)) STORED,
    impressions     INT  DEFAULT 0,
    reach           INT  DEFAULT 0,
    clicks          INT  DEFAULT 0,
    spend           NUMERIC(10,2) DEFAULT 0,
    conversions     INT  DEFAULT 0,
    revenue         NUMERIC(12,2) DEFAULT 0,
    roas            NUMERIC(10,2) DEFAULT 0,
    followers_gained INT DEFAULT 0,
    engagement_rate NUMERIC(8,4) DEFAULT 0,
    idempotency_key TEXT GENERATED ALWAYS AS (project_id || '/' || COALESCE(marketing.int_text(campaign_id), '_') || '/' || platform || '/' || marketing.date_text(week_start_date)) STORED,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_platform_metrics_weekly_idempotency ON marketing.platform_metrics_weekly(idempotency_key);

-- =============================================================================
-- 17. seo_metrics — Search Console data with idempotency
-- =============================================================================
CREATE TABLE marketing.seo_metrics (
    id              SERIAL PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES marketing.projects(project_id),
    url             TEXT NOT NULL,
    date            DATE NOT NULL,
    query           TEXT,
    impressions     INT  DEFAULT 0,
    clicks          INT  DEFAULT 0,
    ctr             NUMERIC(8,4) DEFAULT 0,
    avg_position    NUMERIC(6,2),
    idempotency_key TEXT GENERATED ALWAYS AS (project_id || '/' || url || '/' || marketing.date_text(date) || '/' || COALESCE(query, '_')) STORED,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_seo_metrics_idempotency ON marketing.seo_metrics(idempotency_key);

-- =============================================================================
-- 18. orders — Stripe mirror with attribution
-- =============================================================================
CREATE TABLE marketing.orders (
    id               SERIAL PRIMARY KEY,
    project_id       TEXT NOT NULL REFERENCES marketing.projects(project_id),
    order_id         TEXT NOT NULL,
    stripe_payment_id TEXT,
    customer_email   TEXT,
    amount           NUMERIC(12,2) NOT NULL,
    currency         TEXT DEFAULT 'USD',
    status           TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('pending', 'completed', 'refunded', 'cancelled')),
    source_platform  TEXT,
    source_campaign  TEXT,
    source_asset_id  INT REFERENCES marketing.assets(id),
    utm_source       TEXT,
    utm_medium       TEXT,
    utm_campaign     TEXT,
    utm_content      TEXT,
    items            JSONB DEFAULT '[]',
    idempotency_key  TEXT GENERATED ALWAYS AS (project_id || '/' || order_id) STORED,
    order_date       TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_orders_idempotency ON marketing.orders(idempotency_key);

-- =============================================================================
-- 19. conversion_events — generic event model
-- =============================================================================
CREATE TABLE marketing.conversion_events (
    id              SERIAL PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES marketing.projects(project_id),
    event_type      TEXT NOT NULL CHECK (event_type IN ('purchase', 'lead', 'quote_request', 'appointment', 'call', 'reservation', 'signup', 'add_to_cart', 'checkout_start')),
    event_date      TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_platform TEXT,
    source_campaign TEXT,
    source_asset_id INT REFERENCES marketing.assets(id),
    customer_id     TEXT,
    value           NUMERIC(12,2),
    currency        TEXT DEFAULT 'USD',
    idempotency_key TEXT NOT NULL,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, idempotency_key)
);

-- =============================================================================
-- 20. growth_analyses — Growth diagnostics with idempotency
-- =============================================================================
CREATE TABLE marketing.growth_analyses (
    id              SERIAL PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES marketing.projects(project_id),
    campaign_id     INT  REFERENCES marketing.campaigns(id),
    week_start_date DATE NOT NULL,
    iso_week        TEXT GENERATED ALWAYS AS (marketing.iso_week_text(week_start_date)) STORED,
    analysis_type   TEXT DEFAULT 'weekly_review',
    results         JSONB NOT NULL DEFAULT '{}',
    recommendations JSONB DEFAULT '[]',
    idempotency_key TEXT GENERATED ALWAYS AS (project_id || '/' || COALESCE(marketing.int_text(campaign_id), '_') || '/' || marketing.date_text(week_start_date)) STORED,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_growth_analyses_idempotency ON marketing.growth_analyses(idempotency_key);

-- =============================================================================
-- 21. decisions — post-Growth decision log
-- =============================================================================
CREATE TABLE marketing.decisions (
    id              SERIAL PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES marketing.projects(project_id),
    week_start_date DATE NOT NULL,
    iso_week        TEXT GENERATED ALWAYS AS (marketing.iso_week_text(week_start_date)) STORED,
    decision_type   TEXT NOT NULL CHECK (decision_type IN ('scale', 'kill', 'iterate', 'pause', 'pivot', 'revalidate_strategy')),
    target_type     TEXT,
    target_id       TEXT,
    rationale       TEXT,
    impact          JSONB DEFAULT '{}',
    decided_by      TEXT DEFAULT 'system',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 22. knowledge_base — patterns and learned concepts
-- =============================================================================
CREATE TABLE marketing.knowledge_base (
    id          SERIAL PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES marketing.projects(project_id),
    pattern_id  TEXT NOT NULL,
    category    TEXT,
    title       TEXT NOT NULL,
    description TEXT,
    evidence    JSONB DEFAULT '[]',
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'validated', 'invalidated', 'archived')),
    confidence  NUMERIC(4,2) DEFAULT 0.5,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, pattern_id)
);

-- =============================================================================
-- 23. experiments — A/B tests
-- =============================================================================
CREATE TABLE marketing.experiments (
    id              SERIAL PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES marketing.projects(project_id),
    experiment_id   TEXT NOT NULL,
    experiment_name TEXT NOT NULL,
    hypothesis      TEXT,
    status          TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'proposed', 'running', 'completed', 'cancelled')),
    start_date      DATE,
    end_date        DATE,
    variants        JSONB DEFAULT '[]',
    results         JSONB DEFAULT '{}',
    conclusion      TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, experiment_id)
);

-- =============================================================================
-- 24. gates — human decision checkpoints
-- =============================================================================
CREATE TABLE marketing.gates (
    id          SERIAL PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES marketing.projects(project_id),
    gate_type   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'skipped')),
    context     JSONB DEFAULT '{}',
    decided_by  TEXT,
    decided_at  TIMESTAMPTZ,
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- Additional indexes for common query patterns
-- =============================================================================
CREATE INDEX idx_strategy_versions_status ON marketing.strategy_versions(project_id, status);
CREATE INDEX idx_strategy_outputs_lookup ON marketing.strategy_outputs(project_id, version);
CREATE INDEX idx_buyer_segments_project ON marketing.buyer_segments(project_id, priority);
CREATE INDEX idx_campaigns_project_status ON marketing.campaigns(project_id, status);
CREATE INDEX idx_campaign_runs_week ON marketing.campaign_runs(project_id, week_start_date);
CREATE INDEX idx_assets_project_week ON marketing.assets(project_id, week_start_date);
CREATE INDEX idx_assets_persona ON marketing.assets(persona_id);
CREATE INDEX idx_assets_type ON marketing.assets(project_id, asset_type);
CREATE INDEX idx_asset_metrics_base_asset ON marketing.asset_metrics_base(asset_id, week_start_date);
CREATE INDEX idx_platform_metrics_project ON marketing.platform_metrics_weekly(project_id, week_start_date);
CREATE INDEX idx_seo_metrics_project ON marketing.seo_metrics(project_id, date);
CREATE INDEX idx_orders_project ON marketing.orders(project_id, order_date);
CREATE INDEX idx_conversion_events_project ON marketing.conversion_events(project_id, event_date);
CREATE INDEX idx_growth_analyses_project ON marketing.growth_analyses(project_id, week_start_date);
CREATE INDEX idx_decisions_project ON marketing.decisions(project_id, week_start_date);
CREATE INDEX idx_knowledge_base_project ON marketing.knowledge_base(project_id, status);
CREATE INDEX idx_experiments_project ON marketing.experiments(project_id, status);
CREATE INDEX idx_gates_project ON marketing.gates(project_id, gate_type);

COMMIT;
