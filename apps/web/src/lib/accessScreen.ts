/**
 * UI-S-19 Access screen logic: version frame, write gate, staged matrix edits,
 * and what / why / next copy for empty and error states. Pure, no React.
 */
import type { AccessMatrixOut, Connection, GroupRow } from "@/lib/api";
import { accessScreenBranch } from "@/lib/accessMajor";
import type { CrudPermits } from "@/lib/accessForm";

export type PermKey = keyof CrudPermits;
export type MatrixCell = AccessMatrixOut["cells"][number];

export const PERM_COLUMNS: ReadonlyArray<{ key: PermKey; letter: string; label: string }> = [
  { key: "perm_read", letter: "R", label: "Read" },
  { key: "perm_write", letter: "W", label: "Write" },
  { key: "perm_create", letter: "C", label: "Create" },
  { key: "perm_unlink", letter: "D", label: "Delete" },
];

/* ------------------------------------------------------------------ */
/* Version frame                                                       */
/* ------------------------------------------------------------------ */

export type AccessTab = "matrix" | "lines" | "rules";

export type AccessVersionFrame = {
  major: number | null;
  combined: boolean;
  label: string;
  /** Odoo technical models this screen reads and writes on that major. */
  models: string[];
  summary: string;
  tabs: AccessTab[];
  matrixTitle: string;
  matrixHint: string;
};

export function accessVersionFrame(major: number | null | undefined): AccessVersionFrame {
  const branch = accessScreenBranch(major);
  const known = typeof major === "number";
  if (branch.combinedIrAccess) {
    return {
      major: major as number,
      combined: true,
      label: `Odoo ${major}`,
      models: ["ir.access"],
      summary:
        "Rights and row filters live together in ir.access, so this screen shows one matrix and no record rules tab.",
      tabs: ["matrix", "lines"],
      matrixTitle: "ir.access matrix",
      matrixHint: "Each tick is one ir.access row for that group, model and operation.",
    };
  }
  if (known) {
    return {
      major: major as number,
      combined: false,
      label: `Odoo ${major}`,
      models: ["ir.model.access", "ir.rule"],
      summary:
        "Access lines grant read, write, create and delete per group. Record rules then filter which rows that group sees.",
      tabs: ["matrix", "lines", "rules"],
      matrixTitle: "Access rights matrix",
      matrixHint:
        "Each row is a group. Ticks write ir.model.access lines; record rules stay on their own tab.",
    };
  }
  return {
    major: null,
    combined: false,
    label: "Odoo version unknown",
    models: [],
    summary:
      "Probe the connection first. Odoo 20 stores rights in ir.access; 17 to 19 use ir.model.access plus ir.rule.",
    tabs: ["matrix", "lines"],
    matrixTitle: "Access rights matrix",
    matrixHint: "Ticks stay read-only until the Odoo version is known.",
  };
}

export const ACCESS_TAB_LABELS: Record<AccessTab, string> = {
  matrix: "Matrix",
  lines: "Access lines",
  rules: "Record rules",
};

/* ------------------------------------------------------------------ */
/* Write gate                                                          */
/* ------------------------------------------------------------------ */

export type AccessWriteMode = "inline" | "plan" | "readonly" | "unknown";

export type AccessWriteGate = {
  mode: AccessWriteMode;
  /** Short chip label. */
  label: string;
  title: string;
  why: string;
  next: string;
  /** Plan card inbox for R3 changes on production. */
  planHref: string | null;
};

export function approvalsHref(connectionId: string): string {
  return `/approvals?connection_id=${encodeURIComponent(connectionId)}`;
}

export function accessWriteGate(
  connection: Connection | null | undefined,
  connectionId: string,
): AccessWriteGate {
  if (!connection?.capabilities) {
    return {
      mode: "unknown",
      label: "Probe needed",
      title: "The Odoo version is not probed yet",
      why: "Odoo 20 stores rights differently from 17 to 19, so Ingenium writes nothing until it knows the major.",
      next: "Refresh capabilities, then save your rights.",
      planHref: null,
    };
  }
  if (connection.writes_paused) {
    return {
      mode: "readonly",
      label: "Writes paused",
      title: "Writes are paused on this connection",
      why: "Someone paused writes, so access changes cannot reach Odoo right now.",
      next: "Resume writes in the connection settings, then save.",
      planHref: null,
    };
  }
  if (connection.write_mode === "observer") {
    return {
      mode: "readonly",
      label: "Read only",
      title: "Observer connections only read",
      why: "Observer mode never writes to Odoo, including access rights.",
      next: "Use a standard connection on a sandbox to change rights.",
      planHref: null,
    };
  }
  if (connection.write_mode === "production") {
    return {
      mode: "plan",
      label: "Needs approval",
      title: "Production applies access changes from a plan card",
      why: "Access rights are R3. One person must approve before Odoo changes, so there is no inline save here.",
      next: "Open the plan card inbox to review and approve the change.",
      planHref: approvalsHref(connectionId),
    };
  }
  return {
    mode: "inline",
    label: "Saves to Odoo",
    title: "Saves write straight to Odoo",
    why: "This is a standard connection. Each save takes a snapshot first.",
    next: "Tick the rights you want, then save.",
    planHref: null,
  };
}

