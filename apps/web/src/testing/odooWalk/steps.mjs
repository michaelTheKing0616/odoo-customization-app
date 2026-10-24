// BV-04: expand plan steps (built server-side from the change-set) into browser actions.
// Page text is never read back into the plan.
import { selectorsFor } from './selectors.mjs';

export function homeFor(major) {
  return Number(major) >= 18 ? '/odoo?debug=1' : '/web?debug=1';
}

export function describe(step, major) {
  const sel = selectorsFor(major);
  switch (step.action) {
    case 'open':
      return { kind: 'goto', url: homeFor(major), model: step.model, view: step.view, home: sel.home, wait: sel[step.view] };
    case 'assert':
      if (step.view === 'saved') return { kind: 'assert', absent: [sel.error, sel.dirty] };
      return { kind: 'assert', visible: sel[step.view], absent: [sel.error] };
    case 'fill':
      return { kind: 'fill', selector: step.selector, value: step.value, optional: String(step.target).endsWith('?') };
    case 'click':
      return { kind: 'click', selector: sel[step.selector] ?? null, settled: step.selector === 'save' ? sel.dirty : null };
    default:
      return { kind: 'unknown' };
  }
}

export function domAssertion(d) {
  if (d.kind === 'assert') {
    const parts = [];
    if (d.visible) parts.push(`visible:${d.visible}`);
    for (const a of d.absent ?? []) parts.push(`absent:${a}`);
    return parts.join(' && ');
  }
  if (d.kind === 'goto') return `visible:${d.wait}`;
  if (d.kind === 'fill') return `filled:${d.selector}`;
  if (d.kind === 'click') return `clicked:${d.selector}`;
  return null;
}
