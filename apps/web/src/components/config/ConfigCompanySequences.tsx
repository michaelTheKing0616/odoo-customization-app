"use client";

import { FormEvent } from "react";
import { api } from "@/lib/api";
import { EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import { Button } from "@/components/ui/Button";
import type { ConfigPageModel } from "./use-config-page";

export function ConfigCompanySequences({ vm }: { vm: ConfigPageModel }) {
  const {
    connectionId,
    companies,
    company,
    setCompany,
    sequences,
    setSequences,
    seqQuery,
    setSeqQuery,
    seqForm,
    setSeqForm,
    listsHydrated,
    busy,
    setBusy,
    setError,
    setNotice,
    refresh,
  } = vm;

  async function saveCompany(e: FormEvent) {
    e.preventDefault();
    if (!company) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.updateCompany(connectionId, company.id, {
        name: company.name,
        email: company.email ?? undefined,
        phone: company.phone ?? undefined,
        website: company.website ?? undefined,
        street: company.street ?? undefined,
        street2: company.street2 ?? undefined,
        city: company.city ?? undefined,
        zip: company.zip ?? undefined,
        vat: company.vat ?? undefined,
        company_registry: company.company_registry ?? undefined,
      });
      setCompany(updated);
      setNotice(`Saved company #${updated.id}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
        <form
          onSubmit={saveCompany}
          className="mt-8 space-y-3 border border-border-subtle bg-surface p-5 rounded-md"
        >
          <h2 className="text-ui-title">Company</h2>
          {companies.length > 1 && (
            <select
              value={company?.id ?? ""}
              onChange={(e) =>
                setCompany(companies.find((c) => c.id === Number(e.target.value)) ?? null)
              }
              className="rounded-md border border-border-subtle bg-surface-raised px-3 py-2 text-sm"
            >
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
          {company && (
            <div className="grid gap-3 sm:grid-cols-2">
              {(
                [
                  ["name", "Name"],
                  ["email", "Email"],
                  ["phone", "Phone"],
                  ["website", "Website"],
                  ["street", "Street"],
                  ["street2", "Street 2"],
                  ["city", "City"],
                  ["zip", "ZIP"],
                  ["vat", "VAT"],
                  ["company_registry", "Company registry"],
                ] as const
              ).map(([key, label]) => (
                <label key={key} className="block text-sm">
                  <span className="text-muted">{label}</span>
                  <input
                    value={company[key] ?? ""}
                    onChange={(e) =>
                      setCompany({ ...company, [key]: e.target.value || null })
                    }
                    className="mt-1 w-full rounded-md border border-border-subtle bg-surface-raised px-3 py-2 text-sm"
                  />
                </label>
              ))}
            </div>
          )}
          <button
            type="submit"
            disabled={busy || !company}
            className="h-10 bg-accent px-4 text-sm font-semibold text-white disabled:opacity-60"
          >
            Save company
          </button>
        </form>

        <section className="mt-8 rounded-md border border-border-subtle bg-surface p-5">
          <h2 className="text-ui-title">Sequences</h2>
          <form
            className="mt-3 flex flex-wrap gap-2"
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              try {
                await api.createSequence(connectionId, {
                  name: seqForm.name,
                  code: seqForm.code || null,
                  prefix: seqForm.prefix || null,
                  padding: seqForm.padding,
                });
                setSeqForm({ name: "", code: "", prefix: "", padding: 5 });
                setNotice("Sequence created");
                await refresh();
              } catch (err) {
                setError(err instanceof Error ? err.message : "Create failed");
              } finally {
                setBusy(false);
              }
            }}
          >
            <input
              required
              placeholder="Name"
              value={seqForm.name}
              onChange={(e) => setSeqForm({ ...seqForm, name: e.target.value })}
              className="rounded-md border border-border-subtle bg-surface-raised px-2 py-1 text-sm"
            />
            <input
              placeholder="code"
              value={seqForm.code}
              onChange={(e) => setSeqForm({ ...seqForm, code: e.target.value })}
              className="w-28 rounded-md border border-border-subtle bg-surface-raised px-2 py-1 font-mono text-sm"
            />
            <input
              placeholder="prefix"
              value={seqForm.prefix}
              onChange={(e) => setSeqForm({ ...seqForm, prefix: e.target.value })}
              className="w-24 rounded-md border border-border-subtle bg-surface-raised px-2 py-1 font-mono text-sm"
            />
            <button
              type="submit"
              disabled={busy}
              className="border border-accent px-3 text-sm text-muted"
            >
              Create
            </button>
          </form>
          <div className="mt-3 flex gap-2">
            <input
              value={seqQuery}
              onChange={(e) => setSeqQuery(e.target.value)}
              placeholder="Filter"
              className="rounded-md border border-border-subtle bg-surface-raised px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={() => void refresh()}
              className="border border-border-subtle px-3 text-sm"
            >
              Refresh
            </button>
          </div>
          {!listsHydrated ? (
            <div className="mt-4 space-y-2" data-testid="config-sequences-loading">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : sequences.length === 0 ? (
            <div className="mt-4" data-testid="config-sequences-empty">
              <EmptyState
                title="No ir.sequence rows yet"
                description="Create a sequence above or refresh after numbering exists in Odoo."
                action={
                  <Button type="button" variant="secondary" size="sm" disabled={busy} onClick={() => void refresh()}>
                    Refresh sequences
                  </Button>
                }
              />
            </div>
          ) : (
          <ul className="mt-4 max-h-64 space-y-2 overflow-auto text-sm">
            {sequences.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-2 border-t border-border-subtle py-2">
                <span className="font-medium">
                  {s.name}{" "}
                  <span className="font-mono text-xs text-muted">{s.code}</span>
                </span>
                <input
                  value={s.prefix ?? ""}
                  onChange={(e) =>
                    setSequences((rows) =>
                      rows.map((r) =>
                        r.id === s.id ? { ...r, prefix: e.target.value } : r,
                      ),
                    )
                  }
                  className="w-24 rounded-md border border-border-subtle bg-surface-raised px-2 py-1 font-mono text-xs"
                />
                <input
                  type="number"
                  value={s.number_next}
                  onChange={(e) =>
                    setSequences((rows) =>
                      rows.map((r) =>
                        r.id === s.id
                          ? { ...r, number_next: Number(e.target.value) }
                          : r,
                      ),
                    )
                  }
                  className="w-20 rounded-md border border-border-subtle bg-surface-raised px-2 py-1 font-mono text-xs"
                />
                <button
                  type="button"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      await api.updateSequence(connectionId, s.id, {
                        prefix: s.prefix ?? undefined,
                        number_next: s.number_next,
                        padding: s.padding,
                        active: s.active,
                      });
                      setNotice(`Updated sequence #${s.id}`);
                    } catch (err) {
                      setError(err instanceof Error ? err.message : "Update failed");
                    } finally {
                      setBusy(false);
                    }
                  }}
                  className="text-xs text-muted"
                >
                  Save
                </button>
              </li>
            ))}
          </ul>
          )}
        </section>
    </>
  );
}
