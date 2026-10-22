"use client";

import Editor, { DiffEditor, loader, type OnMount } from "@monaco-editor/react";
import type * as Monaco from "monaco-editor";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { codeRunnerApi, type CRAIAction, type CRAIOut, type CRIssue, type CRSchema, type CRSnippet, type CRVersions } from "@/lib/api/code-runner";
import { connectionsApi } from "@/lib/api/connections";
import type { Connection } from "@/lib/api/types-schema";
import { keystoneTheme, registerOdooLanguage } from "./odooLanguage";
import { RunPanel } from "./RunPanel";
import { AuditPanel, GalleryPanel, LibraryPanel, LiveBar, NotebookPanel, PromotePanel, SettingsPanel, VaultPanel, useLiveScript,
  type LinkedTab } from "./R3Panels";
import type { CRScript } from "@/lib/api/code-runner";
import s from "./CodeRunner.module.css";
import { FrameMeta } from "@/components/frame/FrameMeta";

type Tab = LinkedTab;
type Keys = "default" | "vim" | "emacs";
type Panel = "run" | "problems" | "ai" | "versions" | "library" | "gallery" | "notebook" | "promote" | "audit" | "vault" | "settings" | null;
const MORE: { id: Exclude<Panel, null>; label: string }[] = [
  { id: "library", label: "Library" }, { id: "gallery", label: "Starters" }, { id: "notebook", label: "Notebook" }, { id: "promote", label: "Promote" },
  { id: "audit", label: "History" }, { id: "vault", label: "Secrets" }, { id: "settings", label: "AI settings" }];
const START = '# Scripts talk to Odoo through odoo.execute_kw(model, method, args, kwargs).\n# Type odoo: for snippets, or press Ctrl/Cmd+K for commands.\n';
const storeKey = (id: string) => `ingenium.codeRunner.tabs.${id}`;
const newId = () => Math.random().toString(36).slice(2, 9);

let monacoReady: Promise<void> | null = null;
function useLocalMonaco() {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    monacoReady ??= (async () => {
      (self as unknown as { MonacoEnvironment: Monaco.Environment }).MonacoEnvironment = {
        getWorker: () => new Worker(new URL("monaco-editor/esm/vs/editor/editor.worker.js", import.meta.url), { type: "module" }),
      };
      const monaco = await import("monaco-editor");
      loader.config({ monaco });
    })();
    monacoReady.then(() => setReady(true));
  }, []);
  return ready;
}

