import type { ReactNode } from "react";
import { CircleAlert, Info } from "@/components/ui/icons";

export type MenusGuide = { title: string; why: string; next: string };

type MenusStateGuideProps = {
  guide: MenusGuide;
  tone?: "neutral" | "warning" | "danger";
  actions?: ReactNode;
  testId?: string;
  /** Blocking errors announce assertively; everything else stays quiet. */
  live?: boolean;
  className?: string;
};

/** What happened, why, and what to do next. One quiet block, no nested boxes. */
export function MenusStateGuide({
  guide,
  tone = "neutral",
  actions,
  testId,
  live = false,
  className,
}: MenusStateGuideProps) {
  return (
    <div
      className={["mn-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <div className="mn-guide-head">
        {tone === "neutral" ? (
          <Info className="mn-guide-icon" aria-hidden />
        ) : (
          <CircleAlert className="mn-guide-icon" aria-hidden />
        )}
        <p className="mn-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
          {guide.title}
        </p>
      </div>
      <dl className="mn-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>{guide.why}</dd>
        <dt>Next</dt>
        <dd>{guide.next}</dd>
      </dl>
      {actions ? <div className="mn-guide-actions">{actions}</div> : null}
    </div>
  );
}
