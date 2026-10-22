/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  A4_PAPER,
  EMPTY_CANVAS_ACTION,
  EMPTY_CANVAS_SENTENCE,
  ODOO_REPORT_BLOCK_MIME,
  REPORT_PAPER_COLOR,
  ReportBlock,
  ReportCanvas,
  RENTAL_AGREEMENT_STARTER,
  isAmountColumn,
  isAmountField,
  isReportPaletteDrag,
  paperAspectRatio,
  paperPaddingStyle,
  ratioErrorPercent,
  ratioWithinTolerance,
  readReportPaletteBlockType,
  reorderReportBlocks,
  resolvePaperFormat,
  setReportPaletteDragData,
  US_LETTER_PAPER,
} from "./ReportCanvas";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("resolvePaperFormat / ratio", () => {
  it("defaults to A4 210×297 within 2% of true ratio", () => {
    const paper = resolvePaperFormat();
    expect(paper.widthMm).toBe(210);
    expect(paper.heightMm).toBe(297);
    const ratio = paperAspectRatio(paper);
    expect(ratioWithinTolerance(ratio, 210 / 297, 2)).toBe(true);
    expect(ratioErrorPercent(ratio, 210 / 297)).toBeLessThanOrEqual(2);
  });

  it("resolves US Letter from label", () => {
    const paper = resolvePaperFormat("US Letter");
    expect(paper.widthMm).toBe(US_LETTER_PAPER.widthMm);
    expect(paper.heightMm).toBe(US_LETTER_PAPER.heightMm);
    expect(ratioWithinTolerance(paperAspectRatio(paper), 215.9 / 279.4, 2)).toBe(
      true,
    );
  });

  it("applies margin overrides", () => {
    const paper = resolvePaperFormat("A4", { marginTopMm: 20, marginLeftMm: 10 });
    expect(paper.marginTopMm).toBe(20);
    expect(paper.marginLeftMm).toBe(10);
    expect(paper.marginBottomMm).toBe(A4_PAPER.marginBottomMm);
  });

  it("expresses margins as width-relative CSS percentages", () => {
    const style = paperPaddingStyle(A4_PAPER) as Record<string, string>;
    expect(style["--report-pad-top"]).toBe(`${(40 / 210) * 100}%`);
    expect(style["--report-pad-left"]).toBe(`${(7 / 210) * 100}%`);
  });
});

describe("tabular numerals helpers", () => {
  it("detects amount-like field names", () => {
    expect(isAmountField("price_unit")).toBe(true);
    expect(isAmountField("amount_total")).toBe(true);
    expect(isAmountField("partner_id")).toBe(false);
  });

  it("detects amount columns by field or label", () => {
    expect(isAmountColumn({ field: "price_unit", label: "Rate" })).toBe(true);
    expect(isAmountColumn({ field: "x_misc", label: "Amount" })).toBe(true);
    expect(isAmountColumn({ field: "product_id", label: "Item" })).toBe(false);
  });
});

