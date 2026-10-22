import type { AccessVersionFrame, AccessWriteGate } from "@/lib/accessScreen";
import { Odoo20AccessNote } from "@/components/access/Odoo20AccessNote";

type AccessVersionStripProps = {
  frame: AccessVersionFrame;
  gate: AccessWriteGate;
};

/**
 * Version-honest band: which Odoo major, which technical models this screen
 * writes, and whether a save goes straight to Odoo or through a plan card.
 */
export function AccessVersionStrip({ frame, gate }: AccessVersionStripProps) {
  return (
    <section
      className="ax-strip"
      aria-label="Odoo access model"
      data-testid="access-version-strip"
      data-major={frame.major ?? "unknown"}
      data-combined={frame.combined ? "true" : "false"}
    >
      <div className="ax-strip-lead">
        <span
          className="ax-version-chip"
          data-known={frame.major == null ? "false" : "true"}
          data-testid="access-version-label"
        >
          {frame.label}
        </span>
        {frame.models.map((m, i) => (
          <span key={m} className="contents">
            {i > 0 ? (
              <span className="ax-model-plus" aria-hidden>
                +
              </span>
            ) : null}
            <span className="ax-model-chip" data-testid="access-version-model">
              {m}
            </span>
          </span>
        ))}
        {frame.combined ? (
          <Odoo20AccessNote major={frame.major} className="ax-strip-summary" />
        ) : null}
        <p className="ax-strip-summary" data-testid="access-version-summary">
          {frame.summary}
        </p>
      </div>
      <span
        className="ax-gate-chip"
        data-mode={gate.mode}
        data-testid="access-gate-chip"
        title={gate.why}
      >
        <span className="ax-gate-dot" aria-hidden />
        {gate.label}
      </span>
    </section>
  );
}
