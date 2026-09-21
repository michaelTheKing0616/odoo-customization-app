"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, AtlasClass, AtlasHit, BatchOsRecipeCard } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/layout-primitives";

function riskVariant(risk: string): "default" | "info" | "warning" | "danger" | "success" {
  if (risk === "L0") return "success";
  if (risk === "L1") return "info";
  if (risk === "L2") return "warning";
  return "danger";
}

function statusVariant(status: string): "default" | "success" | "info" {
  if (status === "complete") return "success";
  if (status === "stub") return "default";
  return "info";
}

type Props = { connectionId: string };

export function ConfigAtlasBrowser({ connectionId }: Props) {
  const [classes, setClasses] = useState<AtlasClass[]>([]);
  const [recipes, setRecipes] = useState<BatchOsRecipeCard[]>([]);
  const [hits, setHits] = useState<AtlasHit[] | null>(null);
  const [q, setQ] = useState("");
  const [classFilter, setClassFilter] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [atlas, rec] = await Promise.all([
        api.batchOsAtlas(connectionId, classFilter || undefined),
        api.batchOsRecipes(connectionId),
      ]);
      setClasses(atlas.classes);
      setRecipes(rec);
      setHits(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Atlas load failed");
    } finally {
      setBusy(false);
    }
  }, [connectionId, classFilter]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onSearch = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.batchOsAtlasSearch(connectionId, {
        q,
        class_id: classFilter || undefined,
      });
      setHits(res.hits);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setBusy(false);
    }
  }, [connectionId, q, classFilter]);

  const classOptions = useMemo(
    () => classes.map((c) => ({ id: c.id, title: c.title, status: c.status })),
    [classes],
  );

  return (
    <div className="space-y-4" data-testid="config-atlas-browser">
      <Callout variant="info" title="Config Atlas">
        Intent → class → models → risk → recipe. All eight atlas classes are complete —
        master data, settings, access, automation, UI Studio, and housekeeping included.
      </Callout>
      {error ? <ErrorNotice message={error} /> : null}

      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs text-muted">
          Class
          <select
            className="mt-1 block rounded border border-border-subtle bg-surface px-2 py-1.5 text-sm"
            value={classFilter}
            onChange={(e) => setClassFilter(e.target.value)}
            data-testid="atlas-class-filter"
          >
            <option value="">All classes</option>
            {classOptions.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title} ({c.status})
              </option>
            ))}
          </select>
        </label>
        <label className="min-w-[12rem] flex-1 text-xs text-muted">
          Search
          <Input
            className="mt-1"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="lock dates, journal, CoA…"
            data-testid="atlas-search"
          />
        </label>
        <Button type="button" size="sm" variant="secondary" disabled={busy} onClick={() => void onSearch()}>
          Search
        </Button>
        <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => void refresh()}>
          Reset
        </Button>
      </div>

      {hits ? (
        <ul className="grid gap-3 sm:grid-cols-2">
          {hits.map((h) => (
            <li key={h.intent_id}>
              <Card className="p-4">
                <div className="flex flex-wrap gap-2">
                  <Badge variant={riskVariant(h.risk)}>{h.risk}</Badge>
                  <Badge variant={statusVariant(h.status)}>{h.status}</Badge>
                </div>
                <p className="mt-2 font-medium text-ink">{h.title}</p>
                <p className="text-xs text-muted">
                  {h.class_title} · {h.intent_id}
                  {h.recipe ? ` · recipe ${h.recipe}` : ""}
                </p>
                <p className="mt-1 text-xs text-muted">{h.blurb}</p>
                <p className="mt-1 font-mono text-[11px] text-muted">{h.models.join(", ")}</p>
              </Card>
            </li>
          ))}
          {hits.length === 0 ? (
            <li className="text-sm text-muted">No matches.</li>
          ) : null}
        </ul>
      ) : (
        <div className="space-y-6">
          {classes.map((c) => (
            <section key={c.id} data-testid={`atlas-class-${c.id}`}>
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <h3 className="text-ui-title text-ink">{c.title}</h3>
                <Badge variant={statusVariant(c.status)}>{c.status}</Badge>
              </div>
              <p className="mb-3 text-sm text-muted">{c.blurb}</p>
              <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {c.intents.map((intent) => (
                  <li key={intent.id}>
                    <Card className="h-full p-3">
                      <div className="flex flex-wrap gap-1">
                        <Badge variant={riskVariant(intent.risk)}>{intent.risk}</Badge>
                        <Badge variant={statusVariant(intent.status)}>{intent.status}</Badge>
                      </div>
                      <p className="mt-2 text-sm font-medium text-ink">{intent.title}</p>
                      <p className="mt-1 text-xs text-muted">{intent.blurb}</p>
                      {intent.recipe ? (
                        <p className="mt-2 font-mono text-[11px] text-accent">{intent.recipe}</p>
                      ) : null}
                    </Card>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      <section>
        <h3 className="mb-2 text-ui-title text-ink">Executable recipes</h3>
        <ul className="grid gap-3 sm:grid-cols-2">
          {recipes.map((r) => (
            <li key={r.id}>
              <Card className="p-3" data-testid={`batch-recipe-${r.id}`}>
                <div className="flex flex-wrap gap-1">
                  <Badge variant={riskVariant(r.risk)}>{r.risk}</Badge>
                  <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
                </div>
                <p className="mt-2 text-sm font-medium text-ink">{r.title}</p>
                <p className="text-xs text-muted">{r.blurb}</p>
                <p className="mt-1 font-mono text-[11px] text-muted">{r.id}</p>
              </Card>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