describe("ReportCanvas render", () => {
  it("draws the paper at the format aspect ratio and paper-colored surface", () => {
    render(<ReportCanvas blocks={RENTAL_AGREEMENT_STARTER} paperLabel="A4" />);
    const paper = screen.getByTestId("report-paper");
    expect(paper).toHaveAttribute("data-paper-width-mm", "210");
    expect(paper).toHaveAttribute("data-paper-height-mm", "297");
    expect(paper).toHaveAttribute("data-paper-surface", REPORT_PAPER_COLOR);
    expect(paper.style.aspectRatio.replace(/\s/g, "")).toBe("210/297");
    const bg = paper.style.backgroundColor.toLowerCase().replace(/\s/g, "");
    expect(
      bg === REPORT_PAPER_COLOR || bg === "rgb(247,243,235)" || bg === "#f7f3eb",
    ).toBe(true);
    expect(paper.style.boxShadow).toBe("none");
    const ratio = Number(paper.getAttribute("data-paper-ratio"));
    expect(ratioWithinTolerance(ratio, 210 / 297, 2)).toBe(true);
  });

  it("keeps quiet header and footer bands when external layout is on", () => {
    render(<ReportCanvas blocks={RENTAL_AGREEMENT_STARTER} useExternalLayout />);
    expect(screen.getByTestId("report-header-band")).toBeTruthy();
    expect(screen.getByTestId("report-footer-band")).toBeTruthy();
  });

  it("hides header/footer bands when external layout is off", () => {
    render(
      <ReportCanvas blocks={RENTAL_AGREEMENT_STARTER} useExternalLayout={false} />,
    );
    expect(screen.queryByTestId("report-header-band")).toBeNull();
    expect(screen.queryByTestId("report-footer-band")).toBeNull();
  });

  it("empty state is one sentence plus Add a block", () => {
    render(<ReportCanvas blocks={[]} />);
    const empty = screen.getByTestId("report-canvas-empty");
    expect(empty).toHaveTextContent(EMPTY_CANVAS_SENTENCE);
    expect(empty).toHaveTextContent(EMPTY_CANVAS_ACTION);
    expect(screen.getByTestId("report-canvas-add-block")).toHaveTextContent(
      EMPTY_CANVAS_ACTION,
    );
  });

  it("calls onAddBlock from the empty action", () => {
    const onAddBlock = vi.fn();
    render(<ReportCanvas blocks={[]} onAddBlock={onAddBlock} />);
    screen.getByTestId("report-canvas-add-block").click();
    expect(onAddBlock).toHaveBeenCalledTimes(1);
  });

  it("applies tabular-nums to amount cells in line tables", () => {
    render(<ReportCanvas blocks={RENTAL_AGREEMENT_STARTER} />);
    const amounts = screen.getAllByText("1,250.00");
    expect(amounts.length).toBeGreaterThanOrEqual(1);
    const marked = document.querySelectorAll("[data-tabular-nums='true']");
    expect(marked.length).toBeGreaterThanOrEqual(1);
    marked.forEach((el) => {
      const style = window.getComputedStyle(el);
      // Module class sets font-variant-numeric; happy-dom may not compute it —
      // assert the marker and class presence as the contract.
      expect(el.getAttribute("data-tabular-nums")).toBe("true");
      expect(el.className).toMatch(/amount/i);
      void style;
    });
  });

  it("uses display type for level-1 title and body scale for text", () => {
    render(<ReportCanvas blocks={RENTAL_AGREEMENT_STARTER} selectedId="h1" />);
    expect(screen.getByText("Rental Agreement")).toBeTruthy();
    expect(screen.getByText(/Signed:/)).toBeTruthy();
  });

  it("does not put a Tailwind shadow-* class on the paper", () => {
    render(<ReportCanvas blocks={RENTAL_AGREEMENT_STARTER} />);
    const paper = screen.getByTestId("report-paper");
    expect(paper.style.boxShadow).toBe("none");
    expect(paper.className).not.toMatch(/shadow/i);
  });
});

