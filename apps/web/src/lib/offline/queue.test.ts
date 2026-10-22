import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  CONFIRM_PHRASE,
  backoffMs,
  createOfflineQueue,
  newUlid,
  type ConfirmFlags,
  type OfflineQueue,
} from "./queue";

const CONFIRM: ConfirmFlags = {
  confirm_advanced: true,
  confirm_phrase: CONFIRM_PHRASE,
};

type FlushCall = {
  key: string;
  kind: string;
  confirm_advanced: boolean;
};

function installMemoryIndexedDb() {
  const databases = new Map<string, Map<string, Record<string, unknown>>>();
  const locks = new Map<string, Promise<void>>();

  function enqueueExclusive(dbName: string, run: () => void): Promise<void> {
    const prev = locks.get(dbName) ?? Promise.resolve();
    const next = prev.then(run);
    locks.set(
      dbName,
      next.then(
        () => undefined,
        () => undefined,
      ),
    );
    return next;
  }

  const factory: IDBFactory = {
    open(name: string) {
      const req = {
        result: undefined as IDBDatabase | undefined,
        error: null as DOMException | null,
        onsuccess: null as ((ev: Event) => void) | null,
        onerror: null as ((ev: Event) => void) | null,
        onupgradeneeded: null as ((ev: IDBVersionChangeEvent) => void) | null,
      };
      queueMicrotask(() => {
        const created = !databases.has(name);
        if (created) {
          databases.set(name, new Map());
        }
        const rows = databases.get(name)!;
        const db = {
          name,
          objectStoreNames: { contains: () => true },
          createObjectStore() {
            return {};
          },
          close() {
            return undefined;
          },
          transaction(_storeName: string, mode: IDBTransactionMode = "readonly") {
            let pending = 0;
            let releaseLock: (() => void) | undefined;
            const lock =
              mode === "readwrite"
                ? new Promise<void>((resolve) => {
                    void enqueueExclusive(name, () => {
                      resolve();
                      return new Promise<void>((done) => {
                        releaseLock = done;
                      });
                    });
                  })
                : Promise.resolve();
            const tx = {
              error: null as DOMException | null,
              oncomplete: null as ((ev: Event) => void) | null,
              onerror: null as ((ev: Event) => void) | null,
              onabort: null as ((ev: Event) => void) | null,
              objectStore() {
                const finishIfIdle = () => {
                  if (pending !== 0) {
                    return;
                  }
                  queueMicrotask(() => {
                    tx.oncomplete?.(new Event("complete"));
                    releaseLock?.();
                    releaseLock = undefined;
                  });
                };
                const runOp = <T>(fn: () => T): IDBRequest<T> => {
                  pending += 1;
                  const opReq = {
                    result: undefined as T | undefined,
                    error: null as DOMException | null,
                    onsuccess: null as ((ev: Event) => void) | null,
                    onerror: null as ((ev: Event) => void) | null,
                  };
                  void lock.then(() => {
                    try {
                      opReq.result = fn();
                      opReq.onsuccess?.(new Event("success"));
                    } catch (error) {
                      opReq.error = error as DOMException;
                      opReq.onerror?.(new Event("error"));
                    }
                    pending -= 1;
                    finishIfIdle();
                  });
                  return opReq as IDBRequest<T>;
                };
                return {
                  get(id: string) {
                    return runOp(() => {
                      const row = rows.get(String(id));
                      return row ? structuredClone(row) : undefined;
                    });
                  },
                  put(item: Record<string, unknown>) {
                    return runOp(() => {
                      rows.set(String(item.id), structuredClone(item));
                      return item.id;
                    });
                  },
                  getAll() {
                    return runOp(() => [...rows.values()].map((row) => structuredClone(row)));
                  },
                };
              },
            };
            return tx as unknown as IDBTransaction;
          },
        } as unknown as IDBDatabase;
        req.result = db;
        if (created) {
          req.onupgradeneeded?.(new Event("upgradeneeded") as IDBVersionChangeEvent);
        }
        req.onsuccess?.(new Event("success"));
      });
      return req as IDBOpenDBRequest;
    },
    deleteDatabase(name: string) {
      databases.delete(name);
      const req = {
        result: undefined,
        error: null,
        onsuccess: null as ((ev: Event) => void) | null,
        onerror: null as ((ev: Event) => void) | null,
      };
      queueMicrotask(() => req.onsuccess?.(new Event("success")));
      return req as unknown as IDBOpenDBRequest;
    },
    cmp() {
      return 0;
    },
    databases: async () => [],
  };

  const previous = globalThis.indexedDB;
  Object.defineProperty(globalThis, "indexedDB", {
    configurable: true,
    writable: true,
    value: factory,
  });
  return () => {
    Object.defineProperty(globalThis, "indexedDB", {
      configurable: true,
      writable: true,
      value: previous,
    });
    databases.clear();
  };
}

