"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/layout-primitives";
import { ExternalLink } from "@/components/ui/icons";
import { AccessStateGuide } from "@/components/access/AccessStateGuide";
import type { AccessMatrixOut, GroupRow } from "@/lib/api";
import {
  accessEmptyGuide,
  describeChange,
  effectivePerm,
  findMatrixCell,
  isPermStaged,
  matrixCellEditable,
  matrixCellLockReason,
  PERM_COLUMNS,
  splitGroupName,
  stagedChanges,
  stagedCount,
  stagePerm,
  type AccessVersionFrame,
  type AccessWriteGate,
  type MatrixChange,
  type StagedPerms,
} from "@/lib/accessScreen";

type AccessMatrixPanelProps = {
  frame: AccessVersionFrame;
  gate: AccessWriteGate;
  modelsInput: string;
  onModelsInput: (value: string) => void;
  matrix: AccessMatrixOut | null;
  loading?: boolean;
  saving?: boolean;
  onLoad: () => void;
  /** Resolve true when every change reached Odoo; the stage then clears. */
  onSave: (changes: MatrixChange[]) => Promise<boolean> | boolean;
  /** Harness / tests: start with staged flips. */
  initialStaged?: StagedPerms;
  groupLimit?: number;
};

type MatrixRow = { id: number | null; label: string; group: GroupRow | null };

