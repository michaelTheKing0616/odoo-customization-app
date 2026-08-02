# Local UAT checklist

Operator guide to test the platform on your machine. **Primary stack:** Odoo Community **19** on `:8069`. Optional permanent stacks for **18 / 17 / 16** on `:8070` / `:8071` / `:8072` (see §F).

| Service | URL / port | Default creds |
|---------|------------|----------------|
| Odoo 19 (primary) | `http://127.0.0.1:8069` | db `odoo_dev`, `admin` / `admin` |
| Odoo 18 (optional) | `http://127.0.0.1:8070` | db `odoo18_dev`, `admin` / `admin` |
| Odoo 17 (optional) | `http://127.0.0.1:8071` | db `odoo17_dev`, `admin` / `admin` |
| Odoo 16 (optional) | `http://127.0.0.1:8072` | db `odoo16_dev`, `admin` / `admin` |
| App API | `http://127.0.0.1:8000` | `AUTH_MODE=off` locally |
| Web UI | `http://127.0.0.1:3000` | — |
| App Postgres | `127.0.0.1:5433` | see `docker-compose.yml` |
| Sandbox Odoo | `http://127.0.0.1:18069` | ephemeral (`-p odoo-sandbox`, image matches connection major) |

**CI:** GitHub Actions workflow `Odoo sandbox` — manual dispatch gate `major-matrix` runs matching-major install gates (16–18 matrix or one major); not on the weekly schedule.

**Operator cadence (compat / adapters):** After changing anything under `packages/odoo-client/src/odoo_client/compat/` or list/tree normalization (`list_view_for_major`, `normalize_module_spec_list_views`, view adapters), run the matching-major ephemeral sandbox gates locally before merge:

```bash
./docker/run-sandbox-major-gate.sh 16
./docker/run-sandbox-major-gate.sh 17
./docker/run-sandbox-major-gate.sh 18
```

Use `./docker/run-sandbox-major-gate.sh` (no arg) for Odoo 19. CI `major-matrix` stays **manual dispatch only** — local gates are the pre-merge habit.

**Confirm phrase** (advanced / destructive): `I understand the risks`

**Full product guide (non-developers):** [USER-GUIDE.md](USER-GUIDE.md) — every screen, mode, and flow.

Related: [skills/library-app.md](../skills/library-app.md), [DEPLOY.md](../DEPLOY.md), plan §8 in [FULL-SCALE-LIBRARY-AND-SPEED-PLAN.md](FULL-SCALE-LIBRARY-AND-SPEED-PLAN.md).

---

## A. Bring the stack up

```bash
cd ~/Odoo_Customization_App

docker compose -f docker/docker-compose.yml up -d
./docker/wait-for-odoo.sh
./docker/init-db.sh          # once per fresh volume

uv sync
cp -n .env.example .env      # leave AUTH_MODE=off for local

# Terminal A
uv run --directory apps/api uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal B
pnpm install
pnpm --filter @odoo-custom/web dev
# optional: export NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Checks:

- [ ] `curl -sf http://127.0.0.1:8069/web/login` → HTTP 200  
- [ ] `curl -s http://127.0.0.1:8000/health` → `status` ok, `database_ok` true  
- [ ] Browser: `http://127.0.0.1:3000` loads  
- [ ] Browser: log into Odoo as `admin` / `admin` (keep tab open for Open-in-Odoo)

---

## B. Connection smoke (~5 min)

1. Open `http://127.0.0.1:3000/connect` (or create connection from home).  
2. Create connection: name `Local Dev`, URL `http://127.0.0.1:8069`, db `odoo_dev`, user/password `admin`/`admin`.  
3. Open the connection → metadata / models load.

- [ ] Connection saves and verifies  
- [ ] Model list / introspection works without errors  

---

## C. Library wizard — live metadata (~10–15 min)

1. Connection → **Wizard** (`/connections/{id}/wizard`).  
2. Display name e.g. `Acme Library` (multi-company **off** for first pass).  
3. Click **Library** → confirm phrase → Confirm.  
4. Checklist shows models / menus; use Builder / Designer links.  
5. In Odoo: you must be **logged in** to `odoo_dev` as `admin` / `admin`.

   Open the **home / app switcher** (Odoo logo or grid), not Settings’ sidebar.

   **If Acme Library is still missing after a hard refresh:** Odoo 19 caches menus in
   browser `localStorage`. Hard refresh does **not** clear that. In the Odoo tab:

   - DevTools → Console, paste and Enter:

     ```js
     localStorage.removeItem('webclient_menus');
     localStorage.removeItem('webclient_menus_version');
     location.reload();
     ```

   Or log out → log back in.

