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
  interval_number: 1,
  interval_type: "days",
  active: true,
  nextcall: "2026-10-04 00:00:00",
  lastcall: null,
};

describe("CronJobsList", () => {
  it("shows skeleton while loading without Loading... copy", () => {
    render(
      <div className="cron-operate">
        <CronJobsList
          rows={[]}
          loading
          selected={new Set()}
          busy={false}
          timeZone="UTC"
          zoneLabel="UTC"
          onToggleSelected={vi.fn()}
          onToggleActive={vi.fn()}
          onRefresh={vi.fn()}
        />
      </div>,
    );
    expect(screen.getByTestId("cron-jobs-list-loading")).toBeInTheDocument();
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
  });

  it("shows empty what/why/next with refresh action", () => {
    const onRefresh = vi.fn();
    render(
      <div className="cron-operate">
        <CronJobsList
          rows={[]}
          selected={new Set()}
          busy={false}
          timeZone="UTC"
          zoneLabel="UTC"
          onToggleSelected={vi.fn()}
          onToggleActive={vi.fn()}
          onRefresh={onRefresh}
        />
      </div>,
    );
    expect(screen.getByTestId("cron-empty-guide")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh list" }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it("renders cron rows with Enable/Disable honesty and next run", () => {
    const onToggle = vi.fn();
    render(
      <div className="cron-operate">
        <CronJobsList
          rows={[row]}
          selected={new Set()}
          busy={false}
          timeZone="UTC"
          zoneLabel="UTC (connection tz not reported)"
          onToggleSelected={vi.fn()}
          onToggleActive={onToggle}
          onRefresh={vi.fn()}
        />
      </div>,
    );
    expect(screen.getByTestId("cron-jobs-list")).toBeInTheDocument();
    expect(screen.getByText("Nightly")).toBeInTheDocument();
    expect(screen.getByTestId("cron-toggle-1")).toHaveTextContent("Disable");
    fireEvent.click(screen.getByTestId("cron-toggle-1"));
    expect(onToggle).toHaveBeenCalledWith(row);
  });
});