export function AccessMatrixPanel({
  frame,
  gate,
  modelsInput,
  onModelsInput,
  matrix,
  loading,
  saving,
  onLoad,
  onSave,
  initialStaged,
  groupLimit = 40,
}: AccessMatrixPanelProps) {
  const [staged, setStaged] = useState<StagedPerms>(() => initialStaged ?? {});
  const [groupQuery, setGroupQuery] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [focusPos, setFocusPos] = useState<[number, number]>([0, 0]);
  const tableRef = useRef<HTMLTableElement | null>(null);
  const firstMatrix = useRef(true);

  // A fresh matrix from Odoo invalidates staged flips against the old one.
  useEffect(() => {
    if (firstMatrix.current) {
      firstMatrix.current = false;
      return;
    }
    setStaged({});
  }, [matrix]);

  const rows: MatrixRow[] = useMemo(() => {
    if (!matrix) return [];
    const out: MatrixRow[] = [];
    const hasGlobal = matrix.cells.some((c) => c.group_id == null && c.active !== false);
    if (hasGlobal) out.push({ id: null, label: "All users", group: null });
    for (const g of matrix.groups) {
      out.push({ id: g.id, label: g.full_name || g.name, group: g });
    }
    const needle = groupQuery.trim().toLowerCase();
    return needle ? out.filter((r) => r.label.toLowerCase().includes(needle)) : out;
  }, [matrix, groupQuery]);

  const visibleRows = showAll ? rows : rows.slice(0, groupLimit);
  const models = matrix?.models ?? [];
  const groups = matrix?.groups ?? [];
  const count = stagedCount(staged);
  const changes = useMemo(() => stagedChanges(matrix, staged), [matrix, staged]);
  const canSave = gate.mode === "inline" && count > 0 && !saving;
  const colCount = models.length * PERM_COLUMNS.length;
  const hasGrid = Boolean(matrix) && models.length > 0 && rows.length > 0;
  // Global row (if any) is read-only, so keyboard entry starts on the first group.
  const firstEditableRow = Math.max(
    0,
    visibleRows.findIndex((r) => r.id != null),
  );
  const anchor: [number, number] =
    focusPos[0] >= firstEditableRow && focusPos[0] < visibleRows.length && focusPos[1] < colCount
      ? focusPos
      : [firstEditableRow, 0];

  function moveFocus(event: KeyboardEvent<HTMLButtonElement>, row: number, col: number) {
    const maxRow = visibleRows.length - 1;
    const maxCol = colCount - 1;
    let next: [number, number] | null = null;
    switch (event.key) {
      case "ArrowRight":
        next = [row, Math.min(col + 1, maxCol)];
        break;
      case "ArrowLeft":
        next = [row, Math.max(col - 1, 0)];
        break;
      case "ArrowDown":
        next = [Math.min(row + 1, maxRow), col];
        break;
      case "ArrowUp":
        next = [Math.max(row - 1, firstEditableRow), col];
        break;
      case "Home":
        next = [row, 0];
        break;
      case "End":
        next = [row, maxCol];
        break;
      default:
        return;
    }
    event.preventDefault();
    setFocusPos(next);
    const target = tableRef.current?.querySelector<HTMLButtonElement>(
      `button[data-row="${next[0]}"][data-col="${next[1]}"]`,
    );
    target?.focus();
  }

  async function save() {
    if (!canSave) return;
    const ok = await onSave(changes);
    if (ok) setStaged({});
  }

  const summary =
    changes.length === 0
      ? null
      : changes
          .slice(0, 2)
          .map((c) => describeChange(c, groups))
          .join(". ") + (changes.length > 2 ? `. ${changes.length - 2} more.` : ".");

  return (
    <section
      className="ax-matrix"
      data-testid="access-matrix"
      aria-labelledby="access-matrix-title"
    >
      <div className="ax-matrix-head">
        <div className="ax-matrix-titlerow">
          <div>
            <h2
              id="access-matrix-title"
              className="ax-matrix-title"
              data-testid="access-matrix-title"
            >
              {frame.matrixTitle}
            </h2>
            <p className="ax-matrix-hint">{frame.matrixHint}</p>
          </div>
          <ul className="ax-legend" aria-label="Legend">
            {PERM_COLUMNS.map((c) => (
              <li key={c.key}>
                <kbd>{c.letter}</kbd>
                {c.label}
              </li>
            ))}
            <li>
              <span className="ax-tag">Staged</span>
              not saved yet
            </li>
          </ul>
        </div>
        <form
          className="ax-matrix-tools"
          onSubmit={(e) => {
            e.preventDefault();
            onLoad();
          }}
        >
          <label className="ax-field" style={{ flex: "1 1 260px", maxWidth: 440 }}>
            <span className="ax-field-label">Models</span>
            <input
              className="ax-input is-mono"
              value={modelsInput}
              onChange={(e) => onModelsInput(e.target.value)}
              placeholder="res.partner, sale.order"
              data-testid="access-matrix-models"
              spellCheck={false}
              autoCapitalize="off"
            />
          </label>
          <Button
            type="submit"
            variant="secondary"
            disabled={loading}
            loading={loading}
            data-testid="access-matrix-load"
          >
            Load
          </Button>
          {matrix && rows.length + (groupQuery ? 1 : 0) > 8 ? (
            <label className="ax-field" style={{ flex: "0 1 220px" }}>
              <span className="ax-field-label">Find a group</span>
              <input
                className="ax-input"
                value={groupQuery}
                onChange={(e) => setGroupQuery(e.target.value)}
                placeholder="Sales, Portal…"
                aria-label="Filter groups"
                data-testid="access-matrix-group-filter"
              />
            </label>
          ) : null}
        </form>
      </div>

      {loading && !matrix ? (
        <div
          className="grid gap-2 border-t border-border-subtle p-4"
          data-testid="access-matrix-loading"
        >
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-4/5" />
        </div>
      ) : !matrix || models.length === 0 || rows.length === 0 ? (
        <div className="border-t border-border-subtle p-4">
          <AccessStateGuide
            guide={
              matrix && groupQuery
                ? {
                    title: `No group matches “${groupQuery}”`,
                    why: "The filter only checks group names.",
                    next: "Clear the filter, or try a category such as Sales.",
                  }
                : accessEmptyGuide("matrix", modelsInput)
            }
            testId="access-matrix-empty"
          />
        </div>
      ) : (
        <div className="ax-matrix-scroll" data-testid="access-matrix-scroll">
          <table ref={tableRef} className="ax-table" data-testid="access-matrix-table">
            <caption className="sr-only">
              {frame.matrixTitle}: groups in rows, models and operations in columns.
            </caption>
            <thead>
              <tr>
                <th scope="col" rowSpan={2} className="ax-corner">
                  Group
                </th>
                {models.map((m) => (
                  <th
                    key={m}
                    scope="colgroup"
                    colSpan={PERM_COLUMNS.length}
                    className="ax-model-th"
                  >
                    {m}
                  </th>
                ))}
              </tr>
              <tr>
                {models.map((m) =>
                  PERM_COLUMNS.map((c, i) => (
                    <th
                      key={`${m}-${c.key}`}
                      scope="col"
                      abbr={c.label}
                      title={`${c.label} on ${m}`}
                      className={i === 0 ? "ax-perm-th is-first" : "ax-perm-th"}
                    >
                      {c.letter}
                    </th>
                  )),
                )}
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row, rowIdx) => {
                const { category, name } = splitGroupName(row.label);
                return (
                  <tr
                    key={row.id ?? "global"}
                    data-testid={`access-matrix-row-${row.id ?? "global"}`}
                  >
                    <th scope="row">
                      {category ? <span className="ax-group-cat">{category}</span> : null}
                      <span className="ax-group-name">
                        {name}
                        {row.id == null ? <span className="ax-tag">Global</span> : null}
                        {row.group?.share ? (
                          <span className="ax-tag" data-tone="muted">
                            Portal
                          </span>
                        ) : null}
                      </span>
                    </th>
                    {models.map((m, mIdx) => {
                      const cell = findMatrixCell(matrix, m, row.id);
                      return PERM_COLUMNS.map((c, pIdx) => {
                        const colIdx = mIdx * PERM_COLUMNS.length + pIdx;
                        const on = effectivePerm(staged, cell, c.key);
                        const isStaged = isPermStaged(staged, cell, c.key);
                        const editable = matrixCellEditable({
                          gate: gate.mode,
                          groupId: row.id,
                          busy: saving,
                        });
                        const lock = matrixCellLockReason(gate, row.id);
                        const tabbable = anchor[0] === rowIdx && anchor[1] === colIdx;
                        return (
                          <td
                            key={`${m}-${c.key}`}
                            className={pIdx === 0 ? "is-first" : undefined}
                            data-staged={isStaged ? "true" : undefined}
                          >
                            <button
                              type="button"
                              className="ax-pip"
                              aria-pressed={on}
                              aria-label={`${c.label} on ${m} for ${row.label}${isStaged ? ", staged, not saved" : ""}`}
                              title={lock ?? (isStaged ? "Staged, not saved yet" : undefined)}
                              data-staged={isStaged ? "true" : "false"}
                              data-row={rowIdx}
                              data-col={colIdx}
                              data-testid={`access-pip-${m}-${row.id ?? "global"}-${c.letter}`}
                              tabIndex={tabbable ? 0 : -1}
                              disabled={!editable}
                              onFocus={() => setFocusPos([rowIdx, colIdx])}
                              onKeyDown={(e) => moveFocus(e, rowIdx, colIdx)}
                              onClick={() => setStaged((s) => stagePerm(s, cell, c.key))}
                            >
                              <span className="ax-pip-mark" aria-hidden />
                            </button>
                          </td>
                        );
                      });
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {matrix && rows.length > groupLimit ? (
        <div className="ax-matrix-foot">
          <span>
            Showing {visibleRows.length} of {rows.length} groups
          </span>
          <Button type="button" variant="ghost" size="sm" onClick={() => setShowAll((v) => !v)}>
            {showAll ? `Show first ${groupLimit}` : `Show all ${rows.length}`}
          </Button>
        </div>
      ) : null}

      {hasGrid || gate.mode === "plan" ? (
        <div
          className="ax-savebar"
          data-dirty={count > 0 ? "true" : "false"}
          data-testid="access-savebar"
        >
          <div className="ax-savebar-status" aria-live="polite">
            <p className="ax-savebar-count" data-testid="access-savebar-count">
              {gate.mode === "plan"
                ? "Inline save is off on production"
                : gate.mode !== "inline"
                  ? `Saving is off: ${gate.label.toLowerCase()}`
                  : count === 0
                    ? "No changes staged"
                    : `${count} ${count === 1 ? "change" : "changes"} staged`}
            </p>
            <p className="ax-savebar-detail" data-testid="access-savebar-detail">
              {gate.mode === "inline"
                ? (summary ?? "Tick a cell to stage it. Nothing reaches Odoo until you save.")
                : gate.next}
            </p>
          </div>
          <div className="ax-savebar-actions">
            {count > 0 ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={saving}
                onClick={() => setStaged({})}
                data-testid="access-matrix-discard"
              >
                Discard
              </Button>
            ) : null}
            {gate.mode === "plan" && gate.planHref ? (
              <Button variant="primary" size="sm" asChild>
                <Link href={gate.planHref} data-testid="access-plan-link">
                  Open plan card
                  <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                </Link>
              </Button>
            ) : (
              <Button
                type="button"
                variant="primary"
                size="sm"
                disabled={!canSave}
                loading={saving}
                title={gate.mode === "inline" ? undefined : gate.title}
                onClick={() => void save()}
                data-testid="access-matrix-save"
              >
                {count > 1 ? `Save ${count} rights` : "Save right"}
              </Button>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
