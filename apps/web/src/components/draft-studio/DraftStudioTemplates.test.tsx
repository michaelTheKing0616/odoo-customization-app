/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AppTemplate, Connection } from "@/lib/api";
import { DraftStudioTemplates } from "./DraftStudioTemplates";

afterEach(() => cleanup());

const templates = [
  { id: "library", name: "Library", description: "Books and loans" },
  { id: "crm_lite", name: "CRM Lite", description: "Leads and stages" },
] as unknown as AppTemplate[];

const unprobed = { id: "c1", name: "Demo", url: "https://demo.odoo.com" } as unknown as Connection;

const base = {
  connectionId: "c1",
  templates,
  result: null,
  onOpenTemplate: vi.fn(),
  templateScaffoldOpts: () => ({}),
};

describe("DraftStudioTemplates", () => {
  it("states the capability lock once instead of on every card", () => {
    render(<DraftStudioTemplates {...base} connection={unprobed} />);
    expect(screen.getAllByTestId("templates-capabilities-unknown")).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Open Connect" }).getAttribute("href")).toBe(
      "/connect",
    );
    const cards = screen.getAllByRole("button");
    expect(cards).toHaveLength(2);
    for (const card of cards) {
      expect(card).toBeDisabled();
      expect(card.querySelector(".draft-studio-template-blocked")).toBeNull();
    }
  });

  it("shows skeleton cards while loading, without the locked note", () => {
    render(<DraftStudioTemplates {...base} connection={unprobed} loading />);
    expect(screen.getByTestId("templates-loading")).toBeTruthy();
    expect(screen.queryByTestId("templates-capabilities-unknown")).toBeNull();
  });

  it("gives an empty state with a next step when no templates load", () => {
    render(<DraftStudioTemplates {...base} connection={unprobed} templates={[]} />);
    expect(screen.getByTestId("templates-empty").textContent).toMatch(/Describe the app above/);
  });
});
