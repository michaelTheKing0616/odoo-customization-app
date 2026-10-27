/**
 * F1-PAGINATE. AC1 contract lives in connectScreen and GET /api/connections.
 * AC3 (Playwright), AC4 (hydrate), and AC5 (Alembic) are not this file.
 */
/** @vitest-environment jsdom */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { VirtuosoMockContext } from "react-virtuoso";
import { afterEach, describe, expect, it } from "vitest";
import { SavedConnectionsList } from "@/app/connections/SavedConnectionsList";
import {
  SAVED_CONNECTION_OVERSCAN_MAX,
  SAVED_CONNECTION_ROW_PX,
  SAVED_CONNECTIONS_VIEWPORT_PX,
  applyConnectionsQuery,
  clampSavedListOverscan,
  nextSavedConnectionsQuery,
  savedConnectionMountCap,
  savedConnectionsViewportPx,
  type SavedConnectionRow,
} from "@/lib/connectScreen";

afterEach(() => {
  cleanup();
});

function renderSaved(
  items: readonly SavedConnectionRow[],
  viewportHeight: number,
  overscan?: number,
) {
  const height = savedConnectionsViewportPx(viewportHeight);
  return render(
    createElement(
      VirtuosoMockContext.Provider,
      { value: { viewportHeight: height, itemHeight: SAVED_CONNECTION_ROW_PX } },
      createElement(SavedConnectionsList, {
        items,
        viewportHeight,
        ...(overscan === undefined ? {} : { overscan }),
      }),
    ),
  );
}

async function mountedIds(): Promise<string[]> {
  await waitFor(() => {
    expect(screen.getAllByTestId("saved-connection-row").length).toBeGreaterThan(0);
  });
  return screen.getAllByTestId("saved-connection-row").map((node) => node.getAttribute("data-connection-id") ?? "");
}

function indexedRows(count: number): SavedConnectionRow[] {
  return Array.from({ length: count }, (_, index) => ({
    id: String(index),
    name: `Shop ${index}`,
    url: `https://odoo.example/${index}`,
    db_name: `db_${index}`,
    group_label: "North",
  }));
}

