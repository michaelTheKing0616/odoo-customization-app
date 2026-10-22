"use client";

import Link from "next/link";
import { useSuite } from "./SuiteContext";
import { PageHead } from "./parts";
import styles from "./Suite.module.css";

/** Stage 1 structure: these workspaces open the existing tools until their re-shell stages land. */
const CHANGE: Record<string, { title: string; purpose: string; tool: string; label: string }> = {
  transitions: { title: "Move forward", purpose: "Move many records to their next step, checked first.", tool: "bulk-suite", label: "Open the batch tools" },
  edit: { title: "Edit a field", purpose: "Set one field on many records, checked first, with undo.", tool: "bulk-suite", label: "Open the batch tools" },
  duplicates: { title: "Merge duplicates", purpose: "Find records that are the same thing and merge them.", tool: "bulk-suite", label: "Open the batch tools" },
  activities: { title: "Activities", purpose: "Plan or close activities on many records.", tool: "bulk-suite", label: "Open the batch tools" },
  portal: { title: "Portal access", purpose: "Give or remove portal access for many contacts.", tool: "bulk-suite", label: "Open the batch tools" },
};
const UPKEEP: Record<string, { title: string; purpose: string; tool: string; label: string }> = {
  schedules: { title: "Scheduled actions", purpose: "What runs on its own, when, and whether it failed.", tool: "cron-manager", label: "Open scheduled actions" },
  files: { title: "Files and storage", purpose: "What takes space and what can be cleaned up.", tool: "housekeeping", label: "Open housekeeping" },
};

function Tabs({ items, base, active }: { items: Record<string, { title: string }>; base: string; active: string }) {
  return (
    <nav aria-label="Tools" className={styles.row}>
      {Object.entries(items).map(([k, v]) => <Link key={k} href={`${base}/${k}`} aria-current={k === active ? "page" : undefined}>{v.title}</Link>)}
    </nav>
  );
}

export function ChangeTool({ tool }: { tool: string }) {
  const { connectionId } = useSuite();
  const t = CHANGE[tool] ?? CHANGE.edit;
  return (
    <>
      <PageHead title={t.title} purpose={t.purpose} />
      <Tabs items={CHANGE} base={`/connections/${connectionId}/suite/change`} active={tool} />
      <p className={styles.section}><Link href={`/connections/${connectionId}/${t.tool}`}>{t.label}</Link></p>
    </>
  );
}

export function UpkeepTool({ area }: { area: string }) {
  const { connectionId } = useSuite();
  const t = UPKEEP[area] ?? UPKEEP.schedules;
  return (
    <>
      <PageHead title={t.title} purpose={t.purpose} />
      <Tabs items={UPKEEP} base={`/connections/${connectionId}/suite/upkeep`} active={area} />
      <p className={styles.section}><Link href={`/connections/${connectionId}/${t.tool}`}>{t.label}</Link></p>
    </>
  );
}

export function AskWorkspace() {
  const { connectionId } = useSuite();
  return (
    <>
      <PageHead title="Ask" purpose="Ask about this database. Answers come from it; anything that would change data becomes a plan you check first." />
      <p className={styles.section}><Link href={`/connections/${connectionId}/expert`}>Open the assistant</Link></p>
    </>
  );
}
