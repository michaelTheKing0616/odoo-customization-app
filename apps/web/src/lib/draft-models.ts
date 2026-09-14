/** Primary custom model helpers shared by App Studio and Draft Studio. */

function modelIdFromUnknown(raw: unknown): string | null {
  if (typeof raw === "string") {
    const mid = raw.trim();
    return mid || null;
  }
  if (!raw || typeof raw !== "object") return null;
  const mid = String((raw as { model?: string }).model || "").trim();
  return mid || null;
}

function isPrimaryCustomModel(mid: string): boolean {
  return mid.startsWith("x_") && !mid.endsWith("_line");
}

function isLineModel(mid: string): boolean {
  return mid.endsWith("_line");
}

function previewModelFromEngine(draft: Record<string, unknown>): string | null {
  const engine = draft._generation_engine;
  if (!engine || typeof engine !== "object" || Array.isArray(engine)) return null;
  return modelIdFromUnknown((engine as { form_preview?: unknown }).form_preview);
}

export function primaryCustomModelFromDraft(
  draft: Record<string, unknown> | null | undefined,
): string | null {
  if (!draft) return null;
  const models = Array.isArray(draft.models) ? draft.models : [];
  for (const raw of models) {
    const mid = modelIdFromUnknown(raw);
    if (mid && isPrimaryCustomModel(mid)) return mid;
  }
  const mid = previewModelFromEngine(draft);
  if (mid && isPrimaryCustomModel(mid)) return mid;
  return null;
}

export function inheritHostModelFromDraft(
  draft: Record<string, unknown> | null | undefined,
): string | null {
  if (!draft) return null;
  const models = Array.isArray(draft.models) ? draft.models : [];
  for (const raw of models) {
    const mid = modelIdFromUnknown(raw);
    if (!mid || isLineModel(mid)) continue;
    const mode =
      raw && typeof raw === "object" ? String((raw as { mode?: string }).mode || "") : "";
    if (mode === "inherit" || !mid.startsWith("x_")) return mid;
  }
  const mid = previewModelFromEngine(draft);
  if (mid && !mid.startsWith("x_") && !isLineModel(mid)) return mid;
  return null;
}

export function isFieldPackDraft(draft: Record<string, unknown> | null | undefined): boolean {
  if (!draft) return false;
  const engine = draft._generation_engine;
  if (engine && typeof engine === "object" && !Array.isArray(engine)) {
    const cap = (engine as { capability?: string }).capability;
    if (cap === "option_a_authored" || cap === "option_a_standalone") return false;
    if ((engine as { grain?: string }).grain === "field_pack") return true;
  }
  if (draft.grain === "field_pack") return true;
  return Boolean(inheritHostModelFromDraft(draft) && !primaryCustomModelFromDraft(draft));
}

function fieldRows(model: unknown): Record<string, unknown>[] {
  if (!model || typeof model !== "object") return [];
  const fields = (model as { fields?: unknown[] }).fields;
  if (!Array.isArray(fields)) return [];
  return fields.filter(
    (row): row is Record<string, unknown> => Boolean(row && typeof row === "object"),
  );
}

function chipsFromFields(fields: Record<string, unknown>[]): string[] {
  const chips: string[] = [];
  const optional = fields.find((field) => {
    const name = String(field.name || "");
    return name && name !== "x_name" && name !== "x_status" && field.required !== true;
  });
  if (optional) {
    const label = String(optional.string || optional.name || "").replace(/^x_/, "");
    if (label) chips.push(`remove ${label}`);
  }
  const requiredCandidate = fields.find((field) => {
    const name = String(field.name || "");
    return name && name !== "x_name" && field.required !== true;
  });
  if (requiredCandidate) {
    const label = String(requiredCandidate.string || requiredCandidate.name || "").replace(
      /^x_/,
      "",
    );
    if (label) chips.push(`make the ${label} field required`);
  }
  return chips;
}

export type FormSlotOption = {
  id: string;
  label: string;
  phrase: string;
};

export type InheritPlacementRow = {
  name: string;
  string: string;
  slot: string;
};

function formSlotsStamp(
  draft: Record<string, unknown> | null | undefined,
): Record<string, unknown> | null {
  const raw = draft?._form_slots;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  return raw as Record<string, unknown>;
}

export function formSlotCatalog(
  draft: Record<string, unknown> | null | undefined,
): FormSlotOption[] {
  const stamp = formSlotsStamp(draft);
  const catalog = stamp?.catalog;
  if (!Array.isArray(catalog)) return [];
  return catalog
    .filter((row): row is Record<string, unknown> => Boolean(row && typeof row === "object"))
    .map((row) => ({
      id: String(row.id || ""),
      label: String(row.label || row.id || ""),
      phrase: String(row.phrase || ""),
    }))
    .filter((row) => row.id);
}

export function inheritPlacementRows(
  draft: Record<string, unknown> | null | undefined,
): InheritPlacementRow[] {
  if (!draft) return [];
  const stamp = formSlotsStamp(draft);
  const mapping =
    stamp?.fields && typeof stamp.fields === "object" && !Array.isArray(stamp.fields)
      ? (stamp.fields as Record<string, unknown>)
      : {};
  const models = Array.isArray(draft.models) ? draft.models : [];
  const rows: InheritPlacementRow[] = [];
  for (const model of models) {
    const mid = modelIdFromUnknown(model);
    if (!mid || isLineModel(mid)) continue;
    const mode =
      model && typeof model === "object" ? String((model as { mode?: string }).mode || "") : "";
    if (mode !== "inherit" && mid.startsWith("x_")) continue;
    for (const field of fieldRows(model)) {
      const name = String(field.name || "");
      if (!name || name.endsWith("_ids")) continue;
      const label = String(field.string || name).replace(/^x_/, "");
      rows.push({
        name,
        string: label,
        slot: String(mapping[name] || "next_to_dates"),
      });
    }
    if (rows.length) break;
  }
  return rows;
}

/** Refine chips grounded in the draft — never a stale “add a due date”. */
export function refineSuggestionsFromDraft(
  draft: Record<string, unknown> | null | undefined,
): string[] {
  const models = Array.isArray(draft?.models) ? draft.models : [];
  for (const model of models) {
    const mid = modelIdFromUnknown(model);
    if (!mid || !isPrimaryCustomModel(mid)) continue;
    const chips = chipsFromFields(fieldRows(model));
    if (chips.length) return chips.slice(0, 3);
  }
  for (const model of models) {
    const mid = modelIdFromUnknown(model);
    if (!mid || isLineModel(mid)) continue;
    const mode =
      model && typeof model === "object" ? String((model as { mode?: string }).mode || "") : "";
    if (mode !== "inherit" && mid.startsWith("x_")) continue;
    const chips = chipsFromFields(fieldRows(model));
    const first = inheritPlacementRows(draft)[0];
    const catalog = formSlotCatalog(draft);
    const partner = catalog.find((row) => row.id === "next_to_partner");
    if (first && partner && first.slot !== "next_to_partner") {
      chips.unshift(`put ${first.string} ${partner.phrase}`);
    }
    if (chips.length) return chips.slice(0, 3);
  }
  return [];
}

export function viewDesignerHref(
  connectionId: string,
  draft: Record<string, unknown> | null | undefined,
): string {
  const model = primaryCustomModelFromDraft(draft) || inheritHostModelFromDraft(draft);
  const base = `/connections/${connectionId}/designer`;
  return model ? `${base}?model=${encodeURIComponent(model)}` : base;
}
