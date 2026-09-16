"use client";

type ChatBubbleProps = {
  role: "user" | "assistant" | "system";
  children: React.ReactNode;
};

export function ChatBubble({ role, children }: ChatBubbleProps) {
  const className =
    role === "user"
      ? "chat-bubble chat-bubble-user chat-bubble-enter"
      : role === "system"
        ? "chat-bubble chat-bubble-system chat-bubble-enter"
        : "chat-bubble chat-bubble-assistant chat-bubble-enter";
  return (
    <div className={className} data-role={role}>
      {children}
    </div>
  );
}
