# V-CONNECT-FREEZE

Date: 22 Oct 2026. Worker. No product change. No database opened. No timing taken.

## Claim

- AC1 / `H-3.2-FREEZE`: Connect page freezes; measure before and after with 16k rows. §3.2 L216–L218.
- AC2 / `UIF-FREEZE`: named failure, frozen Connect page. §5.15 L722.

Card definitions, not re-measured here: `before` = time to materialise the full list; `after` = time until the first `SAVED_PAGE` cards paint. A freeze is a main-thread long task ≥ 50 ms before that paint.

## Commands run

```bash
nl -ba docs/specs/INGENIUM_MASTER_HANDOVER.md | sed -n '216,218p;722p'
rg -n "listConnections|SAVED_PAGE|shownSaved" apps/web/src/app/connect/page.tsx apps/web/src/lib/api/connections.ts
rg -n -A 6 "def list_connections" apps/api/app/routers/connections.py
```

Symbol lines were read before they were copied: `apps/web/src/lib/api/connections.ts` L5–L7, `apps/web/src/app/connect/page.tsx` L10, L100, L659, and `list_connections` at `apps/api/app/routers/connections.py` L86–L93 (decision table: does `GET /api/connections` return every row).

## Measured result

Handover, re-checked 22 Oct 2026:

| Line | Text |
|---|---|
| L216 | Freeze sentence. 16,014 rows in one 10.5 MB response is labelled [Verified 21 Oct]. Cause is labelled [Inferred cause]. |
| L217 | Blank. |
| L218 | "Frozen page". |
| L722 | "Frozen Connect page". Evidence cell: "follows from the above [Inferred]". |

`rg` on the two client files: 11 matching lines.

| File:line | What is there |
|---|---|
| `connections.ts:5-7` | `connectionsApi.listConnections` calls `request<Connection[]>("/api/connections", { timeoutMs: CONNECTION_READ_TIMEOUT_MS })`. No limit, offset, or page. The timeout is not a row cap. |
| `page.tsx:10` | `SAVED_PAGE = 50`. |
| `page.tsx:92` | `savedLimit` starts at `SAVED_PAGE`. |
| `page.tsx:94-100` | `matchingSaved` is the full filtered, sorted array. `shownSaved = matchingSaved.slice(0, savedLimit)`. |
| `page.tsx:175-176` | `api.listConnections()` then `setConnections(rows)`. The page holds every returned `Connection`. |
| `page.tsx:659` | `shownSaved.map` renders the slice. |
| `page.tsx:809-815` | "Show more" adds another `SAVED_PAGE`. |

`list_connections` (`connections.py` L86–L93): no limit argument. `scoped_connection_query(...).order_by(...).all()` then a list of every row. `GET /api/connections` materialises the full list.

Code comment at `page.tsx` L91 mentions a past 16,000-row freeze. That comment is not a timing.

## Verdict

**partial.** STOP.

Paint of saved-connection cards is capped at `SAVED_PAGE` (50). The endpoint is not paginated, and `connections` state holds every row the endpoint returns. The false row of the decision table does not apply.

The true row needs a 16_000-row run on a disposable `ingenium_*` database showing a long task ≥ 50 ms before the first 50 cards paint. That run was not done. No timing is recorded.

The only counted 16,014-row response is the prior [Verified 21 Oct] label in §3.2 L216. This session did not open a database and did not read `.env`. Timing that existing store would use a non-`ingenium_*` database unless its name starts with `ingenium_`, which was not checked. That is the STOP.

## Label proposal

Do not upgrade a label.

- Unpaginated `GET /api/connections`, full array held in `connections`, first card paint sliced to 50: [Done, code], 22 Oct 2026, commands above.
- Freeze / long task: leave [Inferred]. `UIF-FREEZE` stays Inferred. `H-3.2-FREEZE` stays Reported.
- 16,014 rows and 10.5 MB: leave [Verified 21 Oct]. Not re-measured.

## Proposed ledger row

Do not apply it in this card.

| ID | one_line | card |
|---|---|---|
| H-3.2-FREEZE | Connect still loads every saved connection and paints 50 cards; 16_000-row long-task timing was not run on an ingenium_* database | V-CONNECT-FREEZE |

## Command not run

Disposable app database only. The database name must start with `ingenium_`. Do not point `DATABASE_URL` at any other database. Do not use ports 3002, 8001, 8002, 8012, 5433, 5436, 8069–8073, or 11434. Drop the database when finished. `list_connections` does not decrypt `secret_encrypted` and does not call the saved URL. `AUTH_MODE=off` (local default) and `workspace_id` NULL make `scoped_connection_query` return every row. `assert_connection_limit` does not cap a null workspace, so seed with SQL, not `POST /api/connections`.

`upgrade_detected` has no server default (`apps/api/alembic/versions/65cd29676b8f_baseline.py`). `write_mode` defaults to `observer`. `writes_paused` defaults to false.

```bash
# NOT RUN 22 Oct 2026. No number from this block is evidence.
# Free Postgres port must not be 5433 or 5436. Example name: ingenium_v_connect_freeze.
createdb -h 127.0.0.1 -p "$PGPORT" ingenium_v_connect_freeze
cd apps/api && DATABASE_URL="postgresql://127.0.0.1:$PGPORT/ingenium_v_connect_freeze" alembic upgrade head
psql "postgresql://127.0.0.1:$PGPORT/ingenium_v_connect_freeze" -v ON_ERROR_STOP=1 -c "
INSERT INTO odoo_connections (id, name, url, db_name, username, secret_encrypted, upgrade_detected, write_mode, writes_paused)
SELECT gen_random_uuid()::text, 'freeze-' || i, 'http://127.0.0.1:9', 'ingenium_unused', 'u', 'unused', false, 'observer', false
FROM generate_series(1, 16000) AS s(i);
"
# API on 8101+ (not 8001). Web on 3017+ (not 3002). AUTH_MODE=off. DATABASE_URL as above.
# before: time until GET /api/connections is parsed and the array length is 16000.
# after: time until [data-testid^=\"connect-row-\"] count is 50 (SAVED_PAGE).
# Record PerformanceObserver longtask entries with duration >= 50.
dropdb -h 127.0.0.1 -p "$PGPORT" ingenium_v_connect_freeze
```
