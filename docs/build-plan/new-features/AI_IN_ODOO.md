# AI in Odoo: How-do-I assistant, Natural-language reports, Process mining

Baseline `00_BASELINE.md` applies. Every model call goes through `app/ai_client` with `fence_fields(source=…)`, after the live schema packet (GND-GATE). Output passes a deterministic validator (INV-13).

<a id="howdo"></a>
## HOWDO: Embedded how-do-I assistant grounded in the client's config
Extends Odoo Expert / Suite Ask (`expert/ask.py`, `expert/live_schema_ask.py`, `expert/access_guidance.py`), FA-A22 (help that knows the page, card DOC-HELP), FA-S18 (Ask everywhere) and the existing Odoo addon `packages/odoo-expert-bridge` (deep-link from Odoo to the Expert panel).
1. **User / job:**
   - A client's end user inside Odoo: "How do I approve this purchase order *here*?"
   - Value: answers use the client's own menus, approval rules and required fields, not generic docs. This cuts consultant support tickets.
   - Metric:
     - On a 60-question set per seeded DB (written by the team, not holdout_fresh): ≥ 90% of answers cite only menus, actions and fields that exist and are visible to the asking user's groups, with 0 invented menus (validator).
     - Median answer ≤ 4 s cached, ≤ 12 s uncached.
2. **UX:**
   - In Odoo: the bridge addon adds a systray "?" that opens a side panel. The user asks; the answer gives steps with clickable menu paths (deep links into their Odoo) and "why" (for example "your company requires a second approval above ₦500,000", from `base.automation` or approval rules read live).
   - Thumbs up or down. "Ask my consultant" creates a portal request (PORTAL).
   - In Ingenium: the same assistant in Suite Ask, with a role switcher to "answer as <role>".
   - States: offline (Ingenium unreachable) shows "Help is offline. Your Odoo works normally".
3. **UI:**
   - Inside Odoo: minimal OWL panel using Odoo's own styles, because it lives in Odoo's UI. There is no Ingenium visual language inside Odoo; only the Ingenium mark in the header per `docs/brand/README.md`.
   - In Ingenium: area 12 Bots (Claude app).
4. **Security:**
   - The bridge addon calls Ingenium with a per-database, per-user short-lived token minted by Ingenium. The token is scoped to read-only ask and is never the integration key.
   - The answer context uses the *asking user's* groups: role x-ray computed for that uid. No record values; schema, config and rule text only, fenced.
   - Prompt injection via record names or notes is not in context by design. Questions are fenced.
   - Install: Online is unsupported (no custom modules), so it offers a link-out instead. Odoo.sh and on-prem install via sandbox → human promote (DEC-067).
5. **Robustness:**
   - Cache by `(question_norm, uid_groups_hash, schema_fingerprint)`.
   - Timeout 15 s with a graceful "try again".
   - Rate limit per Odoo user: 20 per hour by default.
   - Addon versions: OWL differs on 17 vs 18+, so there is one addon per major in `packages/odoo-expert-bridge`, gated by `compat`.
6. **Data / API:**
   - `POST /api/bridge-assist/token` body `AssistTokenRequest {connection_id, odoo_uid}` → `HowdoToken`. `odoo_uid` is `int | None`. Pinned 2026-10-22.
   - `HowdoToken {token, expires_at, scope}`. `token` is `str`. `expires_at` is `datetime`. `scope` is `str` and is `ask` for this route.
   - `POST /api/bridge-assist/ask` body `AssistAsk {question, page_context}` with the Bearer short token → `AssistAnswer`. No `connection_id` in this body. `page_context` is `dict[str, str] | None`. The usual keys are `model`, `view_type`, and `action_id`.
   - `AssistAnswer {answer_md, steps, citations, refused}`. `steps` is `[AssistStep]`. `citations` is `[AssistCitation]`. `refused` is `str | None` (the reason). Null means the answer was given.
   - `AssistStep {text, menu_path, deep_link}`.
   - `AssistCitation {kind, tech_name}`. `kind` is `Literal["doc", "field", "menu"]`.
   - Models. A contract test compares these field names and no others.
   - Auth. The token route depends on `require_api_auth` in `apps/api/app/auth.py` (the integration key: `Authorization: Bearer` or `X-API-Key`). A missing or bad integration key is 401, not 403 `ROLE_DENIED`. `/ask` depends on `require_howdo_token` in `apps/api/app/assist/auth.py` (new). It reads the Bearer short token. A missing or bad short token is 401, not 403 `ROLE_DENIED`. 403 `ROLE_DENIED` is only for a caller who is already authenticated and whose role or scope cannot do the action. HOWDO-01 stubs `require_howdo_token`. It does not check a real sign-in token.
   - Tenancy. `/ask` takes its connection from the token. `NF_HOWDO_ROUTES` is `POST /api/bridge-assist/token` and `POST /api/bridge-assist/ask`. Those paths are not connection-scoped and do not call `get_scoped_connection_or_404`. The contract test is a cross-tenant token test: a token bound to workspace A's connection does not return workspace B's menus, and the reverse. That miss is 404 with the B5 `NOT_FOUND` envelope.
   - Table `assist_feedback`.
