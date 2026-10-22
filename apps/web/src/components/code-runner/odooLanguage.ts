import type * as Monaco from "monaco-editor";
import { codeRunnerApi, type CRField, type CRSchema, type CRSnippet } from "@/lib/api/code-runner";

/** Model named by the nearest execute_kw("model", ...) before the cursor. */
export function nearestModel(textBefore: string): string | null {
  const all = [...textBefore.matchAll(/execute_kw\(\s*["']([\w.]+)["']/g)];
  return all.length ? all[all.length - 1][1] : null;
}

export type Ctx = { kind: "model" | "method" | "field" | "code"; model?: string };

export function contextAt(line: string, textBefore: string): Ctx {
  if (/execute_kw\(\s*["'][\w.]*$/.test(line)) return { kind: "model" };
  const m = line.match(/execute_kw\(\s*["']([\w.]+)["']\s*,\s*["']\w*$/);
  if (m) return { kind: "method", model: m[1] };
  const quotes = (line.match(/["']/g) ?? []).length;
  if (quotes % 2 === 1) return { kind: "field", model: nearestModel(textBefore) ?? undefined };
  return { kind: "code" };
}

/** Registers Odoo-aware completion and hover for Python on one connection; returns a disposer. */
export function registerOdooLanguage(monaco: typeof Monaco, connectionId: string, schema: CRSchema, snippets: CRSnippet[]) {
  const fieldCache = new Map<string, Promise<Record<string, CRField>>>();
  const fieldsOf = (model: string) => {
    if (!fieldCache.has(model)) fieldCache.set(model, codeRunnerApi.fields(connectionId, model).then((r) => r.fields).catch(() => ({})));
    return fieldCache.get(model)!;
  };
  const K = monaco.languages.CompletionItemKind;
  const completion = monaco.languages.registerCompletionItemProvider("python", {
    triggerCharacters: ['"', "'", ".", ","],
    async provideCompletionItems(model, pos) {
      const word = model.getWordUntilPosition(pos);
      const range = { startLineNumber: pos.lineNumber, endLineNumber: pos.lineNumber, startColumn: word.startColumn, endColumn: word.endColumn };
      const line = model.getLineContent(pos.lineNumber).slice(0, pos.column - 1);
      const before = model.getValueInRange({ startLineNumber: 1, startColumn: 1, endLineNumber: pos.lineNumber, endColumn: pos.column });
      const ctx = contextAt(line, before);
      if (ctx.kind === "model") {
        const dotted = line.match(/["']([\w.]*)$/)?.[1] ?? "";
        const r = { ...range, startColumn: pos.column - dotted.length };
        return { suggestions: schema.models.map((m) => ({ label: m.model, detail: m.name, kind: K.Class, insertText: m.model, range: r })) };
      }
      if (ctx.kind === "method") {
        return { suggestions: Object.entries(schema.methods).map(([k, doc]) => ({ label: k, detail: `Odoo ${schema.major}`, documentation: doc, kind: K.Method, insertText: k, range })) };
      }
      if (ctx.kind === "field" && ctx.model) {
        const f = await fieldsOf(ctx.model);
        return { suggestions: Object.entries(f).map(([k, v]) => ({
          label: k, detail: `${v.type}${v.relation ? ` → ${v.relation}` : ""} · ${v.string}`,
          documentation: [v.help, v.selection?.map((s) => `${s[0]} = ${s[1]}`).join(", ")].filter(Boolean).join("\n\n"),
          kind: K.Field, insertText: k, range })) };
      }
      return { suggestions: snippets.map((s) => ({ label: `odoo: ${s.label}`, detail: s.detail, kind: K.Snippet, insertText: s.body,
        insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range })) };
    },
  });
  const hover = monaco.languages.registerHoverProvider("python", {
    async provideHover(model, pos) {
      const w = model.getWordAtPosition(pos);
      if (!w) return null;
      const range = new monaco.Range(pos.lineNumber, w.startColumn, pos.lineNumber, w.endColumn);
      const dep = schema.deprecated[w.word];
      if (dep) return { range, contents: [{ value: `**${w.word}** — ${dep.message}. Use \`${dep.use}\`.` }] };
      if (schema.methods[w.word]) return { range, contents: [{ value: `**${w.word}** (Odoo ${schema.major})\n\n${schema.methods[w.word]}` }] };
      const hit = schema.models.find((m) => m.model === w.word);
      if (hit) return { range, contents: [{ value: `**${hit.model}** — ${hit.name}` }] };
      const before = model.getValueInRange({ startLineNumber: 1, startColumn: 1, endLineNumber: pos.lineNumber, endColumn: w.endColumn });
      const m = nearestModel(before);
      if (!m) return null;
      const f = (await fieldsOf(m))[w.word];
      return f ? { range, contents: [{ value: `**${m}.${w.word}** · ${f.type}${f.relation ? ` → ${f.relation}` : ""}\n\n${f.string}${f.help ? `\n\n${f.help}` : ""}` }] } : null;
    },
  });
  return () => { completion.dispose(); hover.dispose(); };
}

/** Keystone theme from the live design tokens (Monaco needs concrete colours). */
export function keystoneTheme(monaco: typeof Monaco, el: HTMLElement) {
  const css = getComputedStyle(el);
  const v = (name: string, fallback: string) => {
    const raw = css.getPropertyValue(name).trim();
    if (!raw) return fallback;
    const probe = document.createElement("span");
    probe.style.color = raw;
    document.body.appendChild(probe);
    const rgb = getComputedStyle(probe).color.match(/\d+/g) ?? [];
    probe.remove();
    return rgb.length >= 3 ? "#" + rgb.slice(0, 3).map((n) => Number(n).toString(16).padStart(2, "0")).join("") : fallback;
  };
  const dark = matchMedia("(prefers-color-scheme: dark)").matches && document.documentElement.dataset.theme !== "light";
  const bg = v("--surface", dark ? "#111111" : "#ffffff");
  const ink = v("--ink", dark ? "#eeeeee" : "#1a1a1a");
  const accent = v("--accent", "#0f766e");
  const muted = v("--muted", "#6b7280");
  monaco.editor.defineTheme("keystone", {
    base: dark ? "vs-dark" : "vs", inherit: true,
    rules: [
      { token: "comment", foreground: muted.slice(1), fontStyle: "italic" },
      { token: "keyword", foreground: accent.slice(1) },
      { token: "string", foreground: v("--success-strong", "#15803d").slice(1) },
      { token: "number", foreground: v("--warning-strong", "#b45309").slice(1) },
    ],
    colors: { "editor.background": bg, "editor.foreground": ink, "editorCursor.foreground": accent,
      "editor.lineHighlightBackground": v("--surface-muted", bg), "editorLineNumber.foreground": muted,
      "editor.selectionBackground": v("--accent-subtle", "#ccfbf1") },
  });
}
