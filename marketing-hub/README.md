# Marketing Hub — Sistema Multi-Agente de Alfredo

## Qué es esto

Un sistema de marketing digital construido sobre OpenClaw con 4 sub-agentes especializados que comparten conocimiento y se comunican por Telegram. Diseñado para vender productos recurrentes (suscripciones, casos semanales, etc.) pero **completamente agnóstico del producto**: la misma estructura funciona para vender velas, carros, o lo que sea mañana.

---

## Estructura Rápida

```
marketing-hub/
├── shared/
│   ├── knowledge/     ← Lo que NO cambia entre productos
│   │   ├── marca.json        (voz, tono, CPM)
│   │   ├── funnel.json       (embudo, flujos, KPIs)
│   │   ├── hooks.json        (ganchos probados)
│   │   └── templates/        (guiones, emails, blog)
│   └── state.json            ← Estado global del sistema
├── products/
│   ├── misterio-semanal/     ← Producto 1
│   │   ├── producto.json      ← SOLO esto cambia entre productos
│   │   ├── buyer_persona.json ← SOLO esto cambia entre productos
│   │   └── campaigns/         ← Una campaña por semana
│   └── _plantilla/            ← Plantilla para productos nuevos
└── agents/
    ├── Estratega/             ← Configura producto nuevo
    ├── Motor-Contenido/      ← Genera contenido semanal
    ├── Social-Agente/         ← Publica y automatiza
    └── Optimizador/           ← Mide y decide ajustes
```

---

## Para Empezar

### 1. Ya está configurado:
- ✅ `products/misterio-semanal/` con producto.json y buyer_persona.json
- ✅ Knowledge base compartida (marca, funnel, hooks, templates)
- ✅ 4 sub-agentes con sus instrucciones
- ✅ Estado inicial en state.json

### 2. Lo que falta (primera ejecución):
- [ ] **Motor-Contenido → Semana 1**: Generar guiones para "Caso del Museo Vacío"
- [ ] **Social-Agente → Configurar ManyChat** para trigger "MISTERIO"
- [ ] **Publicar y medir** → Optimizador registra resultados

---

## Comandos para Alfredo

| Comando | Qué hace |
|---------|----------|
| `/nuevo-producto [nombre] [tipo] [precio]` | Crea un producto nuevo (ej. velas) |
| `/nuevo-caso [producto] [tema]` | Genera contenido para el caso de esta semana |
| `/status [producto]` | Reporte de KPIs de la última semana |
| `/semana [producto]` | Ejecuta Motor-Contenido + Social-Agente |
| `/reanalizar [producto]` | Re-scraping de competidores + actualizar hooks |
| `/producto [nombre]` | Cambia el producto activo |

---

## Filosofía de Uso

### ✅ Haz una vez:
- Estrategia fundacional (Estratega)
- Setup de embudo y automatizaciones
- Buyer persona

### 🔄 Haz cada semana:
- Motor-Contenido → nuevos guiones para el caso
- Social-Agente → programar y publicar
- Optimizador → medir y ajustar

### 🚨 Haz solo si cae:
- Re-análisis de competidores (Optimizador lo dispara automáticamente)

---

## Cómo Funciona Internamente

```
Alfredo → Telegram → Orchestrator (este)
                         ↓
              [delega al sub-agente correcto]
                         ↓
              [sub-agente escribe resultados]
                         ↓
              [Orchestrator reporta a Alfredo]
```

Los sub-agentes se disparan como **sesiones aisladas** de OpenClaw (`sessions_spawn`), lo que significa que cada uno tiene su propio contexto pero puede leer la knowledge base compartida.

---

## Métricas Objetivo

| KPI | Objetivo |
|-----|----------|
| CPA | < $15.00 (y siempre < margen del producto) |
| CPL | < $2.00 |
| Tasa apertura email | > 25% |
| CTR Reel | > 3% |
| Interacción orgánica | > 2% |

---

## Expandir a Nuevo Producto (ej. velas)

```bash
# Paso 1: Crear directorio
mkdir products/velas-aromaticas

# Paso 2: Copiar plantillas
cp products/_plantilla/producto.json products/velas-aromaticas/
cp products/_plantilla/buyer_persona.json products/velas-aromaticas/

# Paso 3: Llenar los JSON con datos del producto

# Paso 4: Comando:
/nuevo-producto velas-aromaticas subscription 24.99

# ¡El embudo, hooks, agentes y templates son los mismos!
```

---

## Notas Técnicas

- Los agentes usan `~/.openclaw/marketing-hub/` como workspace base
- state.json es la fuente de verdad para qué producto está activo
- campaign files son el registro histórico de qué se hizo cada semana
- hooks.json se actualiza automáticamente después de cada re-análisis de competidores
