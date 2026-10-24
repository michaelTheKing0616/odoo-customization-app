/** @vitest-environment jsdom */
/** BV-UI oracle: evidence viewer for one verify run (botVerify.ts types only). */
import React from "react";
import { readFileSync } from "node:fs";
import path from "node:path";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { LayerResult, RunStatus, VerifyRun } from "@/lib/api/botVerify";
import { EvidenceViewer } from "./EvidenceViewer";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function stubMotion(reduce: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((q: string) => ({
      matches: reduce && q.includes("reduce"),
      media: q,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
}

const live: LayerResult = {
  layer: "live",
  status: "passed",
  reason: null,
  checks: [
    { check: "field_exists", op_index: 0, passed: true, evidence: { field: "x_nf_req" } },
    {
      check: "view_renders",
      op_index: 1,
      passed: false,
      evidence: { view: "sale.order.form", api_key: "sk-live-abc123", email: "ada@client.ng" },
    },
  ],
  steps: [],
};
const walk: LayerResult = {
  layer: "walkthrough",
  status: "failed",
  reason: "The Save button did not appear",
  checks: [],
  steps: [
    { index: 0, op_index: 0, action: "open", target: "Sales / Quotations", passed: true, screenshot_id: "s0", dom_assertion: null },
    { index: 1, op_index: 0, action: "fill", target: "Customer", passed: true, screenshot_id: "s1", dom_assertion: null },
    { index: 2, op_index: 1, action: "click", target: "Save", passed: false, screenshot_id: "s2", dom_assertion: "present:.o_form_button_save" },
    { index: 3, op_index: 1, action: "assert", target: "Saved", passed: false, screenshot_id: null, dom_assertion: null },
  ],
};
const flows: LayerResult = {
  layer: "flows",
  status: "skipped",
  reason: "Stock is not installed on this database",
  checks: [],
  steps: [],
};
const run = (status: RunStatus, layers: LayerResult[] = [live, walk, flows]): VerifyRun => ({
  run_id: "run-1",
  changeset_id: "cs-1",
  status,
  layers,
  started_at: "2026-10-22T09:41:00Z",
  finished_at: status === "running" || status === "queued" ? null : "2026-10-22T09:43:05Z",
});
const url = (id: string) => `/artifacts/${id}.png`;

describe("AC1 statuses", () => {
  const all: RunStatus[] = ["queued", "running", "passed", "failed", "needs_human", "rolled_back"];
  it.each(all)("renders run status %s in plain words with an icon or label", (st) => {
    stubMotion(false);
    render(<EvidenceViewer run={run(st)} artifactUrl={url} />);
    const pill = screen.getByTestId("run-status");
    expect(pill).toHaveAttribute("data-status", st);
    expect(pill.textContent?.trim().length).toBeGreaterThan(3);
    expect(pill.textContent).not.toMatch(/_/);
  });
  it("renders each layer status, and skipped shows its reason", () => {
    stubMotion(false);
    render(<EvidenceViewer run={run("failed")} artifactUrl={url} />);
    for (const [layer, st] of [["live", "passed"], ["walkthrough", "failed"], ["flows", "skipped"]]) {
      expect(screen.getByTestId(`layer-${layer}`)).toHaveAttribute("data-status", st);
    }
    expect(within(screen.getByTestId("layer-flows")).getByText(/Stock is not installed/)).toBeInTheDocument();
  });
  it("shows check results per change", () => {
    stubMotion(false);
    render(<EvidenceViewer run={run("failed")} artifactUrl={url} />);
    const checks = screen.getAllByTestId("check-row");
    expect(checks).toHaveLength(2);
    expect(checks[0]).toHaveAttribute("data-passed", "true");
    expect(checks[1]).toHaveAttribute("data-passed", "false");
    expect(checks[1].textContent).toMatch(/change 2/i);
  });
  it("shows rollback state when the change was undone", () => {
    stubMotion(false);
    render(<EvidenceViewer run={run("rolled_back")} artifactUrl={url} />);
    expect(screen.getByTestId("rollback-state").textContent).toMatch(/undone|rolled back/i);
  });
  it("a platform notice is an amber needs-a-person notice, not a red failure", () => {
    stubMotion(false);
    const notice: LayerResult = {
      ...flows,
      reason:
        "platform notice: Saved correctly. Odoo then shows non-admin users an Access Error (a platform permission notice, e.g. iap.account on Odoo 20).",
    };
    render(<EvidenceViewer run={run("needs_human", [live, notice])} artifactUrl={url} />);
    const n = screen.getByTestId("notice-flows");
    expect(n).toHaveAttribute("data-tone", "warning");
    expect(n.textContent).toMatch(/Saved correctly/);
    expect(n.textContent).not.toMatch(/platform notice:/);
  });
});

describe("states", () => {
  it.each([
    [{ loading: true, run: null }, "loading"],
    [{ run: null }, "empty"],
    [{ run: null, error: true, errorCopy: "Odoo did not answer in time." }, "error"],
    [{ run: null, denied: { group: "base.group_system" } }, "denied"],
    [{ run: run("running") }, "partial"],
    [{ run: run("passed", [live]) }, "ready"],
  ])("draws state %#", (props, st) => {
    stubMotion(false);
    render(<EvidenceViewer artifactUrl={url} {...(props as object)} run={(props as { run: VerifyRun | null }).run} />);
    expect(screen.getByTestId("evidence-viewer")).toHaveAttribute("data-state", st);
  });
});

describe("AC2 timeline", () => {
  it("is keyboard navigable with arrows, j/k, Home and End using roving tabindex", () => {
    stubMotion(false);
    render(<EvidenceViewer run={run("failed")} artifactUrl={url} />);
    const list = screen.getByRole("listbox", { name: /screenshot/i });
    const opts = within(list).getAllByRole("option");
    expect(opts).toHaveLength(4);
    expect(opts.filter((o) => o.tabIndex === 0)).toHaveLength(1);
    opts[0].focus();
    fireEvent.keyDown(opts[0], { key: "ArrowRight" });
    expect(opts[1]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(opts[1], { key: "j" });
    expect(opts[2]).toHaveAttribute("aria-selected", "true");
    expect(document.activeElement).toBe(opts[2]);
    fireEvent.keyDown(opts[2], { key: "k" });
    expect(opts[1]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(opts[1], { key: "End" });
    expect(opts[3]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(opts[3], { key: "Home" });
    expect(opts[0]).toHaveAttribute("aria-selected", "true");
  });
  it("shows the selected screenshot with alt text and says when a step has none", () => {
    stubMotion(false);
    render(<EvidenceViewer run={run("failed")} artifactUrl={url} />);
    const opts = screen.getAllByRole("option");
    fireEvent.click(opts[2]);
    const img = screen.getByTestId("shot-preview").querySelector("img");
    expect(img).toHaveAttribute("src", "/artifacts/s2.png");
    expect(img?.getAttribute("alt")).toMatch(/Save/);
    fireEvent.click(opts[3]);
    expect(screen.getByTestId("shot-preview").querySelector("img")).toBeNull();
    expect(screen.getByTestId("shot-preview").textContent).toMatch(/no screenshot/i);
  });
  it("reduced motion: no transition on the preview", () => {
    stubMotion(true);
    render(<EvidenceViewer run={run("failed")} artifactUrl={url} />);
    expect(screen.getByTestId("shot-preview")).toHaveAttribute("data-motion", "reduced");
  });
});

describe("AC3 + AC5", () => {
  const src = readFileSync(path.join(__dirname, "EvidenceViewer.tsx"), "utf8");
  it("uses botVerify.ts types only and makes no API calls", () => {
    expect(src).toMatch(/from "@\/lib\/api\/botVerify"/);
    expect(src).not.toMatch(/\bfetch\(|botVerifyApi|request\(/);
  });
  it("hides secret-like and personal evidence values", () => {
    stubMotion(false);
    const { container } = render(<EvidenceViewer run={run("failed")} artifactUrl={url} />);
    expect(container.textContent).not.toMatch(/sk-live-abc123|ada@client\.ng/);
    expect(container.textContent).toMatch(/hidden/i);
  });
  it("copy avoids banned words, dashes and raw hex", () => {
    expect(src).not.toMatch(/[\u2013\u2014]/);
    expect(src).not.toMatch(/\b(please|sorry|oops|invalid|click here|payload|endpoint)\b/i);
    expect(src).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(src).not.toMatch(/transition-all|transition: all/);
  });
});

describe("review fixes", () => {
  it("error state shows plain copy and a Retry button only when onRetry is given", () => {
    stubMotion(false);
    const onRetry = vi.fn();
    const { rerender } = render(<EvidenceViewer run={null} artifactUrl={url} error errorCopy="Odoo did not answer in time." onRetry={onRetry} />);
    expect(screen.getByText("Odoo did not answer in time.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
    rerender(<EvidenceViewer run={null} artifactUrl={url} error />);
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(screen.getByTestId("evidence-viewer").textContent).toMatch(/could not reach/);
  });
  it("check evidence is also rendered inside each row for small screens", () => {
    stubMotion(false);
    render(<EvidenceViewer run={run("failed")} artifactUrl={url} />);
    const row = screen.getAllByTestId("check-row")[1];
    const inRow = within(row).getAllByTestId("check-evidence");
    expect(inRow).toHaveLength(2);
    expect(inRow.some((e) => e.className.includes("sm:hidden"))).toBe(true);
  });
  it("timeline labels wrap to two lines instead of title-only truncation", () => {
    stubMotion(false);
    render(<EvidenceViewer run={run("failed")} artifactUrl={url} />);
    for (const o of screen.getAllByRole("option")) {
      const span = o.querySelector(".line-clamp-2");
      expect(span).not.toBeNull();
      expect(o.querySelector(".truncate,[title]")).toBeNull();
    }
  });
  it("rolled_back uses one tone for chip and callout", () => {
    stubMotion(false);
    render(<EvidenceViewer run={run("rolled_back")} artifactUrl={url} />);
    expect(screen.getByTestId("rollback-state").querySelector(".bg-danger-subtle")).not.toBeNull();
    expect(screen.getByTestId("rollback-state").querySelector(".bg-info-subtle")).toBeNull();
    expect(screen.getByTestId("run-status").className).toMatch(/bg-danger-subtle/);
  });
  it("rendered text has no banned words or dashes in any state", () => {
    stubMotion(false);
    const views = [
      <EvidenceViewer key="a" run={run("rolled_back")} artifactUrl={url} />,
      <EvidenceViewer key="b" run={run("needs_human")} artifactUrl={url} />,
      <EvidenceViewer key="c" run={run("running")} artifactUrl={url} />,
      <EvidenceViewer key="d" run={null} artifactUrl={url} onStart={() => {}} />,
      <EvidenceViewer key="e" run={null} artifactUrl={url} error onRetry={() => {}} />,
      <EvidenceViewer key="f" run={null} artifactUrl={url} denied={{ group: "base.group_system" }} />,
      <EvidenceViewer key="g" run={null} artifactUrl={url} loading />,
    ];
    for (const v of views) {
      const { container, unmount } = render(v);
      const t = container.textContent ?? "";
      expect(t).not.toMatch(/[\u2013\u2014]/);
      expect(t).not.toMatch(/\b(please|sorry|oops|invalid|click here|payload|endpoint|null|undefined)\b/i);
      unmount();
    }
  });
});

describe("BV-UI-WIRE: change label", () => {
  it("keeps 'Change 1' on one line", () => {
    stubMotion(false);
    render(<EvidenceViewer run={run("passed")} artifactUrl={url} />);
    const cells = screen.getAllByText(/^Change\s1$/);
    expect(cells.length).toBeGreaterThan(0);
    for (const c of cells) expect(c.className).toMatch(/whitespace-nowrap/);
  });
});
