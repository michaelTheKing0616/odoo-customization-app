# V-STUDIODRAFT

Date: 2026-10-22
Measured by: Worker loop 1, before the type edit

## Historical claim

`startOptionABatch` is `request<{ session_id: string; pieces?: unknown[]; promote?: unknown }>`. That reconstructed type is the claim (handover L243; PROGRESS.md L104). `decideStudioStockApp` is also present on `studioDraftApi`.

## Command

```
rg -n "decideStudioStockApp|startOptionABatch" apps/web/src/lib/api/studio-draft.ts
rg -n -A 2 "startOptionABatch" apps/web/src/lib/api/studio-draft.ts
sed -n '243p' docs/specs/INGENIUM_MASTER_HANDOVER.md
sed -n '104p' apps/api/evals/v2/PROGRESS.md
```

Timings: n/a (not a timed run).

## Measured result

`rg -n "decideStudioStockApp|startOptionABatch"`:

```
135:  decideStudioStockApp: async (sessionId: string, decision: "install" | "decline") => {
192:  startOptionABatch: (sessionId: string) =>
```

`rg -n -A 2 "startOptionABatch"`:

```
192:  startOptionABatch: (sessionId: string) =>
193-    request<{ session_id: string; pieces?: unknown[]; promote?: unknown }>(
194-      `/api/ai/sessions/${sessionId}/option-a-batch`,
```

Handover L243 still says the return type is reconstructed. PROGRESS.md L104 still describes the 19 Oct non-repo Prettier recovery and the same reconstructed shape. Both methods exist. `pieces` and `promote` are optional `unknown`.

## Verdict

true

The historical reconstructed type was in the file when this section was measured.

## Label proposal

[Done, code] for the pre-edit claim only. DEC-031 was not settled by this section.

## After the replacement

The reconstructed `{ pieces?: unknown[]; promote?: unknown }` type is no longer the code. `startOptionABatch` returns `StudioOptionABatchResponse`: required `session_id`, `pieces: StudioOptionAPiece[]`, and `promote: StudioOptionAPromote` (`mode: "single_button"`, `label: "Promote"`, `config_required: false`). `StudioOptionAPiece` is `label`, optional `key`, `models`, `reason`, `delivery_lane`, `online_blocked` (`boolean | "true" | "false"`), and `lane_note`. No `unknown` and no index signature on that type. Decline is one POST. Install is still dry_run true, then dry_run false.

### Command

From `apps/web`:

```
rg -n -A 3 "startOptionABatch|export type StudioOptionA" apps/web/src/lib/api/studio-draft.ts
pnpm exec tsc --noEmit -p tsconfig.json
pnpm exec vitest run src/lib/api/studio-draft.live.test.ts
```

### Measured result

`rg` (after the edit): `StudioOptionAPiece` L6, `StudioOptionAPromote` L17, `StudioOptionABatchResponse` L24, `startOptionABatch` L226 returns `request<StudioOptionABatchResponse>`. `rg "pieces?: unknown[]|promote?: unknown"` on that file: 0 hits.

`pnpm exec tsc --noEmit -p tsconfig.json`: exit 2. Error count 1, not in this card: `src/lib/b0_dist.test.ts(204,36) TS5097` (import path ends in `.ts`). Allow-list files: 0 errors. That file was already committed and is outside the allow-list.

`pnpm exec vitest run src/lib/api/studio-draft.live.test.ts`: exit 0. Test files 1 passed (1). Tests 3 passed (3). Duration 3.29s (tests 3037ms). Disposable API `127.0.0.1:8099`, sqlite `ingenium_v_studiodraft.db`, Odoo stub on `127.0.0.1` outside 8069–8073. Server stopped. Sqlite file removed.

The live test called real `startOptionABatch` (existing child; parent batch status stayed `ready_to_author`), real decline (one POST, stopped session, HTTP 200), and real install (dry_run true then dry_run false; stub `button_immediate_install` only after the preview).

### Verdict

true

DEC-031 is resolved by this test. The historical reconstructed type was true before the edit and is no longer the code after it.

### Label proposal

[Done, live]
