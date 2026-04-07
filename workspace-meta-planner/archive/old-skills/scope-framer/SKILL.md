# Scope Framer — SKILL.md

## Rol
Forzar una decisión entre MVP / Standard / Advanced.

## Input
- 00_intake_summary.json
- 01_gap_analysis.json

## Output
- `02_scope_decision.json` — debe cumplir el schema en schemas/02_scope_decision.schema.json

## Instrucciones

1. Propón 3 versiones del proyecto:
   - **MVP:** Lo mínimo que entrega valor. Feo pero funcional (L-04).
   - **Standard:** MVP + las mejoras más pedidas.
   - **Advanced:** La visión completa.

2. Para cada versión, define:
   - features incluidas
   - features EXPLÍCITAMENTE excluidas
   - número estimado de agentes/scripts
   - esfuerzo estimado en horas
   - costo estimado por ejecución
   - riesgo de under-scoping (qué se pierde)
   - riesgo de over-scoping (qué se desperdicia)

3. Recomienda cuál implementar primero y por qué.
4. Define el upgrade path: cómo pasar de MVP a Standard sin rehacer todo (L-04, L-05).

## Output Schema

```json
{
  "project_name": "string",
  "versions": {
    "mvp": {
      "features_included": ["array of strings (min 1)"],
      "features_excluded": ["array of strings"],
      "estimated_agents_scripts": 3,
      "estimated_effort_hours": 4,
      "estimated_cost_per_run": 0.05,
      "risk_under_scoping": "string — qué se pierde (>5 chars)",
      "risk_over_scoping": "string — qué se desperdicia (>5 chars)"
    },
    "standard": { "...same structure..." },
    "advanced": { "...same structure..." }
  },
  "recommendation": {
    "start_with": "mvp | standard | advanced",
    "reasoning": "string (>20 chars)"
  },
  "upgrade_path": {
    "mvp_to_standard": "string — cómo escalar sin rehacer (>10 chars)",
    "standard_to_advanced": "string (>10 chars)"
  }
}
```

## NUNCA
- Recomiendes empezar por Advanced
- Propongas un MVP que no entrega valor real al usuario
- Ignores los gaps identificados en 01_gap_analysis
- Dejes campos vacíos o con placeholders

## Output Format
Responde ÚNICAMENTE con un JSON válido que cumpla el schema 02_scope_decision.schema.json.
NO incluyas explicaciones, markdown, ni texto fuera del JSON.
NO envuelvas el JSON en bloques de código.
Solo el JSON puro.
