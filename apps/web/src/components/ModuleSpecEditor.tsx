"use client";

import { useMemo, useState } from "react";

export type ModuleSpecField = {
  name: string;
  ttype?: string;
  string?: string;
  required?: boolean;
  readonly?: boolean;
  relation?: string | null;
  relation_field?: string | null;
  selection?: string | null;
  help?: string | null;
};

export type ModuleSpecModel = {
  model: string;
  description?: string;
  mode?: string;
  mixins?: string[];
  fields?: ModuleSpecField[];
};

export type ModuleSpecDoc = {
  technical_name?: string;
  display_name?: string;
  depends?: string[];
  models?: ModuleSpecModel[];
  views?: unknown[];
  menus?: unknown[];
  actions?: unknown[];
  smart_buttons?: Array<Record<string, unknown>>;
  automations?: Array<Record<string, unknown>>;
  unmapped?: Array<Record<string, unknown>>;
  [key: string]: unknown;
};

type Props = {
  value: ModuleSpecDoc;
  onChange: (next: ModuleSpecDoc) => void;
  readOnly?: boolean;
};

const TTYPES = [
  "char",
  "text",
  "integer",
  "float",
  "boolean",
  "date",
  "datetime",
  "selection",
  "many2one",
  "one2many",
  "many2many",
  "binary",
  "html",
  "monetary",
  "json",
];

function ensureModels(spec: ModuleSpecDoc): ModuleSpecModel[] {
  return Array.isArray(spec.models) ? [...spec.models] : [];
}

