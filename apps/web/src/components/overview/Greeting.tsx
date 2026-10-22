"use client";

import { useEffect, useState } from "react";
import { request } from "@/lib/api/client";

/** Q2 touch 93: a greeting with substance, never on its own. Real counts only. */
export function partOfDay(now: Date): "morning" | "afternoon" | "evening" {
  const h = (now.getUTCHours() + 1) % 24; // Lagos, UTC+1
  return h < 12 ? "morning" : h < 17 ? "afternoon" : "evening";
}

export function greetingLine(o: { name: string | null; approvals: number | null; failed: number | null; now: Date }): string | null {
  if (o.approvals == null && o.failed == null) return null; // nothing real to say, so no greeting
  const hello = `Good ${partOfDay(o.now)}${o.name ? `, ${o.name}` : ""}.`;
  const parts: string[] = [];
  if (o.approvals) parts.push(`${o.approvals} ${o.approvals === 1 ? "approval" : "approvals"} waiting`);
  if (o.failed) parts.push(`${o.failed} failed ${o.failed === 1 ? "job" : "jobs"}`);
  return parts.length ? `${hello} ${parts.join(" and ")}.` : `${hello} Nothing needs you right now.`;
}

// Through the API client, so the stored key is sent like every other API call.
const count = (url: string) => request<{ count: number }>(url).then((r) => (typeof r.count === "number" ? r.count : null), () => null);

export function Greeting() {
  const [line, setLine] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    void Promise.all([
      request<{ display_name: string | null }>("/api/accounts/whoami").then((r) => r.display_name, () => null),
      count("/api/command/tiles/pending-approvals"),
      count("/api/command/tiles/failed-jobs"),
    ]).then(([name, approvals, failed]) => alive && setLine(greetingLine({ name, approvals, failed, now: new Date() })));
    return () => {
      alive = false;
    };
  }, []);
  if (!line) return null;
  return <p className="mt-6 text-md text-ink" data-testid="overview-greeting">{line}</p>;
}
