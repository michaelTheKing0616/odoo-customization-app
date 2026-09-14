/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ExpertOverviewCard } from "./ExpertOverviewCard";

afterEach(() => cleanup());

describe("ExpertOverviewCard", () => {
  it("is an Expert destination with inbound studio links, never auto-promote", () => {
    const onAsk = vi.fn();
    render(
      <ExpertOverviewCard connectionId="c1" connectionName="Lab 19" onAsk={onAsk} />,
    );
    expect(screen.getByTestId("expert-overview-card")).toBeTruthy();
    expect(screen.getByTestId("expert-overview-honesty").textContent).toMatch(
      /Completeness ≠ Cert ≠ Autopilot/,
    );
    expect(screen.getByRole("link", { name: "Draft Studio" })).toHaveAttribute(
      "href",
      "/connections/c1/wizard",
    );
    expect(screen.getByRole("link", { name: "View Designer" })).toHaveAttribute(
      "href",
      "/connections/c1/designer",
    );
    expect(screen.getByRole("link", { name: "Projects" })).toHaveAttribute(
      "href",
      "/connections/c1/projects",
    );
    expect(screen.getByRole("link", { name: "Job Autopilot" })).toHaveAttribute(
      "href",
      "/connections/c1/job",
    );
    fireEvent.click(screen.getByRole("button", { name: "XPath inherit" }));
    expect(onAsk).toHaveBeenCalledOnce();
    expect(screen.getByTestId("expert-overview-card").textContent).toMatch(/never applies ModuleSpec/);
  });
});
