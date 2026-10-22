/**
 * Touch 140: optimistic safe actions (rename, pin, tag, reorder, test lists).
 * The change shows at once; if the server refuses, it quietly rolls back and says so.
 * Only for this app's own metadata. Writes to Odoo still go through check and approve.
 */
export async function optimistic<T>(opts: {
  apply: () => void;
  commit: () => Promise<T>;
  rollback: () => void;
  onRolledBack?: (message: string) => void;
  what?: string;
}): Promise<T | undefined> {
  opts.apply();
  try {
    return await opts.commit();
  } catch {
    opts.rollback();
    opts.onRolledBack?.(`Couldn't save ${opts.what ?? "that change"}, so it was put back. Try again.`);
    return undefined;
  }
}
