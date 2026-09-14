"use client";

type OdooChatterStubProps = {
  /** Compact = single message row; full = composer + sample thread. */
  density?: "compact" | "full";
};

export function OdooChatterStub({ density = "full" }: OdooChatterStubProps) {
  return (
    <div className="odoo-chatter-stub" data-testid="odoo-chatter-stub">
      <div className="odoo-chatter-tabs" role="tablist" aria-label="Chatter">
        <button type="button" className="odoo-chatter-tab is-active" role="tab" aria-selected>
          Send message
        </button>
        <button type="button" className="odoo-chatter-tab" role="tab" aria-selected={false}>
          Log note
        </button>
        <button type="button" className="odoo-chatter-tab" role="tab" aria-selected={false}>
          Activities
        </button>
      </div>
      <div className="odoo-chatter-composer">
        <div className="odoo-chatter-avatar" aria-hidden>
          A
        </div>
        <div className="odoo-chatter-composer-input">
          Write a message… (preview only — live chatter needs mail.thread)
        </div>
      </div>
      {density === "full" ? (
        <ul className="odoo-chatter-thread">
          <li className="odoo-chatter-message">
            <div className="odoo-chatter-avatar" aria-hidden>
              S
            </div>
            <div>
              <div className="odoo-chatter-meta">
                <strong>System</strong>
                <span>just now</span>
              </div>
              <p>Record created. Messages and activities appear here after mail mixin.</p>
            </div>
          </li>
        </ul>
      ) : null}
    </div>
  );
}
