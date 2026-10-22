/** Friendly labels for server stage ids (T4-PROG). */

const LABELS: Record<string, string> = {
  retrieve_context: "Retrieving domain context",
  extract_entities: "Extracting entities",
  define_fields: "Defining fields",
  map_relationships: "Mapping relationships",
  build_workflow: "Building workflow",
  add_automations: "Adding automations",
  finalize_draft: "Finalizing draft",
  expert_classify: "Understanding your question",
  expert_retrieve: "Retrieving sources",
  expert_ground: "Grounding on this connection",
  expert_answer: "Writing the answer",
  bulk_resolve: "Resolving records",
  bulk_sample: "Running sample / dry-run",
  bulk_execute: "Executing bulk operation",
  bulk_report: "Summarizing results",
  dash_plan: "Planning the dashboard",
  dash_query: "Running read-only query",
  dash_render: "Rendering charts",
  dash_save: "Saving on project",
  tool_call_limit: "Tool-call limit reached",
};

export function stageFriendlyLabel(stage: string | null | undefined): string {
  if (!stage) return "Working…";
  return LABELS[stage] ?? stage.replace(/_/g, " ");
}
