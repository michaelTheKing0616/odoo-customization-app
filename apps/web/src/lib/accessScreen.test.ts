import { describe, expect, it } from "vitest";
import type { AccessMatrixOut, Connection } from "@/lib/api";
import {
  accessEmptyGuide,
  accessErrorGuide,
  accessVersionFrame,
  accessWriteGate,
  approvalsHref,
  describeChange,
  effectivePerm,
  findMatrixCell,
  isPermStaged,
  matrixCellEditable,
  matrixCellLockReason,
  normalizeMatrix,
  splitGroupName,
  stagedChanges,
  stagedCount,
  stagePerm,
} from "./accessScreen";

const MATRIX: AccessMatrixOut = {
  models: ["sale.order"],
  groups: [
    { id: 2, name: "User", full_name: "Sales / User", share: false },
    { id: 3, name: "Administrator", full_name: "Sales / Administrator", share: false },
  ],
  cells: [
    {
      model: "sale.order",
      group_id: 2,
      access_id: 21,
      name: "Order user",
      perm_read: true,
      perm_write: true,
      perm_create: false,
      perm_unlink: false,
      active: true,
    },
  ],
};

function conn(patch: Partial<Connection> = {}, major: number | null = 19): Connection {
  return {
    id: "c1",
    name: "Dev",
    url: "http://x",
    db_name: "odoo",
    username: "admin",
    server_version: `${major}.0`,
    write_mode: "standard",
    created_at: null,
    updated_at: null,
    capabilities: major == null ? null : ({ major, ga: true } as Connection["capabilities"]),
    ...patch,
  };
}

describe("accessVersionFrame", () => {
  it("Odoo 20 is one ir.access matrix with no record rules tab", () => {
    const f = accessVersionFrame(20);
    expect(f.combined).toBe(true);
    expect(f.models).toEqual(["ir.access"]);
    expect(f.tabs).toEqual(["matrix", "lines"]);
    expect(f.tabs).not.toContain("rules");
    expect(f.matrixTitle).toBe("ir.access matrix");
    expect(f.summary).toMatch(/no record rules tab/);
  });

  it.each([17, 18, 19])("Odoo %i shows ir.model.access plus ir.rule and a rules tab", (major) => {
    const f = accessVersionFrame(major);
    expect(f.combined).toBe(false);
    expect(f.models).toEqual(["ir.model.access", "ir.rule"]);
    expect(f.tabs).toEqual(["matrix", "lines", "rules"]);
    expect(f.label).toBe(`Odoo ${major}`);
  });

  it("unknown major claims no model and offers no rules tab", () => {
    const f = accessVersionFrame(null);
    expect(f.models).toEqual([]);
    expect(f.tabs).not.toContain("rules");
    expect(f.label).toBe("Odoo version unknown");
  });

  it("copy carries no em dash", () => {
    for (const m of [17, 19, 20, null]) {
      const f = accessVersionFrame(m);
      expect(`${f.summary} ${f.matrixHint} ${f.matrixTitle}`).not.toMatch(/—/);
    }
  });
});

describe("accessWriteGate", () => {
  it("standard connection saves inline", () => {
    const g = accessWriteGate(conn(), "c1");
    expect(g.mode).toBe("inline");
    expect(g.planHref).toBeNull();
  });

  it("production is R3: plan card link, no inline apply", () => {
    const g = accessWriteGate(conn({ write_mode: "production" }), "c 1");
    expect(g.mode).toBe("plan");
    expect(g.planHref).toBe("/approvals?connection_id=c%201");
    expect(g.why).toMatch(/R3/);
    expect(g.why).toMatch(/no inline save/);
  });

  it("observer and paused writes are read only", () => {
    expect(accessWriteGate(conn({ write_mode: "observer" }), "c1").mode).toBe("readonly");
    expect(accessWriteGate(conn({ writes_paused: true }), "c1").mode).toBe("readonly");
  });

  it("missing capabilities fail closed", () => {
    const g = accessWriteGate(conn({}, null), "c1");
    expect(g.mode).toBe("unknown");
    expect(accessWriteGate(null, "c1").mode).toBe("unknown");
  });

  it("every gate has what / why / next", () => {
    for (const c of [
      conn(),
      conn({ write_mode: "production" }),
      conn({ write_mode: "observer" }),
      null,
    ]) {
      const g = accessWriteGate(c, "c1");
      expect(g.title.length).toBeGreaterThan(5);
      expect(g.why.length).toBeGreaterThan(5);
      expect(g.next.length).toBeGreaterThan(5);
    }
  });

  it("approvalsHref encodes the id", () => {
    expect(approvalsHref("a/b")).toBe("/approvals?connection_id=a%2Fb");
  });
});

