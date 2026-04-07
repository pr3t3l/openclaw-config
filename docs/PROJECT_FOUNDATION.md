# PROJECT_FOUNDATION.md — OpenClaw
<!--
SCOPE: Vision, purpose, stack, roadmap, key decisions, doc registry.
NOT HERE: Implementation specs → docs/specs/[module]/spec.md
NOT HERE: Database schemas → DATA_MODEL.md
NOT HERE: API details → INTEGRATIONS.md
NOT HERE: Rules/constraints → CONSTITUTION.md
NOT HERE: Failures/fixes → LESSONS_LEARNED.md

TARGET LENGTH: 3-5 pages max.
-->

**Last updated:** 2026-04-07

---

## 1. What This Is

OpenClaw is a multi-agent AI orchestration platform running on WSL Ubuntu. It operates via 3 Telegram bots, each with a dedicated agent and workspace. It executes products (Declassified Cases), support systems (Marketing, Finance), and development tools (Planner).

## 2. What Problem It Solves

Centralize the operation of multiple AI products and workflows on a single platform with model routing, cost tracking, and Telegram-based execution — without depending on third-party cloud services for orchestration.

## 3. What This Is NOT (Anti-Goals)

1. **NOT a SaaS for other users** — it is Alfredo's personal infrastructure (for now)
2. **NOT a replacement for n8n or Zapier** — it is complementary, not a competitor
3. **NOT a generic AI agent framework** — it is optimized for the specific workflows that run here

## 4. Who It's For

| Role | Who | What they need |
|------|-----|---------------|
| Owner/Operator | Alfredo Pretel | Execute workflows, monitor costs, operate remotely |

## 5. Competitive Differentiators

1. **Multi-model routing via LiteLLM** — uses the cheapest model that meets quality per task
2. **Telegram as interface** — operable from phone via Termius + Tailscale
3. **Product-agnostic workflows** — Pipeline, Marketing, Finance are generic and reusable

---

## 6. Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| OS | WSL Ubuntu on Windows | Alfredo's laptop, always-on |
| Orchestration | OpenClaw Gateway (:18789) | Multi-agent management |
| Model Proxy | LiteLLM (:4000) | Multi-provider routing, cost tracking |
| Database | PostgreSQL 16 (:5432) | Marketing schema, LiteLLM data |
| Data Store | Google Sheets | Finance Tracker |
| Interface | Telegram Bots (3) | CEO, Declassified, Planner |
| Remote Access | Tailscale + SSH + tmux | Phone operation via Termius |
| Code Assistant | Claude Code | Implementation |
| Web Store | React + Vite + Supabase + Stripe | declassified.shop |
| Email | Resend + IONOS | Transactional + business email |

## 7. Key Decisions

| Decision | Choice | Date | Why | Alternatives Rejected |
|----------|--------|------|-----|----------------------|
| API calls in WSL | Streaming curl via subprocess | 2026-02 | Python requests fails >30s in WSL | requests library |
| Model routing | LiteLLM proxy | 2026-02 | Multi-provider, cost tracking, single endpoint | Direct API calls per provider |
| Primary interface | Telegram bots | 2026-02 | Mobile-friendly, always accessible, async | Web UI |
| Cost strategy | Codex OAuth ($0) for generation, paid API only for rendering | 2026-03 | 90%+ cost reduction | All-paid API calls |
| Documentation system | SDD (Spec-Driven Development) | 2026-04 | Eliminate 10+ iteration cycles | Ad-hoc docs, monolith bibles |

---

## 8. Module Roadmap

### MVP (Active)

| # | Module/Workflow | Type | Purpose | Status | Depends On |
|---|----------------|------|---------|--------|------------|
| 1 | Platform/Robotin (CEO) | infra | Infrastructure, routing, Telegram, remote ops | ✅ Functional | — |
| 2 | Declassified Pipeline V9 | workflow | AI-generated mystery case → packaged PDFs | 🟡 90% | Platform |
| 3 | Finance Tracker | module (skill) | Personal expense tracking + Airbnb tax deductions | 🟡 90% | Platform |
| 4 | Marketing System | workflow | Automated content generation, 3-layer campaign engine | 🟡 70% | Platform, Pipeline |
| 5 | Planner (SDD) | workflow | Idea → validated spec via multi-model debate | 🟡 Integration Testing | Platform |

### Post-MVP (one line each — spec when ready to build)

| Phase | Module | One-line purpose |
|-------|--------|-----------------|
| 2 | Telegram Ops Bot | Marketing operations via dedicated bot |
| 2 | Social Publishing API | Automated FB/IG/TikTok/YouTube posting |
| 3 | SaaS Finance Tracker | Multi-tenant version for sale |

---

## 9. Roles & Permissions

| Role | Who | Access |
|------|-----|--------|
| Owner/Operator | Alfredo | Full access to all bots, workspaces, and infrastructure |

## 10. Design System Summary

N/A — OpenClaw is infrastructure. Product-specific design (Declassified, Finance) lives in their respective specs.

## 11. Monetization Model

| Product | Price | Channel |
|---------|-------|---------|
| Declassified Cases (single) | $12.00 USD (target: $19.99) | declassified.shop |
| Declassified Cases (4-pack) | $59.00 USD | declassified.shop |
| Finance Tracker (future SaaS) | TBD | Stripe subscription |

## 12. Cross-Cutting Concerns

- **i18n:** English primary, Spanish secondary. Products target Americans in USA.
- **Security:** Telegram ACL (allowFrom.json), PostgreSQL RLS, Supabase RLS for web store.
- **Cost control:** LiteLLM /spend endpoint for API costs. Budget alarm before starting work sessions. See CONSTITUTION.md §6.
- **Testing:** Single-item E2E test before batch. Structural validators before LLM quality checks.
- **Error handling:** Max 2 retries with diagnosis. Save raw output on failure. See LESSONS_LEARNED.md.
- **Observability:** LiteLLM dashboard for model usage. api_audit_log table in PostgreSQL. manifest.json per pipeline run.

---

## 13. Document Registry

<!-- CANONICAL INDEX. If a doc is not here, it doesn't exist. -->

| Document | Purpose | Location | Last Updated |
|----------|---------|----------|-------------|
| PROJECT_FOUNDATION | This file — vision, stack, roadmap | docs/ | 2026-04-03 |
| CONSTITUTION | Immutable rules + AI agent rules | docs/ | Pending |
| DATA_MODEL | PostgreSQL + Google Sheets schemas | docs/ | Pending |
| INTEGRATIONS | Telegram, Stripe, LiteLLM, external APIs | docs/ | Pending |
| LESSONS_LEARNED | All failures + fixes (LL-CAT-XXX format) | docs/ | Pending |
| spec: planner | Planner workflow spec (SDD rebuild) | docs/specs/planner/ | Pending |
| Archive: workflow bibles | Previous documentation (reference only) | docs/archivo/ | 2026-04-03 |

### Anti-Duplication Rules
1. **Reference, never copy.** Use "See [DOC.md §section]" format.
2. **One concept, one location.** If two docs cover the same topic, merge and delete one.
3. **Check registry before creating.** If a doc for this topic exists, update it.
4. **No code in docs.** Code lives in src/. Docs describe intent.
5. **No API keys in docs.** Keys live in .env only.
