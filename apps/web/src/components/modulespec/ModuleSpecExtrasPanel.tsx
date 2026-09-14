"use client";

type RecordRow = Record<string, unknown>;

type ModuleSpecExtrasPanelProps = {
  smartButtons: RecordRow[];
  automations: RecordRow[];
};

function fact(row: RecordRow, keys: string[]): string {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return "";
}

export function ModuleSpecExtrasPanel({ smartButtons, automations }: ModuleSpecExtrasPanelProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2" data-testid="modulespec-extras">
      <section>
        <h3 className="text-sm font-semibold text-ink">Smart buttons</h3>
        <p className="mt-1 text-xs text-muted">
          Metadata only. Generate UI writes inherit button boxes. Live forms stay on View Designer.
        </p>
        {smartButtons.length === 0 ? (
          <p className="mt-3 text-sm text-muted">None in this spec.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {smartButtons.map((row, index) => (
              <li
                key={`${fact(row, ["string", "name", "on_model"])}-${index}`}
                className="rounded-md border border-border-subtle bg-surface-raised px-3 py-2"
              >
                <p className="text-sm text-ink">
                  {fact(row, ["string", "name", "button_label"]) || "Smart button"}
                </p>
                <p className="mt-0.5 font-mono text-xs text-muted">
                  {fact(row, ["on_model"]) || "?"} → {fact(row, ["related_model", "comodel"]) || "?"}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h3 className="text-sm font-semibold text-ink">Automations</h3>
        <p className="mt-1 text-xs text-muted">
          Review-only on Generate UI. Open Automations to create live rules. Python stays Option A.
        </p>
        {automations.length === 0 ? (
          <p className="mt-3 text-sm text-muted">None in this spec.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {automations.map((row, index) => (
              <li
                key={`${fact(row, ["name", "trigger"])}-${index}`}
                className="rounded-md border border-border-subtle bg-surface-raised px-3 py-2"
              >
                <p className="text-sm text-ink">{fact(row, ["name"]) || "Automation"}</p>
                <p className="mt-0.5 font-mono text-xs text-muted">
                  {fact(row, ["model", "on_model"]) || "?"} · {fact(row, ["trigger"]) || "trigger"}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