export function ModuleSpecEditor({ value, onChange, readOnly }: Props) {
  const [tab, setTab] = useState<"models" | "relations" | "extras" | "json" | "unmapped">(
    "models",
  );
  const [selectedModel, setSelectedModel] = useState(0);
  const models = ensureModels(value);
  const model = models[selectedModel];

  const summary = useMemo(
    () => ({
      models: models.length,
      fields: models.reduce((n, m) => n + (m.fields?.length ?? 0), 0),
      views: Array.isArray(value.views) ? value.views.length : 0,
      smart: Array.isArray(value.smart_buttons) ? value.smart_buttons.length : 0,
      autos: Array.isArray(value.automations) ? value.automations.length : 0,
      unmapped: Array.isArray(value.unmapped) ? value.unmapped.length : 0,
    }),
    [models, value],
  );

  function patch(partial: Partial<ModuleSpecDoc>) {
    onChange({ ...value, ...partial });
  }

  function updateModels(next: ModuleSpecModel[]) {
    patch({ models: next });
  }

  function updateModel(idx: number, next: ModuleSpecModel) {
    const copy = ensureModels(value);
    copy[idx] = next;
    updateModels(copy);
  }

  function addModel() {
    const n = models.length + 1;
    updateModels([
      ...models,
      {
        model: `x_new_model_${n}`,
        description: `New Model ${n}`,
        mode: "new",
        fields: [
          { name: "x_name", ttype: "char", string: "Name", required: true },
        ],
      },
    ]);
    setSelectedModel(models.length);
  }

  function removeModel(idx: number) {
    const copy = models.filter((_, i) => i !== idx);
    updateModels(copy);
    setSelectedModel(Math.max(0, Math.min(selectedModel, copy.length - 1)));
  }

  function addField() {
    if (!model) return;
    const fields = [...(model.fields || [])];
    fields.push({ name: `x_field_${fields.length + 1}`, ttype: "char", string: "Field" });
    updateModel(selectedModel, { ...model, fields });
  }

  function updateField(fi: number, field: ModuleSpecField) {
    if (!model) return;
    const fields = [...(model.fields || [])];
    fields[fi] = field;
    updateModel(selectedModel, { ...model, fields });
  }

  function removeField(fi: number) {
    if (!model) return;
    const fields = (model.fields || []).filter((_, i) => i !== fi);
    updateModel(selectedModel, { ...model, fields });
  }

  const tabs: Array<{ id: typeof tab; label: string }> = [
    { id: "models", label: `Models (${summary.models})` },
    { id: "relations", label: "Relations" },
    { id: "extras", label: `UI / Autos (${summary.smart + summary.autos})` },
    { id: "unmapped", label: `Code-only (${summary.unmapped})` },
    { id: "json", label: "JSON" },
  ];

  return (
    <div className="border border-[#3d2a38] bg-[#0f1a16]/70">
      <div className="flex flex-wrap items-end gap-3 border-b border-[#1e2f29] p-4">
        <label className="min-w-[10rem] flex-1 text-sm">
          <span className="text-[#a8909e]">Display name</span>
          <input
            disabled={readOnly}
            value={String(value.display_name ?? "")}
            onChange={(e) => patch({ display_name: e.target.value })}
            className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
          />
        </label>
        <label className="min-w-[10rem] flex-1 text-sm">
          <span className="text-[#a8909e]">Technical name</span>
          <input
            disabled={readOnly}
            value={String(value.technical_name ?? "")}
            onChange={(e) => patch({ technical_name: e.target.value })}
            className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
          />
        </label>
        <p className="pb-2 text-xs text-[#8f7a88]">
          {summary.fields} fields · {summary.views} views · ModuleSpec contract
        </p>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-[#1e2f29] px-2 pt-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`px-3 py-2 text-sm ${
              tab === t.id
                ? "border-b-2 border-[#c9a9c0] text-[#c9a9c0]"
                : "text-[#8f7a88] hover:text-[#d4c4ce]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "models" && (
        <div className="grid gap-0 md:grid-cols-[14rem_1fr]">
          <aside className="border-r border-[#1e2f29] p-3">
            <ul className="space-y-1">
              {models.map((m, i) => (
                <li key={i}>
                  <button
                    type="button"
                    onClick={() => setSelectedModel(i)}
                    className={`w-full truncate px-2 py-1.5 text-left font-mono text-xs ${
                      selectedModel === i
                        ? "bg-[#1a1218] text-[#c9a9c0]"
                        : "text-[#d4c4ce] hover:bg-[#1a1218]"
                    }`}
                  >
                    {m.model}
                  </button>
                </li>
              ))}
            </ul>
            {!readOnly && (
              <button
                type="button"
                onClick={addModel}
                className="mt-3 w-full border border-[#3d2a38] px-2 py-1.5 text-xs text-[#c9a9c0]"
              >
                + Add model
              </button>
            )}
          </aside>
          <div className="p-4">
            {!model ? (
              <p className="text-sm text-[#8f7a88]">No models yet.</p>
            ) : (
              <>
                <div className="flex flex-wrap gap-3">
                  <label className="min-w-[12rem] flex-1 text-sm">
                    <span className="text-[#a8909e]">Model</span>
                    <input
                      disabled={readOnly}
                      value={model.model}
                      onChange={(e) =>
                        updateModel(selectedModel, { ...model, model: e.target.value })
                      }
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-sm"
                    />
                  </label>
                  <label className="min-w-[12rem] flex-1 text-sm">
                    <span className="text-[#a8909e]">Label</span>
                    <input
                      disabled={readOnly}
                      value={model.description ?? ""}
                      onChange={(e) =>
                        updateModel(selectedModel, {
                          ...model,
                          description: e.target.value,
                        })
                      }
                      className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
                    />
                  </label>
                  {!readOnly && (
                    <button
                      type="button"
                      onClick={() => removeModel(selectedModel)}
                      className="self-end border border-[#f0a8a0] px-3 py-1.5 text-xs text-[#f0a8a0]"
                    >
                      Remove model
                    </button>
                  )}
                </div>

                <div className="mt-4 overflow-x-auto">
                  <table className="w-full min-w-[36rem] text-left text-sm">
                    <thead className="text-xs uppercase text-[#8f7a88]">
                      <tr>
                        <th className="py-1 pr-2">Name</th>
                        <th className="py-1 pr-2">Type</th>
                        <th className="py-1 pr-2">Label</th>
                        <th className="py-1 pr-2">Relation</th>
                        <th className="py-1">Req</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {(model.fields || []).map((f, fi) => (
                        <tr key={fi} className="border-t border-[#1e2f29]">
                          <td className="py-1 pr-2">
                            <input
                              disabled={readOnly}
                              value={f.name}
                              onChange={(e) =>
                                updateField(fi, { ...f, name: e.target.value })
                              }
                              className="w-full border border-[#3d2a38] bg-[#0c090b] px-1.5 py-1 font-mono text-xs"
                            />
                          </td>
                          <td className="py-1 pr-2">
                            <select
                              disabled={readOnly}
                              value={f.ttype || "char"}
                              onChange={(e) =>
                                updateField(fi, { ...f, ttype: e.target.value })
                              }
                              className="w-full border border-[#3d2a38] bg-[#0c090b] px-1.5 py-1 text-xs"
                            >
                              {TTYPES.map((t) => (
                                <option key={t} value={t}>
                                  {t}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="py-1 pr-2">
                            <input
                              disabled={readOnly}
                              value={f.string ?? ""}
                              onChange={(e) =>
                                updateField(fi, { ...f, string: e.target.value })
                              }
                              className="w-full border border-[#3d2a38] bg-[#0c090b] px-1.5 py-1 text-xs"
                            />
                          </td>
                          <td className="py-1 pr-2">
                            <input
                              disabled={readOnly}
                              value={f.relation ?? ""}
                              onChange={(e) =>
                                updateField(fi, {
                                  ...f,
                                  relation: e.target.value || null,
                                })
                              }
                              placeholder="res.partner"
                              className="w-full border border-[#3d2a38] bg-[#0c090b] px-1.5 py-1 font-mono text-xs"
                            />
                          </td>
                          <td className="py-1">
                            <input
                              type="checkbox"
                              disabled={readOnly}
                              checked={Boolean(f.required)}
                              onChange={(e) =>
                                updateField(fi, { ...f, required: e.target.checked })
                              }
                            />
                          </td>
                          <td className="py-1 pl-2">
                            {!readOnly && (
                              <button
                                type="button"
                                onClick={() => removeField(fi)}
                                className="text-xs text-[#f0a8a0]"
                              >
                                ×
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!readOnly && (
                    <button
                      type="button"
                      onClick={addField}
                      className="mt-3 border border-[#3d2a38] px-3 py-1.5 text-xs text-[#c9a9c0]"
                    >
                      + Add field
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {tab === "relations" && (
        <div className="space-y-2 p-4 text-sm">
          <p className="text-[#8f7a88]">
            Relational fields across models (many2one / one2many / many2many).
          </p>
          <ul className="space-y-1 font-mono text-xs text-[#d4c4ce]">
            {models.flatMap((m) =>
              (m.fields || [])
                .filter((f) =>
                  ["many2one", "one2many", "many2many"].includes(
                    String(f.ttype || ""),
                  ),
                )
                .map((f) => (
                  <li key={`${m.model}.${f.name}`}>
                    {m.model}.{f.name} → {f.ttype} {f.relation || "?"}
                  </li>
                )),
            )}
          </ul>
        </div>
      )}

      {tab === "extras" && (
        <div className="grid gap-4 p-4 md:grid-cols-2">
          <div>
            <h3 className="text-sm text-[#a8909e]">Smart buttons</h3>
            <pre className="mt-2 max-h-48 overflow-auto border border-[#1e2f29] bg-[#0c090b] p-2 text-xs text-[#d4c4ce]">
              {JSON.stringify(value.smart_buttons ?? [], null, 2)}
            </pre>
          </div>
          <div>
            <h3 className="text-sm text-[#a8909e]">Automations (metadata)</h3>
            <pre className="mt-2 max-h-48 overflow-auto border border-[#1e2f29] bg-[#0c090b] p-2 text-xs text-[#d4c4ce]">
              {JSON.stringify(value.automations ?? [], null, 2)}
            </pre>
          </div>
          <div className="md:col-span-2">
            <h3 className="text-sm text-[#a8909e]">Depends</h3>
            <input
              disabled={readOnly}
              value={(value.depends || []).join(", ")}
              onChange={(e) =>
                patch({
                  depends: e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                })
              }
              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
            />
          </div>
        </div>
      )}

      {tab === "unmapped" && (
        <div className="p-4">
          <p className="text-sm text-[#8f7a88]">
            Custom Python methods / non-view XML preserved from Code→UI import — view as
            code, not edited visually.
          </p>
          {(value.unmapped || []).length === 0 ? (
            <p className="mt-3 text-sm text-[#c9a9c0]">None — full visual fidelity.</p>
          ) : (
            <ul className="mt-3 space-y-3">
              {(value.unmapped || []).map((u, i) => (
                <li
                  key={i}
                  className="border border-[#3d2a38] bg-[#0c090b] p-3 text-xs text-[#d4c4ce]"
                >
                  <p className="font-mono text-[#c9a96e]">
                    {String(u.kind)} · {String(u.path || u.model || "")}
                  </p>
                  <p className="mt-1 text-[#8f7a88]">{String(u.reason || "")}</p>
                  <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap">
                    {typeof u.source === "string"
                      ? u.source.slice(0, 2000)
                      : JSON.stringify(u.snippets || u, null, 2).slice(0, 2000)}
                  </pre>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {tab === "json" && (
        <div className="p-4">
          <textarea
            disabled={readOnly}
            value={JSON.stringify(value, null, 2)}
            onChange={(e) => {
              try {
                const parsed = JSON.parse(e.target.value) as ModuleSpecDoc;
                onChange(parsed);
              } catch {
                /* keep typing until valid */
              }
            }}
            rows={18}
            className="w-full border border-[#3d2a38] bg-[#0c090b] p-3 font-mono text-xs text-[#d4c4ce]"
          />
        </div>
      )}
    </div>
  );
}
