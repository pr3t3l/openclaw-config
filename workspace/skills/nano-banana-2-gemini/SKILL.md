---
name: nano-banana-2
description: |
  Gemini image generation, editing, and search-grounded image creation via
  gemini-3.1-flash-image-preview (Nano Banana 2).

  USE FOR:
  - Generating images from text prompts (text-to-image)
  - Editing or transforming an existing image with text instructions
  - Generating images grounded in live web/image search results

  Requires GEMINI_API_KEY environment variable. See rules/setup.md for
  configuration and rules/security.md for output handling guidelines.
allowed-tools:
  - Bash(curl *)
  - Bash(python3 *)
  - Bash(mkdir *)
  - Bash(open .nano-banana/*)
---

# nano-banana-2

Gemini image generation and editing via `gemini-3.1-flash-image-preview`. All
output images are written to `.nano-banana/` in the current project directory.

## Prerequisites

`GEMINI_API_KEY` must be set in the environment. Verify with:

```bash
echo $GEMINI_API_KEY
```

If empty, see [rules/setup.md](rules/setup.md). For output handling and security
guidelines, see [rules/security.md](rules/security.md).

## Workflow

**Read inputs silently.**
- If you read any local files (prompts, briefs, JSON, logs) to do the task, do so *silently*.
- **Never echo, quote, paste, or summarize file contents verbatim** in your output.

Follow this escalation pattern:

1. **Generate** - Create a new image from a text prompt only.
2. **Edit** - Modify an existing local image with a text instruction.
3. **Search-Grounded** - Generate informed by live web/image search results (use when current visual references, styles, or real-world accuracy matter).

| Goal                               | Operation         | When                                           |
| ---------------------------------- | ----------------- | ---------------------------------------------- |
| Create image from scratch          | `generate`        | No source image; prompt is self-contained      |
| Modify or extend an existing image | `edit`            | Have a local PNG/JPEG to transform             |
| Ground output in current web data  | `search-grounded` | Need up-to-date styles or real-world references|

## Output & Organization

All images are saved to `.nano-banana/` in the current working directory.
Add `.nano-banana/` to `.gitignore` to prevent generated assets from being committed.

```bash
mkdir -p .nano-banana
echo ".nano-banana/" >> .gitignore
```

Naming conventions:

```
.nano-banana/gen-{slug}-{timestamp}.png
.nano-banana/edit-{slug}-{timestamp}.png
.nano-banana/search-{slug}-{timestamp}.png
```

Where `{slug}` is a short kebab-case label from the first 4-5 words of the prompt,
and `{timestamp}` is `YYYYMMDD-HHMMSS`.

## API Reference

| Property             | Value                                                                                                     |
| -------------------- | --------------------------------------------------------------------------------------------------------- |
| Model                | `gemini-3.1-flash-image-preview`                                                                          |
| Endpoint             | `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent` |
| Auth header          | `x-goog-api-key: $GEMINI_API_KEY`                                                                         |
| Image output         | `candidates[0].content.parts[].inlineData.data` (base64 PNG)                                             |

(See rules/setup.md and rules/security.md.)
