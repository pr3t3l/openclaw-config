# Marketing Hub — Arquitectura General

## Filosofía

> El trabajo profundo (investigación, estrategia, setup) se hace **una vez**. El esfuerzo semanal se Concentra en **crear y distribuir contenido** para el caso de esa semana. El sistema es **agnóstico del producto**: la estructura no cambia, solo los datos del producto se intercambian.

---

## Los Tres Pilares

```
┌─────────────────────────────────────────────────────┐
│                  PRODUCTO ESPECÍFICO                 │
│  (casos / velas / carros — lo que sea hoy)          │
│  → buyer_persona.json                                │
│  → producto.json                                     │
│  → campana_semana_N.json                            │
└──────────┬──────────────────────────────────────────┘
           │ hereda de
┌──────────▼──────────────────────────────────────────┐
│               KNOWLEDGE BASE COMPARTIDA              │
│  (nunca cambia entre productos — solo se amplía)    │
│  → marca.json        (voz, tono, promesa)           │
│  → funnel.json       (embudo, lead magnet, flujos)  │
│  → seo_base.json     (keyword research genérico)     │
│  → hooks.json        (ganchos probados)              │
│  → automations.json  (ManyChat, Make.com configs)    │
└──────────┬──────────────────────────────────────────┘
           │ configurado por
┌──────────▼──────────────────────────────────────────┐
│              AGENTES OPENCLAW                        │
│  Corren en background, se disparan por cron/chat    │
│  No repiten estrategia — solo ejecutan y miden       │
└─────────────────────────────────────────────────────┘
```

---

## Directorio

```
~/.openclaw/marketing-hub/
├── shared/
│   ├── knowledge/           ← Base de conocimiento reutilizable
│   │   ├── marca.json       # Voz, tono, CPM, promesa de marca
│   │   ├── funnel.json      # Embudo, lead magnet, flujos nurturing
│   │   ├── seo_base.json    # Keywords genéricas, intenciones
│   │   ├── hooks.json       # Ganchos que ya funcionaron
│   │   ├── automations.json  # Config ManyChat / Make.com
│   │   └── templates/        # Guiones base, prompts reutilizables
│   │       ├── guion_reel.json
│   │       ├── guion_tiktok.json
│   │       ├── email_nurturing.json
│   │       └── articulo_blog.json
│   └── scripts/             # Utilidades compartidas
│       ├── publish_to_telegram.sh
│       ├── generate_campaign_report.py
│       └── trigger_automation.py
├── products/                ← Un directorio por producto
│   └── misterio-semanal/
│       ├── producto.json    # Descripción, precio, márgenes
│       ├── buyer_persona.json
│       ├── seo_producto.json  # Keywords específicas del nicho
│       └── campaigns/
│           ├── semana_01.json
│           ├── semana_02.json
│           └── ...
├── agents/                  ← Configs de sub-agentes
│   ├── Estratega/
│   ├── Motor-Contenido/
│   ├── Social-Agente/
│   └── Optimizador/
└── runs/                    ← Logs de ejecuciones semanales
    └── 2026-03-30/
```

---

## Product-Agnostic en la Práctica

El sistema funciona para **cualquier producto** cambiando **solo 2 archivos**:

```bash
# Para cambiar de casos de misterio → velas:
cp products/misterio-semanal/producto.json  products/velas-aromaticas/producto.json
# Editar: descripción, precio, dolor, activadores
# ¡El resto (scripts, agentes, embudo) es idéntico!
```

El funnel, los flujos de email, la estructura de los guiones, los hooks — todo permanece. Solo el **contenido específico** cambia.

---

## Métricas de Salud del Sistema

| Métrica | Bueno | Malo → Trigger |
|---------|-------|----------------|
| CPA vs Margen | CPA < 70% margen | Reescalado de campaña |
| CTR Reels | > 3% | Regenerar hook |
| Tasa apertura email | > 25% | Test A/B asunto |
| Leads/semana | Creciendo o estable | Re-ejecutar Workflow 1 |
| Interacción orgánica | > 2% | Analizar competidores |