/* ------------------------------------------------------------------ */
/* Matrix: normalise + staged edits                                    */
/* ------------------------------------------------------------------ */

/** Defensive parse: a proxy or mock can return [] or {} for the matrix route. */
export function normalizeMatrix(raw: unknown): AccessMatrixOut | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const r = raw as Partial<AccessMatrixOut>;
  return {
    models: Array.isArray(r.models) ? r.models : [],
    groups: Array.isArray(r.groups) ? r.groups : [],
    cells: Array.isArray(r.cells) ? r.cells : [],
  };
}

export function matrixCellKey(model: string, groupId: number | null): string {
  return `${model}::${groupId ?? "global"}`;
}

export function blankCell(model: string, groupId: number | null): MatrixCell {
  return {
    model,
    group_id: groupId,
    access_id: null,
    name: null,
    perm_read: false,
    perm_write: false,
    perm_create: false,
    perm_unlink: false,
    active: true,
  };
}

export function findMatrixCell(
  matrix: AccessMatrixOut | null,
  model: string,
  groupId: number | null,
): MatrixCell {
  const found = matrix?.cells.find(
    (c) => c.model === model && (c.group_id ?? null) === groupId && c.active !== false,
  );
  return found ?? blankCell(model, groupId);
}

export type StagedPerms = Record<string, Partial<CrudPermits>>;

/** Flip one perm. A flip back to the saved value removes it from the stage. */
export function stagePerm(staged: StagedPerms, cell: MatrixCell, key: PermKey): StagedPerms {
  const cellKey = matrixCellKey(cell.model, cell.group_id ?? null);
  const current = staged[cellKey] ?? {};
  const effective = key in current ? Boolean(current[key]) : cell[key];
  const nextValue = !effective;
  const nextCell: Partial<CrudPermits> = { ...current };
  if (nextValue === cell[key]) {
    delete nextCell[key];
  } else {
    nextCell[key] = nextValue;
  }
  const next = { ...staged };
  if (Object.keys(nextCell).length === 0) {
    delete next[cellKey];
  } else {
    next[cellKey] = nextCell;
  }
  return next;
}

export function effectivePerm(staged: StagedPerms, cell: MatrixCell, key: PermKey): boolean {
  const patch = staged[matrixCellKey(cell.model, cell.group_id ?? null)];
  if (patch && key in patch) return Boolean(patch[key]);
  return cell[key];
}

export function isPermStaged(staged: StagedPerms, cell: MatrixCell, key: PermKey): boolean {
  const patch = staged[matrixCellKey(cell.model, cell.group_id ?? null)];
  return Boolean(patch && key in patch);
}

export function stagedCount(staged: StagedPerms): number {
  return Object.values(staged).reduce((n, patch) => n + Object.keys(patch).length, 0);
}

export type MatrixChange = {
  model: string;
  groupId: number | null;
  accessId: number | null;
  /** Full perms after the change (what Odoo should hold). */
  after: CrudPermits;
  /** Only the flipped perms. */
  patch: Partial<CrudPermits>;
};

export function stagedChanges(matrix: AccessMatrixOut | null, staged: StagedPerms): MatrixChange[] {
  const out: MatrixChange[] = [];
  for (const [cellKey, patch] of Object.entries(staged)) {
    if (!patch || Object.keys(patch).length === 0) continue;
    const sep = cellKey.lastIndexOf("::");
    const model = cellKey.slice(0, sep);
    const rawGroup = cellKey.slice(sep + 2);
    const groupId = rawGroup === "global" ? null : Number(rawGroup);
    const cell = findMatrixCell(matrix, model, groupId);
    out.push({
      model,
      groupId,
      accessId: cell.access_id,
      patch: { ...patch },
      after: {
        perm_read: patch.perm_read ?? cell.perm_read,
        perm_write: patch.perm_write ?? cell.perm_write,
        perm_create: patch.perm_create ?? cell.perm_create,
        perm_unlink: patch.perm_unlink ?? cell.perm_unlink,
      },
    });
  }
  return out.sort(
    (a, b) => a.model.localeCompare(b.model) || (a.groupId ?? -1) - (b.groupId ?? -1),
  );
}

export function groupLabel(groups: GroupRow[], groupId: number | null): string {
  if (groupId == null) return "All users";
  const g = groups.find((x) => x.id === groupId);
  return g ? g.full_name || g.name : `Group ${groupId}`;
}

/** Split "Sales / User: Own Documents Only" into a muted category and the name. */
export function splitGroupName(full: string): { category: string | null; name: string } {
  const idx = full.indexOf(" / ");
  if (idx === -1) return { category: null, name: full };
  return { category: full.slice(0, idx), name: full.slice(idx + 3) };
}

