import type { ReactNode } from "react";
import type { StateGuide } from "@/lib/accessScreen";

type AccessStateGuideProps = {
  guide: StateGuide;
  tone?: "neutral" | "warning" | "danger" | "accent";
  actions?: ReactNode;
  testId?: string;
  /** Errors announce; empty and gate states do not. */
  live?: boolean;
  className?: string;
};

/** What happened, why, and what to do next. One quiet block, no nested boxes. */
export function AccessStateGuide({
  guide,
  tone = "neutral",
  actions,
  testId,
  live = false,
  className,
}: AccessStateGuideProps) {
  return (
    <div
      className={["ax-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p className="ax-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
        {guide.title}
      </p>
      <dl className="ax-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>{guide.why}</dd>
        <dt>Next</dt>
        <dd data-testid={testId ? `${testId}-next` : undefined}>{guide.next}</dd>
      </dl>
      {actions ? <div className="ax-guide-actions">{actions}</div> : null}
    </div>
  );
}
