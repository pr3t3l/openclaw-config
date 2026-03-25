# Data Flow Mapper — SKILL.md

## Rol
Definir CADA artefacto que el workflow producirá, quién lo produce, quién lo consume, y por qué existe.

## Input
- 00_intake_summary.json
- 01_gap_analysis.json
- 02_scope_decision.json (scope seleccionado)

## Output
- 03_data_flow_map.json — debe cumplir el schema

## Instrucciones

1. Para el scope seleccionado, lista TODOS los artefactos (archivos) que se producirán durante la ejecución del workflow.
2. Para cada artefacto, define:
   - Quién lo produce (agente, script, humano, API externa)
   - Quién lo consume (puede ser más de uno)
   - Formato (json, md, csv, pdf, image, etc.)
   - Por qué existe (qué valor aporta)
   - Si es fuente de verdad o artefacto intermedio
   - Si debe persistir o puede eliminarse después

3. REGLA DURA (L-01): Si un artefacto no tiene consumidor, NO lo incluyas. Pon una nota en orphan_outputs explicando por qué se descartó.
4. REGLA DURA (L-01): Si un consumidor necesita un artefacto que nadie produce, ponlo en missing_required_artifacts.
5. Si orphan_outputs o missing_required_artifacts no están vacíos, el planner FALLA y no avanza.

## NUNCA
- Incluyas artefactos "por si acaso"
- Dejes un output sin consumidor explícito
- Dejes un consumidor sin productor explícito

## Contexto adicional
El scope seleccionado está en 02_scope_decision.json. Usa SOLO las features del scope seleccionado (usualmente MVP).
El gap analysis está en 01_gap_analysis.json. Los gaps que marcaste como "blocker" deben estar resueltos por el data flow — cada gap resuelto tiene un artefacto o un mecanismo que lo cubre.

## Output Schema (STRICT — follow exactly)

```json
{
  "project_name": "string",
  "scope_version": "mvp | standard | advanced",
  "artifacts": [
    {
      "name": "string — artifact filename (e.g., 'marketing_study.json')",
      "produced_by": "string — simple name (e.g., 'marketing_study_agent')",
      "consumed_by": ["string", "string — simple names (e.g., 'copy_generator', 'human_reviewer')"],
      "format": "json | md | csv | pdf | image | html | txt | sqlite | yaml | other",
      "purpose": "string — why this artifact exists (>10 chars)",
      "is_source_of_truth": true,
      "must_persist": true
    }
  ],
  "orphan_outputs": [],
  "missing_required_artifacts": []
}
```

CRITICAL RULES for the schema:
- "produced_by" is a SIMPLE STRING, not an object. Example: "marketing_agent" not {"type": "agent", "name": "..."}
- "consumed_by" is an ARRAY OF SIMPLE STRINGS. Example: ["copy_agent", "human_reviewer"] not [{"id": "...", "name": "..."}]
- "format" must be exactly one of: json, md, csv, pdf, image, html, txt, sqlite, yaml, other
- NO additional properties beyond: name, produced_by, consumed_by, format, purpose, is_source_of_truth, must_persist
- The root object has ONLY: project_name, scope_version, artifacts, orphan_outputs, missing_required_artifacts
- NO additional root properties (no agents_and_scripts, no flow_sequence, no storage_conventions, etc.)

## Output Format
Responde ÚNICAMENTE con un JSON válido que cumpla el schema exacto de arriba.
NO incluyas explicaciones, markdown, ni texto fuera del JSON.
NO envuelvas el JSON en bloques de código.
Solo el JSON puro.
