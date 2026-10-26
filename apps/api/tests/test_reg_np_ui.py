"""Pin REG-NP-UI behaviour the product already shows.

AC3 split: the screen spec names no route marked "can be empty", so that
set is not asserted. Loading routes expose an sr-only name and do not
render the kit Skeleton; the Skeleton sentence is not asserted.
Keyboard focus opens a tooltip immediately, so the "not before 125 ms"
sentence is not asserted. Hover stays hidden at 124 ms and is shown by
200 ms. Escape removes the tooltip.
A single text ``asChild`` child throws
``Button: asChild expects a single React element child.``
Zero or several children still fail ``React.Children.only``.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.no_app_db

_REPO = Path(__file__).resolve().parents[3]
_WEB = _REPO / "apps" / "web"
_ALERTS = _WEB / "src" / "styles" / "globals" / "alerts.css"
_TABS = _WEB / "src" / "components" / "ui" / "Tabs.tsx"
_TOOLTIP = _WEB / "src" / "components" / "ui" / "Tooltip.tsx"
_BUTTON = _WEB / "src" / "components" / "ui" / "Button.tsx"
_DATA = _WEB / "src" / "components" / "ui" / "DataTable.tsx"
_SCRATCH_TEST = _WEB / f"reg_np_ui.runtime.{os.getpid()}.test.tsx"
_SCRATCH_CONFIG = _WEB / f"vitest.reg-np-ui.{os.getpid()}.config.ts"

_ALERT_RULE = re.compile(
    r"(?P<name>\.odoo-form-alert--(?:info|warning|danger))\s*\{(?P<body>[^{}]*)\}"
)
_HEX = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
_CASES: dict[str, dict[str, Any]] | None = None
_RUN_ERROR: Exception | None = None


def _remove_scratch() -> None:
    _SCRATCH_TEST.unlink(missing_ok=True)
    _SCRATCH_CONFIG.unlink(missing_ok=True)


atexit.register(_remove_scratch)

_CONFIG_TS = """import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  esbuild: { jsx: "automatic" },
  css: { postcss: { plugins: [] } },
  test: {
    environment: "happy-dom",
    include: ["reg_np_ui.runtime.test.tsx"],
    setupFiles: ["./vitest.setup.ts"],
    css: false,
    fileParallelism: false,
  },
  resolve: {
    alias: [
      {
        find: /^(.+)\\.module\\.css$/,
        replacement: path.resolve(__dirname, "./vitest.css-module-stub.js"),
      },
      { find: "@", replacement: path.resolve(__dirname, "./src") },
    ],
  },
});
"""

_RUNTIME_TSX = r"""/** @vitest-environment jsdom */
import { useState } from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { Button } from "@/components/ui/Button";
import { Tabs } from "@/components/ui/Tabs";
import { Tooltip, TooltipProvider } from "@/components/ui/Tooltip";
import { TotpCodeInput } from "@/components/auth/TotpCodeInput";
import {
  DataTable,
  DEFAULT_VIRTUALIZE_THRESHOLD,
  shouldVirtualizeRows,
  sortDataTableRows,
  stepActiveRowIndex,
  type DataTableColumn,
} from "@/components/ui/DataTable";
import {
  BulkResultTable,
  filterBulkResultRows,
  type BulkRunResult,
  type PerRecordResult,
} from "@/components/ui/BulkResultTable";
import RootLoading from "@/app/loading";
import RootError from "@/app/error";
import RootNotFound from "@/app/not-found";
import ConnectionLoading from "@/app/connections/[id]/loading";
import ConnectionError from "@/app/connections/[id]/error";
import ConnectionNotFound from "@/app/connections/[id]/not-found";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: unknown }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

beforeAll(() => {
  if (typeof document.elementFromPoint !== "function") {
    document.elementFromPoint = () => null;
  }
  const original = CSS.supports.bind(CSS);
  vi.spyOn(CSS, "supports").mockImplementation((property: string, value?: string) => {
    if (property === "-webkit-touch-callout" && value === "none") return true;
    if (value === undefined) return original(property);
    return original(property, value);
  });
});

