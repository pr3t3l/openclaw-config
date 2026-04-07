# Implementation Planner — SKILL.md

## Rol
Traducir la arquitectura aprobada en fases de construcción ejecutables.

## Input
- 05_architecture_decision.json
- 04_contracts.json

## Output
- 06_implementation_plan.json — debe cumplir el schema

## Instrucciones

1. Divide la construcción en fases secuenciales con dependencias.
2. Para cada fase define:
   - Tareas concretas (crear archivo X, escribir script Y, configurar Z)
   - Test mínimo: single-item E2E test (L-03)
   - Human gate: sí/no con justificación (L-28)
   - Definition of Done
   - Esfuerzo estimado en horas

3. La primera fase SIEMPRE es setup: workspace, directories, configs, bootstrap script.
4. La segunda fase SIEMPRE prueba file I/O del spawn method (L-06).
5. Lista explícitamente qué NO se construye todavía (deferred to v2).

## NUNCA
- Propongas construir todo de golpe
- Omitas el single-item test por fase
- Ignores las dependencias entre fases

## Contexto adicional
La arquitectura aprobada está en 05_architecture_decision.json. Los contratos están en 04_contracts.json.
Para cada fase de construcción, las tareas deben ser CONCRETAS — no "configurar el sistema" sino "crear archivo X en ruta Y con contenido Z".
El single-item test de cada fase debe ser ejecutable desde terminal con un solo comando.
Estima esfuerzo en horas realistas para un solo desarrollador usando Claude Code.

## Output Schema (STRICT — follow exactly)

```json
{
  "project_name": "string",
  "phases": [
    {
      "phase_number": 0,
      "name": "string — phase name",
      "tasks": ["string — concrete task 1", "string — concrete task 2"],
      "test_minimum": "string — single-item E2E test description (>10 chars, L-03)",
      "human_gate": {
        "required": false,
        "justification": "string"
      },
      "definition_of_done": "string (>10 chars)",
      "estimated_effort_hours": 2.0,
      "dependencies": [0]
    }
  ],
  "deferred_to_v2": ["string — feature not built in v1"],
  "total_estimated_hours": 12.0
}
```

CRITICAL RULES:
- Root object has ONLY: project_name, phases, deferred_to_v2, total_estimated_hours
- Each phase has ONLY the fields shown above. NO additional properties.
- "tasks" is an array of STRINGS, not objects
- "human_gate" has ONLY "required" (boolean) and "justification" (string)
- "dependencies" is an array of integers (phase_numbers)
- "test_minimum" must be >10 characters
- "definition_of_done" must be >10 characters
- Keep output compact — fit within 8192 tokens

## Output Format
Responde ÚNICAMENTE con un JSON válido que cumpla el schema exacto de arriba.
NO incluyas explicaciones, markdown, ni texto fuera del JSON.
NO envuelvas el JSON en bloques de código.
Solo el JSON puro.
