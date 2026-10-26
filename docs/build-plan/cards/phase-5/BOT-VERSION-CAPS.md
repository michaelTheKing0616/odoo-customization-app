# BOT-VERSION-CAPS: Odoo version-capability catalogue (17-20)

**Why (t449u):** checks must be made against what is *possible* in the target Odoo version, not
only what the live database has installed, so a design can say "available in Odoo N via module X;
needs install" before the user installs X.

**What:** `apps/api/app/bots/versioncaps/` (lookups) + `data/caps_<v>.json.gz` (generated) +
`apps/api/scripts/gen_versioncaps.py` (rerunnable generator).

- Generation: public XML-RPC only, clean-room. Disposable sandbox per version, install every
  installable Community module (skips `l10n_*` except `l10n_generic_coa`, `theme_*`, `test_*`,
  `hw_*`), bisect batches, failures recorded as `not_introspectable`. Reads `ir.module.module`
  (+dependencies), `ir.model`, `ir.model.fields` (`modules`), `ir.model.fields.selection`.
- Enterprise: from the reviewed `fitgap_table.json` -> `enterprise_modules`; models/fields never
  guessed ("enterprise-only; fields not verifiable").
- API: `module_info`, `model_info`, `field_info`, `find_module_for`, `availability` ->
  installed-ok / available-needs-install (module, missing depends) / enterprise-only /
  not-in-this-version (+ other versions) / unknown. `install_reason` adapter for cannot-read text.
- Fail closed: unknown version, missing/corrupt data, non-introspected module -> `unknown`.
- Integration: `process_design._ground` consults caps when a model or fields are absent from the
  live inventory (stock-install with depends chain; needs-custom only when not in that version
  and no non-introspected/Enterprise module could provide it). `configverify` cannot-read
  reasons add "available in Odoo N via module X; needs install" (guarded; old wording on fault).
- Variance: **not wired at runtime yet.** Only the `install_reason` adapter plus a test that every
  model/field in `variance/metrics.json` exists in the 17-20 catalogues. Runtime wiring is a
  follow-up.
- Custom/Studio fields (`x_*`) get no catalogue claim. Odd input or a corrupt/truncated/mis-shaped
  data file -> `unknown`, never an exception.

Depends refresh without a full install (same values; dependency rows come from the apps list):
`python apps/api/scripts/gen_versioncaps.py 17 18 19 20 --depends-only`.

Regenerate: `python apps/api/scripts/gen_versioncaps.py 17 18 19 20 [--port-base 18300]`.

## Review follow-ups

1. Models and fields in the shipped files come from the earlier full all-modules run; only depends were regenerated with --depends-only. A full rerun with the fixed script should give the same files but is unproven (25-40 min per version).
2. Whole-model absences return unknown when unread or Enterprise modules could provide them, so account.group on 20 says unknown.
3. Variance runtime wiring: adapter and test only today.
4. Localisations (l10n_*) and themes are not read, so they return unknown.
5. The module that defines a field is a best guess (the most basic module) when several declare it.
6. Enterprise models and fields are never verified.
7. One module per version has no depends (presumably base).
8. Config verify treats a DB as Enterprise only if web_enterprise is installed; process design and variance take the version only from the spec odoo_major.
9. Wire the catalogue into BOT-OPERATOR-FLOW / BOT-CLIENT-DOC when built.
