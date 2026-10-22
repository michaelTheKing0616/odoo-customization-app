"use client";

import { PaperclipIcon, UserIcon } from "./OdooIcons";

type OdooChatterStubProps = {
  /** Compact = top bar only; full = top bar, composer and a Today log line. */
  density?: "compact" | "full";
};

/** Odoo chatter: Send message / Log note / Activities, followers, Today log. Preview only. */
export function OdooChatterStub({ density = "full" }: OdooChatterStubProps) {
  return (
    <aside className="ofp-chatter" data-testid="odoo-chatter-stub" aria-label="Chatter preview">
      <div className="ofp-chatter-top">
        <div className="ofp-chatter-actions">
          <span className="ofp-btn ofp-btn-primary ofp-btn-sm">Send message</span>
          <span className="ofp-btn ofp-btn-secondary ofp-btn-sm">Log note</span>
          <span className="ofp-btn ofp-btn-secondary ofp-btn-sm">Activities</span>
        </div>
        <div className="ofp-chatter-meta">
          <PaperclipIcon />
          <span className="ofp-chatter-followers">
            <UserIcon />1
          </span>
          <span className="ofp-chatter-follow">Following</span>
        </div>
      </div>
      {density === "full" ? (
        <>
          <div className="ofp-chatter-composer">
            <span className="ofp-avatar" aria-hidden>
              A
            </span>
            <span className="ofp-chatter-input">Write a message...</span>
          </div>
          <div className="ofp-chatter-day">
            <span>Today</span>
          </div>
          <div className="ofp-chatter-msg">
            <span className="ofp-avatar ofp-avatar--muted" aria-hidden>
              M
            </span>
            <div className="ofp-chatter-msg-body">
              <div className="ofp-chatter-msg-head">
                <strong>Mitchell Admin</strong>
                <span>now</span>
              </div>
              <p>Record created</p>
            </div>
          </div>
          <p className="ofp-chatter-note">Preview only. Live messages need the mail mixin on the model.</p>
        </>
      ) : null}
    </aside>
  );
}