7. **Risks / DEC:** DEC-067 (install path). HOWDO-01 stays Worker L2: it is the contract only, with the stub `require_howdo_token`. The later card that checks real sign-in tokens is L3, because that token design touches sign-in.

<a id="nlr"></a>
## NLR: Natural-language reports
Extends SUITE-04 (filters from words with a live count), T4-DASH (AI Dashboard Studio), the report designer and RD.
1. **User / job:**
   - An owner or manager: "Sales by salesperson for Lagos customers last quarter."
   - Value: answers without building pivots.
   - Metric:
     - On a 50-question set per seeded DB, ≥ 90% of produced queries execute and return the same numbers as a hand-written `read_group`.
     - 0 queries reference a model or field outside the live schema or outside the user's read access (validator).
2. **UX:**
   - Reports → Ask. Type a question and get a table and chart with "How this was computed" (model, filters, group-by, measure in plain words, and `TechName` on hover).
   - Save as: an Ingenium saved report, an Odoo favourite filter (a plan with Undo), or a dashboard tile (T4-DASH).
   - Edit the filter chips directly.
   - Huge data: `read_group` only, never raw rows above 5,000.
   - ⌘K: "Ask for a report".
3. **UI:** area 16 Charts (Stripe, Linear Insights) and area 12 for the ask box.
4. **Security:**
   - The model emits a `ReportSpec {model, domain, groupby[], measures[], order, limit}` only.
   - The validator checks every token against the live schema and allow-listed operators, and refuses `ir.*`, `res.users` password fields and `mail.*` bodies.
   - Results run as the connection user, and are shown only to Ingenium users with access to that connection. Client-mode users see only shared reports (DEC-068).
5. **Robustness:** spec execution has a 20 s timeout, with partial "too big, narrow by date?" suggestions. Results are cached for 10 min.
6. **Data / API:**
   - `POST /api/connections/{id}/nl-reports/ask {question}` → `{spec, rows[], chart:{kind, x, y}, explanation}`.
   - `POST …/nl-reports {spec, name}` → saved.
   - `POST …/nl-reports/{rid}/to-filter` → plan id.
   - Table `nl_reports`.
7. **Risks:** ambiguous dates and currencies. The explanation always states the resolved period and currency.

<a id="pmine"></a>
## PMINE: Process mining
Decomposition of BOLD-B2 (process mining). It extends FA 6.4 (approval bottleneck report) and `suite_insights.automation_catalogue`.
1. **User / job:**
   - An ops lead: "Where do orders get stuck between quote and invoice, and what should we automate?"
   - Value: evidence-based automation suggestions.
   - Metric:
     - On the seeded live DB with scripted state changes, the event log reconstructs 100% of scripted transitions, and stage durations equal the scripted ones within 1 s.
     - Each suggestion compiles to an automation plan that passes Check.
2. **UX:**
   - Explore → Process.
   - Pick a flow template (Lead → Quote → Order → Delivery → Invoice) or a model and its state field.
   - The flow map shows stages as nodes and transitions with counts and median time. Stalls are highlighted with "Quotes wait 9 days on median before sending".
   - Suggestions: "Remind the salesperson after 3 days" becomes an automation plan with Check, Approve, Run and Undo.
   - Filters: period, team, company.
   - ⌘K: "Open process map".
3. **UI:** area 10 canvas components, read-only, for the map (existing BR-CANVAS primitives), and area 16 for durations. A text table alternative is provided for a11y.
4. **Security:**
   - Reads `mail.tracking.value` (state field changes) and `create_date`, aggregated. No message bodies.
   - The window is 180 days, sampled above 200k events (DEC-072).
   - Suggestions are templates from the existing automation recipes; the model only ranks them (fenced counts).
5. **Robustness:**
   - The event extractor pages by id. Tracking field names differ on 17 vs 18+ (`field` vs `field_id`) [Inferred: verify in PMINE-LIVE], via compat.
6. **Data / API:**
   - Scan id `process`.
   - `GET /api/connections/{id}/process/flows` → templates available given the installed apps.
   - `POST …/process/runs {template|model, state_field, period}`.
   - `GET …/process/runs/{rid}` → `{nodes[{state, count}], edges[{from, to, count, median_s, p90_s}], stalls[], suggestions[{template, params, impact}]}`.
7. **Risks:** state fields without tracking yield sparse logs. The screen says "This field is not tracked, so durations are estimated from created/changed dates" and labels the result.
