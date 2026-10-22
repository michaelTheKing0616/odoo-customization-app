/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReportDesigner } from "./ReportDesigner";
import { ODOO_REPORT_BLOCK_MIME } from "./ReportCanvas";
import type { Connection } from "@/lib/api";

const compileReportDesign = vi.fn().mockResolvedValue({
  arch: `<t t-name="x" t-inherit="account.report_invoice" t-inherit-mode="extension">
  <xpath expr="//div[@class='page']" position="after"><p>Thanks</p></xpath>
</t>`,
});
const getReportDesignPalette = vi.fn().mockResolvedValue([
  { type: "heading", label: "Heading", hint: "Section title" },
  { type: "field", label: "Field", hint: "Model field" },
  { type: "divider", label: "Divider", hint: "" },
]);
const listReports = vi.fn();

const listFields = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    compileReportDesign: (...args: unknown[]) => compileReportDesign(...args),
    getReportDesignPalette: (...args: unknown[]) => getReportDesignPalette(...args),
    previewReportDesign: vi.fn(),
    reportDesignToModuleSpec: vi.fn(),
    listReports: (...args: unknown[]) => listReports(...args),
    listFields: (...args: unknown[]) => listFields(...args),
  },
}));

const gaConnection = {
  id: "c1",
  name: "GA",
  url: "http://localhost",
  db_name: "odoo",
  username: "admin",
  server_version: "19.0",
  write_mode: "standard",
  created_at: null,
  updated_at: null,
  capabilities: {
    major: 19,
    edition: "community",
    server_version: "19.0",
    supported: ["list_as_list_type"],
    unsupported: [],
    ga: true,
    message: "ok",
  },
} as Connection;

const odoo16Connection = {
  ...gaConnection,
  server_version: "16.0",
  capabilities: {
    major: 16,
    edition: "community",
    server_version: "16.0",
    supported: [],
    unsupported: [],
    ga: false,
    message: "experimental",
  },
} as Connection;

const fixtureReports = [
  {
    id: 10,
    name: "Invoices",
    report_name: "account.report_invoice",
    model: "account.move",
    arch: null,
  },
  {
    id: 11,
    name: "Quotation",
    report_name: "sale.report_saleorder",
    model: "sale.order",
    arch: null,
  },
];

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.localStorage.clear();
});

const schemaFields = [
  {
    id: 1,
    name: "display_name",
    field_description: "Display Name",
    ttype: "char",
    required: false,
    readonly: true,
    relation: null,
    state: "base",
  },
  {
    id: 2,
    name: "partner_id",
    field_description: "Customer",
    ttype: "many2one",
    required: false,
    readonly: false,
    relation: "res.partner",
    state: "base",
  },
  {
    id: 3,
    name: "order_line",
    field_description: "Order Lines",
    ttype: "one2many",
    required: false,
    readonly: false,
    relation: "sale.order.line",
    state: "base",
  },
];

const lineSchemaFields = [
  {
    id: 10,
    name: "product_id",
    field_description: "Product",
    ttype: "many2one",
    required: false,
    readonly: false,
    relation: "product.product",
    state: "base",
  },
  {
    id: 11,
    name: "name",
    field_description: "Description",
    ttype: "char",
    required: false,
    readonly: false,
    relation: null,
    state: "base",
  },
];

beforeEach(() => {
  compileReportDesign.mockResolvedValue({
    arch: `<t t-name="x" t-inherit="account.report_invoice" t-inherit-mode="extension">
  <xpath expr="//div[@class='page']" position="after"><p>Thanks</p></xpath>
</t>`,
  });
  getReportDesignPalette.mockResolvedValue([
    { type: "heading", label: "Heading", hint: "Section title" },
    { type: "field", label: "Field", hint: "Model field" },
    { type: "o2m_table", label: "Lines table", hint: "" },
    { type: "divider", label: "Divider", hint: "" },
  ]);
  listFields.mockImplementation(async (_id: string, model: string) => {
    if (model === "sale.order.line") return lineSchemaFields;
    return schemaFields;
  });
});

