/** @vitest-environment happy-dom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  listConnections: vi.fn(),
  listPipelines: vi.fn(),
  listPipelineHops: vi.fn(),
  createPipeline: vi.fn(),
  pipelinePromote: vi.fn(),
}));

vi.mock("@/lib/api", () => {
  class ConfirmationRequiredError extends Error {
    warning = "";
  }
  return { api: mocks, ConfirmationRequiredError };
});

import PipelinesPage from "./page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("pipelines page states", () => {
  it("shows a list skeleton while pipelines load", () => {
    mocks.listConnections.mockReturnValue(new Promise(() => undefined));
    mocks.listPipelines.mockReturnValue(new Promise(() => undefined));
    render(<PipelinesPage />);

    const loading = screen.getByTestId("pipelines-list-loading");
    expect(loading).toHaveAttribute("role", "status");
    expect(screen.getByText("Loading pipelines.")).toBeInTheDocument();
    expect(loading.querySelectorAll(".shimmer-15")).toHaveLength(2);
    expect(screen.queryByText("No pipelines yet")).toBeNull();
    expect(screen.queryByText(/Loading…|Loading\.\.\./)).toBeNull();
  });

  it("shows the empty state and focuses the name field from its action", async () => {
    mocks.listConnections.mockResolvedValue([]);
    mocks.listPipelines.mockResolvedValue([]);
    render(<PipelinesPage />);

    expect(await screen.findByRole("heading", { name: "No pipelines yet" })).toBeInTheDocument();
    expect(
      screen.getByText("Pipelines you create appear here with their staging and prod connections."),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("pipelines-list-loading")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Name a pipeline" }));
    expect(document.activeElement).toBe(screen.getByLabelText("Name"));
  });
});
