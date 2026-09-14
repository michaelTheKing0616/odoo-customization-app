"use client";

type ChatBubbleProps = {
  role: "user" | "assistant" | "system";
  children: React.ReactNode;
};

export function ChatBubble({ role, children }: ChatBubbleProps) {
  const className =
    role === "user"
      ? "chat-bubble chat-bubble-user"
      : role === "system"
        ? "chat-bubble chat-bubble-system"
        : "chat-bubble chat-bubble-assistant";
  return <div className={className}>{children}</div>;
}
