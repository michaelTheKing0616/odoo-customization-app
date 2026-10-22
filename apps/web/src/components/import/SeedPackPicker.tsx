"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/layout-primitives";
import { ImportStateGuide } from "@/components/import/ImportStateGuide";
import { seedPacksEmptyGuide } from "@/lib/importScreen";

type SeedPackPickerProps = {
  connectionId: string;
  onPick: (model: string, csv: string) => void;
};

export function SeedPackPicker({ connectionId, onPick }: SeedPackPickerProps) {
  const [packs, setPacks] = useState<
    Array<{ id: string; name: string; description: string; models: string[] }> | null
  >(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    setPacks(null);
    setError(null);
    api
      .listSeedPacks(connectionId)
      .then(setPacks)
      .catch((err: Error) => setError(err.message));
  }, [connectionId, reloadKey]);

  if (error) {
    return (
      <ImportStateGuide
        tone="danger"
        live
        testId="import-seed-error"
        guide={{
          title: "Could not load seed packs",
          why: error,
          next: "Reload packs, or skip seeds and upload a CSV instead.",
        }}
        actions={
          <Button type="button" variant="secondary" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
            Reload packs
          </Button>
        }
      />
    );
  }

  if (packs === null) {
    return (
      <div className="im-seed-grid" data-testid="seed-packs-loading">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-28 w-full" />
      </div>
    );
  }

  if (packs.length === 0) {
    return (
      <ImportStateGuide
        testId="import-seed-empty"
        guide={seedPacksEmptyGuide()}
        actions={
          <Button type="button" variant="secondary" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
            Reload packs
          </Button>
        }
      />
    );
  }

  return (
    <div className="im-seed-grid" data-testid="import-seed-grid">
      {packs.map((p) => (
        <div key={p.id} className="im-seed-card">
          <h3>{p.name}</h3>
          <p>{p.description}</p>
          <div className="im-seed-models">
            {p.models.map((m) => (
              <Button
                key={m}
                type="button"
                variant="secondary"
                size="sm"
                className="font-mono text-xs"
                onClick={async () => {
                  const detail = await api.getSeedPack(connectionId, p.id);
                  const entry = detail.models.find((x) => x.model === m);
                  if (entry) onPick(entry.model, entry.csv);
                }}
              >
                {m}
              </Button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
