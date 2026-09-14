/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { ExpertAnswerCard } from "./ExpertAnswerCard";
import type { ExpertAskResponse } from "@/lib/api";

afterEach(() => cleanup());

const GROUNDED: ExpertAskResponse = {
  answer_markdown: "XPath inherit extends a form without replacing the primary arch [1].",
  citations: [
    {
      source: "odoo_docs",
      version: "19.0",
      breadcrumb: "Views",
      chunk_id: "c1",
      source_index: 1,
    },
  ],
  grounded: true,
  declined: false,
  suggested_tools: [{ id: "designer", label: "View Designer", deep_link: "/connections/c1/designer" }],
  caution_flags: ["low_retrieval"],
  reasoning: false,
  uncited_warning: false,
};

describe("ExpertAnswerCard", () => {
  it("shows grounded badge, caution, sources, and inbound tools — not promote", () => {
    render(
      <TooltipProvider>
        <ExpertAnswerCard response={GROUNDED} connectionId="c1" />
      </TooltipProvider>,
    );
    expect(screen.getByText("Grounded")).toBeTruthy();
    expect(screen.getByTestId("expert-answer").textContent).toMatch(/XPath inherit/);
    expect(screen.getByTestId("expert-caution-flags").textContent).toMatch(/Limited source matches/);
    expect(screen.getByTestId("expert-sources").textContent).toMatch(/odoo_docs/);
    expect(screen.getByTestId("expert-suggested-tools").textContent).toMatch(/View Designer/);
    expect(screen.getByTestId("expert-copy-answer")).toBeTruthy();
    expect(screen.queryByText(/auto-promote/i)).toBeNull();
  });
});