describe("ReportDesigner PDF-02 palette", () => {
  it("palette items are draggable with report block MIME", async () => {
    render(
      <ReportDesigner
        connectionId="c1"
        model="sale.order"
        reportKey="sale.report_test"
        reportName="Test"
        reportId={null}
        onArchChange={vi.fn()}
      />,
    );
    const heading = await screen.findByTestId("report-palette-heading");
    expect(heading).toHaveAttribute("draggable", "true");

    const store: Record<string, string> = {};
    const dataTransfer = {
      types: [] as string[],
      effectAllowed: "none",
      setData(type: string, value: string) {
        store[type] = value;
        if (!this.types.includes(type)) this.types.push(type);
      },
      getData(type: string) {
        return store[type] || "";
      },
    };
    fireEvent.dragStart(heading, { dataTransfer });
    expect(store[ODOO_REPORT_BLOCK_MIME]).toBe("heading");
    expect(dataTransfer.effectAllowed).toBe("copy");
  });

  it("dropping a palette type onto the canvas inserts at the drop index", async () => {
    render(
      <ReportDesigner
        connectionId="c1"
        model="sale.order"
        reportKey="sale.report_test"
        reportName="Test"
        reportId={null}
        onArchChange={vi.fn()}
      />,
    );
    await screen.findByTestId("report-palette-field");
    const list = screen.getByTestId("report-blocks");
    const itemsBefore = list.querySelectorAll("[data-reorder-item]").length;

    vi.spyOn(list, "getBoundingClientRect").mockReturnValue({
      x: 0,
      y: 0,
      width: 240,
      height: 400,
      top: 0,
      left: 0,
      right: 240,
      bottom: 400,
      toJSON: () => ({}),
    } as DOMRect);
    list.querySelectorAll("[data-reorder-item]").forEach((item, index) => {
      vi.spyOn(item, "getBoundingClientRect").mockReturnValue({
        x: 0,
        y: index * 40,
        width: 240,
        height: 40,
        top: index * 40,
        left: 0,
        right: 240,
        bottom: index * 40 + 40,
        toJSON: () => ({}),
      } as DOMRect);
    });

    const store: Record<string, string> = {
      [ODOO_REPORT_BLOCK_MIME]: "divider",
      "text/plain": "divider",
    };
    const dataTransfer = {
      types: [ODOO_REPORT_BLOCK_MIME, "text/plain"],
      dropEffect: "copy",
      effectAllowed: "copy",
      getData: (t: string) => store[t] || "",
      setData: vi.fn(),
    };

    const dropEvent = new Event("drop", { bubbles: true, cancelable: true }) as Event & {
      clientX: number;
      clientY: number;
      dataTransfer: unknown;
    };
    Object.defineProperty(dropEvent, "clientX", { value: 20 });
    Object.defineProperty(dropEvent, "clientY", { value: 50 });
    Object.defineProperty(dropEvent, "dataTransfer", { value: dataTransfer });
    list.dispatchEvent(dropEvent);

    await waitFor(() => {
      const itemsAfter = list.querySelectorAll("[data-reorder-item]").length;
      expect(itemsAfter).toBe(itemsBefore + 1);
    });
  });
});

