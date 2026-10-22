import { Term } from "@/components/ui/Term";
/** UI-S-18: the two limits, stated plainly. The Option A warning must never be removed. */
export function CodeStudioHonesty() {
  return (
    <section aria-label="Limits" data-testid="code-studio-limits" className="cs-honesty">
      <div className="cs-limit">
        <h2 className="cs-limit-title">Live <Term tech="ir.actions.server">server action</Term></h2>
        <p className="cs-limit-body" data-testid="code-studio-limit-live">
          A live bind writes <code className="cs-code">state=code</code> only after Validate passes,
          the instance probe clears, you type the confirm phrase, and a snapshot is saved. Import,
          sudo, and unlink are refused. This app does not run that action in its own process.
        </p>
      </div>
      <div className="cs-limit cs-limit-option-a" data-testid="code-studio-option-a-warning">
        <div className="cs-limit-band">
          <h2 className="cs-limit-title">Custom-code module</h2>
          <span className="cs-band-tag">Never installs from here</span>
        </div>
        <div className="cs-limit-inner">
          <p className="cs-limit-body" data-testid="code-studio-limit-option-a">
            Custom code downloads a module zip. This screen does not install it and does not publish
            it. Sandbox the module, then a person publishes it.
          </p>
          <ol className="cs-steps" aria-label="Custom code path">
            <li>
              <span className="cs-step-no" aria-hidden="true">1</span>
              <span>
                <strong>Download the zip.</strong> The Python ships inside the module.
              </span>
            </li>
            <li>
              <span className="cs-step-no" aria-hidden="true">2</span>
              <span>
                <strong>Prove it on a sandbox</strong> of the same Odoo major.
              </span>
            </li>
            <li>
              <span className="cs-step-no" aria-hidden="true">3</span>
              <span>
                <strong>A person promotes it.</strong> Nothing here does that for you.
              </span>
            </li>
          </ol>
        </div>
      </div>
    </section>
  );
}
