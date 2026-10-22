"use client";

import { Command } from "cmdk";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import type { CommandOut, EngineOp, EngineViewType, Marker } from "@/lib/api/view-engine";
import { jumpItems } from "@/lib/viewDesigner2a";
import type { TreeIndex } from "@/lib/viewEngineOps";
import { Note } from "../view-designer/Note";
import styles from "./ViewDesigner.module.css";

export type CommandAction = { id: string; label: string; run: () => void };

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  connectionId: string;
  model: string;
  viewType: EngineViewType;
  ops: EngineOp[];
  index: TreeIndex | null;
  actions: CommandAction[];
  onJump: (id: string) => void;
  onMarkers: (markers: Record<string, Marker> | null) => void;
  onApply: (ops: EngineOp[], summary: string) => void;
  errorText: (err: unknown) => string;
};

/** ⌘K: jump to an item, run an action, or describe a change (AI proposes, the server checks). */
export function CommandBar({ open, onOpenChange, connectionId, model, viewType, ops, index, actions, onJump, onMarkers, onApply, errorText }: Props) {
  const [search, setSearch] = useState("");
  const [asking, setAsking] = useState(false);
  const [proposal, setProposal] = useState<CommandOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState<Set<number>>(new Set());
  const boxRef = useRef<HTMLDivElement>(null);
  // SPEC 10: focus moves in, stays in (Tab wraps), and goes back where it was when the bar closes.
  // The element to return to is tracked while the bar is closed: by the time an open effect runs,
  // the search box has already taken focus, so reading activeElement then would return to nothing.
  const lastFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (open) return;
    const keep = (el: EventTarget | null) => {
      if (el instanceof HTMLElement && el !== document.body && !el.closest('[role="dialog"]')) lastFocus.current = el;
    };
    keep(document.activeElement);
    const onFocus = (e: FocusEvent) => keep(e.target);
    document.addEventListener("focusin", onFocus);
    return () => document.removeEventListener("focusin", onFocus);
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const back = lastFocus.current;
    return () => { if (back?.isConnected) back.focus(); };
  }, [open]);
  const trap = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      if (!(e.target instanceof HTMLInputElement)) close(); // the search box handles its own Escape
      return;
    }
    if (e.key !== "Tab" || !boxRef.current) return;
    const items = Array.from(boxRef.current.querySelectorAll<HTMLElement>('button, input, textarea, select, a[href], [tabindex]:not([tabindex="-1"])')).filter((el) => !el.hasAttribute("disabled"));
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  if (!open) return null;
  const close = () => {
    setProposal(null);
    setError(null);
    setSearch("");
    onMarkers(null);
    onOpenChange(false);
  };

  const ask = async (override?: string) => {
    const text = (override ?? search).trim();
    if (!text) return;
    setAsking(true);
    setError(null);
    try {
      const out = await api.command(connectionId, { model, view_type: viewType, ops }, text);
      setProposal(out);
      setSkip(new Set());
      onMarkers(out.ops.length ? out.markers : null);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setAsking(false);
    }
  };

  return (
    <>
      <button type="button" className={styles.cmdOverlay} aria-label="Close the command bar" onClick={close} />
      <div ref={boxRef} className={styles.cmdBox} role="dialog" aria-modal="true" aria-label="Command bar" data-testid="vd-command" onKeyDown={trap}>
        {proposal ? (
          <div className={styles.proposal}>
            {proposal.ops.length ? (
              <>
                <p>Proposed change, checked by Ingenium. The screen marks what moves. Untick anything you don&apos;t want.</p>
                <ul className={styles.list} data-testid="vd-ai-ops">
                  {(proposal.op_descriptions ?? proposal.descriptions).map((d, i) => (
                    <li key={`${d}-${i}`}>
                      <label><input type="checkbox" checked={!skip.has(i)} onChange={() => setSkip((s) => { const n = new Set(s); if (n.has(i)) n.delete(i); else n.add(i); return n; })} /> {d}</label>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <>
                <p role="note">{proposal.unclear ?? "Nothing to change for that."}</p>
                {proposal.choices?.length ? (
                  <div className={styles.row} role="group" aria-label="Did you mean">
                    {proposal.choices.map((c) => <Button key={c} size="sm" variant="secondary" onClick={() => { setSearch(c); void ask(c); }}>{c}</Button>)}
                  </div>
                ) : null}
              </>
            )}
            <div className={styles.row}>
              {proposal.ops.length ? (
                <Button
                  variant="primary"
                  size="sm"
                  disabled={skip.size === proposal.ops.length}
                  onClick={() => {
                    const keep = proposal.ops.filter((_, i) => !skip.has(i));
                    const words = (proposal.op_descriptions ?? proposal.descriptions).filter((_, i) => !skip.has(i));
                    onApply(keep, words.join(", "));
                    close();
                  }}
                >
                  {skip.size ? `Apply ${proposal.ops.length - skip.size} of ${proposal.ops.length}` : `Apply ${proposal.ops.length} ${proposal.ops.length === 1 ? "change" : "changes"}`}
                </Button>
              ) : null}
              <Button size="sm" variant="ghost" onClick={() => { setProposal(null); onMarkers(null); }}>
                {proposal.ops.length ? "Discard" : "Back"}
              </Button>
            </div>
          </div>
        ) : (
          <Command label="Command bar" loop shouldFilter>
            <Command.Input
              className={styles.cmdInput}
              placeholder="Jump to a field, or describe a change…"
              value={search}
              onValueChange={setSearch}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Escape") close();
              }}
            />
            <Command.List className={styles.cmdList}>
              <Command.Empty>
                {search.trim() ? (
                  <Button size="sm" loading={asking} onClick={() => void ask()}>
                    {asking ? "Thinking…" : `Make this change: “${search.trim()}”`}
                  </Button>
                ) : (
                  "Type to search"
                )}
              </Command.Empty>
              {search.trim() ? (
                <Command.Group heading="Describe a change" className={styles.cmdGroup}>
                  <Command.Item className={styles.cmdItem} value={`ask ${search}`} onSelect={() => void ask()}>
                    <span>{asking ? "Thinking…" : `Make this change: “${search.trim()}”`}</span>
                  </Command.Item>
                </Command.Group>
              ) : null}
              <Command.Group heading="Actions" className={styles.cmdGroup}>
                {actions.map((a) => (
                  <Command.Item key={a.id} className={styles.cmdItem} value={a.label} onSelect={() => { a.run(); close(); }}>
                    {a.label}
                  </Command.Item>
                ))}
              </Command.Group>
              <Command.Group heading="Jump to" className={styles.cmdGroup}>
                {(index ? jumpItems(index) : []).map((j) => (
                  <Command.Item key={j.id} className={styles.cmdItem} value={`${j.label} ${j.hint} ${j.id}`} onSelect={() => { onJump(j.id); close(); }}>
                    <span>{j.label}</span>
                    <span className={styles.muted}>{j.hint}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            </Command.List>
            {error ? <Note tone="danger" role="alert">{error}</Note> : null}
          </Command>
        )}
      </div>
    </>
  );
}
