# Wave 4 — TIER: four-tier hosting/edition coverage + Enterprise drivers (Document 6, generalized)

Shared context: all four tiers are first-class (Online, Odoo.sh, Community on-prem,
Enterprise). Detection per instance, never assumption by tier. Clean-room: public RPC + public
docs only; never Enterprise source. Existing code: `hosting.py` (heuristic tier),
`capabilities.py` (probes), `ee_playbooks.py` (EE surface probes), `studio_feature_recipes.py`
(honesty catalog), `preview_proxy.py`.

---

## TIER-1 — Capability matrix engine (Grok 4.5 card)

TASK: Replace hosting heuristics with an explicit machine-readable capability matrix keyed by
(capability, hosting, edition, detected modules), encoding Doc 6 §2 fully.

INPUT: `hosting.py`, `capabilities.py`, PCM-2 manifest, `schemas.py`.

CHECKLIST:
- [ ] `apps/api/app/tier_matrix.py`: capability registry — for each capability key
      (custom_models, custom_fields, views_community, views_enterprise_types, menus_actions,
      security_acl_rules, qweb_reports, xpath_inherit, images_media, base_automation,
      approval_rules_studio, property_fields, module_deploy, sandbox_parity, direct_sql,
      financial_link_only, bulk_rpc_suite, report_merge_print, …) → rule function over
      `{hosting: online|sh|onprem|unknown, edition: community|enterprise|unknown,
      installed: set[str], version: major}` returning
      `{available: yes|no|verify|plan_gated, reason, options: []}`.
- [ ] Doc 6 §2 rows encoded exactly: the always-yes core rows; base_automation/approvals =
      module-presence detection (never plan assumption); property fields = live-verify
      (probe hook filled by CMP-7); module_deploy: online no / sh git / onprem direct;
      sandbox: approximate on online, sh-staging real; direct SQL never.
- [ ] Hosting/edition detection hardened: hosting from URL heuristics + web.base.url +
      instance markers (documented, best-effort with `unknown` honesty); edition from
      installed modules (web_enterprise etc.).
- [ ] `GET /api/connections/{id}/capability-matrix` returns full evaluated matrix; probe
      populates + caches it; version-change invalidates (TIER-4 hook).
- [ ] Existing consumers migrated: `hosting.py` API preserved as a thin shim over the matrix
      (no breakage of existing tests), power-ops capabilities + automations gating read from
      it.
- [ ] Tests: matrix evaluation truth-table tests (≥20 combos), shim compatibility, endpoint.

DONE MEANS: matrix endpoint live for docker Odoo 19 (onprem/community) with correct rows;
all existing hosting/capability tests green.

DO NOT: break `test_hosting_m1.py` / power-ops capability tests; assume plan tiers from
hosting.

GATE: `uv run pytest tests/test_hosting_m1.py tests/test_capabilities_m1.py tests/test_power_ops*.py -q` + new matrix tests + RPC smoke 19.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## TIER-2 — Honest gating UX + per-tier deployment + dry-run

TASK: Wire the matrix into the product: three-options gating messages, per-tier module
deployment flows, sandbox honesty labels, and a pre-write dry-run validator.

INPUT: TIER-1 matrix; `routers/automations.py`, `export_sandbox.py`; web pages: automations,
hub export section, wizard; COPY_GUIDE gating template.

CHECKLIST:
- [ ] Automations/approvals UI + API gate on matrix: absent → the three options rendered with
      exact COPY_GUIDE text (upgrade-plan explanation / ir.cron-module path for sh+onprem /
      plainly scoped out) — user picks, nothing silently chosen.
- [ ] Deployment per tier on export/promote surfaces: onprem → existing promote;
      sh → generated `DEPLOY_ODOO_SH.md` inside the exported zip (git push steps, branch
      naming, module placement) + UI panel; online → portable-ownership panel (COPY_GUIDE
      copy) + TIER-3 links. Promote endpoint refuses online targets with the honest message
      (verify current behavior, make explicit).
- [ ] Sandbox honesty: sandbox run results on online-target connections carry
      `approximation: true` + label; sh-staging suggestion when a second sh connection exists
      in the workspace.
- [ ] Dry-run validator `POST .../module-spec/validate-live`: read-only checks against the
      live instance — field references exist, xpath anchors resolve (reuse views/parse +
      introspection), selection keys valid, menu parents exist; returns per-item pass/warn/fail.
      Wired as an automatic pre-apply step in the wizard/ModuleSpec apply flow (blocking on
      fail, overridable with confirm).
- [ ] Tests: gating decision tests per tier combo; dry-run validator against fake + live 19.

DONE MEANS: connecting a Community docker instance shows automations available; a simulated
no-base_automation instance shows the three options; dry-run catches a bad xpath before write
(live test).

DO NOT: invent gating copy (COPY_GUIDE only); auto-pick an option for the user.

GATE: pytest + RPC smoke 19 + Playwright on the gated automations page.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## TIER-3 — Apps Store packaging assist + migration assist

TASK: Two product surfaces for Online customers at the ceiling (Doc 6 §3 Gap 2).

