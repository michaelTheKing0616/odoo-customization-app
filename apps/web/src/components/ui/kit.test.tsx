/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen, waitFor, within, act } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { BulkResultTable, type BulkRunResult } from "@/components/ui/BulkResultTable";
import { ToastProvider, useToast } from "@/components/ui/Toast";

type Row = { id: string; name: string; score: number };

const sampleColumns: DataTableColumn<Row>[] = [
  {
    id: "name",
    header: "Name",
    accessor: (r) => r.name,
    sortValue: (r) => r.name,
  },
  {
    id: "score",
    header: "Score",
    accessor: (r) => r.score,
    sortValue: (r) => r.score,
  },
];

const sampleRows: Row[] = [
  { id: "a", name: "Zeta", score: 10 },
  { id: "b", name: "Alpha", score: 30 },
  { id: "c", name: "Beta", score: 20 },
];

afterEach(() => {
  cleanup();
});

describe("Button", () => {
  it("renders primary and danger variants", () => {
    render(
      <>
        <Button variant="primary">Save</Button>
        <Button variant="danger">Delete</Button>
      </>,
    );
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
  });

  it("shows loading state", () => {
    render(<Button loading>Working</Button>);
    expect(screen.getByRole("button", { name: "Working" })).toBeDisabled();
  });
});

describe("Callout", () => {
  it("renders title, body, and actions", () => {
    render(
      <Callout
        variant="warning"
        title="Blocked"
        actions={<button type="button">Learn more</button>}
      >
        Choose another path.
      </Callout>,
    );
    expect(screen.getByText("Blocked")).toBeInTheDocument();
    expect(screen.getByText("Choose another path.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Learn more" })).toBeInTheDocument();
  });
});

describe("DataTable", () => {
  it("sorts columns on header click", () => {
    render(
      <DataTable columns={sampleColumns} rows={sampleRows} rowKey={(r) => r.id} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Name" }));
    const cells = within(screen.getByTestId("data-table")).getAllByRole("cell");
    expect(cells[0]).toHaveTextContent("Alpha");
  });

  it("toggles row selection", () => {
    const onChange = vi.fn();
    render(
      <DataTable
        columns={sampleColumns}
        rows={sampleRows}
        rowKey={(r) => r.id}
        selectable
        selectedKeys={new Set()}
        onSelectedKeysChange={onChange}
      />,
    );
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[1]);
    expect(onChange).toHaveBeenCalledWith(new Set(["a"]));
  });

  it("virtualizes large row sets", () => {
    const manyRows: Row[] = Array.from({ length: 250 }, (_, i) => ({
      id: `row-${i}`,
      name: `Row ${i}`,
      score: i,
    }));
    render(
      <DataTable
        columns={sampleColumns}
        rows={manyRows}
        rowKey={(r) => r.id}
        virtualizeThreshold={200}
        viewportHeight={200}
      />,
    );
    const table = screen.getByTestId("data-table");
    const renderedRows = table.querySelectorAll("tbody tr:not([aria-hidden])");
    expect(renderedRows.length).toBeLessThan(manyRows.length);
    expect(renderedRows.length).toBeGreaterThan(0);
  });
});

describe("BulkResultTable", () => {
  const result: BulkRunResult = {
    run_id: "r1",
    operation: "mass_edit",
    model: "res.partner",
    total: 2,
    succeeded: 1,
    failed: 1,
    per_record: [
      { record_id: 1, display_name: "A", ok: true },
      { record_id: 2, display_name: "B", ok: false, error: "boom" },
    ],
  };

  it("filters failed rows", () => {
    render(<BulkResultTable result={result} />);
    fireEvent.click(screen.getByRole("button", { name: "Failed" }));
    expect(screen.getByText("boom")).toBeInTheDocument();
    expect(screen.queryByText("A")).not.toBeInTheDocument();
  });
});

describe("CodeBlock", () => {
  it("highlights json and copies to clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    render(<CodeBlock code='{"ok":true}' language="json" />);
    const block = screen.getByTestId("code-block");
    expect(block.querySelector(".token.property")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    expect(writeText).toHaveBeenCalledWith('{"ok":true}');
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Copied" })).toBeInTheDocument();
    });
  });

  it("toggles wrap", () => {
    render(<CodeBlock code="line one" language="text" />);
    const pre = screen.getByTestId("code-block").querySelector("pre")!;
    expect(pre.className).toContain("whitespace-pre");
    expect(pre.className).not.toContain("whitespace-pre-wrap");
    fireEvent.click(screen.getByRole("button", { name: "Wrap lines" }));
    expect(pre.className).toContain("whitespace-pre-wrap");
  });
});

describe("ConfirmDialogV2", () => {
  it("danger variant shows red header, risks, and snapshot note", () => {
    render(
      <ConfirmDialogV2
        open
        title="Delete model"
        warning="This cannot be undone."
        risks={["Drops columns", "Breaks integrations"]}
        riskLevel="danger"
        snapshotNote="A snapshot will be taken before apply."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByTestId("confirm-dialog-v2")).toHaveAttribute("data-risk-level", "danger");
    expect(screen.getByTestId("confirm-dialog-v2-header").className).toMatch(/danger/);
    expect(screen.getByTestId("confirm-dialog-v2-snapshot")).toHaveTextContent("snapshot");
    expect(screen.getByTestId("confirm-dialog-v2-risks")).toHaveTextContent("Drops columns");
  });

  it("requires phrase before confirm", () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialogV2
        open
        title="Proceed"
        warning="Careful."
        risks={[]}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onConfirm).not.toHaveBeenCalled();
    fireEvent.change(screen.getByTestId("confirm-dialog-v2-input"), {
      target: { value: "I understand the risks" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onConfirm).toHaveBeenCalled();
  });
});

describe("Toast", () => {
  function ToastProbe() {
    const { toast } = useToast();
    return (
      <button
        type="button"
        onClick={() => toast({ variant: "success", title: "Saved", description: "Done." })}
      >
        Fire toast
      </button>
    );
  }

  it("shows and auto-dismisses toasts", async () => {
    vi.useFakeTimers();
    try {
      render(
        <ToastProvider>
          <ToastProbe />
        </ToastProvider>,
      );
      fireEvent.click(screen.getByRole("button", { name: "Fire toast" }));
      expect(screen.getByTestId("toast")).toHaveTextContent("Saved");
      await act(async () => {
        await vi.advanceTimersByTimeAsync(6100);
      });
      expect(screen.queryByTestId("toast")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