function fakeFlushServer() {
  const effects: string[] = [];
  const results = new Map<string, { applied: true; effect_seq: number }>();
  let dropNextAck = false;
  const calls: FlushCall[] = [];

  const fetchImpl: typeof fetch = async (_url, init) => {
    const headers = new Headers(init?.headers);
    const key = headers.get("Idempotency-Key") || "";
    const payload = JSON.parse(String(init?.body || "{}")) as {
      kind: string;
      confirm_advanced?: boolean;
      confirm_phrase?: string | null;
    };
    calls.push({
      key,
      kind: payload.kind,
      confirm_advanced: Boolean(payload.confirm_advanced),
    });
    if (payload.kind === "promote" && payload.confirm_advanced !== true) {
      return new Response(JSON.stringify({ detail: { requires_confirmation: true } }), {
        status: 403,
      });
    }
    if (!results.has(key)) {
      effects.push(key);
      results.set(key, { applied: true, effect_seq: effects.length });
    }
    if (dropNextAck) {
      dropNextAck = false;
      throw new TypeError("dropped ack");
    }
    return new Response(JSON.stringify(results.get(key)), { status: 200 });
  };

  return {
    fetchImpl,
    effects,
    calls,
    dropAckOnce() {
      dropNextAck = true;
    },
  };
}

