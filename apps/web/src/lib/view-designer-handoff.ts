import type { PreviewFormView } from "@/lib/draft-form-preview";

/** App Studio -> View Designer: the generated (not yet installed) view travels in sessionStorage, keyed in the URL. */
const PREFIX = "ingenium.vd-handoff.";

export function stashDesignerDraft(view: PreviewFormView): string {
  const key = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
  try { window.sessionStorage.setItem(PREFIX + key, JSON.stringify(view)); } catch { /* storage full/blocked: link still opens the model */ }
  return key;
}

export function readDesignerDraft(key: string | null | undefined): PreviewFormView | null {
  if (!key) return null;
  try {
    const raw = window.sessionStorage.getItem(PREFIX + key);
    const v = raw ? (JSON.parse(raw) as PreviewFormView) : null;
    return v && v.type === "form" && Array.isArray(v.groups) ? v : null;
  } catch { return null; }
}

export function designerDraftHref(connectionId: string, model: string, key: string): string {
  return `/connections/${encodeURIComponent(connectionId)}/view-designer?model=${encodeURIComponent(model)}&type=form&draft=${encodeURIComponent(key)}`;
}
