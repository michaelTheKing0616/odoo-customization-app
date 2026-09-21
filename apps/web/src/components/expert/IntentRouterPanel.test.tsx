import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IntentRouterPanel } from "./IntentRouterPanel";

vi.mock("@/lib/api", () => ({
  api: {
    expertIntentRoute: vi.fn(),
  },
}));

import { api } from "@/lib/api";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("IntentRouterPanel", () => {
  it("renders input + routes to a feature with Go link", async () => {
    vi.mocked(api.expertIntentRoute).mockResolvedValue({
      prompt: "upload 200 journal entries",
      can_handle: "true",
      message: "Best fit: Journal batch.",
      matches: [
        {
          feature_id: "journal.batch",
          title: "Journal batch",
          confidence: 0.9,
          why: "Matched journal entries.",
          route: "journal?tab=batch",
          deep_link: "/connections/c1/journal?tab=batch",
          can_handle: "true",
          recipe: "accounting.journal_batch",
        },
      ],
      alternatives: [],
      ambiguous: false,
      honesty: "Preview ≠ posted.",
      source: "deterministic",
      llm_used: false,
    });

    render(<IntentRouterPanel connectionId="c1" />);
    expect(screen.getByTestId("intent-router-panel")).toBeTruthy();
    expect(screen.getByTestId("intent-router-input")).toBeTruthy();
    expect(screen.getByText(/What do you want to do/i)).toBeTruthy();

    fireEvent.change(screen.getByTestId("intent-router-input"), {
      target: { value: "upload 200 journal entries" },
    });
    fireEvent.click(screen.getByTestId("intent-router-submit"));

    await waitFor(() => {
      expect(screen.getByTestId("intent-router-results")).toBeTruthy();
    });
    expect(api.expertIntentRoute).toHaveBeenCalledWith("c1", {
      prompt: "upload 200 journal entries",
      limit: 5,
    });
    const go = screen.getByTestId("intent-route-go");
    expect(go).toHaveAttribute("href", "/connections/c1/journal?tab=batch");
    expect(screen.getByText("Journal batch")).toBeTruthy();
  });

  it("shows honesty for unsupported goals", async () => {
    vi.mocked(api.expertIntentRoute).mockResolvedValue({
      prompt: "send SMS blast",
      can_handle: "false",
      message: "ingenium does not send SMS/WhatsApp blasts.",
      matches: [],
      alternatives: [],
      ambiguous: false,
      honesty: "Preview ≠ posted.",
      source: "unsupported_catalog",
      llm_used: false,
    });

    render(<IntentRouterPanel connectionId="c1" />);
    fireEvent.change(screen.getByTestId("intent-router-input"), {
      target: { value: "send SMS blast" },
    });
    fireEvent.click(screen.getByTestId("intent-router-submit"));

    await waitFor(() => {
      expect(screen.getByTestId("intent-router-unsupported")).toBeTruthy();
    });
    expect(screen.getByText(/does not send SMS/i)).toBeTruthy();
    expect(screen.queryByTestId("intent-route-go")).toBeNull();
  });
});
