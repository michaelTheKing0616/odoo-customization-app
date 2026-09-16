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

  it("enables Open in Odoo after authored Promote when a host href is provided", () => {
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
        goldCanPromote
        goldCanOpenSettings={false}
        goldPromoted
        authoringPassed
        authoringRetryable={false}
        hostInstallOffers={[]}
        leftoverAuthoringFindings={[]}
        isOdooOnline={false}
        busy={null}
        onInstallInvoicing={() => undefined}
        onDownloadZip={() => undefined}
        onProveSandbox={() => undefined}
        onPromote={() => undefined}
        onRetryAuthoring={() => undefined}
        onReverify={() => undefined}
        onInstallHost={() => undefined}
        openInOdooHref="http://127.0.0.1:8069/web#model=sale.order&view_type=list"
        openInOdooLabel="Open Quotation"
      />,
    );
    const link = screen.getByTestId("studio-authored-open-odoo");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute(
      "href",
      "http://127.0.0.1:8069/web#model=sale.order&view_type=list",
    );
    expect(link).toHaveTextContent("Open Quotation");
    expect(screen.getByRole("button", { name: "Promote again" })).toBeTruthy();
  });

  it("shows quota-oriented copy when authoring failed with Gemini quota finding", () => {
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
        authoringPassed={false}
        authoringRetryable
        hostInstallOffers={[]}
        leftoverAuthoringFindings={[
          {
            code: "author_failed",
            message: "Gemini free-tier quota is exhausted",
            file: "",
          },
        ]}
        isOdooOnline={false}
        busy={null}
        onInstallInvoicing={() => undefined}
        onDownloadZip={() => undefined}
        onProveSandbox={() => undefined}
        onPromote={() => undefined}
        onRetryAuthoring={() => undefined}
        onReverify={() => undefined}
        onInstallHost={() => undefined}
      />,
    );
    expect(screen.getByTestId("studio-authored-option-a")).toHaveTextContent(
      /Gemini free-tier quota/i,
    );
    expect(screen.getByTestId("studio-retry-authoring")).toBeTruthy();
  });
});