6. You should see **Acme Library** next to Discuss / Apps / Settings. Click it (opens Books)
   or use the top search for `Library Book` / `Books`.

   Under Acme Library: **Categories**, **Authors**, **Books**, **Loans**.
   Book form uses labeled groups (Identity / Catalog / Circulation). Create authors from
   the Author field (Create) or the **Authors** menu.

   Direct links (while logged in):

   - Books: `http://127.0.0.1:8069/web#action=180&model=x_lib_book&view_type=list`
   - Categories: `http://127.0.0.1:8069/web#action=179&model=x_lib_category&view_type=list`
   - Loans: `http://127.0.0.1:8069/web#action=181&model=x_lib_loan&view_type=list`

7. Create Category → Author → Book (ISBN + barcode) → Contact with email → Loan.
- [ ] Scaffold completes without error  
- [ ] After clearing menu cache (or re-login), **Acme Library** appears on home  
- [ ] Models `x_lib_category` / `x_lib_book` / `x_lib_loan` exist  
- [ ] Sample category, book, loan creatable  
- [ ] Connection page **Library** stats strip shows counts (when models exist)  

Note: full chatter / fine Python / QWeb are strongest on the **zip + sandbox** path (section E).

---

## D. Builder / Designer / Open-in-Odoo (~10 min)

1. **Builder** — open `x_lib_book`; adjust a field or add one; set M2O **on delete** if needed.  
2. **Designer** — model `x_lib_book`; edit form/list/kanban; **Save**.  
3. Click **Open in Odoo** (new tab; use existing Odoo login).  
4. Optional: **Toggle preview** — blank iframe is OK (X-Frame-Options); Open-in-Odoo is the real check.

- [ ] View save succeeds (snapshot/undo if offered)  
- [ ] Open-in-Odoo opens the model form  
- [ ] Saved layout / fields visible after refresh if needed  

Optional UI spots:

- [ ] **Reminders** (`/connections/{id}/reminders`) — create overdue reminder with confirm  
- [ ] **Projects** — create library draft → **Diff vs live** → Apply with confirm  
- [ ] Connection **Suggest depends** — suggestions appear (e.g. `mail`)  

---

## E. Portable zip + sandbox (full fidelity) (~15–25 min)

### E1. CLI gates

```bash
./docker/run-library-uat.sh
./docker/run-sandbox-library-gate.sh
./docker/run-library-functional-uat.sh
```

- [ ] `run-library-uat.sh` — all zip/spec checks PASS  
- [ ] `run-sandbox-library-gate.sh` — install OK  
- [ ] `run-library-functional-uat.sh` — all RPC checks PASS (fines, chatter, mail, report, barcode)  

Never tear down the **primary** stack when cleaning sandbox. Use project `odoo-sandbox` only:

```bash
docker compose -p odoo-sandbox -f docker/docker-compose.sandbox.yml down -v
```

### E2. UI sandbox → promote (optional)

1. Wizard **Export library zip** and/or connection **Export module**.  
2. Connection → **Sandbox** (async job banner polls; Cancel if still queued/running).  
3. On success, note `validation_id`.  
4. **Promote** with confirm phrase.  
5. In Odoo: Library menus, Print → Loan Receipt, overdue return → fine fields.

- [ ] Sandbox job succeeds  
- [ ] Promote succeeds  
- [ ] Library menu + loan receipt available on target  

---

## F. Automated tests (dev machine)

### F1. Unit / offline (no live Odoo)

```bash
uv run --directory packages/module-generator pytest -q
uv run --directory apps/api pytest -q -k "not integration"
pnpm --filter @odoo-custom/web test
```

### F2. Live Odoo integration (`pytest -m integration`)

Requires the matching Docker stack up and DB initialized (`init-db.sh`, `init-db-18.sh`, etc.).

**Odoo 19 (primary, `:8069`):**

```bash
ODOO_URL=http://127.0.0.1:8069 ODOO_DB=odoo_dev ODOO_USER=admin ODOO_PASSWORD=admin \
  uv run --directory packages/odoo-client pytest -q -m integration \
  tests/test_integration_odoo19.py

uv run --directory apps/api pytest -q -m integration
```

**Odoo 18 (`:8070`, project `odoo18`):**

```bash
docker compose -p odoo18 -f docker/docker-compose.odoo18.yml up -d
./docker/init-db-18.sh

ODOO18_URL=http://127.0.0.1:8070 ODOO18_DB=odoo18_dev ODOO18_USER=admin ODOO18_PASSWORD=admin \
  uv run --directory packages/odoo-client pytest -q -m integration \
  tests/test_integration_odoo18.py

ODOO18_URL=http://127.0.0.1:8070 ODOO18_DB=odoo18_dev \
  uv run --directory apps/api pytest -q -m integration \
  tests/test_power_ops_odoo18.py
```

