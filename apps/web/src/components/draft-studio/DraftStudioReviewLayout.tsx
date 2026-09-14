"use client";

type DraftStudioReviewLayoutProps = {
  header?: React.ReactNode;
  preview: React.ReactNode;
  chrome: React.ReactNode;
  footer?: React.ReactNode;
  mobileTab?: "preview" | "chrome";
};

export function DraftStudioReviewLayout({
  header,
  preview,
  chrome,
  footer,
  mobileTab = "preview",
}: DraftStudioReviewLayoutProps) {
  const tabClass =
    mobileTab === "chrome" ? "review-layout show-chat" : "review-layout show-preview";

  return (
    <div className={tabClass} data-testid="draft-studio-review-layout">
      {header ? <div className="review-layout-header">{header}</div> : null}
      <div className="review-preview-pane">{preview}</div>
      <div className="review-chat-pane">
        <div className="chat-thread">{chrome}</div>
      </div>
      {footer ? <div className="review-footer">{footer}</div> : null}
    </div>
  );
}