/** "Sales / User gains Delete on sale.order" in plain words. */
export function describeChange(change: MatrixChange, groups: GroupRow[]): string {
  const who = groupLabel(groups, change.groupId);
  const gains: string[] = [];
  const loses: string[] = [];
  for (const col of PERM_COLUMNS) {
    if (!(col.key in change.patch)) continue;
    (change.patch[col.key] ? gains : loses).push(col.label);
  }
  const parts: string[] = [];
  if (gains.length) parts.push(`gains ${joinWords(gains)}`);
  if (loses.length) parts.push(`loses ${joinWords(loses)}`);
  const creates = change.accessId == null ? " (new line)" : "";
  return `${who} ${parts.join(" and ")} on ${change.model}${creates}`;
}

function joinWords(words: string[]): string {
  if (words.length <= 1) return words.join("");
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}

/**
 * Can a matrix cell be toggled in place? Only on an inline-save connection.
 * Global lines (no group) stay in Access lines, where the warning lives.
 * Production (R3 plan) never stages inline: the CTA links to the plan card.
 */
export function matrixCellEditable(opts: {
  gate: AccessWriteMode;
  groupId: number | null;
  busy?: boolean;
}): boolean {
  if (opts.busy) return false;
  if (opts.groupId == null) return false;
  return opts.gate === "inline";
}

/** Why a cell is locked, for its tooltip and accessible description. */
export function matrixCellLockReason(gate: AccessWriteGate, groupId: number | null): string | null {
  if (groupId == null) return "Global lines affect every user. Edit them in Access lines.";
  if (gate.mode === "inline") return null;
  return gate.title;
}

/* ------------------------------------------------------------------ */
/* What / why / next                                                   */
/* ------------------------------------------------------------------ */

export type StateGuide = { title: string; why: string; next: string };

export function accessErrorGuide(message: string | null | undefined, model?: string): StateGuide {
  const raw = (message ?? "").trim();
  if (/access ?denied|accesserror|not allowed|forbidden|\b403\b/i.test(raw)) {
    return {
      title: "Odoo refused to show access rights",
      why: "The Odoo user on this connection lacks the Administration: Settings right.",
      next: "Reconnect with an admin user, or ask your Odoo admin for Settings access, then retry.",
    };
  }
  if (
    /ir\.model\.access|ir\.rule|ir\.access/i.test(raw) &&
    /exist|unknown|not found|invalid model/i.test(raw)
  ) {
    return {
      title: "This Odoo uses a different access model",
      why: "Odoo 20 replaced ir.model.access and ir.rule with ir.access, and the probe is out of date.",
      next: "Refresh capabilities so Ingenium picks the matching branch, then retry.",
    };
  }
  if (/model .*(not found|does not exist|unknown)|no model|\b404\b/i.test(raw)) {
    return {
      title: model ? `Odoo has no model named ${model}` : "Odoo has no model with that name",
      why: "The technical name is mistyped, or the app that owns it is not installed.",
      next: "Check the technical name (for example sale.order) or install its app, then load again.",
    };
  }
  if (/timeout|timed out|network|failed to fetch|econn|\b50[234]\b|unreachable/i.test(raw)) {
    return {
      title: "Odoo did not answer",
      why: "The server is down, slow, or unreachable from Ingenium right now.",
      next: "Check that the Odoo URL opens, then retry.",
    };
  }
  return {
    title: "Access rights could not load",
    why: raw || "Odoo returned an error without a message.",
    next: "Retry. If it fails again, use Explain access for a diagnosis.",
  };
}

export function accessEmptyGuide(kind: "lines" | "rules" | "matrix", model: string): StateGuide {
  if (kind === "rules") {
    return {
      title: `No record rules on ${model}`,
      why: "Every group with an access line sees all rows of this model.",
      next: "Add a rule when a group should only see some rows, such as its own records.",
    };
  }
  if (kind === "matrix") {
    return {
      title: "No groups to show yet",
      why: "The matrix lists groups once a model loads from Odoo.",
      next: "Enter one or more technical model names and load the matrix.",
    };
  }
  return {
    title: `No access lines on ${model}`,
    why: "Without a line, only the superuser can open records of this model.",
    next: "Tick a group in the matrix and save, or create a line here.",
  };
}

export function sanitizeAccessCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

export function accessHonestyGuide(opts: { mode: string }): { title: string; why: string; next: string } {
  if (opts.mode === "plan") {
    return {
      title: "Writes are gated on this Odoo major.",
      why: "Inline edits are off. Stage a plan, then apply through the plan path.",
      next: "Review the gate, stage matrix changes, then open the plan when ready.",
    };
  }
  return {
    title: "Who can read, write, create and delete each model.",
    why: "Access lines and record rules write to this live connection after confirm. Snapshots cover restores.",
    next: "Pick a model, edit the matrix or compose a right, then Save.",
  };
}

export function accessSessionBadge(opts: { mode: string; unsaved: boolean }): {
  label: string;
  variant: "default" | "warning" | "success" | "info" | "danger";
} {
  if (opts.mode === "plan") return { label: "Plan gate", variant: "warning" };
  if (opts.unsaved) return { label: "Unsaved", variant: "warning" };
  return { label: "Ready", variant: "default" };
}