describe("staged matrix edits", () => {
  const cell = findMatrixCell(MATRIX, "sale.order", 2);
  const blank = findMatrixCell(MATRIX, "sale.order", 3);

  it("flip stages a change; flipping back removes it", () => {
    let s = stagePerm({}, cell, "perm_unlink");
    expect(stagedCount(s)).toBe(1);
    expect(effectivePerm(s, cell, "perm_unlink")).toBe(true);
    expect(isPermStaged(s, cell, "perm_unlink")).toBe(true);
    s = stagePerm(s, cell, "perm_unlink");
    expect(stagedCount(s)).toBe(0);
    expect(s).toEqual({});
  });

  it("stagedChanges carries full after-perms and the patch", () => {
    let s = stagePerm({}, cell, "perm_unlink");
    s = stagePerm(s, cell, "perm_write");
    s = stagePerm(s, blank, "perm_read");
    const changes = stagedChanges(MATRIX, s);
    expect(changes).toHaveLength(2);
    const update = changes.find((c) => c.accessId === 21)!;
    expect(update.patch).toEqual({ perm_unlink: true, perm_write: false });
    expect(update.after).toEqual({
      perm_read: true,
      perm_write: false,
      perm_create: false,
      perm_unlink: true,
    });
    const create = changes.find((c) => c.accessId == null)!;
    expect(create.groupId).toBe(3);
    expect(create.after.perm_read).toBe(true);
    expect(stagedCount(s)).toBe(3);
  });

  it("describeChange speaks plain words", () => {
    let s = stagePerm({}, cell, "perm_unlink");
    s = stagePerm(s, cell, "perm_write");
    s = stagePerm(s, blank, "perm_read");
    const [a, b] = stagedChanges(MATRIX, s);
    expect(describeChange(a, MATRIX.groups)).toBe(
      "Sales / User gains Delete and loses Write on sale.order",
    );
    expect(describeChange(b, MATRIX.groups)).toBe(
      "Sales / Administrator gains Read on sale.order (new line)",
    );
  });

  it("only inline connections edit cells; global rows never", () => {
    expect(matrixCellEditable({ gate: "inline", groupId: 2 })).toBe(true);
    expect(matrixCellEditable({ gate: "inline", groupId: null })).toBe(false);
    expect(matrixCellEditable({ gate: "plan", groupId: 2 })).toBe(false);
    expect(matrixCellEditable({ gate: "readonly", groupId: 2 })).toBe(false);
    expect(matrixCellEditable({ gate: "unknown", groupId: 2 })).toBe(false);
    expect(matrixCellEditable({ gate: "inline", groupId: 2, busy: true })).toBe(false);
    const plan = accessWriteGate(conn({ write_mode: "production" }), "c1");
    expect(matrixCellLockReason(plan, 2)).toBe(plan.title);
    expect(matrixCellLockReason(plan, null)).toMatch(/Global lines/);
  });

  it("normalizeMatrix survives [] and {} from a proxy", () => {
    expect(normalizeMatrix([])).toBeNull();
    expect(normalizeMatrix(null)).toBeNull();
    expect(normalizeMatrix({})).toEqual({ models: [], groups: [], cells: [] });
    expect(normalizeMatrix(MATRIX)).toEqual(MATRIX);
  });

  it("splitGroupName separates the category", () => {
    expect(splitGroupName("Sales / User: Own Documents Only")).toEqual({
      category: "Sales",
      name: "User: Own Documents Only",
    });
    expect(splitGroupName("All users")).toEqual({ category: null, name: "All users" });
  });
});

describe("what / why / next", () => {
  it("maps access denied", () => {
    const g = accessErrorGuide("AccessError: not allowed");
    expect(g.title).toBe("Odoo refused to show access rights");
    expect(g.next).toMatch(/admin/);
  });

  it("maps the Odoo 20 model mismatch", () => {
    const g = accessErrorGuide("Object ir.model.access doesn't exist");
    expect(g.title).toBe("This Odoo uses a different access model");
    expect(g.why).toMatch(/ir\.access/);
  });

  it("maps a missing model with its name", () => {
    expect(accessErrorGuide("Model not found: x_foo", "x_foo").title).toBe(
      "Odoo has no model named x_foo",
    );
  });

  it("maps network failures", () => {
    expect(accessErrorGuide("Failed to fetch").title).toBe("Odoo did not answer");
  });

  it("falls back with the raw message as why", () => {
    const g = accessErrorGuide("weird");
    expect(g.why).toBe("weird");
    expect(g.next).toMatch(/Retry/);
  });

  it("empty guides name the model and the next step", () => {
    expect(accessEmptyGuide("lines", "x_visit").title).toBe("No access lines on x_visit");
    expect(accessEmptyGuide("rules", "x_visit").why).toMatch(/sees all rows/);
    expect(accessEmptyGuide("matrix", "").next).toMatch(/load the matrix/);
  });
});