describe("ReportDesigner PDF-03 inherit slots", () => {
  it("slot picker replaces raw xpath and maps to one anchor", async () => {
    render(
      <ReportDesigner
        connectionId="c1"
        model="account.move"
        reportKey="custom.report_ext"
        reportName="Invoice extra"
        reportId={1}
        connection={gaConnection}
        availableReports={fixtureReports}
        onArchChange={vi.fn()}
      />,
    );
    const mode = await screen.findByTestId("report-mode-select");
    fireEvent.change(mode, { target: { value: "inherit" } });
    expect(screen.getByTestId("report-inherit-slot-picker")).toBeTruthy();
    expect(screen.queryByLabelText(/XPath anchor/i)).toBeNull();
    fireEvent.click(screen.getByTestId("report-inherit-slot-header"));
    expect(screen.getByTestId("report-inherit-anchor-preview").textContent).toMatch(
      /\/\/div\[@class='header'\].*inside/,
    );
  });

  it("save emits report.inherit with exactly one anchor", async () => {
    const onEmitSave = vi.fn().mockResolvedValue(undefined);
    const onError = vi.fn();
    render(
      <ReportDesigner
        connectionId="c1"
        model="account.move"
        reportKey="custom.report_ext"
        reportName="Invoice extra"
        reportId={1}
        connection={gaConnection}
        availableReports={fixtureReports}
        onArchChange={vi.fn()}
        onEmitSave={onEmitSave}
        onError={onError}
      />,
    );
    fireEvent.change(await screen.findByTestId("report-mode-select"), {
      target: { value: "inherit" },
    });
    fireEvent.change(screen.getByTestId("report-inherit-base-select"), {
      target: { value: "account.report_invoice" },
    });
    fireEvent.click(screen.getByTestId("report-inherit-slot-footer"));
    fireEvent.click(screen.getByTestId("report-save-printout"));
    await waitFor(() => expect(onEmitSave).toHaveBeenCalled());
    const payload = onEmitSave.mock.calls[0][0];
    expect(payload.mode).toBe("inherit");
    expect(payload.op?.type).toBe("report.inherit");
    expect(payload.op?.params.expect_matches).toBe(1);
    expect(payload.op?.params.xpath).toBe("//div[@class='footer']");
    expect(payload.op?.params.position).toBe("inside");
    expect(payload.spec.inherit?.slot).toBe("footer");
    expect(onError).not.toHaveBeenCalled();
  });

  it("refuses a base report key that is not on the connection", async () => {
    const onEmitSave = vi.fn();
    const onError = vi.fn();
    render(
      <ReportDesigner
        connectionId="c1"
        model="account.move"
        reportKey="custom.report_ext"
        reportName="Invoice extra"
        reportId={1}
        connection={gaConnection}
        availableReports={fixtureReports}
        onArchChange={vi.fn()}
        onEmitSave={onEmitSave}
        onError={onError}
      />,
    );
    fireEvent.change(await screen.findByTestId("report-mode-select"), {
      target: { value: "inherit" },
    });
    // Force a missing key via the select's empty state then save
    fireEvent.change(screen.getByTestId("report-inherit-base-select"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByTestId("report-save-printout"));
    await waitFor(() => expect(onError).toHaveBeenCalled());
    expect(onEmitSave).not.toHaveBeenCalled();
    expect(String(onError.mock.calls[0][0])).toMatch(/pick an existing report/i);
  });

  it("Odoo 16 shows experimental caveat and hides apply to production", async () => {
    render(
      <ReportDesigner
        connectionId="c1"
        model="sale.order"
        reportKey="sale.report_test"
        reportName="Test"
        reportId={1}
        connection={odoo16Connection}
        availableReports={fixtureReports}
        onArchChange={vi.fn()}
      />,
    );
    expect(await screen.findByTestId("report-odoo16-experimental-caveat")).toBeTruthy();
    expect(screen.queryByTestId("report-apply-to-production")).toBeNull();
  });

  it("GA connection offers apply to production", async () => {
    render(
      <ReportDesigner
        connectionId="c1"
        model="sale.order"
        reportKey="sale.report_test"
        reportName="Test"
        reportId={1}
        connection={gaConnection}
        availableReports={fixtureReports}
        onArchChange={vi.fn()}
      />,
    );
    expect(await screen.findByTestId("report-apply-to-production")).toBeTruthy();
    expect(screen.queryByTestId("report-odoo16-experimental-caveat")).toBeNull();
  });

  it("round-trip reload restores slot and blocks from localStorage", async () => {
    const storageKey = "odoo-report-design:c1:custom.report_ext";
    window.localStorage.setItem(
      storageKey,
      JSON.stringify({
        mode: "inherit",
        inheritSlot: "header",
        inheritBase: "account.report_invoice",
        blocks: [
          { id: "b_round", type: "text", text: "Round-trip block" },
        ],
        useExternalLayout: true,
        tLang: "",
      }),
    );
    render(
      <ReportDesigner
        connectionId="c1"
        model="account.move"
        reportKey="custom.report_ext"
        reportName="Invoice extra"
        reportId={1}
        connection={gaConnection}
        availableReports={fixtureReports}
        onArchChange={vi.fn()}
      />,
    );
    await waitFor(() => {
      expect(screen.getByTestId("report-mode-select")).toHaveValue("inherit");
    });
    expect(screen.getByTestId("report-inherit-base-select")).toHaveValue(
      "account.report_invoice",
    );
    expect(screen.getByTestId("report-inherit-slot-header")).toBeChecked();
    expect(screen.getByText("Round-trip block")).toBeTruthy();
  });
});

describe("ReportDesigner PDF-04 grounded fields", () => {
  it("field picker only lists schema fields", async () => {
    render(
      <ReportDesigner
        connectionId="c1"
        model="sale.order"
        reportKey="sale.report_test"
        reportName="Test"
        reportId={1}
        onArchChange={vi.fn()}
      />,
    );
    await waitFor(() => expect(listFields).toHaveBeenCalled());
    fireEvent.click(await screen.findByTestId("report-block-f1"));
    await waitFor(() => {
      expect(screen.getByTestId("report-field-picker")).toBeTruthy();
    });
    const picker = screen.getByTestId("report-field-picker") as HTMLSelectElement;
    const values = Array.from(picker.options).map((o) => o.value).filter(Boolean);
    expect(values).toContain("display_name");
    expect(values).toContain("partner_id");
    expect(values).toContain("order_line");
    expect(values).not.toContain("ghost_field");
  });

  it("unknown field blocked on save", async () => {
    const onEmitSave = vi.fn();
    const onError = vi.fn();
    // Seed localStorage with an unknown field token
    window.localStorage.setItem(
      "odoo-report-design:c1:sale.report_test",
      JSON.stringify({
        mode: "primary",
        blocks: [{ id: "bad", type: "field", field: "ghost_field" }],
        useExternalLayout: true,
        tLang: "",
      }),
    );
    render(
      <ReportDesigner
        connectionId="c1"
        model="sale.order"
        reportKey="sale.report_test"
        reportName="Test"
        reportId={1}
        onArchChange={vi.fn()}
        onEmitSave={onEmitSave}
        onError={onError}
      />,
    );
    await waitFor(() => expect(listFields).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId("report-block-bad")).toBeTruthy());
    fireEvent.click(screen.getByTestId("report-save-printout"));
    await waitFor(() => expect(onError).toHaveBeenCalled());
    expect(onEmitSave).not.toHaveBeenCalled();
    expect(String(onError.mock.calls[0][0])).toMatch(/unknown field/);
  });

  it("empty spec blocked on save", async () => {
    const onEmitSave = vi.fn();
    const onError = vi.fn();
    window.localStorage.setItem(
      "odoo-report-design:c1:sale.report_empty",
      JSON.stringify({
        mode: "primary",
        blocks: [],
        useExternalLayout: true,
        tLang: "",
      }),
    );
    render(
      <ReportDesigner
        connectionId="c1"
        model="sale.order"
        reportKey="sale.report_empty"
        reportName="Empty"
        reportId={1}
        onArchChange={vi.fn()}
        onEmitSave={onEmitSave}
        onError={onError}
      />,
    );
    await waitFor(() => expect(listFields).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId("report-save-printout"));
    await waitFor(() => expect(onError).toHaveBeenCalled());
    expect(onEmitSave).not.toHaveBeenCalled();
    expect(String(onError.mock.calls[0][0])).toMatch(/empty design/);
  });

  it("o2m columns only offer related model fields", async () => {
    window.localStorage.setItem(
      "odoo-report-design:c1:sale.report_lines",
      JSON.stringify({
        mode: "primary",
        blocks: [
          {
            id: "lines",
            type: "o2m_table",
            o2m_field: "order_line",
            columns: [{ field: "product_id", label: "Product" }],
          },
        ],
        useExternalLayout: true,
        tLang: "",
      }),
    );
    render(
      <ReportDesigner
        connectionId="c1"
        model="sale.order"
        reportKey="sale.report_lines"
        reportName="Lines"
        reportId={1}
        onArchChange={vi.fn()}
      />,
    );
    await waitFor(() => expect(listFields).toHaveBeenCalledWith("c1", "sale.order"));
    fireEvent.click(await screen.findByTestId("report-block-lines"));
    await waitFor(() => {
      expect(screen.getByTestId("report-o2m-field-picker")).toBeTruthy();
    });
    const o2mPicker = screen.getByTestId("report-o2m-field-picker") as HTMLSelectElement;
    const o2mValues = Array.from(o2mPicker.options).map((o) => o.value).filter(Boolean);
    expect(o2mValues).toEqual(["order_line"]);
    await waitFor(() => expect(listFields).toHaveBeenCalledWith("c1", "sale.order.line"));
    await waitFor(() => {
      expect(screen.getByTestId("report-o2m-column-field-0")).toBeTruthy();
    });
    const colPicker = screen.getByTestId("report-o2m-column-field-0") as HTMLSelectElement;
    const colValues = Array.from(colPicker.options).map((o) => o.value).filter(Boolean);
    expect(colValues).toContain("product_id");
    expect(colValues).toContain("name");
    expect(colValues).not.toContain("partner_id");
  });

  it("external layout default is on for new primary designs", async () => {
    render(
      <ReportDesigner
        connectionId="c1"
        model="sale.order"
        reportKey="sale.report_layout"
        reportName="Layout"
        reportId={null}
        onArchChange={vi.fn()}
      />,
    );
    const checkbox = await screen.findByLabelText(/web.external_layout/i);
    expect((checkbox as HTMLInputElement).checked).toBe(true);
  });
});

