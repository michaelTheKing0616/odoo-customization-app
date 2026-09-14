/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { XPathInheritPanel } from "./XPathInheritPanel";

afterEach(() => cleanup());

function renderPanel(
  overrides: Partial<React.ComponentProps<typeof XPathInheritPanel>> = {},
) {
  const onSave = vi.fn();
  const onUseNamedLocator = vi.fn();
  render(
    <XPathInheritPanel
      expr="//group[2]"
      position="inside"
      bodyXml={'<field name="x_extra"/>'}
      previewArch={'<data><xpath expr="//group[2]" position="inside"/></data>'}
      issues={[
        {
          severity: "warning",
          code: "positional_fragility",
          message: "Positional predicate ([n] / last()) breaks when the parent view is upgraded.",
          suggestion: "//group[@string='Other']",
        },
      ]}
      suggestedExpr="//group[@string='Other']"
      defaultInjectExpr="//group[@id='header_left_group']"
      matchCount={1}
      blocking={false}
      busy={false}
      model="res.partner"
      hasOverride={false}
      onExprChange={vi.fn()}
      onPositionChange={vi.fn()}
      onBodyChange={vi.fn()}
      onPreview={vi.fn()}
      onUseNamedLocator={onUseNamedLocator}
      onUseAsOverride={vi.fn()}
      onSave={onSave}
      onClearOverride={vi.fn()}
      {...overrides}
    />,
  );
  return { onSave, onUseNamedLocator };
}

describe("XPathInheritPanel", () => {
  it("surfaces upgrade warnings and a named alternative", () => {
    const { onUseNamedLocator } = renderPanel();
    expect(screen.getByTestId("xpath-warning-callout")).toHaveTextContent("break on upgrade");
    expect(screen.getByTestId("xpath-named-suggestion")).toHaveTextContent(
      "//group[@string='Other']",
    );
    fireEvent.click(screen.getByRole("button", { name: "Use named locator" }));
    expect(onUseNamedLocator).toHaveBeenCalledWith("//group[@string='Other']");
  });

  it("blocks save when the locator is an error", () => {
    const { onSave } = renderPanel({
      blocking: true,
      issues: [
        {
          severity: "error",
          code: "missing_node",
          message: "Locator matches no node in the parent view (//field[@name='nope']).",
        },
      ],
      suggestedExpr: null,
    });
    expect(screen.getByTestId("xpath-error-callout")).toBeInTheDocument();
    expect(screen.getByTestId("xpath-save-blocked")).toBeInTheDocument();
    expect(screen.getByTestId("xpath-save")).toBeDisabled();
    expect(onSave).not.toHaveBeenCalled();
  });
});