const tabItems = [
  { value: "one", label: "Tab One", content: <p>Panel one</p> },
  { value: "two", label: "Tab Two", content: <p>Panel two</p> },
];

function renderTooltip() {
  render(
    <TooltipProvider>
      <Tooltip label="Helper text">
        <button type="button">Trigger button</button>
      </Tooltip>
    </TooltipProvider>,
  );
  return screen.getByRole("button", { name: "Trigger button" });
}

type Row = { id: string; name: string; score: number };

const columns: DataTableColumn<Row>[] = [
  { id: "name", header: "Name", accessor: (row) => row.name, sortValue: (row) => row.name },
  { id: "score", header: "Score", accessor: (row) => row.score, sortValue: (row) => row.score },
];

function makeRows(count: number): Row[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `row-${i}`,
    name: `Row ${String(i).padStart(4, "0")}`,
    score: count - 1 - i,
  }));
}

function makeBulkResult(count: number): BulkRunResult {
  const per_record: PerRecordResult[] = Array.from({ length: count }, (_, i) => ({
    record_id: i + 1,
    display_name: `Record ${i + 1}`,
    ok: i % 2 === 0,
    error: i % 2 === 0 ? null : "failed",
  }));
  return {
    run_id: "run",
    operation: "mass_edit",
    model: "res.partner",
    total: count,
    succeeded: per_record.filter((row) => row.ok).length,
    failed: per_record.filter((row) => !row.ok).length,
    per_record,
  };
}

function dataRows() {
  return screen.getByTestId("data-table").querySelectorAll("tbody tr:not([aria-hidden])");
}

function paste(input: HTMLInputElement, text: string) {
  fireEvent.focus(input);
  const pasteEvent = new Event("paste", { bubbles: true, cancelable: true });
  Object.defineProperty(pasteEvent, "clipboardData", {
    value: { getData: (format: string) => (format === "text/plain" ? text : "") },
  });
  input.dispatchEvent(pasteEvent);
}

function TotpHarness({ onComplete }: { onComplete?: (value: string) => void }) {
  const [value, setValue] = useState("");
  return (
    <>
      <TotpCodeInput
        label="Two-factor code"
        value={value}
        onChange={setValue}
        onComplete={onComplete}
      />
      <output data-testid="totp-value">{value}</output>
    </>
  );
}

