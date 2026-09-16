"use client";

import { useEffect, useRef } from "react";
import type { StudioTurn } from "@/lib/studio-session";
import { undoInstructionForRefine } from "@/lib/studio-session";
import { ChatBubble } from "./ChatBubble";
import { RefineHistoryPopover } from "./RefineHistoryPopover";

type StudioChatThreadProps = {
  conversation: StudioTurn[] | undefined;
  localRefineError: string | null;
  refineBusy: boolean;
  onReuse: (content: string) => void;
  onUndo: (instruction: string) => void;
};

export function StudioChatThread({
  conversation,
  localRefineError,
  refineBusy,
  onReuse,
  onUndo,
}: StudioChatThreadProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const reviewTurns = (conversation || []).filter(
    (t) => t.kind === "refine" || t.kind === "refine_result",
  );
  let latestUserRefineIdx = -1;
  reviewTurns.forEach((turn, idx) => {
    if (turn.kind === "refine" && turn.role === "user") latestUserRefineIdx = idx;
  });

  useEffect(() => {
    const el = endRef.current;
    if (!el) return;
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "end" });
  }, [reviewTurns.length, localRefineError, refineBusy]);

  return (
    <>
      <div className="studio-chat-toolbar">
        <span className="studio-chat-toolbar-label">Refine</span>
        <RefineHistoryPopover
          conversation={conversation}
          onReuse={onReuse}
          onUndo={onUndo}
          undoBusy={refineBusy}
        />
      </div>
      {reviewTurns.length === 0 ? (
        <ChatBubble role="assistant">
          Preview is on the left. Ask for a change and the form updates — remove a field,
          make one required, or add one.
        </ChatBubble>
      ) : null}
      {reviewTurns.map((turn, idx) => {
        const isUserRefine = turn.kind === "refine" && turn.role === "user";
        const undoInstruction =
          isUserRefine && idx === latestUserRefineIdx
            ? undoInstructionForRefine(turn.content, true)
            : null;
        return (
          <div
            key={`${turn.at || idx}-${turn.kind}`}
            className={isUserRefine ? "studio-user-turn" : undefined}
          >
            <ChatBubble
              role={
                turn.role === "user"
                  ? "user"
                  : turn.role === "system"
                    ? "system"
                    : "assistant"
              }
            >
              {turn.content}
            </ChatBubble>
            {undoInstruction ? (
              <button
                type="button"
                className="studio-bubble-undo"
                disabled={refineBusy}
                data-testid="refine-chat-undo"
                title="Undo this change (sends “oops”)"
                onClick={() => onUndo(undoInstruction)}
              >
                Undo
              </button>
            ) : null}
          </div>
        );
      })}
      {localRefineError ? <ChatBubble role="assistant">{localRefineError}</ChatBubble> : null}
      <div ref={endRef} aria-hidden className="studio-chat-scroll-anchor" />
    </>
  );
}
