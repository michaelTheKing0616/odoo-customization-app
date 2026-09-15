/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StudioOptionAPanel } from "./StudioOptionAPanel";

afterEach(() => cleanup());

describe("StudioOptionAPanel", () => {
  it("shows Repair with AI when authored Option A authoring passed", () => {
    const onRepairWithAi = vi.fn();
    render(
      <StudioOptionAPanel
        goldOptionA={false}
        authoredOptionA
        goldId=""
        goldHonesty=""
        goldSettings={null}
        goldHost={null}
        goldInspect={null}
        goldNeedsInvoicing={false}
        goldCanPromote={false}
        goldCanOpenSettings={false}
        goldPromoted={false}
        authoringPassed
        authoringRetryable={false}
        hostInstallOffers={[]}
        leftoverAuthoringFindings={[]}
        isOdooOnline={false}
        busy={null}
        onInstallInvoicing={() => undefined}
        onDownloadZip={() => undefined}
        onProveSandbox={() => undefined}
        onRepairWithAi={onRepairWithAi}
        onPromote={() => undefined}
        onRetryAuthoring={() => undefined}
        onReverify={() => undefined}
        onInstallHost={() => undefined}
      />,
    );
    expect(screen.getByTestId("studio-repair-with-ai")).toHaveTextContent("Repair with AI");
  });
});