INPUT: `export_service.py`, module-generator manifest emission, hub/export UI.

CHECKLIST:
- [ ] Store-readiness checker on export: validates manifest completeness (name, summary,
      description length, category from Odoo's category list, version format
      `<major>.0.x.y.z`, license key valid, author, website), icon present
      (`static/description/icon.png` — generate a placeholder if absent, flagged),
      `static/description/index.html` listing page scaffold generated from spec summary;
      returns a checklist report (pass/warn per item) — clearly labeled "review/approval is
      Odoo's process, on Odoo's timeline" (COPY_GUIDE).
- [ ] `POST .../export-module?store_ready=true` → zip includes the above + report.
- [ ] Migration assist: matrix-driven panel "what moving to Odoo.sh unlocks for this
      connection" — computed diff of capability rows online→sh (real automation deploy,
      true staging, shell recompute), rendered on hub + shown when a gated feature is hit;
      links Odoo's public migration docs (no legal/commercial promises).
- [ ] Tests: manifest checker matrix (good/bad manifests), zip content assertions, panel
      render test.

DONE MEANS: store-ready export of the library template passes its own checker with zero fails;
migration panel renders correct diffs from the matrix.

DO NOT: claim store approval likelihood; auto-submit anywhere.

GATE: pytest + zip inspection + web build.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## TIER-4 — Post-upgrade health check

TASK: Detect target version changes and re-validate everything we created (Doc 6 §3 Gap 4).

INPUT: TIER-1 matrix cache, snapshots store (what we created), views/parse, `jobs.py`.

CHECKLIST:
- [ ] Version watch: connection stores last_seen version/serie; probe + any RPC session start
      compares; change → flag `upgrade_detected` + auto-queue health check job.
- [ ] Health sweep (background job): for artifacts this tool created/tracked (snapshots +
      promoted modules + spec-apply journal): views still parse (fields_view_get), referenced
      fields exist, automations still resolve (model + action refs), reports render probe,
      menus/actions resolve, discovery caches (BLK-1) invalidated.
- [ ] Report: per-artifact ok/broken + reason + deep link to the owning page; stored, listed
      on Overview banner + Journal; re-runnable manually
      (`POST .../health-check/run`).
- [ ] Manual trigger works on any tier; auto-trigger emphasized for Online in copy.
- [ ] Tests: fake sweep with a broken view + missing field; version-change detection;
      job lifecycle.

DONE MEANS: simulated upgrade (edit stored version) triggers sweep; broken-view fixture is
caught and reported with a working deep link.

DO NOT: attempt auto-repair (report + link only, v1); sweep artifacts we didn't create.

GATE: pytest + RPC smoke 19 (sweep runs clean on healthy instance).

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## TIER-5 — Enterprise feature drivers

TASK: When detection confirms availability, drive Enterprise capabilities via public RPC:
Studio approval rules, EE view types, EE playbook actions.

INPUT: TIER-1 matrix; `ee_playbooks.py` (probes exist); designer + view save endpoints;
CMP-5 dependency note (approvals UI lands there; this card builds the RPC driver).

CHECKLIST:
- [ ] Studio approvals driver (`apps/api/app/ee_drivers.py`): CRUD `studio.approval.rule`
      via RPC — model/method/button binding, approver users/groups, exclusive/ordered/
      conditional (domain) attrs; field names verified LIVE against an Enterprise or
      web_studio-bearing instance IF AVAILABLE; if no such instance is available in the dev
      environment, implement against Odoo's public docs, mark each RPC call with
      `verified: pending-live` in code comments, and add `[SKIPPED-LIVE-VERIFY]` note in the
      return for the user — never fake a verification.
- [ ] EE view arch emission: generator + designer can emit map (res_partner field, routing
      attr), gantt (date_start/date_stop, progress), cohort (date_start/date_stop, measure,
      interval), grid arches — only offered when matrix says edition supports; arch
      attributes sourced from public docs; designer canvas types already exist (bind save
      paths).
- [ ] EE playbook actions (module-presence-gated, each action probed): sign — list templates
      + create sign request from a record (RPC models `sign.template`/`sign.request`);
      documents — list folders + attach a record's files into a folder; spreadsheet —
      list dashboards (read-only). Every action visible only when its module is installed.
- [ ] Matrix rows for each driver capability; honest `verify` state where live verification
      is pending.
- [ ] Tests: fake-RPC driver tests; matrix gating tests; live smoke section marked
      conditional on an Enterprise instance being configured (env
      `ODOO_EE_TEST_URL` — skip cleanly with a visible SKIP reason otherwise).

DONE MEANS: drivers implemented + fake-tested; gating correct; live verification either done
(record it) or explicitly flagged pending with the user informed.

DO NOT: consult any Enterprise source code; ship an EE action un-gated; fake live results.

GATE: pytest (fake suite) + conditional live suite + `uv run pytest tests/test_ee_playbooks_m5.py -q` (existing must stay green).

RETURN: ≤10 lines + verification status table.

DEVIATIONS: conservative + log.