export function CodeRunnerEditor({ connectionId }: { connectionId: string }) {
  const ready = useLocalMonaco();
  const host = useRef<HTMLDivElement>(null);
  const [tabs, setTabs] = useState<Tab[]>([{ id: "main", name: "script.py", code: START }]);
  const [active, setActive] = useState("main");
  const [splitId, setSplitId] = useState<string | null>(null);
  const [minimap, setMinimap] = useState(true);
  const [keys, setKeys] = useState<Keys>("default");
  const [schema, setSchema] = useState<CRSchema | null>(null);
  const [snippets, setSnippets] = useState<CRSnippet[]>([]);
  const [issues, setIssues] = useState<CRIssue[]>([]);
  const [panel, setPanel] = useState<Panel>("run");
  const [cmdOpen, setCmdOpen] = useState(false);
  const [err, setErr] = useState("");
  const editorRef = useRef<Monaco.editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<typeof Monaco | null>(null);
  const statusRef = useRef<HTMLSpanElement>(null);
  const tab = tabs.find((t) => t.id === active) ?? tabs[0];
  const live = useLiveScript(connectionId, tab, (p) => patchTab(tab.id, p));

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(storeKey(connectionId)) ?? "null") as { tabs: Tab[]; active: string } | null;
      if (saved?.tabs?.length) { setTabs(saved.tabs); setActive(saved.active); }
    } catch { /* fresh start */ }
  }, [connectionId]);
  useEffect(() => { localStorage.setItem(storeKey(connectionId), JSON.stringify({ tabs, active })); }, [tabs, active, connectionId]);

  useEffect(() => {
    codeRunnerApi.schema(connectionId).then(setSchema).catch((e: Error) => setErr(`Couldn't read this database's models: ${e.message}`));
    codeRunnerApi.snippets(connectionId).then((r) => setSnippets(r.snippets)).catch(() => setSnippets([]));
  }, [connectionId]);

  useEffect(() => {
    const monaco = monacoRef.current;
    if (!monaco || !schema) return;
    return registerOdooLanguage(monaco, connectionId, schema, snippets);
  }, [schema, snippets, connectionId, ready]);

  // Live lint, debounced; markers in the editor plus the Problems list.
  useEffect(() => {
    const ctl = new AbortController();
    const t = setTimeout(() => {
      codeRunnerApi.lint(connectionId, tab.code, ctl.signal).then((r) => {
        setIssues(r.issues);
        const monaco = monacoRef.current;
        const model = editorRef.current?.getModel();
        if (!monaco || !model) return;
        const sev = { error: monaco.MarkerSeverity.Error, warning: monaco.MarkerSeverity.Warning, info: monaco.MarkerSeverity.Info };
        monaco.editor.setModelMarkers(model, "odoo", r.issues.map((i) => ({
          startLineNumber: i.line, startColumn: i.col, endLineNumber: i.end_line, endColumn: Math.max(i.end_col, i.col + 1),
          message: i.fix ? `${i.message} Did you mean '${i.fix}'?` : i.message, severity: sev[i.severity] })));
      }).catch(() => undefined);
    }, 600);
    return () => { clearTimeout(t); ctl.abort(); };
  }, [tab.code, connectionId]);

  // Vim / Emacs key modes.
  useEffect(() => {
    const ed = editorRef.current;
    if (!ed || keys === "default") return;
    let dispose = () => {};
    let gone = false;
    (async () => {
      if (keys === "vim") {
        const { initVimMode } = await import("monaco-vim");
        if (!gone) { const v = initVimMode(ed, statusRef.current); dispose = () => v.dispose(); }
      } else {
        const { EmacsExtension } = await import("monaco-emacs");
        if (!gone) { const e = new EmacsExtension(ed); e.start(); dispose = () => e.dispose(); }
      }
    })();
    return () => { gone = true; dispose(); };
  }, [keys, active, ready]);

  const setCode = useCallback((id: string, code: string) => setTabs((ts) => ts.map((t) => (t.id === id ? { ...t, code } : t))), []);
  const patchTab = useCallback((id: string, p: Partial<Tab>) => setTabs((ts) => ts.map((t) => (t.id === id ? { ...t, ...p } : t))), []);
  const openTab = useCallback((t: Omit<Tab, "id">) => {
    const existing = t.sid ? tabs.find((x) => x.sid === t.sid) : undefined;
    if (existing) { setActive(existing.id); return; }
    const id = newId();
    setTabs((ts) => [...ts, { ...t, id }]);
    setActive(id);
  }, [tabs]);
  const openScript = useCallback((sc: CRScript) => openTab({ name: `${sc.name}.py`, code: sc.code, sid: sc.id, rev: sc.rev, kind: sc.kind, cells: sc.cells }), [openTab]);
  const addTab = useCallback(() => {
    const id = newId();
    setTabs((ts) => [...ts, { id, name: `script-${ts.length + 1}.py`, code: START }]);
    setActive(id);
  }, []);
  const closeTab = (id: string) => {
    if (tabs.length === 1) return;
    const rest = tabs.filter((t) => t.id !== id);
    setTabs(rest);
    if (active === id) setActive(rest[0].id);
    if (splitId === id) setSplitId(null);
  };
  const insert = useCallback((body: string) => {
    const ed = editorRef.current;
    if (!ed) return;
    ed.focus();
    (ed.getContribution("snippetController2") as unknown as { insert: (t: string) => void } | null)?.insert(body);
  }, []);

  const onMount: OnMount = (ed, monaco) => {
    editorRef.current = ed;
    monacoRef.current = monaco;
    if (host.current) keystoneTheme(monaco, host.current);
    monaco.editor.setTheme("keystone");
    ed.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyK, () => setCmdOpen(true));
  };

  const commands = useMemo(() => [
    { id: "new", label: "New tab", key: "", run: addTab },
    { id: "split", label: splitId ? "Close split view" : "Split view (side by side)", key: "", run: () => setSplitId(splitId ? null : tabs.find((t) => t.id !== active)?.id ?? null) },
    { id: "minimap", label: minimap ? "Hide minimap" : "Show minimap", key: "", run: () => setMinimap(!minimap) },
    { id: "palette", label: "All editor commands", key: "F1", run: () => editorRef.current?.trigger("cmd", "editor.action.quickCommand", null) },
    { id: "ai-explain", label: "AI: explain this script", key: "", run: () => setPanel("ai") },
    { id: "versions", label: "Compare a model across Odoo versions", key: "", run: () => setPanel("versions") },
    { id: "problems", label: "Show problems", key: "", run: () => setPanel("problems") },
    ...MORE.map((m) => ({ id: `panel-${m.id}`, label: `Open: ${m.label}`, key: "", run: () => setPanel(m.id) })),
    ...(["default", "vim", "emacs"] as Keys[]).map((k) => ({ id: `keys-${k}`, label: `Keys: ${k === "default" ? "standard" : k}`, key: "", run: () => setKeys(k) })),
    ...snippets.map((sn) => ({ id: `snip-${sn.id}`, label: `Insert: ${sn.label}`, key: "", run: () => insert(sn.body) })),
  ], [addTab, splitId, tabs, active, minimap, snippets, insert]);

  const goTo = (i: CRIssue) => {
    editorRef.current?.revealLineInCenter(i.line);
    editorRef.current?.setPosition({ lineNumber: i.line, column: i.col });
    editorRef.current?.focus();
  };
  const options = { minimap: { enabled: minimap }, fontSize: 13, fontFamily: "var(--font-mono-stack), monospace", tabSize: 4,
    automaticLayout: true, scrollBeyondLastLine: false, quickSuggestions: { strings: true, other: true, comments: false } };
  const counts = { error: issues.filter((i) => i.severity === "error").length, warning: issues.filter((i) => i.severity === "warning").length };
  const split = splitId ? tabs.find((t) => t.id === splitId) : null;

  return (
    <div className={s.shell} ref={host}>
      <div className={s.bar}>
        <FrameMeta />
        <h1 className={s.title}>Code runner</h1>
        <span className={s.muted}>{schema ? `Odoo ${schema.major} · ${schema.models.length} models` : "Reading the database…"}</span>
        <span className={s.spacer} />
        <select className={s.select} aria-label="Key mode" value={keys} onChange={(e) => setKeys(e.target.value as Keys)}>
          <option value="default">Standard keys</option><option value="vim">Vim</option><option value="emacs">Emacs</option>
        </select>
        <button className={s.btn} aria-pressed={minimap} onClick={() => setMinimap(!minimap)}>Minimap</button>
        <button className={s.btn} aria-pressed={!!splitId} onClick={() => setSplitId(splitId ? null : tabs.find((t) => t.id !== active)?.id ?? null)} disabled={tabs.length < 2}>Split</button>
        {(["run", "problems", "ai", "versions"] as const).map((p) => (
          <button key={p} className={s.btn} aria-pressed={panel === p} onClick={() => setPanel(panel === p ? null : p)}>
            {p === "run" ? "Run" : p === "problems" ? `Problems${issues.length ? ` (${issues.length})` : ""}` : p === "ai" ? "AI" : "Versions"}
          </button>
        ))}
        <select className={s.select} aria-label="More tools" value={MORE.some((m) => m.id === panel) ? panel ?? "" : ""}
          onChange={(e) => setPanel((e.target.value || null) as Panel)}>
          <option value="">More tools…</option>
          {MORE.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
        </select>
        <button className={s.btn} onClick={() => setCmdOpen(true)}>Commands <span className={s.kbd}>⌘K</span></button>
      </div>
      <div className={s.tabs} role="tablist">
        {tabs.map((t) => (
          <span key={t.id} style={{ display: "inline-flex" }}>
            <button role="tab" className={s.tab} aria-selected={t.id === active} onClick={() => setActive(t.id)}
              onDoubleClick={() => { const n = prompt("Tab name", t.name); if (n) setTabs((ts) => ts.map((x) => (x.id === t.id ? { ...x, name: n } : x))); }}>
              {t.name}{t.sid ? <span className={s.muted} title="Saved in the library"> ●</span> : null}
            </button>
            {tabs.length > 1 && <button className={s.close} aria-label={`Close ${t.name}`} onClick={() => closeTab(t.id)}>×</button>}
          </span>
        ))}
        <button className={s.tab} onClick={addTab} aria-label="New tab">+</button>
      </div>
      <div className={s.work}>
        <div className={`${s.editors} cr-editors-host`}>
          {err && <p className={s.warn} role="alert">{err}</p>}
          {tab.sid && (live.conflict || live.editors.length > 1) && <div style={{ gridColumn: "1 / -1" }}><LiveBar live={live} /></div>}
          {ready && (
            <div>
              <Editor key={tab.id} path={`file:///${connectionId}/${tab.id}.py`} language="python" theme="keystone" value={tab.code}
                onChange={(v) => setCode(tab.id, v ?? "")} onMount={onMount} options={options} />
            </div>
          )}
          {ready && split && split.id !== tab.id && (
            <div>
              <Editor key={`split-${split.id}`} path={`file:///${connectionId}/${split.id}.py`} language="python" theme="keystone" value={split.code}
                onChange={(v) => setCode(split.id, v ?? "")} options={options} />
            </div>
          )}
        </div>
        {panel && (
          <aside className={s.side} aria-label="Side panel">
            {panel === "run" && <RunPanel connectionId={connectionId} code={tab.code} goToLine={(line) => goTo({ line, col: 1 } as CRIssue)} />}
            {panel === "problems" && <Problems issues={issues} goTo={goTo} />}
            {panel === "ai" && <AIPanel connectionId={connectionId} code={tab.code} onAccept={(c) => setCode(tab.id, c)} />}
            {panel === "versions" && <VersionsPanel connectionId={connectionId} />}
            {panel === "library" && <LibraryPanel connectionId={connectionId} tab={tab} onOpen={openScript} onLinked={(p) => patchTab(tab.id, p)}
              goToLine={(line) => goTo({ line, col: 1 } as CRIssue)} />}
            {panel === "gallery" && <GalleryPanel connectionId={connectionId} onUse={(name, code) => openTab({ name: `${name}.py`, code })} />}
            {panel === "notebook" && <NotebookPanel connectionId={connectionId} tab={tab} onLinked={(p) => patchTab(tab.id, p)} onCreate={openScript} />}
            {panel === "promote" && <PromotePanel connectionId={connectionId} tab={tab} />}
            {panel === "audit" && <AuditPanel connectionId={connectionId} />}
            {panel === "vault" && <VaultPanel connectionId={connectionId} />}
            {panel === "settings" && <SettingsPanel connectionId={connectionId} />}
          </aside>
        )}
      </div>
      <div className={s.status}>
        <span ref={statusRef} />
        <span>{counts.error} errors · {counts.warning} warnings</span>
        <span className={s.spacer} />
        <span>Test run first, always. Real runs need a matching test run, and money changes need an approver.</span>
      </div>
      {cmdOpen && <CommandBar commands={commands} onClose={() => { setCmdOpen(false); editorRef.current?.focus(); }} />}
    </div>
  );
}

