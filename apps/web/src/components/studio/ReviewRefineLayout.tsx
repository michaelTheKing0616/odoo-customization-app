"use client";

type ReviewRefineLayoutProps = {
  header?: React.ReactNode;
  preview: React.ReactNode;
  chat: React.ReactNode;
  chatInput: React.ReactNode;
  footer?: React.ReactNode;
  mobileTab?: "preview" | "chat";
};

export function ReviewRefineLayout({
  header,
  preview,
  chat,
  chatInput,
  footer,
  mobileTab = "preview",
}: ReviewRefineLayoutProps) {
  const tabClass =
    mobileTab === "chat" ? "review-layout show-chat" : "review-layout show-preview";

  return (
    <div className={tabClass} data-testid="studio-review-layout">
      {header ? <div className="review-layout-header">{header}</div> : null}
      <div className="review-preview-pane">{preview}</div>
      <div className="review-chat-pane">
        <div className="chat-thread">{chat}</div>
        {chatInput}
      </div>
      {footer ? <div className="review-footer">{footer}</div> : null}
    </div>
  );
}
