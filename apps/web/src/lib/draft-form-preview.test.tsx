import { describe, expect, it } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import {
  busyLabelFromJobResult,
  draftFinisherComplete,
  formPreviewFromDraft,
  generationEngineFromDraft,
  isGoldOptionADraft,
  isOptionAAuthoredDraft,
  isRefuseCloneDraft,
  isStockReuseDraft,
  optionAAuthoringPassed,
  optionAAuthoringRetryable,
  optionAAuthoringNeedsAutoRepair,
  hostInstallOffersFromDraft,
  authoringFindingsWithoutHostInstall,
  normalizeFormPreview,
  optionASettingsFromDraft,
  previewViewsFromDraft,
  residualFormPreviewFromDraft,
  stockAppsFromDraft,
  surfaceGateBlocksInstall,
  surfaceGateFindingsFromDraft,
  documentGrammarFromDraft,
  wantsModuleDelivery,
} from "./draft-form-preview";
import { DraftOdooPreview } from "@/components/odoo-preview/DraftOdooPreview";
import { OdooViewRenderer } from "@/components/odoo-preview/OdooViewRenderer";
import type { PreviewFormView } from "./draft-form-preview";

const RICH_FORM: PreviewFormView = {
  type: "form",
  model: "x_store_order",
  title: "Store sales order",
  statusbar: {
    field: "x_status",
    stages: ["draft", "confirmed", "picking", "delivered"],
    activeStage: "draft",
  },
  headerButtons: [{ id: "confirm", string: "Confirm", variant: "primary" }],
  smartButtons: [{ id: "lines", string: "Order line", count: 2 }],
  groups: [
    {
      id: "identity",
      string: "Identity",
      columns: 2,
      fields: [
        { id: "x_name", name: "x_name", string: "Order", ttype: "char", required: true },
        {
          id: "x_partner_id",
          name: "x_partner_id",
          string: "Customer",
          ttype: "many2one",
        },
      ],
    },
    {
      id: "details",
      string: "Details",
      columns: 2,
      fields: [
        {
          id: "x_amount_total",
          name: "x_amount_total",
          string: "Total",
          ttype: "monetary",
        },
      ],
    },
  ],
  notebooks: [
    {
      id: "nb1",
      pages: [
        {
          id: "lines",
          string: "Lines",
          fields: [{ id: "x_line_ids", name: "x_line_ids", string: "Lines", ttype: "one2many" }],
        },
      ],
    },
  ],
  groupLayout: "two-column",
  chatter: "stub",
};

describe("normalizeFormPreview / legacy IR", () => {
  it("accepts legacy Stage-H payloads without type and with string statusbar", () => {
    const legacy = {
      title: "Rental Contract",
      model: "x_rent_contract",
      statusbar: "x_status",
      groups: [
        {
          id: "identity",
          string: "Identity",
          fields: [{ id: "x_name", name: "x_name", string: "Reference" }],
        },
      ],
    };
    const normalized = normalizeFormPreview(legacy);
    expect(normalized?.type).toBe("form");
    expect(normalized?.statusbar?.field).toBe("x_status");
    expect(normalized?.groups[0].columns).toBe(1);
    expect(formPreviewFromDraft({ _generation_engine: { form_preview: legacy } })?.model).toBe(
      "x_rent_contract",
    );
  });

  it("rejects non-form payloads", () => {
    expect(normalizeFormPreview({ type: "list", model: "x", columns: [] })).toBeNull();
    expect(normalizeFormPreview(null)).toBeNull();
  });
});