function Problems({ issues, goTo }: { issues: CRIssue[]; goTo: (i: CRIssue) => void }) {
  if (!issues.length) return <p className={s.muted}>No problems found against this database.</p>;
  return (
    <div>
      <h3>Problems</h3>
      {issues.map((i, n) => (
        <button key={n} className={s.issue} data-sev={i.severity} onClick={() => goTo(i)}>
          Line {i.line}: {i.message}{i.fix ? ` Did you mean '${i.fix}'?` : ""}
        </button>
      ))}
    </div>
  );
}

function AIPanel({ connectionId, code, onAccept }: { connectionId: string; code: string; onAccept: (c: string) => void }) {
  const [action, setAction] = useState<CRAIAction>("explain");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<CRAIOut | null>(null);
  const [err, setErr] = useState("");
  const ask = async () => {
    setBusy(true); setErr(""); setOut(null);
    try {
      setOut(await codeRunnerApi.ai(connectionId, { action, code, request: action === "comment_to_code" ? text : "", error: action === "fix" ? text : "" }));
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <h3>Ask the assistant</h3>
      <select className={s.select} value={action} onChange={(e) => setAction(e.target.value as CRAIAction)} aria-label="What to do">
        <option value="explain">Explain this script</option>
        <option value="comment_to_code">Write code from my comments</option>
        <option value="fix">Fix an error</option>
      </select>
      {action !== "explain" && (
        <textarea className={s.input} rows={3} value={text} onChange={(e) => setText(e.target.value)}
          placeholder={action === "fix" ? "Paste the error message" : "Anything to add (optional)"} />
      )}
      <button className={`${s.btn} ${s.primary}`} onClick={ask} disabled={busy}>{busy ? "Thinking…" : "Ask"}</button>
      {err && <p className={s.warn} role="alert">{err}</p>}
      {out && !out.ok && <p className={s.warn}>{out.reason}</p>}
      {out?.explanation && <p className={s.note}>{out.explanation}</p>}
      {out?.ok && out.code && (
        <>
          {!!out.money?.length && <p className={s.warn}>This change writes to money records ({out.money.join(", ")}). It will need a test run and approval when it runs.</p>}
          {!!out.issues?.length && <p className={s.muted}>{out.issues.length} problem(s) found in the suggestion; check them before accepting.</p>}
          <div style={{ blockSize: 260, border: "1px solid var(--border-subtle)" }}>
            <DiffEditor original={code} modified={out.code} language="python" theme="keystone"
              options={{ renderSideBySide: false, readOnly: true, minimap: { enabled: false }, automaticLayout: true }} />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className={`${s.btn} ${s.primary}`} onClick={() => { onAccept(out.code); setOut(null); }}>Accept change</button>
            <button className={s.btn} onClick={() => setOut(null)}>Discard</button>
          </div>
        </>
      )}
    </div>
  );
}

function VersionsPanel({ connectionId }: { connectionId: string }) {
  const [conns, setConns] = useState<Connection[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [model, setModel] = useState("res.partner");
  const [out, setOut] = useState<CRVersions | null>(null);
  const [onlyDiff, setOnlyDiff] = useState(true);
  const [err, setErr] = useState("");
  useEffect(() => { connectionsApi.listConnections().then((c) => setConns(c.filter((x) => x.id !== connectionId))).catch(() => setConns([])); }, [connectionId]);
  const run = async () => {
    setErr("");
    try { setOut(await codeRunnerApi.versions(connectionId, model, picked)); } catch (e) { setErr((e as Error).message); }
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <h3>One model across versions</h3>
      <input className={s.input} value={model} onChange={(e) => setModel(e.target.value)} aria-label="Model" />
      <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
        <legend className={s.muted}>Compare with</legend>
        {conns.map((c) => (
          <label key={c.id} style={{ display: "block" }}>
            <input type="checkbox" checked={picked.includes(c.id)} onChange={(e) => setPicked(e.target.checked ? [...picked, c.id] : picked.filter((x) => x !== c.id))} />{" "}
            {c.name} {c.server_version ? `(${c.server_version})` : ""}
          </label>
        ))}
      </fieldset>
      <button className={`${s.btn} ${s.primary}`} onClick={run}>Compare</button>
      {err && <p className={s.warn} role="alert">{err}</p>}
      {out && (
        <>
          <p className={s.muted}>{out.differing} field(s) differ.{out.missing_model.length ? ` Missing on Odoo ${out.missing_model.join(", ")}.` : ""}</p>
          <label><input type="checkbox" checked={onlyDiff} onChange={(e) => setOnlyDiff(e.target.checked)} /> Only differences</label>
          <table className={s.table}>
            <thead><tr><th>Field</th>{out.versions.map((v) => <th key={v}>{v}</th>)}</tr></thead>
            <tbody>
              {out.rows.filter((r) => !onlyDiff || r.differs).map((r) => (
                <tr key={r.field} data-differs={r.differs}>
                  <td>{r.field}</td>
                  {out.versions.map((v) => <td key={v}>{r.cells[v]?.type ?? "—"}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

type Cmd = { id: string; label: string; key: string; run: () => void };
function CommandBar({ commands, onClose }: { commands: Cmd[]; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const list = commands.filter((c) => c.label.toLowerCase().includes(q.toLowerCase()));
  const pick = (c?: Cmd) => { if (c) { onClose(); c.run(); } };
  return (
    <div className={s.cmdBackdrop} onClick={onClose} role="presentation">
      <div className={s.cmd} role="dialog" aria-modal="true" aria-label="Commands" onClick={(e) => e.stopPropagation()}>
        <input autoFocus value={q} placeholder="Type a command…" aria-label="Command"
          onChange={(e) => { setQ(e.target.value); setI(0); }}
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
            if (e.key === "ArrowDown") { e.preventDefault(); setI(Math.min(i + 1, list.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setI(Math.max(i - 1, 0)); }
            if (e.key === "Enter") pick(list[i]);
          }} />
        <ul>
          {list.map((c, n) => (
            <li key={c.id}><button className={s.cmdItem} data-active={n === i} onMouseEnter={() => setI(n)} onClick={() => pick(c)}>
              <span>{c.label}</span>{c.key && <span className={s.kbd}>{c.key}</span>}
            </button></li>
          ))}
          {!list.length && <li className={s.muted} style={{ padding: 10 }}>No command matches.</li>}
        </ul>
      </div>
    </div>
  );
}