describe("offline queue", () => {
  let restoreIdb: () => void;
  let clock: { now: number };
  let queue: OfflineQueue;
  let dbName: string;

  beforeEach(() => {
    restoreIdb = installMemoryIndexedDb();
    clock = { now: 1_700_000_000_000 };
    dbName = `offline-test-${newUlid(clock.now)}`;
    queue = createOfflineQueue({
      dbName,
      now: () => clock.now,
    });
  });

  afterEach(() => {
    queue.close();
    restoreIdb();
  });

  it("assigns ULID keys and exponential backoff", () => {
    const first = newUlid(clock.now, new Uint8Array(10).fill(1));
    const second = newUlid(clock.now + 1, new Uint8Array(10).fill(1));
    expect(first).toHaveLength(26);
    expect(second > first).toBe(true);
    expect(backoffMs(0)).toBe(1_000);
    expect(backoffMs(1)).toBe(2_000);
    expect(backoffMs(2)).toBe(4_000);
    expect(backoffMs(20)).toBe(60_000);
  });

  it("survives reload and a second tab", async () => {
    const stored = await queue.enqueue({
      kind: "mutation",
      path: "/api/connections/c1/fields",
      body: { name: "x_note" },
    });
    await queue.enqueue({
      kind: "promote",
      path: "/api/connections/c1/modules/promote",
      body: { validation_id: "val-1" },
    });
    queue.close();

    const afterReload = createOfflineQueue({ dbName, now: () => clock.now });
    const secondTab = createOfflineQueue({ dbName, now: () => clock.now });
    const reloaded = await afterReload.list();
    const otherTab = await secondTab.list();
    expect(reloaded.map((item) => item.id)).toEqual([stored.id, reloaded[1]?.id]);
    expect(otherTab.map((item) => item.id)).toEqual(reloaded.map((item) => item.id));
    expect(reloaded[1]?.kind).toBe("promote");
    expect(reloaded[1]?.status).toBe("awaiting_confirm");
    afterReload.close();
    secondTab.close();
  });

  it("does not auto-flush a queued promote", async () => {
    const server = fakeFlushServer();
    const live = createOfflineQueue({
      dbName,
      now: () => clock.now,
      fetchImpl: server.fetchImpl,
    });
    const mutation = await live.enqueue({
      kind: "mutation",
      path: "/api/connections/c1/fields",
    });
    const promote = await live.enqueue({
      kind: "promote",
      path: "/api/connections/c1/modules/promote",
    });

    const result = await live.flushReady();
    expect(result.flushed.map((item) => item.id)).toEqual([mutation.id]);
    expect(result.skippedPromote.map((item) => item.id)).toEqual([promote.id]);
    expect(server.calls.every((call) => call.kind !== "promote")).toBe(true);
    expect(server.effects).toEqual([mutation.id]);

    const stillQueued = (await live.list()).find((item) => item.id === promote.id);
    expect(stillQueued?.status).toBe("awaiting_confirm");
    live.close();
  });

  it("does not mark a promote flushed without a confirm flag", async () => {
    const server = fakeFlushServer();
    const live = createOfflineQueue({
      dbName,
      now: () => clock.now,
      fetchImpl: server.fetchImpl,
    });
    const promote = await live.enqueue({
      kind: "promote",
      path: "/api/connections/c1/modules/promote",
    });

    await expect(live.confirmPromote(promote.id, { confirm_advanced: false, confirm_phrase: "" })).rejects.toThrow(
      /human confirm/,
    );
    await expect(
      live.confirmPromote(promote.id, { confirm_advanced: true, confirm_phrase: "not the phrase" }),
    ).rejects.toThrow(/human confirm/);

    const pending = await live.list();
    expect(pending[0]?.status).toBe("awaiting_confirm");
    expect(server.calls).toEqual([]);

    const flushed = await live.confirmPromote(promote.id, CONFIRM);
    expect(flushed.status).toBe("acked");
    expect(server.calls).toEqual([
      { key: promote.id, kind: "promote", confirm_advanced: true },
    ]);
    live.close();
  });

  it("retries a dropped ack with the same ULID and does not double-apply", async () => {
    const server = fakeFlushServer();
    server.dropAckOnce();
    const live = createOfflineQueue({
      dbName,
      now: () => clock.now,
      fetchImpl: server.fetchImpl,
    });
    const item = await live.enqueue({
      kind: "mutation",
      path: "/api/connections/c1/fields",
    });

    const first = await live.flushReady();
    expect(first.failed).toHaveLength(1);
    expect(first.flushed).toHaveLength(0);
    expect(server.effects).toEqual([item.id]);

    clock.now += backoffMs(1);
    const second = await live.flushReady();
    expect(second.flushed.map((row) => row.id)).toEqual([item.id]);
    expect(second.flushed[0]?.status).toBe("acked");
    expect(server.effects).toEqual([item.id]);
    expect(server.calls.every((call) => call.key === item.id)).toBe(true);
    live.close();
  });

  it("two tabs flushing the same item produce one server effect", async () => {
    const server = fakeFlushServer();
    const seed = createOfflineQueue({
      dbName,
      now: () => clock.now,
      fetchImpl: server.fetchImpl,
    });
    const item = await seed.enqueue({
      kind: "mutation",
      path: "/api/connections/c1/fields",
    });
    seed.close();

    const tabA = createOfflineQueue({
      dbName,
      now: () => clock.now,
      fetchImpl: server.fetchImpl,
    });
    const tabB = createOfflineQueue({
      dbName,
      now: () => clock.now,
      fetchImpl: server.fetchImpl,
    });

    const [a, b] = await Promise.all([tabA.flushReady(), tabB.flushReady()]);
    expect([...a.flushed, ...b.flushed].map((row) => row.id)).toContain(item.id);
    expect(server.effects).toEqual([item.id]);
    expect(new Set(server.calls.map((call) => call.key))).toEqual(new Set([item.id]));
    tabA.close();
    tabB.close();
  });
});