describe("REG-NP-UI", () => {
  it("ac2-root-loading", () => {
    render(<RootLoading />);
    expect(screen.getByText("Loading page")).toBeInTheDocument();
  });

  it("ac2-root-error", () => {
    const reset = vi.fn();
    render(<RootError error={new Error("render failed")} reset={reset} />);
    expect(screen.getByRole("heading", { name: "Load this page failed" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "The app hit an error while rendering. Try again, or return home if the problem continues.",
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Go home" })).toBeInTheDocument();
  });

  it("ac2-root-not-found", () => {
    render(<RootNotFound />);
    expect(screen.getByRole("heading", { name: "This page isn't here" })).toBeInTheDocument();
    expect(screen.getByText(/The link may be old or mistyped/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go home" })).toHaveAttribute("href", "/");
  });

  it("ac2-connection-loading", () => {
    render(<ConnectionLoading />);
    expect(screen.getByText("Loading connection")).toBeInTheDocument();
  });

  it("ac2-connection-error", () => {
    const reset = vi.fn();
    render(<ConnectionError error={new Error("render failed")} reset={reset} />);
    expect(
      screen.getByRole("heading", { name: "Load this connection failed" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Something blocked this connection view from rendering. Try again, or pick another connection from the list.",
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("link", { name: "View connections" })).toHaveAttribute(
      "href",
      "/connections",
    );
  });

  it("ac2-connection-not-found", () => {
    render(<ConnectionNotFound />);
    expect(
      screen.getByRole("heading", { name: "Find this connection failed" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "No connection matches this id, or it was removed. Open the connections list and choose an active instance.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View connections" })).toHaveAttribute(
      "href",
      "/connections",
    );
  });

  it("ac4-arrow-right", async () => {
    render(<Tabs items={tabItems} defaultValue="one" />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs[0]).toHaveAttribute("aria-selected", "true");
    expect(tabs[1]).toHaveAttribute("aria-selected", "false");
    tabs[0].focus();
    fireEvent.keyDown(tabs[0], { key: "ArrowRight", code: "ArrowRight", bubbles: true });
    await waitFor(() => {
      const after = screen.getAllByRole("tab");
      expect(after[0]).toHaveAttribute("aria-selected", "false");
      expect(after[1]).toHaveAttribute("aria-selected", "true");
    });
  });

  it("ac5-focus-escape", async () => {
    const trigger = renderTooltip();
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    trigger.focus();
    fireEvent.focus(trigger);
    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toHaveTextContent("Helper text");
    });
    fireEvent.keyDown(document, { key: "Escape", code: "Escape", bubbles: true });
    await waitFor(() => {
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    });
  });

  it("ac6-as-child", () => {
    render(
      <Button asChild>
        <a href="/connect">Go connect</a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Go connect" });
    expect(link.tagName).toBe("A");
    expect(link.getAttribute("href")).toBe("/connect");
    expect(screen.queryByRole("button")).toBeNull();
    expect(link.className).toContain("inline-flex");
  });

  it("ac6-children-only", () => {
    const only = "React.Children.only expected to receive a single React element child.";
    expect(() => render(<Button asChild></Button>)).toThrow(only);
    expect(() =>
      render(
        <Button asChild>
          <a href="/a">A</a>
          <a href="/b">B</a>
        </Button>,
      ),
    ).toThrow(only);
  });

  it("ac6-text-child", () => {
    const message = "Button: asChild expects a single React element child.";
    expect(() => render(<Button asChild>Go connect</Button>)).toThrow(message);
  });

  it("ac7-paste-digits", async () => {
    const onComplete = vi.fn();
    render(<TotpHarness onComplete={onComplete} />);
    const input = screen.getByLabelText("Two-factor code") as HTMLInputElement;
    paste(input, "123456");
    await waitFor(() => expect(screen.getByTestId("totp-value")).toHaveTextContent("123456"));
    expect(input.value).toBe("123456");
    await waitFor(() => expect(onComplete).toHaveBeenCalledWith("123456"));
  });

  it("ac7-paste-spaces", async () => {
    render(<TotpHarness />);
    const input = screen.getByLabelText("Two-factor code") as HTMLInputElement;
    paste(input, "123 456");
    await waitFor(() => expect(screen.getByTestId("totp-value")).toHaveTextContent("123456"));
  });

  it("ac7-attributes", () => {
    render(<TotpHarness />);
    const input = screen.getByLabelText("Two-factor code");
    expect(input).toHaveAttribute("autocomplete", "one-time-code");
    expect(input).toHaveAttribute("inputmode", "numeric");
    expect(input).toHaveAttribute("maxlength", "6");
    expect(input).toHaveAttribute("data-input-otp");
  });

  it("ac8-threshold", () => {
    expect(DEFAULT_VIRTUALIZE_THRESHOLD).toBe(50);
    expect(shouldVirtualizeRows(50)).toBe(false);
    expect(shouldVirtualizeRows(51)).toBe(true);
    expect(stepActiveRowIndex(0, "ArrowDown", 10)).toBe(1);
    expect(stepActiveRowIndex(1, "ArrowUp", 10)).toBe(0);
  });

  it("ac8-row-counts", () => {
    const { unmount } = render(
      <DataTable columns={columns} rows={makeRows(50)} rowKey={(row) => row.id} />,
    );
    expect(screen.queryByTestId("data-table-scroll")).not.toBeInTheDocument();
    expect(dataRows()).toHaveLength(50);
    unmount();

    render(<DataTable columns={columns} rows={makeRows(51)} rowKey={(row) => row.id} />);
    expect(screen.getByTestId("data-table-scroll")).toBeInTheDocument();
    expect(dataRows().length).toBeLessThan(51);
    cleanup();

    render(<BulkResultTable result={makeBulkResult(50)} />);
    expect(screen.queryByTestId("data-table-scroll")).not.toBeInTheDocument();
    expect(dataRows()).toHaveLength(50);
    cleanup();

    render(<BulkResultTable result={makeBulkResult(51)} />);
    expect(screen.getByTestId("data-table-scroll")).toBeInTheDocument();
    expect(dataRows().length).toBeLessThan(51);
  });

  it("ac8-arrows", () => {
    render(<DataTable columns={columns} rows={makeRows(10)} rowKey={(row) => row.id} />);
    const grid = screen.getByRole("grid");
    grid.focus();
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    const down = within(grid).getByText("Row 0001").closest("tr");
    expect(down).toHaveAttribute("data-active", "true");
    fireEvent.keyDown(grid, { key: "ArrowUp" });
    const up = within(grid).getByText("Row 0000").closest("tr");
    expect(up).toHaveAttribute("data-active", "true");
  });

  it("ac8-sort-filter", () => {
    const rows = makeRows(5000);
    const records = makeBulkResult(5000).per_record;
    const started = performance.now();
    const sorted = sortDataTableRows(rows, columns, { id: "score", dir: "asc" });
    const filtered = filterBulkResultRows(records, "failed");
    const elapsedMs = performance.now() - started;
    expect(sorted).toHaveLength(5000);
    expect(sorted[0]?.score).toBe(0);
    expect(sorted[4999]?.score).toBe(4999);
    expect(filtered).toHaveLength(2500);
    expect(filtered.every((row) => !row.ok)).toBe(true);
    expect(elapsedMs).toBeLessThan(100);
  });

  it(
    "ac5-hover-delay",
    async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      const trigger = renderTooltip();
      fireEvent.pointerEnter(trigger, { pointerType: "mouse" });
      fireEvent.mouseEnter(trigger);
      fireEvent.mouseMove(trigger);
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
      await vi.advanceTimersByTimeAsync(124);
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
      await vi.advanceTimersByTimeAsync(76);
      expect(screen.getByRole("tooltip")).toBeInTheDocument();
    },
    20000,
  );
});
"""


def _remove_report(path: Path) -> None:
    path.unlink(missing_ok=True)


def _index_report(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for suite in payload.get("testResults", []):
        for case in suite.get("assertionResults", []):
            title = str(case.get("title", ""))
            if title:
                found[title] = case
    if not found:
        keys = ",".join(payload.keys())
        raise RuntimeError(f"vitest json had no cases ({keys})")
    return found


def _run_vitest() -> dict[str, dict[str, Any]]:
    config = _CONFIG_TS.replace("reg_np_ui.runtime.test.tsx", _SCRATCH_TEST.name)
    _SCRATCH_CONFIG.write_text(config, encoding="utf-8")
    _SCRATCH_TEST.write_text(_RUNTIME_TSX, encoding="utf-8")
    fd, name = tempfile.mkstemp(prefix="reg-np-ui-", suffix=".json")
    os.close(fd)
    report_path = Path(name)
    try:
        env = os.environ.copy()
        env["CI"] = "1"
        proc = subprocess.run(
            [
                "pnpm",
                "exec",
                "vitest",
                "run",
                "--config",
                _SCRATCH_CONFIG.name,
                "--reporter=json",
                "--outputFile",
                str(report_path),
                "--testTimeout",
                "20000",
            ],
            cwd=_WEB,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        raw = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
        if not raw.strip():
            tail = f"{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"
            raise RuntimeError(f"vitest wrote no json (exit {proc.returncode})\n{tail}")
        return _index_report(json.loads(raw))
    finally:
        _remove_scratch()
        _remove_report(report_path)


def _cases() -> dict[str, dict[str, Any]]:
    global _CASES, _RUN_ERROR
    if _RUN_ERROR is not None:
        raise _RUN_ERROR
    if _CASES is None:
        try:
            _CASES = _run_vitest()
        except Exception as exc:
            _RUN_ERROR = exc
            raise
    return _CASES


def _require(title: str) -> None:
    cases = _cases()
    if title not in cases:
        known = ", ".join(sorted(cases))
        raise AssertionError(f"missing vitest case {title}; have {known}")
    case = cases[title]
    if case.get("status") != "passed":
        messages = case.get("failureMessages") or []
        detail = "\n".join(str(item) for item in messages)[:2000]
        raise AssertionError(f"{title} {case.get('status')}\n{detail}")


def test_ac2_root_loading_names_the_page() -> None:
    _require("ac2-root-loading")


def test_ac2_root_error_what_why_next() -> None:
    text = (_WEB / "src/app/error.tsx").read_text(encoding="utf-8")
    assert 'window.location.assign("/")' in text
    _require("ac2-root-error")


def test_ac2_root_not_found_what_why_next() -> None:
    _require("ac2-root-not-found")


def test_ac2_connection_loading_names_the_connection() -> None:
    _require("ac2-connection-loading")


def test_ac2_connection_error_what_why_next() -> None:
    _require("ac2-connection-error")


def test_ac2_connection_not_found_what_why_next() -> None:
    _require("ac2-connection-not-found")


def test_ac1_dark_mode_alert_tokens() -> None:
    css = _ALERTS.read_text(encoding="utf-8")
    found = {match.group("name"): match.group("body") for match in _ALERT_RULE.finditer(css)}
    expect = {
        ".odoo-form-alert--info": "info",
        ".odoo-form-alert--warning": "warning",
        ".odoo-form-alert--danger": "danger",
    }
    assert set(found) == set(expect)
    for name, token in expect.items():
        body = found[name]
        assert f"background: var(--{token}-1)" in body
        assert f"border-color: var(--{token}-2)" in body
        assert f"color: var(--{token}-5)" in body
        assert _HEX.search(body) is None


def test_ac4_tabs_import_base_ui() -> None:
    text = _TABS.read_text(encoding="utf-8")
    needle = 'import { Tabs as BaseTabs } from "@base-ui/react/tabs";'
    assert needle in text
    assert "@radix-ui/react-tabs" not in text


def test_ac4_arrow_right_moves_aria_selected() -> None:
    _require("ac4-arrow-right")


def test_ac5_open_delay_is_200() -> None:
    text = _TOOLTIP.read_text(encoding="utf-8")
    assert "export const TOOLTIP_OPEN_DELAY_MS = 200;" in text
    assert "delay={TOOLTIP_OPEN_DELAY_MS}" in text


def test_ac5_hover_hidden_before_125_shown_by_200() -> None:
    _require("ac5-hover-delay")


def test_ac5_escape_removes_tooltip() -> None:
    _require("ac5-focus-escape")


def test_ac6_as_child_renders_child() -> None:
    text = _BUTTON.read_text(encoding="utf-8")
    assert "Children.only(children)" in text
    assert "<SlotButton" in text
    _require("ac6-as-child")


def test_ac6_zero_or_several_children_fail_children_only() -> None:
    _require("ac6-children-only")


def test_ac6_text_child_throws_named_error() -> None:
    _require("ac6-text-child")


def test_ac7_paste_sets_value_and_completes() -> None:
    _require("ac7-paste-digits")


def test_ac7_paste_strips_spaces() -> None:
    _require("ac7-paste-spaces")


def test_ac7_otp_input_attributes() -> None:
    _require("ac7-attributes")


def test_ac8_virtualize_threshold() -> None:
    _require("ac8-threshold")


def test_ac8_row_counts() -> None:
    text = _DATA.read_text(encoding="utf-8")
    assert "<TableVirtuoso" in text
    _require("ac8-row-counts")


def test_ac8_arrow_keys_step_active_row() -> None:
    text = _DATA.read_text(encoding="utf-8")
    needle = "stepActiveRowIndex(current, key, sortedRows.length)"
    assert needle in text
    _require("ac8-arrows")


def test_ac8_sort_and_filter_under_100ms() -> None:
    _require("ac8-sort-filter")


def test_runtime_scratch_removed() -> None:
    _cases()
    assert not _SCRATCH_TEST.exists()
    assert not _SCRATCH_CONFIG.exists()
