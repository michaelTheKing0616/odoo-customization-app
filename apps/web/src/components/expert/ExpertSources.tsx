"use client";

import { useMemo } from "react";
import { Tooltip } from "@/components/ui/Tooltip";
import type { ExpertCitation } from "@/lib/api";

export function CitationChip({ citation, index }: { citation: ExpertCitation; index?: number }) {
  const label = index ?? citation.source_index;
  return (
    <Tooltip label={`${citation.source} · ${citation.version} — ${citation.breadcrumb}`}>
      <sup className="expert-cite-chip cursor-help" data-testid="expert-citation-chip">
        [{label}]
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
            <CitationChip citation={c} />
            <span className="min-w-0 truncate">
              <span className="font-medium text-ink">{c.source}</span>
              <span className="text-muted">
                {" "}
                · {c.version} — {c.breadcrumb}
              </span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
