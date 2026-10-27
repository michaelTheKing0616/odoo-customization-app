"use client";

import { Virtuoso } from "react-virtuoso";
import {
  SAVED_CONNECTION_OVERSCAN_MAX,
  SAVED_CONNECTION_ROW_PX,
  SAVED_CONNECTIONS_VIEWPORT_PX,
  clampSavedListOverscan,
  savedConnectionsViewportPx,
  type SavedConnectionRow,
} from "@/lib/connectScreen";

export function SavedConnectionsList({
  items,
  viewportHeight = SAVED_CONNECTIONS_VIEWPORT_PX,
  overscan = SAVED_CONNECTION_OVERSCAN_MAX,
}: {
  items: readonly SavedConnectionRow[];
  viewportHeight?: number;
  overscan?: number;
}) {
  const clamped = clampSavedListOverscan(overscan);
  const overscanItems = clamped.ok ? clamped.overscan : SAVED_CONNECTION_OVERSCAN_MAX;
  const height = savedConnectionsViewportPx(viewportHeight);

  return (
    <section
      aria-label="Saved connections"
      className="bg-surface text-ink"
      data-testid="saved-connections-list"
    >
      <Virtuoso
        data={items}
        style={{ height }}
        increaseViewportBy={0}
        minOverscanItemCount={0}
        overscan={overscanItems}
        fixedItemHeight={SAVED_CONNECTION_ROW_PX}
        computeItemKey={(_index, row) => row.id}
        itemContent={(_index, row) => (
          <article
            data-testid="saved-connection-row"
            data-connection-id={row.id}
            className="box-border flex h-11 items-center gap-3 border-b border-border-subtle px-3"
          >
            <span className="min-w-0 flex-1 truncate text-ui-body text-ink">{row.name}</span>
            <span className="min-w-0 truncate text-ui-label text-muted">{row.db_name}</span>
          </article>
        )}
      />
    </section>
  );
}
