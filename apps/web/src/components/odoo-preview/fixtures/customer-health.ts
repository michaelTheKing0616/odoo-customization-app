/** Fixture: Customer Health form preview + integration plan (vitest and e2e harness). */
import type { PreviewFormView } from "@/lib/draft-form-preview";
import type { IntegrationPlan } from "@/lib/integration-plan";

export const CUSTOMER_HEALTH_FORM: PreviewFormView = {
  type: "form",
  model: "x_customer_health",
  title: "Customer Health",
  appLabel: "Customer Success",
  recordTitleField: "x_name",
  statusbar: {
    field: "x_state",
    stages: ["healthy", "watch", "at_risk", "churned"],
    activeStage: "watch",
  },
  headerButtons: [
    { id: "recompute", string: "Recompute score", variant: "primary" },
    { id: "plan", string: "Start success plan", variant: "secondary" },
  ],
  smartButtons: [
    { id: "opps", string: "Expansion opportunities", count: 3 },
    { id: "invoices", string: "Open invoices", count: 2 },
    { id: "history", string: "Score history", count: 12 },
  ],
  groups: [
    {
      id: "main",
      string: "",
      columns: 2,
      fields: [
        { id: "x_name", name: "x_name", string: "Account name", ttype: "char", required: true },
        { id: "x_partner_id", name: "x_partner_id", string: "Customer", ttype: "many2one", relation: "res.partner", required: true },
        { id: "x_owner_id", name: "x_owner_id", string: "Customer success manager", ttype: "many2one", relation: "res.users" },
        { id: "x_score", name: "x_score", string: "Health score (0 to 100)", ttype: "integer" },
        {
          id: "x_risk_level",
          name: "x_risk_level",
          string: "Risk level",
          ttype: "selection",
          selection: [
            { value: "low", label: "Low" },
            { value: "medium", label: "Medium" },
            { value: "high", label: "High" },
          ],
        },
        { id: "x_renewal_date", name: "x_renewal_date", string: "Renewal date", ttype: "date" },
        { id: "x_arr", name: "x_arr", string: "Annual recurring revenue", ttype: "monetary" },
        { id: "x_tag_ids", name: "x_tag_ids", string: "Segments", ttype: "many2many", widget: "many2many_tags" },
        { id: "x_auto_alert", name: "x_auto_alert", string: "Send alerts when the score drops below the threshold", ttype: "boolean" },
        { id: "x_ticket_id", name: "x_ticket_id", string: "Latest helpdesk ticket", ttype: "many2one", relation: "helpdesk.ticket" },
      ],
    },
  ],
  notebooks: [
    {
      id: "nb",
      pages: [
        {
          id: "signals",
          string: "Score signals",
          fields: [
            {
              id: "x_signal_ids",
              name: "x_signal_ids",
              string: "Signals",
              ttype: "one2many",
              relation: "x_health_signal",
              relationColumns: [
                { name: "x_name", string: "Signal", ttype: "char" },
                { name: "x_weight", string: "Weight", ttype: "float" },
                { name: "x_threshold", string: "Threshold", ttype: "float" },
                { name: "x_active", string: "Active", ttype: "boolean" },
              ],
            },
          ],
        },
        {
          id: "plan",
          string: "Success plan",
          fields: [{ id: "x_plan_notes", name: "x_plan_notes", string: "Plan", ttype: "html" }],
        },
        {
          id: "explain",
          string: "Why this score",
          fields: [{ id: "x_explanation", name: "x_explanation", string: "Explanation", ttype: "text" }],
        },
      ],
    },
  ],
  chatter: "stub",
  groupLayout: "two-column",
};

export const CUSTOMER_HEALTH_PLAN: IntegrationPlan = {
  primary_module: null,
  edition: "community",
  hosting: "online",
  core_built: true,
  integrations: [
    { module: "crm", app_label: "CRM", model: "crm.lead", status: "available", note: "" },
    { module: "account", app_label: "Invoicing", model: "account.move", status: "available", note: "" },
    {
      module: "project",
      app_label: "Project",
      model: "project.task",
      status: "deferred",
      note: "Project is not installed, so its links are left out for now. Install Project, then refine this app to add them.",
    },
    {
      module: "helpdesk",
      app_label: "Helpdesk",
      model: "helpdesk.ticket",
      status: "left_out",
      note: "Helpdesk was left out: it is an Odoo Enterprise app and this database is Community. To add it later, move to Odoo Enterprise, install Helpdesk, then refine this app.",
    },
  ],
  left_out: ["helpdesk"],
  omitted_models: ["project.task", "helpdesk.ticket"],
  python_pieces: [
    { key: "computed_score", label: "Computed scores", online_blocked: "true" },
    { key: "rules_engine", label: "the rules engine", online_blocked: "true" },
    { key: "scheduled_actions", label: "score history", online_blocked: "true" },
  ],
};
