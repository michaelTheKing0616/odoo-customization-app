/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DraftStudioReusePanel } from "./DraftStudioReusePanel";

afterEach(() => cleanup());

const baseProps = {
  reuseModels: [] as string[],
  reuseCatalog: [],
  reuseCatalogByModel: new Map(),
  filteredReuseCatalog: [],
  reuseSearch: "",
  reuseCatalogStatus: "ready" as const,
  reuseCatalogError: null,
  autoWiredReuse: [],
  inferredReuseSuggestions: [],
  installableReuseSuggestions: [],
  aiBusy: false,
  aiBusyLabel: null,
  onToggleReuse: vi.fn(),
  onSearch: vi.fn(),
  onReloadCatalog: vi.fn(),
  onConfirmInferred: vi.fn(),
  onRejectInferred: vi.fn(),
  onConfirmInstallable: vi.fn(),
  onRejectInstallable: vi.fn(),
};

describe("DraftStudioReusePanel", () => {
  it("shows skeleton while catalog loads without Loading... copy", () => {
    render(
      <DraftStudioReusePanel
        {...baseProps}
        reuseCatalogStatus="loading"
      />,
    );
    expect(screen.getByTestId("reuse-catalog-loading")).toBeInTheDocument();
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
  });

  it("shows empty state with retry action when catalog is empty", () => {
    const onReloadCatalog = vi.fn();
    render(
      <DraftStudioReusePanel
        {...baseProps}
        onReloadCatalog={onReloadCatalog}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry catalog" }));
    expect(onReloadCatalog).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
  });
});
