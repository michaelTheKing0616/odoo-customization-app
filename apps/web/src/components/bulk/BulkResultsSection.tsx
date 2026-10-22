import { BulkResultTable } from "@/components/ui/BulkResultTable";
import { partialFailureGuide } from "@/lib/bulkSuiteScreen";
import { BulkResultCounts } from "./BulkResultCounts";
import { BulkStateGuide } from "./BulkStateGuide";
import { bulkRunToTable } from "./bulk-helpers";
import type { BulkSuitePageModel } from "./use-bulk-suite-page";

export function BulkResultsSection({ vm }: { vm: BulkSuitePageModel }) {
  if (!vm.result) return null;
  const result = vm.result;
  const failureGuide = partialFailureGuide({
    total: result.total,
    succeeded: result.succeeded,
    failed: result.failed,
    model: result.model,
  });

  return (
    <section className="bu-panel" data-testid="bulk-results-panel" aria-labelledby="bulk-results-title">
      <h2 id="bulk-results-title" className="bu-panel-title">
        Results
      </h2>
      <p className="bu-panel-sub">
        {result.dry_run ? "Test run counts. No records were written." : "Per-row outcomes for the last run."}
      </p>

      <BulkResultCounts
        total={result.total}
        succeeded={result.succeeded}
        failed={result.failed}
        dryRun={Boolean(result.dry_run)}
      />

      {failureGuide ? (
        <BulkStateGuide
          className="!mt-3"
          tone="warning"
          live
          testId="bulk-partial-guide"
          guide={failureGuide}
        />
      ) : null}

      {result.preview && result.preview.length > 0 ? (
        <div className="bu-table-wrap">
          <table className="bu-table">
            <thead>
              <tr>
                <th scope="col">Id</th>
                <th scope="col">Record</th>
                <th scope="col">Before</th>
                <th scope="col">After</th>
              </tr>
            </thead>
            <tbody>
              {result.preview.map((row) => (
                <tr key={row.id}>
                  <td className="font-mono">{row.id}</td>
                  <td>{row.display_name}</td>
                  <td className="font-mono text-xs">{JSON.stringify(row.before)}</td>
                  <td className="font-mono text-xs">{JSON.stringify(row.after)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {result.relinks && result.relinks.length > 0 ? (
        <div className="bu-table-wrap">
          <table className="bu-table">
            <thead>
              <tr>
                <th scope="col">Model</th>
                <th scope="col">Field</th>
                <th scope="col">Type</th>
                <th scope="col">Rows relinked</th>
              </tr>
            </thead>
            <tbody>
              {result.relinks.map((row) => (
                <tr key={`${row.model}.${row.field}`}>
                  <td className="font-mono">{row.model}</td>
                  <td className="font-mono">{row.field}</td>
                  <td>{row.ttype}</td>
                  <td>{row.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
    </section>
  );
}
