/** @vitest-environment jsdom */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi, beforeEach } from "vitest";
import { ConfigAtlasBrowser } from "@/components/config/ConfigAtlasBrowser";

vi.mock("@/lib/api", () => ({
  api: {
    batchOsAtlas: vi.fn(async () => ({
      classes: [
        { id: "settings", title: "Settings", status: "complete", blurb: "", intents: [
          { id: "settings.board", title: "Settings board", models: ["account.payment.term"], risk: "L2", recipe: "settings.board_apply", status: "complete", blurb: "pack" },
        ]},
        { id: "master_data", title: "Master data", status: "complete", blurb: "", intents: [
          { id: "master.partners", title: "Partners", models: ["res.partner"], risk: "L1", recipe: "master_data.partners_batch", status: "complete", blurb: "csv" },
        ]},
      ],
      honesty: "Preview ≠ written",
    })),
    batchOsRecipes: vi.fn(async () => []),
    batchOsAtlasSearch: vi.fn(async () => ({ hits: [] })),
  },
}));

afterEach(() => cleanup());

describe("ConfigAtlasBrowser", () => {
  beforeEach(() => vi.clearAllMocks());

  it("filters by class and shows complete settings/master_data (no empty stubs)", async () => {
    render(<ConfigAtlasBrowser connectionId="conn-1" />);
    await waitFor(() => {
      expect(screen.getByTestId("config-atlas-browser")).toBeInTheDocument();
    });
    expect(screen.getByTestId("atlas-class-filter")).toBeInTheDocument();
    expect(screen.getByText(/All eight atlas classes are complete/i)).toBeInTheDocument();
    expect(screen.getByText(/zero stub intents/i)).toBeInTheDocument();
  });

  it("shows empty recipes without Loading... copy after hydrate", async () => {
    render(<ConfigAtlasBrowser connectionId="conn-1" />);
    await waitFor(() => {
      expect(screen.getByTestId("config-atlas-recipes-empty")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /reload recipes/i })).toBeInTheDocument();
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
  });
});