describe("ReportDesigner PDF-07 table inspector", () => {
  const numericLineFields = [
    ...lineSchemaFields,
    {
      id: 12,
      name: "price_subtotal",
      field_description: "Subtotal",
      ttype: "monetary",
      required: false,
      readonly: true,
      relation: null,
      state: "base",
    },
  ];

  function seedTable(key: string, block: Record<string, unknown>) {
    window.localStorage.setItem(
      `odoo-report-design:c1:${key}`,
      JSON.stringify({
        mode: "primary",
        blocks: [{ id: "lines", type: "o2m_table", o2m_field: "order_line", ...block }],
        useExternalLayout: true,
        tLang: "",
      }),
    );
  }

  beforeEach(() => {
    listFields.mockImplementation(async (_id: string, model: string) => {
      if (model === "sale.order.line") return numericLineFields;
      return schemaFields;
    });
  });

  it("selecting a lines table opens the inspector; edits reflect on paper and save into the spec", async () => {
    seedTable("sale.report_ti", {
      columns: [
        { field: "name", label: "Description" },
        { field: "price_subtotal", label: "Subtotal" },
      ],
    });
    const onEmitSave = vi.fn().mockResolvedValue(undefined);
    const onError = vi.fn();
    render(
      <ReportDesigner
        connectionId="c1"
        model="sale.order"
        reportKey="sale.report_ti"
        reportName="Lines"
        reportId={1}
        onArchChange={vi.fn()}
        onEmitSave={onEmitSave}
        onError={onError}
      />,
    );
    fireEvent.click(await screen.findByTestId("report-block-lines"));
    expect(await screen.findByTestId("report-table-inspector")).toBeTruthy();
    await waitFor(() => expect(listFields).toHaveBeenCalledWith("c1", "sale.order.line"));

    // Schema types reach the paper: monetary column defaults right.
    const table = screen.getByTestId("report-table-lines");
    await waitFor(() => {
      const th = table.querySelectorAll("thead th")[1] as HTMLElement;
      expect(th.style.textAlign).toBe("right");
    });

    // Column 0: center + 40% width
    fireEvent.click(screen.getByTestId("report-table-align-center"));
    fireEvent.click(screen.getByTestId("report-table-width-mode-pct"));
    fireEvent.change(screen.getByTestId("report-table-width-input"), { target: { value: "40" } });
    const th0 = table.querySelectorAll("thead th")[0] as HTMLElement;
    expect(th0.style.textAlign).toBe("center");
    expect(th0.style.width).toBe("40%");

    // Totals on → numeric column pre-marked; footer on paper
    fireEvent.click(screen.getByTestId("report-table-totals-toggle"));
    expect(await screen.findByTestId("report-table-totals-lines")).toBeTruthy();

    fireEvent.click(screen.getByTestId("report-save-printout"));
    await waitFor(() => expect(onEmitSave).toHaveBeenCalled());
    expect(onError).not.toHaveBeenCalled();
    const saved = onEmitSave.mock.calls[0][0].spec.blocks[0];
    expect(saved.totals_row).toBe(true);
    expect(saved.columns[0]).toMatchObject({ field: "name", align: "center", width: 40 });
    expect(saved.columns[1]).toMatchObject({ field: "price_subtotal", sum: true });

    // persisted for reload (spec round-trip)
    const persisted = JSON.parse(
      window.localStorage.getItem("odoo-report-design:c1:sale.report_ti") || "{}",
    );
    expect(persisted.blocks[0].columns[0]).toMatchObject({ align: "center", width: 40 });
    expect(persisted.blocks[0].totals_row).toBe(true);

    // compile payload carries the inspector settings to the API
    const lastCompile = compileReportDesign.mock.calls.at(-1)?.[1] as {
      spec: { blocks: Array<{ columns?: Array<Record<string, unknown>> }> };
    };
    expect(lastCompile.spec.blocks[0].columns?.[0]).toMatchObject({ align: "center", width: 40 });
  });

  it("round-trip reload restores align / width / totals into the inspector", async () => {
    seedTable("sale.report_rt", {
      totals_row: true,
      totals_label: "Grand total",
      columns: [
        { field: "name", label: "Description", align: "center", width: "2fr" },
        { field: "price_subtotal", label: "Subtotal", width: 25, sum: true, align: "right" },
      ],
    });
    render(
      <ReportDesigner
        connectionId="c1"
        model="sale.order"
        reportKey="sale.report_rt"
        reportName="Lines"
        reportId={1}
        onArchChange={vi.fn()}
      />,
    );
    fireEvent.click(await screen.findByTestId("report-block-lines"));
    await screen.findByTestId("report-table-inspector");
    expect(screen.getByTestId("report-table-align-center")).toHaveAttribute("aria-checked", "true");
    expect(screen.getByTestId("report-table-width-mode-fr")).toHaveAttribute("aria-checked", "true");
    expect(screen.getByTestId("report-table-width-resolved")).toHaveTextContent("75%");
    expect(screen.getByTestId("report-table-totals-toggle")).toHaveAttribute("aria-checked", "true");
    expect(screen.getByTestId("report-table-totals-label")).toHaveValue("Grand total");
    expect(screen.getByTestId("report-table-totals-lines")).toHaveTextContent("Grand total");
  });

  it("persisted junk widths / aligns are sanitized on load", async () => {
    seedTable("sale.report_junk", {
      columns: [{ field: "name", label: "D", width: "10px; color:red", align: "diagonal" }],
    });
    const onEmitSave = vi.fn().mockResolvedValue(undefined);
    render(
      <ReportDesigner
        connectionId="c1"
        model="sale.order"
        reportKey="sale.report_junk"
        reportName="Lines"
        reportId={1}
        onArchChange={vi.fn()}
        onEmitSave={onEmitSave}
      />,
    );
    await waitFor(() => expect(screen.getByTestId("report-block-lines")).toBeTruthy());
    await waitFor(() => expect(listFields).toHaveBeenCalledWith("c1", "sale.order.line"));
    fireEvent.click(screen.getByTestId("report-save-printout"));
    await waitFor(() => expect(onEmitSave).toHaveBeenCalled());
    expect(onEmitSave.mock.calls[0][0].spec.blocks[0].columns[0]).toEqual({ field: "name", label: "D" });
  });

  it("totals on a non-numeric column are blocked on save", async () => {
    seedTable("sale.report_badsum", {
      totals_row: true,
      columns: [{ field: "name", label: "D", sum: true }],
    });
    const onEmitSave = vi.fn();
    const onError = vi.fn();
    render(
      <ReportDesigner
        connectionId="c1"
        model="sale.order"
        reportKey="sale.report_badsum"
        reportName="Lines"
        reportId={1}
        onArchChange={vi.fn()}
        onEmitSave={onEmitSave}
        onError={onError}
      />,
    );
    await waitFor(() => expect(listFields).toHaveBeenCalledWith("c1", "sale.order.line"));
    await waitFor(() => expect(screen.getByTestId("report-block-lines")).toBeTruthy());
    // wait until related schema is loaded into the designer
    fireEvent.click(screen.getByTestId("report-block-lines"));
    await waitFor(() =>
      expect(
        Array.from(
          (screen.getByTestId("report-o2m-column-field-0") as HTMLSelectElement).options,
        ).map((o) => o.value),
      ).toContain("price_subtotal"),
    );
    fireEvent.click(screen.getByTestId("report-save-printout"));
    await waitFor(() => expect(onError).toHaveBeenCalled());
    expect(onEmitSave).not.toHaveBeenCalled();
    expect(String(onError.mock.calls[0][0])).toMatch(/only sum numeric fields/);
  });

  it("unknown column still refused even with inspector settings", async () => {
    seedTable("sale.report_ghost", {
      columns: [{ field: "ghost", label: "G", align: "right", width: 30 }],
    });
    const onEmitSave = vi.fn();
    const onError = vi.fn();
    render(
      <ReportDesigner
        connectionId="c1"
        model="sale.order"
        reportKey="sale.report_ghost"
        reportName="Lines"
        reportId={1}
        onArchChange={vi.fn()}
        onEmitSave={onEmitSave}
        onError={onError}
      />,
    );
    await waitFor(() => expect(listFields).toHaveBeenCalledWith("c1", "sale.order.line"));
    fireEvent.click(await screen.findByTestId("report-block-lines"));
    await screen.findByTestId("report-table-column-orphan-0");
    fireEvent.click(screen.getByTestId("report-save-printout"));
    await waitFor(() => expect(onError).toHaveBeenCalled());
    expect(onEmitSave).not.toHaveBeenCalled();
    expect(String(onError.mock.calls[0][0])).toMatch(/unknown field on related model/);
  });

  it("QWeb in the totals caption is refused on save (PDF-05)", async () => {
    seedTable("sale.report_unsafe_total", {
      totals_row: true,
      totals_label: '<t t-esc="1"/>',
      columns: [{ field: "price_subtotal", label: "S", sum: true }],
    });
    const onEmitSave = vi.fn();
    const onError = vi.fn();
    render(
      <ReportDesigner
        connectionId="c1"
        model="sale.order"
        reportKey="sale.report_unsafe_total"
        reportName="Lines"
        reportId={1}
        onArchChange={vi.fn()}
        onEmitSave={onEmitSave}
        onError={onError}
      />,
    );
    await waitFor(() => expect(screen.getByTestId("report-block-lines")).toBeTruthy());
    fireEvent.click(screen.getByTestId("report-save-printout"));
    await waitFor(() => expect(onError).toHaveBeenCalled());
    expect(onEmitSave).not.toHaveBeenCalled();
    expect(String(onError.mock.calls[0][0])).toMatch(/totals_label/);
  });

  it("clicking a column header on the paper focuses it in the inspector", async () => {
    seedTable("sale.report_focus", {
      columns: [
        { field: "name", label: "Description" },
        { field: "price_subtotal", label: "Subtotal" },
      ],
    });
    render(
      <ReportDesigner
        connectionId="c1"
        model="sale.order"
        reportKey="sale.report_focus"
        reportName="Lines"
        reportId={1}
        onArchChange={vi.fn()}
      />,
    );
    await waitFor(() => expect(screen.getByTestId("report-block-lines")).toBeTruthy());
    const th = screen.getByTestId("report-table-lines").querySelectorAll("thead th")[1];
    fireEvent.click(th);
    expect(await screen.findByTestId("report-table-inspector")).toBeTruthy();
    expect(screen.getByTestId("report-o2m-column-field-1")).toHaveValue("price_subtotal");
    expect(screen.getByTestId("report-table-column-row-1")).toHaveAttribute("aria-pressed", "true");
  });
});
