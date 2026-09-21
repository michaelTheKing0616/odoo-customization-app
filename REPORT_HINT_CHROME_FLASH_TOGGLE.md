# Hint chrome (all grains) + Studio Flash enrich toggle

## Mandate
1. **Hint chrome** for ANY prompt with Must-do/AST status hints — preview banner + Apply decoration (alert/ribbon), never Char junk. Prefer Sales Documents hint + residual + any grain.
2. **Studio UI toggle** for Flash AST enrich — honest label, wired to same path as `AI_INTENT_LLM`, env remains server default/override.

## What shipped
### Hint chrome
- `apps/api/app/ai_hint_chrome.py` — extract status/banner/alert/ribbon hints from AST/Must-do/brief; stamp `_hint_chrome`; inject `//sheet` alert/ribbon IR; never Char fields.
- Wired in `finish_senior_component` after form slots.
- `build_form_preview` stamps `alerts[]` for canvas.
- Web: `OdooFormView` renders alert chrome; CSS levels info/warning/danger.

### Flash enrich toggle
- `intent_llm_enabled()` honors request/connection override via contextvar.
- `studio_prefs` stores `flash_ast_enrich` on connection `ingest_prefs_json.studio`.
- API: `GET/PATCH /connections/{id}/studio/prefs`; create session accepts `flash_ast_enrich`.
- Studio brief UI: **"Enrich Must-do with Flash"** checkbox (off = det floor only).

### Precedence
1. Request body / UI toggle for this session  
2. Connection studio pref  
3. `AI_INTENT_LLM` env (`off`/`on`/`auto`; product default when unset: **auto**)

## Tests
`AI_INTENT_LLM=off` goldens + new hint-chrome + toggle tests — **90 passed**.

## How Tope uses it
1. Open App Studio on a connection.
2. On the brief screen, toggle **Enrich Must-do with Flash** (persists for that connection).
3. Prefer Sales re-Build: Must-do still has status hint; canvas shows warning banner; Apply IR has alert widget — no Char field from hint prose.
