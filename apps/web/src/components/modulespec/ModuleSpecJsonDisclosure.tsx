"use client";

import { useEffect, useRef, useState } from "react";
import type { ModuleSpecDoc } from "@/lib/modulespec-types";

type ModuleSpecJsonDisclosureProps = {
  value: ModuleSpecDoc;
  readOnly?: boolean;
  onChange: (next: ModuleSpecDoc) => void;
};

export function ModuleSpecJsonDisclosure({
  value,
  readOnly,
  onChange,
}: ModuleSpecJsonDisclosureProps) {
  const serialized = JSON.stringify(value, null, 2);
  const [draft, setDraft] = useState(serialized);
  const [parseError, setParseError] = useState<string | null>(null);
  const focusedRef = useRef(false);

  useEffect(() => {
    if (!focusedRef.current) {
      setDraft(serialized);
      setParseError(null);
    }
  }, [serialized]);

  function onEdit(next: string) {
    setDraft(next);
    try {
      const parsed = JSON.parse(next) as ModuleSpecDoc;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        setParseError("JSON must be an object.");
        return;
      }
      setParseError(null);
      onChange(parsed);
    } catch (error) {
      setParseError(error instanceof Error ? error.message : "Invalid JSON");
    }
  }

  return (
    <details className="ms-json-disclosure" data-testid="modulespec-json-disclosure">
      <summary>Raw JSON escape hatch</summary>
      <p className="mt-2 text-sm text-muted">
        Prefer the structured sections. Paste only when importing a draft the workbench cannot show.
      </p>
      <textarea
        disabled={readOnly}
        value={draft}
        rows={18}
        className="textarea mt-3 font-mono text-xs"
        data-testid="modulespec-json"
        onFocus={() => {
          focusedRef.current = true;
        }}
        onBlur={() => {
          focusedRef.current = false;
        }}
        onChange={(event) => onEdit(event.target.value)}
      />
      {parseError ? (
        <p className="mt-2 text-xs text-danger" data-testid="modulespec-json-error">
          {parseError}
        </p>
      ) : (
        <p className="mt-2 text-xs text-muted">Valid object. Structured sections stay in sync.</p>
      )}
    </details>
  );
}