describe("draft-form-preview accessors", () => {
  it("reads residual FormCanvas preview from the generation engine IR", () => {
    const draft = {
      _generation_engine: {
        capability: "residual_app",
        form_preview: RICH_FORM,
        list_preview: {
          type: "list",
          model: "x_store_order",
          title: "Orders",
          columns: [{ id: "x_name", name: "x_name", string: "Order" }],
        },
        kanban_preview: {
          type: "kanban",
          model: "x_store_order",
          title: "Orders",
          groupBy: "x_status",
          cardFields: [{ id: "x_name", name: "x_name", string: "Order" }],
        },
      },
    };
    const preview = residualFormPreviewFromDraft(draft);
    expect(preview?.model).toBe("x_store_order");
    expect(preview?.groups[0].fields[0].name).toBe("x_name");
    const all = previewViewsFromDraft(draft);
    expect(all.list?.columns).toHaveLength(1);
    expect(all.kanban?.groupBy).toBe("x_status");
    expect(optionASettingsFromDraft(draft)).toBeNull();
  });

  it("reads Option A settings and module-delivery CTA", () => {
    const draft = {
      _delivery_preference: "module_zip",
      _generation_engine: {
        capability: "option_a_standalone",
        module_delivery: true,
        option_a_settings: {
          model: "pos.config",
          fields: [{ name: "x_receipt_header", string: "Receipt header" }],
        },
      },
    };
    expect(optionASettingsFromDraft(draft)?.model).toBe("pos.config");
    expect(wantsModuleDelivery(draft)).toBe(true);
    expect(isRefuseCloneDraft(draft)).toBe(false);
    expect(isGoldOptionADraft(draft)).toBe(false);
  });

  it("locks zip until authored Option A gate passes", () => {
    const blocked = {
      _generation_engine: { capability: "option_a_authored", module_delivery: true },
      _option_a_authoring: { status: "fail", findings: [{ code: "empty_module", message: "empty_module" }] },
    };
    expect(isOptionAAuthoredDraft(blocked)).toBe(true);
    expect(optionAAuthoringPassed(blocked)).toBe(false);
    const ready = {
      ...blocked,
      _option_a_authoring: { status: "pass", findings: [] },
    };
    expect(optionAAuthoringPassed(ready)).toBe(true);
    expect(optionAAuthoringRetryable(blocked)).toBe(true);
    expect(
      optionAAuthoringRetryable({
        _generation_engine: { capability: "option_a_authored" },
        _option_a_authoring: {
          status: "fail",
          retryable: true,
          findings: [{ code: "author_failed", message: "Gemini HTTP 503" }],
        },
      }),
    ).toBe(true);
    expect(optionAAuthoringRetryable(ready)).toBe(false);
    expect(
      optionAAuthoringNeedsAutoRepair({
        _generation_engine: { capability: "option_a_authored" },
        _option_a_authoring: {
          status: "fail",
          retryable: true,
          findings: [
            {
              code: "author_failed",
              message: "AI response was JSON but not an object (expected a ModuleSpec draft).",
            },
          ],
        },
      }),
    ).toBe(true);
    expect(optionAAuthoringNeedsAutoRepair(blocked)).toBe(false);
  });

  it("groups missing sale.order and sale.order.line into one Sales install offer", () => {
    const draft = {
      _generation_engine: { capability: "option_a_authored" },
      _option_a_authoring: {
        status: "fail",
        findings: [
          {
            code: "model_missing",
            message: "Inherit model sale.order is not on this connection. (models)",
          },
          {
            code: "model_missing",
            message: "Inherit model sale.order.line is not on this connection. (models)",
          },
          {
            code: "tax_xmlid_missing",
            message: "Tax xmlid l10n_ng.wht is not on this connection.",
          },
        ],
      },
    };
    const offers = hostInstallOffersFromDraft(draft);
    expect(offers).toHaveLength(1);
    expect(offers[0].module).toBe("sale");
    expect(offers[0].label).toBe("Sales");
    expect(offers[0].models).toEqual(["sale.order", "sale.order.line"]);
    const leftover = authoringFindingsWithoutHostInstall(draft);
    expect(leftover).toHaveLength(1);
    expect(leftover[0].code).toBe("tax_xmlid_missing");
  });

  it("flags gold Option A drafts that must not live-install", () => {
    const draft = {
      _generation_engine: {
        capability: "option_a_standalone",
        gold_artifact_id: "currency_rate_cbn",
        module_delivery: true,
      },
    };
    expect(isGoldOptionADraft(draft)).toBe(true);
    expect(wantsModuleDelivery(draft)).toBe(true);
  });

  it("flags refuse-clone drafts", () => {
    const draft = {
      _generation_engine: { capability: "refuse_clone", honesty: "no clone" },
    };
    expect(isRefuseCloneDraft(draft)).toBe(true);
    expect(generationEngineFromDraft(draft)?.honesty).toBe("no clone");
  });

  it("reads stock-reuse coverage labels from depends when IR stock_apps is missing", () => {
    const draft = {
      depends: ["point_of_sale", "sale", "account"],
      _generation_engine: { capability: "stock_reuse" },
    };
    expect(isStockReuseDraft(draft)).toBe(true);
    const apps = stockAppsFromDraft(draft);
    expect(apps.map((a) => a.label)).toEqual(["Point of Sale", "Sales", "Invoicing"]);
  });

  it("treats stock_reuse as finished even when live-apply ready is false", () => {
    const draft = {
      _generation_engine: { capability: "stock_reuse" },
      _scorecard: { score_0_10: 10 },
      _live_apply: { ready: false, findings: [] },
    };
    expect(draftFinisherComplete(draft)).toBe(true);
  });

  it("treats a scored residual as finished even when live-apply ready is false", () => {
    expect(
      draftFinisherComplete({
        _scorecard: { score_0_10: 8 },
        _live_apply: {
          ready: false,
          findings: [{ detail: "live apply: next_activity needs mail.activity.mixin" }],
        },
      }),
    ).toBe(true);
  });

  it("reads a document grammar card and surface-gate findings", () => {
    const draft = {
      _document_grammar: {
        shape: "transactional_header",
        display_name: "Purchase Requests",
        header_model: "x_purchase_request",
        document_count: 1,
        slots: ["Amount + Currency", "Requester = Employee"],
        states: ["draft", "submitted"],
        extra_apps: 0,
        summary: "1 document · Purchase Requests · Amount + Currency · 0 extra apps",
      },
      _live_apply: {
        ready: false,
        findings: [
          { dimension: "surface", detail: "surface: duplicate notebook pages (same columns)" },
          { dimension: "hygiene", detail: "live apply: monetary missing x_currency_id" },
        ],
      },
    };
    const card = documentGrammarFromDraft(draft);
    expect(card?.display_name).toBe("Purchase Requests");
    expect(card?.summary).toContain("1 document");
    expect(surfaceGateBlocksInstall(draft)).toBe(true);
    expect(surfaceGateFindingsFromDraft(draft).map((f) => f.detail)).toEqual([
      "surface: duplicate notebook pages (same columns)",
    ]);
  });

  it("prefers user_phase_label over step_label", () => {
    expect(
      busyLabelFromJobResult({
        user_phase_label: "Building your app…",
        step_label: "Defining fields",
      }),
    ).toBe("Building your app…");
    expect(busyLabelFromJobResult({ step_label: "Defining fields" })).toBe("Defining fields…");
  });
});