**Odoo 17 (`:8071`, project `odoo17`):**

```bash
docker compose -p odoo17 -f docker/docker-compose.odoo17.yml up -d
./docker/init-db-17.sh

ODOO17_URL=http://127.0.0.1:8071 ODOO17_DB=odoo17_dev ODOO17_USER=admin ODOO17_PASSWORD=admin \
  uv run --directory packages/odoo-client pytest -q -m integration \
  tests/test_integration_odoo17.py
```

**Odoo 16 (`:8072`, project `odoo16`, experimental — no dotted update_path):**

```bash
docker compose -p odoo16 -f docker/docker-compose.odoo16.yml up -d
./docker/init-db-16.sh

ODOO16_URL=http://127.0.0.1:8072 ODOO16_DB=odoo16_dev ODOO16_USER=admin ODOO16_PASSWORD=admin \
  uv run --directory packages/odoo-client pytest -q -m integration \
  tests/test_integration_odoo16.py
```

**Matching-major ephemeral sandbox gate (`:18069`, `-p odoo-sandbox`):**

```bash
./docker/run-sandbox-major-gate.sh        # Odoo 19 (default)
./docker/run-sandbox-major-gate.sh 18
./docker/run-sandbox-major-gate.sh 17
./docker/run-sandbox-major-gate.sh 16
```

### F3. Playwright (web UI harness, no live Odoo)

```bash
# once: pnpm --filter @odoo-custom/web exec playwright install chromium
pnpm --filter @odoo-custom/web test:e2e
```

Harness routes (built with `NEXT_PUBLIC_E2E=1`): `/e2e/confirm`, `/e2e/automation-caps` (mock Odoo 16 greys out update_field / related_write).

- [ ] Unit suites green (§F1)  
- [ ] Playwright confirm + automation caps green (optional)  
- [ ] Live integration for majors you care about (§F2)

---

## G. Suggested 45–60 min happy path

1. A — stack up  
2. B — connection  
3. C — Library wizard + sample data in Odoo  
4. D — Designer save + Open-in-Odoo  
5. E1 — sandbox library + functional UAT scripts  
6. E2 — UI promote once (if practicing release flow)  

---

## Troubleshooting

| Symptom | Likely fix |
|---------|------------|
| API `database_ok: false` | App Postgres on `:5433` — `docker compose -f docker/docker-compose.yml ps` |
| Connection verify fails | Odoo up; db `odoo_dev`; `admin`/`admin` |
| Wizard / promote 403 | Exact phrase `I understand the risks` |
| iframe blank in Designer | Expected; use **Open in Odoo** while logged into Odoo |
| Web cannot reach API | `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` |
| Library sandbox install fails | Docker running; `SANDBOX_EXTRA_MODULES=contacts,mail`; do not `down -v` primary stack |
| EMFILE on `next dev` / Playwright | Use `next build && next start` for e2e; raise `ulimit -n` if needed |

---

## Human confidence (optional)

After automated §8 / E1 are green:

- [ ] Wizard scaffold in UI under ~2 minutes  
- [ ] Kanban of loans + Print → Loan Receipt in Odoo  
- [ ] Promote to a non-sandbox target and understand uninstall residuals  

---

## H. Phase 2 — functional buttons / smart counts / Automations (RPC gate)

Live script (Acme Library must already exist on `odoo_dev`):

```bash
uv run --directory packages/odoo-client python ../../scripts/smoke_library_phase2.py
# or from repo root after PYTHONPATH/uv project install:
uv run python scripts/smoke_library_phase2.py
```

Expect **PASS / FAIL = 0** for: update-field execute (`loaned`→`available`), smart count field,
next_activity (assignee falls back to `create_uid`), mail_post note, form inherit
(header + statusbar + oe_stat_button), inactive automation `mail_post`.

HTTP (API up, `AUTH_MODE=off`, connection → Local Odoo 19):

- `POST .../actions/server/update-field|next-activity|mail-post`
- `POST .../actions/smart-button` → **403** without confirm; **200** with
  `confirm_advanced` + phrase `I understand the risks`
- `POST .../views/xpath/preview`
- `POST .../automations` with `action_kind=mail_post`

UI: Designer → `x_lib_book` → Load existing view → bind Update / Activity / Mail / Smart
(with count confirm) → Save inherit → **Open in Odoo**. Automations page has Designer link
and mail_post action kind.

**Note:** Book `x_status` values are `available|loaned|lost` (not `borrowed`). Designer
selection picker uses the field’s real selection options.
