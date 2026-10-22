"use client";

import { CONNECT_STEPS, type ConnectStepId } from "@/lib/connectScreen";

const STEP_IDS: ConnectStepId[] = ["credentials", "probe", "summary"];

type ConnectStepRailProps = {
  current: ConnectStepId;
};

export function ConnectStepRail({ current }: ConnectStepRailProps) {
  const currentIndex = STEP_IDS.indexOf(current);
  return (
    <ol
      className="cn-stages"
      data-testid="connect-step-rail"
      aria-label="Connect stages"
    >
      {CONNECT_STEPS.map((label, i) => {
        const id = STEP_IDS[i];
        const state = i < currentIndex ? "done" : i === currentIndex ? "current" : "todo";
        return (
          <li key={id} className="cn-stage" style={{ display: "contents" }}>
            {i > 0 ? <span className="cn-stage-sep" aria-hidden /> : null}
            <span
              className="cn-stage"
              data-state={state}
              data-testid={`connect-step-${id}`}
              aria-current={state === "current" ? "step" : undefined}
            >
              <span className="cn-stage-dot" aria-hidden />
              <span>{label}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
