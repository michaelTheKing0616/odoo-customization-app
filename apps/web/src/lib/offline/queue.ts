/** IndexedDB offline queue. Promote is never flushed automatically. */

export const CONFIRM_PHRASE = "I understand the risks";
export const FLUSH_PATH = "/api/offline/flush";
export const DEFAULT_DB_NAME = "ingenium-offline-queue";
export const STORE_NAME = "queue";
export const INITIAL_BACKOFF_MS = 1_000;
export const MAX_BACKOFF_MS = 60_000;

const ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

export type QueueKind = "mutation" | "promote";
export type QueueStatus = "queued" | "flushing" | "acked" | "awaiting_confirm" | "failed";
export type QueueMethod = "POST" | "PUT" | "PATCH" | "DELETE";

export type OfflineQueueItem = {
  id: string;
  kind: QueueKind;
  method: QueueMethod;
  path: string;
  body: Record<string, unknown>;
  createdAt: number;
  attempts: number;
  nextAttemptAt: number;
  status: QueueStatus;
  lastError?: string;
};

export type EnqueueInput = {
  kind: QueueKind;
  method?: QueueMethod;
  path: string;
  body?: Record<string, unknown>;
};

export type ConfirmFlags = {
  confirm_advanced: boolean;
  confirm_phrase: string;
};

export type QueueOptions = {
  dbName?: string;
  fetchImpl?: typeof fetch;
  now?: () => number;
  idbFactory?: IDBFactory;
};

export type FlushResult = {
  flushed: OfflineQueueItem[];
  skippedPromote: OfflineQueueItem[];
  failed: OfflineQueueItem[];
};

function randomEntropy(): Uint8Array {
  const bytes = new Uint8Array(10);
  const cryptoObj = globalThis.crypto;
  if (cryptoObj?.getRandomValues) {
    cryptoObj.getRandomValues(bytes);
    return bytes;
  }
  for (let i = 0; i < bytes.length; i += 1) {
    bytes[i] = Math.floor(Math.random() * 256);
  }
  return bytes;
}

export function newUlid(nowMs: number = Date.now(), entropy: Uint8Array = randomEntropy()): string {
  if (!Number.isFinite(nowMs) || nowMs < 0 || nowMs > 0xffffffffffff) {
    throw new RangeError("ULID time out of range");
  }
  if (entropy.length < 10) {
    throw new Error("ULID entropy must be 10 bytes");
  }
  let time = Math.floor(nowMs);
  let timeChars = "";
  for (let i = 0; i < 10; i += 1) {
    timeChars = ULID_ALPHABET[time % 32] + timeChars;
    time = Math.floor(time / 32);
  }
  let bits = BigInt(0);
  for (let i = 0; i < 10; i += 1) {
    bits = (bits << BigInt(8)) | BigInt(entropy[i]);
  }
  let randChars = "";
  for (let i = 0; i < 16; i += 1) {
    randChars = ULID_ALPHABET[Number(bits & BigInt(31))] + randChars;
    bits >>= BigInt(5);
  }
  return timeChars + randChars;
}

export function backoffMs(attempts: number): number {
  const exp = Math.max(0, Math.floor(attempts));
  return Math.min(MAX_BACKOFF_MS, INITIAL_BACKOFF_MS * 2 ** exp);
}

export function isPromote(item: Pick<OfflineQueueItem, "kind">): boolean {
  return item.kind === "promote";
}

function requireIndexedDb(factory: IDBFactory | undefined): IDBFactory {
  if (!factory) {
    throw new Error("IndexedDB is required for the offline queue");
  }
  return factory;
}

function openDatabase(factory: IDBFactory, dbName: string): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = factory.open(dbName, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error("indexedDB open failed"));
  });
}

function cloneItem(item: OfflineQueueItem): OfflineQueueItem {
  return {
    ...item,
    body: { ...item.body },
  };
}

function putItem(db: IDBDatabase, item: OfflineQueueItem): Promise<OfflineQueueItem> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    tx.objectStore(STORE_NAME).put(item);
    tx.oncomplete = () => resolve(cloneItem(item));
    tx.onerror = () => reject(tx.error ?? new Error("indexedDB put failed"));
  });
}

function getAllItems(db: IDBDatabase): Promise<OfflineQueueItem[]> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const req = tx.objectStore(STORE_NAME).getAll();
    req.onsuccess = () => {
      const rows = (req.result as OfflineQueueItem[] | undefined) ?? [];
      resolve(rows.map(cloneItem).sort((a, b) => a.createdAt - b.createdAt || a.id.localeCompare(b.id)));
    };
    tx.onerror = () => reject(tx.error ?? new Error("indexedDB getAll failed"));
  });
}

function claimItem(
  db: IDBDatabase,
  id: string,
  now: number,
  allowed: (item: OfflineQueueItem) => boolean,
): Promise<OfflineQueueItem | null> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    const getReq = store.get(id);
    let claimed: OfflineQueueItem | null = null;
    getReq.onsuccess = () => {
      const item = getReq.result as OfflineQueueItem | undefined;
      if (!item || !allowed(item)) {
        return;
      }
      const next = cloneItem(item);
      next.status = "flushing";
      next.nextAttemptAt = now + backoffMs(next.attempts);
      store.put(next);
      claimed = next;
    };
    tx.oncomplete = () => resolve(claimed);
    tx.onerror = () => reject(tx.error ?? new Error("indexedDB claim failed"));
  });
}

