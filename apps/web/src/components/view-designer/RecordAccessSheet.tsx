"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import { api } from "@/lib/api";
import type { AccessChange, ModelAccessOut, Perms } from "@/lib/api/view-engine";
import { Note } from "../view-designer/Note";
import styles from "./ViewDesigner.module.css";
import { Term } from "@/components/ui/Term";

const PERM_COLS: Array<[keyof Perms, string]> = [["read", "Open"], ["write", "Change"], ["create", "Create"], ["unlink", "Delete"]];

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  connectionId: string;
  model: string;
  errorText: (err: unknown) => string;
};

/** "Access to this record type": who can open, change, create, delete; rules in plain words. */
export function RecordAccessSheet({ open, onOpenChange, connectionId, model, errorText }: Props) {
  const [data, setData] = useState<ModelAccessOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [want, setWant] = useState<Record<string, Perms>>({});
  const [preview, setPreview] = useState<{ impact: string[]; blocks: string[] } | null>(null);
  const [applying, setApplying] = useState(false);

  const load = async () => {
    try {
      const out = await api.modelAccess(connectionId, model);
      setData(out);
      setWant(Object.fromEntries(out.roles.map((r) => [r.group, { ...r.perms }])));
      setError(null);
    } catch (err) {
      setError(errorText(err));
    }
  };

  useEffect(() => {
    if (open) void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, model, connectionId]);

  const changes: AccessChange[] = useMemo(() => {
    if (!data) return [];
    return data.roles
      .filter((r) => JSON.stringify(r.perms) !== JSON.stringify(want[r.group]))
      .map((r) => ({ group: r.group, ...want[r.group] }));
  }, [data, want]);

  useEffect(() => {
    setPreview(null);
    if (!changes.length) return;
    let live = true;
    const t = window.setTimeout(() => {
      api
        .modelAccessPreview(connectionId, model, changes)
        .then((out) => live && setPreview(out))
        .catch((err) => live && setPreview({ impact: [], blocks: [errorText(err)] }));
    }, 300);
    return () => {
      live = false;
      window.clearTimeout(t);
    };
  }, [changes, connectionId, model, errorText]);

  const apply = async () => {
    setApplying(true);
    try {
      const out = await api.modelAccessApply(connectionId, model, changes);
      toast.success(out.impact[0] ?? "Access changed", {
        duration: 10000,
        action: {
          label: "Undo",
          onClick: () =>
            void api
              .modelAccessUndo(connectionId, model, out.undo)
              .then(() => {
                toast.success("Access change undone");
                void load();
              })
              .catch((err) => toast.error(errorText(err))),
        },
      });
      await load();
    } catch (err) {
      toast.error(errorText(err));
    } finally {
      setApplying(false);
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={`Access to ${data?.label ?? "this record type"}`} description="Which roles can open, change, create and delete these records.">
      <div className={styles.stack} data-testid="vd-record-access">
        {error ? <Note tone="danger" role="alert">{error}</Note> : null}
        {data ? (
          <>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">Role</th>
                  {PERM_COLS.map(([, label]) => <th key={label} scope="col">{label}</th>)}
                </tr>
              </thead>
              <tbody>
                {data.roles.map((r) => (
                  <tr key={r.group}>
                    <th scope="row">
                      {r.name} <span className={styles.muted}>{r.people === 1 ? "1 person" : `${r.people} people`}</span>
                    </th>
                    {PERM_COLS.map(([p, label]) => (
                      <td key={p}>
                        <input
                          type="checkbox"
                          aria-label={`${r.name}: ${label}`}
                          checked={Boolean(want[r.group]?.[p])}
                          disabled={!data.editable}
                          onChange={(e) => setWant((w) => ({ ...w, [r.group]: { ...w[r.group], [p]: e.target.checked } }))}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {!data.editable ? <p className={styles.muted}>System <Term tech="ir.model">record types</Term> can only be changed in Odoo&apos;s settings.</p> : null}
            {preview ? (
              <div className={styles.stack}>
                {preview.impact.map((l) => <p key={l}>{l}</p>)}
                {preview.blocks.map((b) => <Note tone="danger" key={b} role="alert">{b}</Note>)}
              </div>
            ) : null}
            <Button
              variant="primary"
              size="sm"
              loading={applying}
              disabled={!changes.length || !preview || preview.blocks.length > 0}
              onClick={() => void apply()}
            >
              Apply access changes
            </Button>
            <h4 className={styles.sectionTitle}>Which records they reach</h4>
            <ul className={styles.list}>
              {data.rules.map((r) => (
                <li key={r.id} className={styles.listItem}>
                  <span>
                    {r.applies_to}: {r.plain ?? "A rule too complex to put in words."}
                  </span>
                </li>
              ))}
              {!data.rules.length ? <li className={styles.muted}>No limits: every role above reaches all records.</li> : null}
            </ul>
            <a href={data.rules_link}>Open the Access page</a>
          </>
        ) : null}
      </div>
    </Sheet>
  );
}
