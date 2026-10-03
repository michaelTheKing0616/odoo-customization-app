/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CronJobsList } from "./CronJobsList";
import type { CronRowOut } from "@/lib/api";

afterEach(() => cleanup());

const row: CronRowOut = {
  id: 1,
  name: "Nightly",
  description: "Cleanup",
  model_name: "res.partner",
  active: true,
  nextcall: "2026-10-04 00:00:00",
};

describe("CronJobsList", () => {
  it("shows skeleton while loading without Loading... copy", () => {
    render(
      <CronJobsList
        rows={[]}
        loading
        selected={new Set()}
        busy={false}
        onToggleSelected={vi.fn()}
        onToggleActive={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    expect(screen.getByTestId("cron-jobs-list-loading")).toBeInTheDocument();
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
  });

  it("shows empty state with refresh action", () => {
    const onRefresh = vi.fn();
    render(
      <CronJobsList
        rows={[]}
        selected={new Set()}
        busy={false}
        onToggleSelected={vi.fn()}
        onToggleActive={vi.fn()}
        onRefresh={onRefresh}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Refresh list" }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
  });

  it("renders cron rows when populated", () => {
    render(
      <CronJobsList
        rows={[row]}
        selected={new Set()}
        busy={false}
        onToggleSelected={vi.fn()}
        onToggleActive={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    expect(screen.getByTestId("cron-jobs-list")).toBeInTheDocument();
    expect(screen.getByText("Nightly")).toBeInTheDocument();
  });
});