function confirmFlagsAreValid(flags: ConfirmFlags | undefined): flags is ConfirmFlags {
  return Boolean(
    flags &&
      flags.confirm_advanced === true &&
      (flags.confirm_phrase || "").trim() === CONFIRM_PHRASE,
  );
}

export type OfflineQueue = {
  enqueue: (input: EnqueueInput) => Promise<OfflineQueueItem>;
  list: () => Promise<OfflineQueueItem[]>;
  pending: () => Promise<OfflineQueueItem[]>;
  flushReady: () => Promise<FlushResult>;
  confirmPromote: (id: string, flags: ConfirmFlags) => Promise<OfflineQueueItem>;
  close: () => void;
};

export function createOfflineQueue(options: QueueOptions = {}): OfflineQueue {
  const dbName = options.dbName ?? DEFAULT_DB_NAME;
  const factory = requireIndexedDb(options.idbFactory ?? globalThis.indexedDB);
  const fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis);
  const now = options.now ?? Date.now;
  let dbPromise: Promise<IDBDatabase> | null = null;
  let closed = false;
  let lastCreatedAt = Number.NEGATIVE_INFINITY;

  function nextCreatedAt(): number {
    const t = now();
    const createdAt = t > lastCreatedAt ? t : lastCreatedAt + 1;
    lastCreatedAt = createdAt;
    return createdAt;
  }

  function db(): Promise<IDBDatabase> {
    if (closed) {
      throw new Error("offline queue is closed");
    }
    if (!dbPromise) {
      dbPromise = openDatabase(factory, dbName);
    }
    return dbPromise;
  }

  async function postFlush(item: OfflineQueueItem, flags?: ConfirmFlags): Promise<void> {
    const res = await fetchImpl(FLUSH_PATH, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": item.id,
      },
      body: JSON.stringify({
        kind: item.kind,
        method: item.method,
        path: item.path,
        body: item.body,
        confirm_advanced: flags?.confirm_advanced ?? false,
        confirm_phrase: flags?.confirm_phrase ?? null,
      }),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`flush failed (${res.status}): ${text.slice(0, 200)}`);
    }
  }

  async function finishSuccess(item: OfflineQueueItem): Promise<OfflineQueueItem> {
    const next = cloneItem(item);
    next.status = "acked";
    delete next.lastError;
    return putItem(await db(), next);
  }

  async function finishFailure(
    item: OfflineQueueItem,
    error: unknown,
    restore: QueueStatus,
  ): Promise<OfflineQueueItem> {
    const next = cloneItem(item);
    next.status = restore;
    next.attempts += 1;
    next.nextAttemptAt = now() + backoffMs(next.attempts);
    next.lastError = error instanceof Error ? error.message : String(error);
    return putItem(await db(), next);
  }

  function mutationClaimable(item: OfflineQueueItem): boolean {
    if (isPromote(item) || item.status === "acked" || item.status === "failed") {
      return false;
    }
    if (item.status === "awaiting_confirm") {
      return false;
    }
    return item.nextAttemptAt <= now();
  }

  function promoteClaimable(item: OfflineQueueItem): boolean {
    return isPromote(item) && item.status !== "acked" && item.status !== "failed";
  }

  return {
    async enqueue(input: EnqueueInput): Promise<OfflineQueueItem> {
      const createdAt = nextCreatedAt();
      const item: OfflineQueueItem = {
        id: newUlid(createdAt),
        kind: input.kind,
        method: input.method ?? "POST",
        path: input.path,
        body: input.body ?? {},
        createdAt,
        attempts: 0,
        nextAttemptAt: createdAt,
        status: input.kind === "promote" ? "awaiting_confirm" : "queued",
      };
      return putItem(await db(), item);
    },

    async list(): Promise<OfflineQueueItem[]> {
      return getAllItems(await db());
    },

    async pending(): Promise<OfflineQueueItem[]> {
      const items = await getAllItems(await db());
      return items.filter((item) => item.status !== "acked");
    },

    async flushReady(): Promise<FlushResult> {
      const items = await getAllItems(await db());
      const skippedPromote = items.filter(isPromote);
      const flushed: OfflineQueueItem[] = [];
      const failed: OfflineQueueItem[] = [];
      for (const item of items) {
        if (isPromote(item)) {
          continue;
        }
        const claimed = await claimItem(await db(), item.id, now(), mutationClaimable);
        if (!claimed) {
          continue;
        }
        try {
          await postFlush(claimed);
          flushed.push(await finishSuccess(claimed));
        } catch (error) {
          failed.push(await finishFailure(claimed, error, "queued"));
        }
      }
      return { flushed, skippedPromote, failed };
    },

    async confirmPromote(id: string, flags: ConfirmFlags): Promise<OfflineQueueItem> {
      if (!confirmFlagsAreValid(flags)) {
        throw new Error("queued promote still requires a human confirm");
      }
      const claimed = await claimItem(await db(), id, now(), promoteClaimable);
      if (!claimed) {
        const items = await getAllItems(await db());
        const found = items.find((item) => item.id === id);
        if (!found) {
          throw new Error("queued promote not found");
        }
        if (found.status === "acked") {
          return found;
        }
        throw new Error("queued promote still requires a human confirm");
      }
      try {
        await postFlush(claimed, flags);
        return finishSuccess(claimed);
      } catch (error) {
        await finishFailure(claimed, error, "awaiting_confirm");
        throw error;
      }
    },

    close() {
      closed = true;
      if (dbPromise) {
        void dbPromise.then((opened) => opened.close()).catch(() => undefined);
        dbPromise = null;
      }
    },
  };
}
