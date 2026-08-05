"use client";

import { useEffect, useState } from "react";
import { api, type StudioFeatureRecipe } from "@/lib/api";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { formatFetchError } from "@/lib/format-fetch-error";

type Props = {
  className?: string;
};

export function StudioFeatureRecipesPanel({ className = "" }: Props) {
  const [rows, setRows] = useState<StudioFeatureRecipe[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .listStudioFeatureRecipes()
      .then((list) => {
        if (!cancelled) {
          setRows(list);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const raw = err instanceof Error ? err.message : "Failed to load feature recipes";
          setError(formatFetchError(raw));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  return (
    <div className={`text-sm ${className}`} data-testid="studio-feature-recipes-panel">
      <p className="text-xs font-medium text-[#a8909e]">Studio feature recipes (public ORM)</p>
      <p className="mt-0.5 text-[11px] text-[#6b5a66]">
        How each Studio-doc suggested feature maps to Builder / Designer / Option A — honesty
        statuses, not a Studio clone.
      </p>
      {loading && <p className="mt-2 text-xs text-muted">Loading…</p>}
      {error ? (
        <ErrorNotice
          message={error}
          showDiagnose={false}
          onRetry={() => setReloadKey((k) => k + 1)}
          className="mt-2"
        />
      ) : null}
      {!loading && !error && (
        <ul className="mt-2 max-h-64 space-y-1 overflow-y-auto">
          {rows.map((r) => (
            <li
              key={r.id}
              data-testid={`feature-recipe-${r.id}`}
              data-status={r.status}
              className="border border-border-subtle bg-[#120e14] px-2 py-1.5 text-xs text-muted"
            >
              <span className="font-medium">{r.name}</span>
              <span className="ml-2 text-[10px] uppercase tracking-wide text-muted">
                {r.status}
              </span>
              <span className="mt-0.5 block text-[11px] text-muted">{r.how}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
