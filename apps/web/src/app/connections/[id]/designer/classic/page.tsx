import { redirect } from "next/navigation";

/** The classic designer was retired; old links land on the current designer (backup: /tmp/designer_classic.bak). */
export default async function ClassicDesignerRedirect({
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
    if (val) q.set(k, val);
  }
  const qs = q.toString();
  redirect(`/connections/${encodeURIComponent(id)}/designer${qs ? `?${qs}` : ""}`);
}