describe("F1-PAGINATE", () => {
  it("AC1 pages search and group before the default 50", () => {
    const lookalike: SavedConnectionRow = {
      id: "lookalike",
      name: "North lookalike",
      url: "https://south.example/1",
      db_name: "db_south",
      group_label: "South",
    };
    const quiet: SavedConnectionRow = {
      id: "quiet",
      name: "Quiet shop",
      url: "https://example.test/quiet",
      db_name: "quiet_db",
      group_label: "North",
    };
    const north: SavedConnectionRow[] = Array.from({ length: 80 }, (_, index) => ({
      id: `n-${index}`,
      name: `North shop ${index}`,
      url: `https://north.example/${index}`,
      db_name: `db_${index}`,
      group_label: "North",
    }));

    const page = applyConnectionsQuery([lookalike, quiet, ...north], {
      search: "north.example",
      group: "North",
    });

    expect(page).toMatchObject({
      ok: true,
      total: 80,
      limit: 50,
      offset: 0,
      nextOffset: 50,
      path: "/api/connections?limit=50&offset=0&q=north.example&group=North",
    });
    if (!page.ok) return;
    expect(page.items.map((row) => row.id)).toEqual(Array.from({ length: 50 }, (_, index) => `n-${index}`));
  });

  it("AC1 rejects a limit above 200", () => {
    const rows: SavedConnectionRow[] = [
      {
        id: "n-0",
        name: "North shop 0",
        url: "https://north.example/0",
        db_name: "db_0",
        group_label: "North",
      },
    ];
    expect(applyConnectionsQuery(rows, { search: "north.example", group: "North", limit: 201 })).toEqual({
      ok: false,
      status: 422,
      detail: "limit must be from 1 to 200",
    });
  });

  it("AC2 mounts only the rows that fit plus overscan", async () => {
    expect(SAVED_CONNECTIONS_VIEWPORT_PX).toBe(440);
    expect(SAVED_CONNECTION_ROW_PX).toBe(44);
    expect(SAVED_CONNECTION_OVERSCAN_MAX).toBe(2);
    expect(savedConnectionMountCap(440, 44, 2)).toEqual({ ok: true, mountAtMost: 14 });

    renderSaved(indexedRows(400), 440);
    const ids = await mountedIds();
    expect(ids.length).toBeGreaterThan(0);
    expect(ids.length).toBeLessThanOrEqual(14);
    expect(ids).not.toContain("399");
  });

  it("AC2 refuses an overscan that would mount the whole list", async () => {
    expect(clampSavedListOverscan(16000)).toEqual({
      ok: false,
      status: 422,
      detail: "overscan must be an integer from 0 to 2",
    });
    expect(savedConnectionMountCap(440, 44, 16000)).toEqual({
      ok: false,
      status: 422,
      detail: "overscan must be an integer from 0 to 2",
    });

    renderSaved(indexedRows(400), 440, 16000);
    const ids = await mountedIds();
    expect(ids.length).toBeGreaterThan(0);
    expect(ids.length).toBeLessThanOrEqual(14);
    expect(ids).not.toContain("399");
  });

  it("AC6 does not mount 16000 row nodes", async () => {
    renderSaved(indexedRows(16000), 440);
    const ids = await mountedIds();
    expect(ids.length).toBeGreaterThan(0);
    expect(ids.length).toBeLessThanOrEqual(14);
    expect(ids).not.toContain("15999");
  });

  it("AC6 rejects a zero viewport instead of mounting every row", async () => {
    expect(savedConnectionMountCap(0, 44, 2)).toEqual({
      ok: false,
      status: 422,
      detail: "viewport and row height must be positive",
    });
    expect(savedConnectionsViewportPx(0)).toBe(440);

    renderSaved(indexedRows(16000), 0);
    const ids = await mountedIds();
    expect(ids.length).toBeGreaterThan(0);
    expect(ids.length).toBeLessThanOrEqual(14);
    expect(ids).not.toContain("15999");
  });

  it("AC7 keeps search and paging on a bounded query", async () => {
    const rows: SavedConnectionRow[] = Array.from({ length: 16000 }, (_, index) => ({
      id: String(index),
      name: index < 80 ? `Lagos shop ${index}` : `Abuja shop ${index}`,
      url: `https://example.test/${index}`,
      db_name: `db_${index}`,
      group_label: index < 80 ? "West" : "East",
    }));

    const searched = nextSavedConnectionsQuery(
      { limit: 50, offset: 100, search: "", group: "" },
      { search: "lagos" },
    );
    expect(searched).toEqual({
      ok: true,
      limit: 50,
      offset: 0,
      search: "lagos",
      group: "",
      path: "/api/connections?limit=50&offset=0&q=lagos",
    });
    if (!searched.ok) return;

    const paged = nextSavedConnectionsQuery(searched, { offset: 50 });
    expect(paged).toEqual({
      ok: true,
      limit: 50,
      offset: 50,
      search: "lagos",
      group: "",
      path: "/api/connections?limit=50&offset=50&q=lagos",
    });
    if (!paged.ok) return;

    const page = applyConnectionsQuery(rows, paged);
    expect(page.ok).toBe(true);
    if (!page.ok) return;
    expect(page.total).toBe(80);
    expect(page.items.map((row) => row.id)).toEqual(
      Array.from({ length: 30 }, (_, index) => String(50 + index)),
    );

    renderSaved(page.items, 440);
    const ids = await mountedIds();
    expect(ids.length).toBeGreaterThan(0);
    expect(ids.length).toBeLessThanOrEqual(14);
    expect(ids).not.toContain("79");
  });

  it("AC7 rejects a page large enough to freeze the list", () => {
    expect(nextSavedConnectionsQuery({ limit: 50, offset: 0, search: "lagos" }, { limit: 16000 })).toEqual({
      ok: false,
      status: 422,
      detail: "limit must be from 1 to 200",
    });
  });
});
