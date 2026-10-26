# TAX-CATALOGUE-IMPORT

Source: `~/.ingenium_nf/taxonomy/CARDS_PROPOSED.md` #1: check `catalogue.csv` into the repo as data, plus a loader and a schema test. Decisions (DECISIONS.md): Enterprise sandbox extraction YES and l10n sweep YES are follow-on cards (TAX-ENTERPRISE-EXTRACT, TAX-L10N-SWEEP); this card only lands the Community 17-20 catalogue.

## Scope
- Data: `apps/api/app/catalogue/data/catalogue.csv` (byte-identical to the taxonomy file, 11,929 rows, sha256 `fe99ac08…cfcbc`), pinned by `catalogue.meta.json`; `.gitattributes` keeps it `-text` so CRLF is never normalized (the pin would break).
- Loader `app/catalogue/loader.py`: fail-closed, all-or-nothing. Checks the sha pin and row count, ASCII-only, no BOM, exact header, strict CSV, id grammar and kinds, tier, versions (17-20, sorted, unique), a fixed risk profile per class (name, reversibility, blast), controls (distinct, include `audit`, human approval or FORBIDDEN/REFUSE above R2, one control set per class), formula-like cells, control characters, whitespace, cell and row caps, and duplicate ids.
- API: `load()`, `by_id()`, `tasks_for_version()`, frozen `Task`. Operator refresh: `python -m app.catalogue --import <csv>` validates first, then swaps in data and meta via temp file and rename.
- The authoritative risk decision stays in `app.bots.risk.classifier`; the catalogue is data only.

## Worker result
- Files (all new): `apps/api/app/catalogue/{__init__,__main__,loader}.py`, `apps/api/app/catalogue/data/{catalogue.csv,catalogue.meta.json,.gitattributes}`, `apps/api/tests/test_nf_tax_catalogue_import.py`, this card. No shared files were touched.
- Tests: 46 in the card file (schema, 31 adversarial defects, each asserted by refusal reason, 6 fail-closed load cases, an atomic import that leaves data untouched on a bad source, and drift checks: sha equals `bots/risk/catalogue_rows.json`, every row's class and versions match the classifier groups, and the irreversible ids exist). Run with the risk suites in both orders, twice: 2027 passed, 6 skipped each time. ruff check and format are clean.
- Caveats: the CSV's per-class control strings are the older taxonomy wording (for example `clone-rehearsal-walkthrough`), while the classifier's control map is stricter and stays authoritative. The 4 MB CSV is committed as a binary-diff file. No live Odoo is needed (data only).