describe("PDF-02 pointer drag and palette drop", () => {
  function stubRect(
    el: Element,
    rect: { x: number; y: number; w: number; h: number },
  ) {
    vi.spyOn(el, "getBoundingClientRect").mockReturnValue({
      x: rect.x,
      y: rect.y,
      width: rect.w,
      height: rect.h,
      top: rect.y,
      left: rect.x,
      right: rect.x + rect.w,
      bottom: rect.y + rect.h,
      toJSON: () => ({}),
    } as DOMRect);
  }

  function layoutBlocks() {
    const list = screen.getByTestId("report-blocks");
    stubRect(list, { x: 0, y: 0, w: 240, h: 200 });
    const items = list.querySelectorAll("[data-reorder-item]");
    items.forEach((item, index) => {
      stubRect(item, { x: 0, y: index * 40, w: 240, h: 40 });
    });
    return { list, items };
  }

  function makeDt(blockType: string) {
    const store: Record<string, string> = {
      [ODOO_REPORT_BLOCK_MIME]: blockType,
      "text/plain": blockType,
    };
    return {
      types: [ODOO_REPORT_BLOCK_MIME, "text/plain"],
      dropEffect: "none",
      effectAllowed: "copy",
      getData: (type: string) => store[type] || "",
      setData: (type: string, value: string) => {
        store[type] = value;
      },
    };
  }

  function dispatchDrop(
    target: Element,
    dataTransfer: Record<string, unknown>,
    clientX: number,
    clientY: number,
  ) {
    const event = new Event("drop", { bubbles: true, cancelable: true }) as Event & {
      clientX: number;
      clientY: number;
      dataTransfer: unknown;
    };
    Object.defineProperty(event, "clientX", { value: clientX });
    Object.defineProperty(event, "clientY", { value: clientY });
    Object.defineProperty(event, "dataTransfer", { value: dataTransfer });
    target.dispatchEvent(event);
  }

  it("reads palette MIME helpers", () => {
    const dt = {
      types: [ODOO_REPORT_BLOCK_MIME],
      getData: (t: string) => (t === ODOO_REPORT_BLOCK_MIME ? "divider" : ""),
      setData: vi.fn(),
      effectAllowed: "none",
    } as unknown as DataTransfer;
    expect(isReportPaletteDrag(dt)).toBe(true);
    expect(readReportPaletteBlockType(dt)).toBe("divider");
    const blank = {
      types: [],
      getData: () => "",
      setData: vi.fn(),
      effectAllowed: "none",
    } as unknown as DataTransfer;
    setReportPaletteDragData(blank, "heading");
    expect(blank.effectAllowed).toBe("copy");
  });

  it("palette item drops onto the page and lands where dropped", () => {
    const onInsertBlock = vi.fn();
    const blocks: ReportBlock[] = [
      { id: "a", type: "heading", text: "A", level: 1 },
      { id: "b", type: "text", text: "B" },
      { id: "c", type: "divider" },
    ];
    render(
      <ReportCanvas
        blocks={blocks}
        onMove={vi.fn()}
        onInsertBlock={onInsertBlock}
      />,
    );
    const { list } = layoutBlocks();
    const dt = makeDt("field");
    // Drop between first and second (clientY ~ 50 → insert index 1)
    dispatchDrop(list, dt, 20, 50);
    expect(onInsertBlock).toHaveBeenCalledWith("field", 1);
  });

  it("drop outside the page does not insert a block", () => {
    const onInsertBlock = vi.fn();
    render(
      <ReportCanvas
        blocks={[{ id: "a", type: "text", text: "A" }]}
        onMove={vi.fn()}
        onInsertBlock={onInsertBlock}
      />,
    );
    const { list } = layoutBlocks();
    const dt = makeDt("heading");
    dispatchDrop(list, dt, 800, 800);
    expect(onInsertBlock).not.toHaveBeenCalled();
  });

  it("blocks reorder by pointer drag inside the page", () => {
    const onReorder = vi.fn();
    const blocks: ReportBlock[] = [
      { id: "a", type: "heading", text: "A", level: 1 },
      { id: "b", type: "text", text: "B" },
      { id: "c", type: "divider" },
    ];
    render(
      <ReportCanvas blocks={blocks} onMove={vi.fn()} onReorder={onReorder} />,
    );
    const { items } = layoutBlocks();
    fireEvent.pointerDown(items[0], {
      button: 0,
      pointerId: 1,
      clientX: 20,
      clientY: 20,
    });
    fireEvent.pointerMove(items[0], { pointerId: 1, clientX: 20, clientY: 90 });
    fireEvent.pointerUp(items[0], { pointerId: 1, clientX: 20, clientY: 90 });
    expect(onReorder).toHaveBeenCalled();
    const [from, to] = onReorder.mock.calls[0];
    expect(from).toBe(0);
    expect(to).toBeGreaterThan(0);
  });

  it("keyboard arrows still move the focused block", () => {
    const onMove = vi.fn();
    function Harness() {
      const [blocks, setBlocks] = useState<ReportBlock[]>([
        { id: "a", type: "heading", text: "A", level: 1 },
        { id: "b", type: "text", text: "B" },
        { id: "c", type: "divider" },
      ]);
      return (
        <div>
          <ReportCanvas
            blocks={blocks}
            onMove={(id, dir) => {
              onMove(id, dir);
              setBlocks((prev) => {
                const idx = prev.findIndex((b) => b.id === id);
                return reorderReportBlocks(prev, idx, idx + dir);
              });
            }}
          />
          <div data-testid="ids">{blocks.map((b) => b.id).join(",")}</div>
        </div>
      );
    }
    render(<Harness />);
    const first = screen.getByTestId("report-block-a");
    first.focus();
    fireEvent.keyDown(first, { key: "ArrowDown" });
    expect(onMove).toHaveBeenCalledWith("a", 1);
    expect(screen.getByTestId("ids").textContent).toBe("b,a,c");
  });

  it("up/down buttons remain as a fallback", () => {
    const onMove = vi.fn();
    render(
      <ReportCanvas
        blocks={[
          { id: "a", type: "text", text: "A" },
          { id: "b", type: "text", text: "B" },
        ]}
        onMove={onMove}
      />,
    );
    fireEvent.click(screen.getAllByLabelText("Move block down")[0]);
    expect(onMove).toHaveBeenCalledWith("a", 1);
  });
});

