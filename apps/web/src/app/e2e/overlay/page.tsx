"use client";

import { useRef, useState } from "react";
import { OverlayEditor } from "@/components/designer/OverlayEditor";
import type { FieldRow } from "@/lib/api";

const MOCK_FIELDS: FieldRow[] = [
  {
    id: 1,
    name: "name",
    field_description: "Name",
    ttype: "char",
    required: true,
    readonly: false,
    relation: null,
    state: "base",
  },
  {
    id: 2,
    name: "email",
    field_description: "Email",
    ttype: "char",
    required: false,
    readonly: false,
    relation: null,
    state: "base",
  },
  {
    id: 3,
    name: "phone",
    field_description: "Phone",
    ttype: "char",
    required: false,
    readonly: false,
    relation: null,
    state: "base",
  },
  {
    id: 4,
    name: "x_note",
    field_description: "Note",
    ttype: "text",
    required: false,
    readonly: false,
    relation: null,
    state: "base",
  },
];

/** E2E harness for overlay editor without a live Odoo iframe. */
export default function OverlayHarnessPage() {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [pick, setPick] = useState<string | null>(null);
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-6" data-testid="overlay-harness">
      <h1 className="text-lg font-semibold text-ink">Overlay editor harness</h1>
      <iframe ref={iframeRef} title="overlay mock frame" className="hidden" src="about:blank" />
      <div className="flex gap-2">
        <button type="button" data-testid="pick-email" onClick={() => setPick("email")}>
          Pick email
        </button>
        <button type="button" data-testid="pick-name" onClick={() => setPick("name")}>
          Pick name
        </button>
      </div>
      <OverlayEditor
        key={pick ?? "idle"}
        iframeRef={iframeRef}
        connectionId="e2e-connection"
        model="res.partner"
        viewType="form"
        fields={MOCK_FIELDS}
        selectionOverride={
          pick ? { fieldName: pick, xpath: `//field[@name='${pick}']` } : null
        }
        onSaved={() => undefined}
      />
    </main>
  );
}
