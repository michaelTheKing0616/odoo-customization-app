"use client";

import { FrameMeta } from "@/components/frame/FrameMeta";
import type { ReactNode } from "react";
import { OperateStudioBar, type OperateGuide, type OperateSessionBadge } from "./OperateStudioBar";
import "./operate-studio.css";

type OperateStudioChromeProps = {
  testIdPrefix: string;
  pageTestId: string;
  kicker: string;
  title: string;
  subtitle: string;
  badge: OperateSessionBadge;
  honesty?: OperateGuide | null;
  hint?: string;
  sanitize?: (text: string) => string;
  rail?: ReactNode;
  titleActions?: ReactNode;
  children: ReactNode;
  className?: string;
  shellClassName?: string;
};

/** Basalt studio header + paper desk wrapper for Operate leaps. */
export function OperateStudioChrome({
  testIdPrefix,
  pageTestId,
  kicker,
  title,
  subtitle,
  badge,
  honesty,
  hint,
  sanitize,
  rail,
  titleActions,
  children,
  className,
  shellClassName,
}: OperateStudioChromeProps) {
  return (
    <div
      className={["op-studio-shell", shellClassName, className].filter(Boolean).join(" ")}
      data-testid={pageTestId}
    >
      <header className="op-studio" data-testid={`${testIdPrefix}-studio-chrome`}>
        <div className="op-titlebar">
          <div className="op-title-block">
            <FrameMeta />
            <p className="op-kicker">{kicker}</p>
            <h1 className="op-title">{title}</h1>
            <p className="op-subtitle">{subtitle}</p>
          </div>
          {titleActions ? <div className="op-title-actions">{titleActions}</div> : null}
        </div>
        <OperateStudioBar
          testIdPrefix={testIdPrefix}
          badge={badge}
          honesty={honesty}
          hint={hint}
          sanitize={sanitize}
        />
        {rail}
      </header>
      <div className="op-desk">
        <div className="op-paper">{children}</div>
      </div>
    </div>
  );
}
