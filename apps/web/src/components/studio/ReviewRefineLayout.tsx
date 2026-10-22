"use client";

import { useState } from "react";

type ReviewRefineLayoutProps = {
  header?: React.ReactNode;
  preview: React.ReactNode;
  chat: React.ReactNode;
  chatInput: React.ReactNode;
  footer?: React.ReactNode;
  mobileTab?: "preview" | "chat";
};

function RailIcon({ collapsed }: { collapsed: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden focusable="false">
      <rect x="1.75" y="2.75" width="12.5" height="10.5" rx="2" stroke="currentColor" strokeWidth="1.3" />
      <path d="M5.75 3v10" stroke="currentColor" strokeWidth="1.3" />
      <path
        d={collapsed ? "M8.75 6.5 10.25 8l-1.5 1.5" : "M10.25 6.5 8.75 8l1.5 1.5"}
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/**
 * Review workspace: the form preview gets most of the width; Refine is a narrow
 * side panel that folds to an icon rail on desktop. Collapsed state lives in
 * component state only (starts open on server and client, so no hydration
 * mismatch). Below 1024px the layout stacks and mobile tabs pick the pane.
 */
export function ReviewRefineLayout({
  header,
  preview,
  chat,
  chatInput,
  footer,
  mobileTab = "preview",
}: ReviewRefineLayoutProps) {
  const [collapsed, setCollapsed] = useState(false);
  const tabClass = [
    "review-layout",
    mobileTab === "chat" ? "show-chat" : "show-preview",
    collapsed ? "is-chat-collapsed" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={tabClass} data-testid="studio-review-layout" data-chat={collapsed ? "collapsed" : "open"}>
      {header ? <div className="review-layout-header">{header}</div> : null}
      <div className="review-chat-pane" data-testid="studio-refine-pane">
        <div className="review-rail-bar">
          <span className="review-rail-title">Refine</span>
          <button
            type="button"
            className="review-rail-toggle"
            data-testid="studio-refine-toggle"
            aria-expanded={!collapsed}
            aria-controls="studio-refine-body"
            aria-label={collapsed ? "Show refine panel" : "Hide refine panel"}
            title={collapsed ? "Show refine panel" : "Hide refine panel"}
            onClick={() => setCollapsed((c) => !c)}
          >
            <RailIcon collapsed={collapsed} />
          </button>
        </div>
        <div className="review-chat-body" id="studio-refine-body">
          <div className="chat-thread">{chat}</div>
          {chatInput}
        </div>
      </div>
      <aside className="review-preview-pane" data-testid="studio-artifact-pane" aria-label="Form preview">
        {preview}
      </aside>
      {footer ? <div className="review-footer">{footer}</div> : null}
    </div>
  );
}
