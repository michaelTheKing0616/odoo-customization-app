"use client";

import { useMemo } from "react";
import { Tooltip } from "@/components/ui/Tooltip";
import type { ExpertCitation } from "@/lib/api";

export function citationTooltip(citation: ExpertCitation): string {
  return [citation.source, citation.version, citation.breadcrumb].filter(Boolean).join(" · ");
}

export function CitationChip({ citation, index }: { citation: ExpertCitation; index?: number }) {
  const label = index ?? citation.source_index;
  return (
    <Tooltip label={citationTooltip(citation)}>
      <sup
        className="expert-cite-chip"
        tabIndex={0}
        aria-label={`Source ${label}: ${citationTooltip(citation)}`}
        data-testid="expert-citation-chip"
      >
        {label}
      </sup>
    </Tooltip>
  );
}

type ExpertSourcesProps = {
  citations: ExpertCitation[];
};

export function ExpertSources({ citations }: ExpertSourcesProps) {
  const rows = useMemo(
    () =>
      citations.filter(
        (c, i, all) => all.findIndex((other) => other.chunk_id === c.chunk_id) === i,
      ),
    [citations],
  );
  if (rows.length === 0) return null;

  return (
    <div className="expert-sources" data-testid="expert-sources">
      <p className="expert-sources-label">Sources</p>
      <ol className="expert-source-list">
        {rows.map((c) => (
          <li key={c.chunk_id} className="expert-source-row">
            <span className="expert-source-index" aria-hidden>
              {c.source_index}
            </span>
            <span className="min-w-0">
              <span className="expert-source-name">{c.source}</span>
              <span className="expert-source-meta">
                {" "}
                {c.version} · {c.breadcrumb}
              </span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
