import { redirect } from "next/navigation";

/** Old View Designer address: moved to the new View Designer (old links keep working, D1-style).
 * /designer/classic redirects here too. */
const RENAME: Record<string, string> = { viewType: "type", view_type: "type", view_id: "view", viewId: "view" };

export default async function OldDesignerRedirect({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(await searchParams)) {
    const val = Array.isArray(v) ? v[0] : v;
    if (val) q.set(RENAME[k] ?? k, val);
  }
  const qs = q.toString();
  redirect(`/connections/${encodeURIComponent(id)}/view-designer${qs ? `?${qs}` : ""}`);
}