describe("DraftOdooPreview + OdooViewRenderer", () => {
  it("renders Odoo sheet grammar for a supermarket-like form IR", () => {
    const draft = {
      _generation_engine: {
        form_preview: RICH_FORM,
        list_preview: {
          type: "list" as const,
          model: "x_store_order",
          title: "Orders",
          columns: [
            { id: "x_name", name: "x_name", string: "Order" },
            { id: "x_status", name: "x_status", string: "Status" },
          ],
        },
        kanban_preview: {
          type: "kanban" as const,
          model: "x_store_order",
          title: "Orders",
          groupBy: "x_status",
          cardFields: [{ id: "x_name", name: "x_name", string: "Order" }],
        },
      },
    };
    render(<DraftOdooPreview draft={draft} breadcrumb="App Studio" />);
    expect(screen.getByTestId("odoo-preview-banner")).toBeTruthy();
    expect(screen.getByTestId("odoo-statusbar")).toBeTruthy();
    expect(screen.getByTestId("odoo-form-groups").className).toContain("is-two-column");
    expect(screen.getByTestId("odoo-button-box")).toBeTruthy();
    expect(screen.getByTestId("odoo-chatter-stub")).toBeTruthy();
    expect(screen.getByTestId("odoo-widget-m2o-x_partner_id")).toBeTruthy();
    expect(screen.getByTestId("odoo-widget-monetary-x_amount_total")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "List" }));
    expect(screen.getByTestId("odoo-list-view")).toBeTruthy();
    expect(screen.getByTestId("list-preview-table")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Kanban" }));
    expect(screen.getByTestId("odoo-kanban-view")).toBeTruthy();
  });

  it("explains field-pack inherit instead of asking for an x_* document", () => {
    render(
      <DraftOdooPreview
        draft={{
          grain: "field_pack",
          models: [{ model: "account.move", mode: "inherit" }],
        }}
        breadcrumb="App Studio"
      />,
    );
    const empty = screen.getByTestId("draft-odoo-preview-empty");
    expect(empty.textContent).toMatch(/form people already use/i);
    expect(empty.textContent).not.toMatch(/x_\*/);
    cleanup();
  });

  it("explains authored Option A instead of asking to start a new app", () => {
    render(
      <DraftOdooPreview
        draft={{ _generation_engine: { capability: "option_a_authored" } }}
        breadcrumb="App Studio"
      />,
    );
    const empty = screen.getByTestId("draft-odoo-preview-empty");
    expect(empty.textContent).toMatch(/Option A module/i);
    expect(empty.textContent).not.toMatch(/Start a new app/i);
    cleanup();
  });

  it("explains stock-reuse instead of sending the operator to the wizard", () => {
    render(
      <DraftOdooPreview
        draft={{ _generation_engine: { capability: "stock_reuse" } }}
        breadcrumb="App Studio"
      />,
    );
    const empty = screen.getByTestId("draft-odoo-preview-empty");
    expect(empty.textContent).toMatch(/stock Community apps/i);
    expect(empty.textContent).not.toMatch(/open the wizard/i);
  });

  it("renders list schema via OdooViewRenderer", () => {
    render(
      <OdooViewRenderer
        schema={{
          type: "list",
          model: "x_ticket",
          title: "Tickets",
          columns: [{ id: "x_name", name: "x_name", string: "Subject" }],
          decorations: { danger: "x_priority == 'urgent'" },
        }}
      />,
    );
    expect(screen.getByTestId("odoo-list-view")).toBeTruthy();
  });
});
