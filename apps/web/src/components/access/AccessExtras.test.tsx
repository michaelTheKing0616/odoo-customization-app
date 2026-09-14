/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccessExtras } from "./AccessExtras";

afterEach(() => cleanup());

describe("AccessExtras", () => {
  it("does not apply the live pack on click — parent must confirm the phrase", () => {
    const onApply = vi.fn();
    render(
      <AccessExtras
        model="x_visitor_log"
        groups={[]}
        mcGuidance={null}
        docsGate={null}
        docsFolders={[]}
        docsFolderId=""
        docsMapping={{}}
        onDocsFolderId={() => undefined}
        onApplyMultiCompany={onApply}
        onLoadFolders={() => undefined}
        onSaveFolder={() => undefined}
      />,
    );
    expect(screen.getByTestId("access-apply-live-pack")).toHaveTextContent(
      "Apply live pack to loaded model",
    );
    expect(screen.getByTestId("access-apply-live-pack").closest("div")?.textContent).toMatch(
      /global ir\.rule/i,
    );
    fireEvent.click(screen.getByTestId("access-apply-live-pack"));
    expect(onApply).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/!/)).toBeNull();
  });

  it("disables apply on stock models so a global ir.rule cannot be created from this control", () => {
    render(
      <AccessExtras
        model="res.partner"
        groups={[]}
        mcGuidance={null}
        docsGate={null}
        docsFolders={[]}
        docsFolderId=""
        docsMapping={{}}
        onDocsFolderId={() => undefined}
        onApplyMultiCompany={() => undefined}
        onLoadFolders={() => undefined}
        onSaveFolder={() => undefined}
      />,
    );
    expect(screen.getByTestId("access-apply-live-pack")).toBeDisabled();
  });
});
