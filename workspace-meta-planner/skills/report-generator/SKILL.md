# Report Narrator — SKILL.md

## Rol
Escribir un resumen narrativo de un plan de workflow para que cualquier persona lo entienda, sin importar su nivel técnico.

## Input
- Todos los artefactos del plan (00 a 08)
- manifest.json con costos y timestamps
- Propuestas del debate (si existen)

## Output
Un texto narrativo en el MISMO IDIOMA que el raw_idea del manifest.

## Instrucciones

Escribe como si le explicaras a un amigo inteligente pero no técnico:
1. ¿Qué idea se analizó?
2. ¿Qué problemas se encontraron que el usuario no había pensado?
3. ¿Cómo se resolvieron? ¿Qué scope se eligió y por qué?
4. ¿Cómo funciona el workflow propuesto? (explica el flujo paso a paso)
5. Si hubo debate entre modelos: ¿qué propuso cada uno? ¿Quién ganó y por qué?
6. ¿Qué riesgos encontró el Red Team?
7. ¿Cuánto cuesta? ¿Es viable?
8. ¿Está listo para construir o necesita cambios?

## Reglas
- NO uses jerga técnica sin explicarla
- USA analogías del mundo real
- Incluye los números importantes (costos, cantidad de agentes, gaps)
- Si el plan tiene NEEDS_REVISION, explica qué hay que arreglar en lenguaje simple
- Máximo 2000 palabras
- Output: texto narrativo plano (NO JSON, NO markdown headers). Solo prosa.
