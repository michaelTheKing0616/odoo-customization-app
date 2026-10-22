import { redirect } from "next/navigation";

type Search = Record<string, string | string[] | undefined>;

/** D1: old tool routes move into the Configuration Suite, keeping their query state. */
export async function redirectIntoSuite(
  params: Promise<{ id: string }>,
  searchParams: Promise<Search>,
  target: string,
  extra: Record<string, string> = {},
): Promise<never> {
  const { id } = await params;
  const sp = await searchParams;
  const q = new URLSearchParams(extra);
  for (const [k, v] of Object.entries(sp)) {
    if (Array.isArray(v)) v.forEach((x) => q.append(k, x));
    else if (v !== undefined && !q.has(k)) q.set(k, v);
  }
  const qs = q.toString();
  redirect(`/connections/${encodeURIComponent(id)}/suite/${target}${qs ? `?${qs}` : ""}`);
}
