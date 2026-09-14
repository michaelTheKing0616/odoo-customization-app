"use client";

import type { PreviewKanbanView } from "@/lib/draft-form-preview";

type OdooKanbanViewProps = {
  view: PreviewKanbanView;
};

/** Public Odoo color index palette (0–11) — structural mimic, not copied CSS. */
const COLOR_INDEX = [
  "#aecf55",
  "#f06050",
  "#f4a460",
  "#ebc13e",
  "#61bd4f",
  "#40a9ff",
  "#2d7ff9",
  "#884dff",
  "#eb2f96",
  "#00c2e0",
  "#4dd0e1",
  "#7f8c8d",
];

const DEFAULT_STAGES = ["draft", "open", "done"];

const SAMPLE_CARDS: Array<{
  title: string;
  stageIdx: number;
  color: number;
  kanbanState: "normal" | "done" | "blocked";
}> = [
  { title: "Sample record", stageIdx: 0, color: 5, kanbanState: "normal" },
  { title: "Urgent follow-up", stageIdx: 1, color: 1, kanbanState: "blocked" },
  { title: "Ready to close", stageIdx: 2, color: 4, kanbanState: "done" },
];

function KanbanStateDot({ state }: { state: "normal" | "done" | "blocked" }) {
  return (
    <span
      className={`odoo-kanban-state odoo-kanban-state-${state}`}
      title={state}
      data-testid="odoo-kanban-state"
      aria-label={`kanban state ${state}`}
    />
  );
}

export function OdooKanbanView({ view }: OdooKanbanViewProps) {
  const stages = view.groupBy ? DEFAULT_STAGES : ["all"];
  return (
    <div className="odoo-kanban-canvas p-3 shadow-sm" data-testid="odoo-kanban-view">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-[var(--odoo-primary)]">{view.title}</span>
        {view.groupBy ? (
          <span className="text-xs text-[var(--odoo-muted)]">group by {view.groupBy}</span>
        ) : null}
      </div>
      <div className="flex gap-3 overflow-x-auto">
        {stages.map((stage, stageIdx) => {
          const cards = view.groupBy
            ? SAMPLE_CARDS.filter((c) => c.stageIdx === stageIdx)
            : SAMPLE_CARDS;
          return (
            <div key={stage} className="odoo-kanban-column min-w-[14rem] flex-1">
              <div className="odoo-kanban-column-title">
                {stage === "all" ? "All records" : stage.replaceAll("_", " ")}
                <span className="odoo-kanban-count">{cards.length}</span>
              </div>
              <div className="odoo-kanban-column-body">
                {cards.map((card) => (
                  <div
                    key={`${stage}-${card.title}`}
                    className="odoo-kanban-card"
                    style={{
                      borderLeftColor: COLOR_INDEX[card.color % COLOR_INDEX.length],
                    }}
                    data-testid="odoo-kanban-card"
                  >
                    <div className="odoo-kanban-card-top">
                      <span className="odoo-kanban-card-title">
                        {view.cardFields[0]?.string
                          ? `${card.title}`
                          : card.title}
                      </span>
                      <KanbanStateDot state={card.kanbanState} />
                    </div>
                    {view.cardFields.slice(1, 4).map((field) => (
                      <div key={field.id} className="odoo-kanban-card-field">
                        {field.string}: sample
                      </div>
                    ))}
                    <div
                      className="odoo-kanban-color-swatch"
                      style={{
                        background: COLOR_INDEX[card.color % COLOR_INDEX.length],
                      }}
                      title={`color ${card.color}`}
                      data-testid="odoo-kanban-color"
                    />
                  </div>
                ))}
                {cards.length === 0 ? (
                  <p className="text-xs text-[var(--odoo-muted)]">No cards</p>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