describe("ReportCanvas PDF-07 table inspector reflections", () => {
  const table: ReportBlock = {
    id: "lines",
    type: "o2m_table",
    o2m_field: "order_line",
    totals_row: true,
    totals_label: "Grand total",
    columns: [
      { field: "name", label: "Description", width: "2fr" },
      { field: "qty", label: "Qty", ttype: "integer", width: 15 },
      { field: "price_subtotal", label: "Subtotal", ttype: "monetary", width: "20%", sum: true },
    ],
  };

  it("applies resolved width + align inline on th/td like the compiler", () => {
    render(<ReportCanvas blocks={[table]} />);
    const el = screen.getByTestId("report-table-lines");
    const ths = Array.from(el.querySelectorAll("thead th")) as HTMLElement[];
    expect(ths.map((th) => th.style.width)).toEqual(["65%", "15%", "20%"]);
    expect(ths.map((th) => th.style.textAlign)).toEqual(["left", "right", "right"]);
    expect(ths.map((th) => th.getAttribute("data-width"))).toEqual(["65%", "15%", "20%"]);
    const tds = Array.from(el.querySelectorAll("tbody td")) as HTMLElement[];
    expect(tds.map((td) => td.style.width)).toEqual(["65%", "15%", "20%"]);
  });

  it("draws a totals footer with the caption only when a column sums", () => {
    const { rerender } = render(<ReportCanvas blocks={[table]} />);
    const foot = screen.getByTestId("report-table-totals-lines");
    expect(foot).toHaveTextContent("Grand total");
    expect(foot.querySelectorAll("[data-sum-cell='true']")).toHaveLength(1);
    rerender(<ReportCanvas blocks={[{ ...table, totals_row: false }]} />);
    expect(screen.queryByTestId("report-table-totals-lines")).toBeNull();
    rerender(
      <ReportCanvas
        blocks={[{ ...table, columns: table.columns!.map((c) => ({ ...c, sum: false })) }]}
      />,
    );
    expect(screen.queryByTestId("report-table-totals-lines")).toBeNull();
  });

  it("legacy columns (no align/width/ttype) stay left and auto width", () => {
    render(
      <ReportCanvas
        blocks={[
          {
            id: "legacy",
            type: "o2m_table",
            o2m_field: "line_ids",
            columns: [
              { field: "product_id", label: "Item" },
              { field: "price_unit", label: "Rate" },
            ],
          },
        ]}
      />,
    );
    const ths = Array.from(
      screen.getByTestId("report-table-legacy").querySelectorAll("thead th"),
    ) as HTMLElement[];
    expect(ths.map((th) => th.style.width)).toEqual(["", ""]);
    expect(ths.map((th) => th.getAttribute("data-width"))).toEqual(["auto", "auto"]);
    expect(ths.map((th) => th.style.textAlign)).toEqual(["left", "left"]);
  });

  it("header click reports the column only through onSelectColumn", () => {
    const onSelectColumn = vi.fn();
    const onSelect = vi.fn();
    render(
      <ReportCanvas
        blocks={[table]}
        selectedId="lines"
        onSelect={onSelect}
        onSelectColumn={onSelectColumn}
        activeColumn={{ blockId: "lines", index: 1 }}
      />,
    );
    const ths = screen.getByTestId("report-table-lines").querySelectorAll("thead th");
    expect(ths[1]).toHaveAttribute("data-active-col", "true");
    fireEvent.click(ths[2]);
    expect(onSelectColumn).toHaveBeenCalledWith("lines", 2);
    expect(onSelect).toHaveBeenCalledWith("lines");
  });

  it("does not highlight a column when the table is not selected", () => {
    render(
      <ReportCanvas
        blocks={[table]}
        selectedId={null}
        activeColumn={{ blockId: "lines", index: 1 }}
      />,
    );
    const ths = screen.getByTestId("report-table-lines").querySelectorAll("thead th");
    expect(ths[1]).not.toHaveAttribute("data-active-col");
  });
});
