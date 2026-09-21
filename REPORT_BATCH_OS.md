# Config & Batch Operating System — ship report

Mac machine `4fc0d119-…` was unreachable from this agent box. Built on tip checkout
`/workspace/odoo-mac-tip` (branch `premium-local-tip`), then patch + APPLY for Mac path
`/Users/temitopeolaitanmichael/Odoo_Customization_App`.

## What shipped

### A. Universal batch runner — `apps/api/app/batch_os/`
Lifecycle: **intake → map → validate → dry-run → apply → audit**
Persists on existing **`bulk_runs`** table (`operation=batch_os:<recipe>`). No second job stack.
Risk tiers **L0–L3**; dry-run before apply; per-row errors.

### B. Journal Batch v1 (P0)
- CSV/XLSX upload (reuses `data_import.parse_tabular`)
- Column map → journal, date, ref, label, account, debit, credit, partner, analytic, move_group
- Validates balanced moves; resolves accounts/journals via public RPC
- Dry-run preview; Apply creates `account.move` **drafts**; optional post (L2 + confirm)
- Honesty: **Preview ≠ posted**

### C. Config Atlas
- Seed: `apps/api/app/batch_os/atlas/seed/atlas.yaml` (+ `.json` sibling)
- Accounting class **COMPLETE** (journals, CoA, taxes, FY, lock dates, opening balances, currency, payment terms, journal batch)
- Other **7** classes stubbed
- API: `GET …/batch-os/atlas`, `…/atlas/search`

### D. Recipe engine
- `accounting.journal_batch`, `accounting.opening_balances`, `accounting.lock_dates` (L3)
- Plus 7 stubs pointing at Bulk Suite / Import / App Studio

### E. UI
- **Snapshots & Journal** → tabs: Timeline | **Batch flow**
- **Instance Config** → **Config Atlas** browser (class filters + risk badges)
- App Studio untouched

### F. Tests
```bash
cd apps/api && AI_INTENT_LLM=off uv run pytest \
  tests/test_batch_os_parse_balance.py \
  tests/test_batch_os_atlas_recipes.py \
  tests/test_batch_os_journal_dry_run.py -q
# 10 passed
```

## Paths for Tope to try

1. Open connection → **Snapshots & Journal** → **Batch flow**
   - Upload a CSV with columns like: `journal,date,ref,label,account,debit,credit`
   - Map → Dry-run → Apply (phrase confirm)
2. Open **Instance Config** → scroll to **Config Atlas**
   - Filter class=Accounting; search “lock” / “journal”
3. API smoke (authed):
   - `GET /api/connections/{id}/batch-os/atlas`
   - `GET /api/connections/{id}/batch-os/recipes`
   - `POST /api/connections/{id}/batch-os/journal/intake` (multipart file)

## Apply on Mac

```bash
# from repo root on Mac, after pulling or applying patch:
bash /path/to/APPLY_BATCH_OS_ON_MAC.sh
# or: git pull origin premium-local-tip
# restart API on :8001
```

Sample CSV:

```csv
journal,date,ref,label,account,debit,credit
MISC,2024-01-15,JE1,Cash in bank,101000,1000,0
MISC,2024-01-15,JE1,Opening equity,300000,0,1000
```
