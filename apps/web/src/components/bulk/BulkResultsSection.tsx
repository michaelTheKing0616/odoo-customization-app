import { BulkResultTable } from "@/components/ui/BulkResultTable";
import { Card } from "@/components/ui/layout-primitives";
import { bulkRunToTable } from "./bulk-helpers";
import type { BulkSuitePageModel } from "./use-bulk-suite-page";

export function BulkResultsSection({ vm }: { vm: BulkSuitePageModel }) {
  if (!vm.result) return null;
  const result = vm.result;

  return (
    <Card className="mt-6 overflow-x-auto p-4">
      <h2 className="text-lg font-semibold text-ink">Results</h2>
      {result.preview && result.preview.length > 0 ? (
        <table className="mt-3 w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border-subtle">
              <th className="py-1 pr-2">Id</th>
              <th className="py-1 pr-2">Record</th>
              <th className="py-1 pr-2">Before</th>
              <th className="py-1">After</th>
            </tr>
          </thead>
          <tbody>
            {result.preview.map((row) => (
              <tr key={row.id} className="border-b border-border-subtle/50">
                <td className="py-1 pr-2 font-mono">{row.id}</td>
                <td className="py-1 pr-2">{row.display_name}</td>
                <td className="py-1 pr-2 font-mono text-xs">
                  {JSON.stringify(row.before)}
                </td>
                <td className="py-1 font-mono text-xs">{JSON.stringify(row.after)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {result.relinks && result.relinks.length > 0 ? (
        <table className="mt-3 w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border-subtle">
              <th className="py-1 pr-2">Model</th>
              <th className="py-1 pr-2">Field</th>
              <th className="py-1 pr-2">Type</th>
              <th className="py-1">Rows relinked</th>
            </tr>
          </thead>
          <tbody>
            {result.relinks.map((row) => (
              <tr
                key={`${row.model}.${row.field}`}
                className="border-b border-border-subtle/50"
              >
                <td className="py-1 pr-2 font-mono">{row.model}</td>
                <td className="py-1 pr-2 font-mono">{row.field}</td>
                <td className="py-1 pr-2">{row.ttype}</td>
                <td className="py-1">{row.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      <div className="mt-4">
        <BulkResultTable
          result={bulkRunToTable(result)}
          onContinue={result.can_continue ? vm.continueSampleRun : undefined}
          onAbort={result.status === "sample_paused" ? vm.abortSampleRun : undefined}
          continueBusy={vm.runControlBusy}
          abortBusy={vm.runControlBusy}
        />
        {result.snapshot_id && result.operation === "dedupe_merge" && !result.dry_run ? (
          <p className="mt-3 text-sm">
            <a
              className="text-accent underline"
              href={`/api/connections/${vm.connectionId}/snapshots/${result.snapshot_id}/artifact.json`}
              data-testid="dedupe-merge-backup-download"
            >
              Download merge backup (JSON)
            </a>
          </p>
        ) : null}
      </div>
    </Card>
  );
}
