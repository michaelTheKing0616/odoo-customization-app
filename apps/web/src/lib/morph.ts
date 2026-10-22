/**
 * Touch 35: shared-element morphs. The thing you clicked (a connection card, a row, a script card)
 * grows into the page it opens, so you never lose your place. Uses the View Transitions API;
 * without it, or with reduced motion, it is a plain navigation.
 */
const NAME = "ing-morph";
type VTDoc = Document & { startViewTransition?: (cb: () => Promise<void> | void) => { finished: Promise<void> } };

export function canMorph(): boolean {
  if (typeof document === "undefined") return false;
  const d = document as VTDoc;
  return typeof d.startViewTransition === "function" && !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

function routeSettled(timeoutMs = 1200): Promise<void> {
  return new Promise((resolve) => {
    const t = window.setTimeout(done, timeoutMs);
    function done() { window.clearTimeout(t); window.removeEventListener("ingenium:route-settled", done); resolve(); }
    window.addEventListener("ingenium:route-settled", done);
  });
}

export function morphNavigate(push: (href: string) => void, href: string, source: HTMLElement | null): void {
  if (!source || !canMorph()) { push(href); return; }
  const d = document as VTDoc;
  source.style.setProperty("view-transition-name", NAME);
  const vt = d.startViewTransition!(async () => {
    source.style.removeProperty("view-transition-name");
    push(href);
    await routeSettled();
    document.querySelector<HTMLElement>(".page-move-host")?.style.setProperty("view-transition-name", NAME);
  });
  void vt.finished.finally(() => document.querySelector<HTMLElement>(".page-move-host")?.style.removeProperty("view-transition-name"));
}

/** Same-page morph: `source` grows into the element matching `targetSelector` after `update` renders it. */
export function morphInPlace(source: HTMLElement | null, update: () => void | Promise<void>, targetSelector: string): void {
  if (!source || !canMorph()) { void update(); return; }
  const d = document as VTDoc;
  source.style.setProperty("view-transition-name", NAME);
  const vt = d.startViewTransition!(async () => {
    source.style.removeProperty("view-transition-name");
    await update();
    await new Promise<void>((r) => requestAnimationFrame(() => r()));
    document.querySelector<HTMLElement>(targetSelector)?.style.setProperty("view-transition-name", NAME);
  });
  void vt.finished.finally(() => document.querySelector<HTMLElement>(targetSelector)?.style.removeProperty("view-transition-name"));
}
