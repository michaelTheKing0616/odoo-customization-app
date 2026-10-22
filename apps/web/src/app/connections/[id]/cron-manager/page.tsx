import { redirectIntoSuite } from "@/lib/suiteRedirect";

// D1: this tool now lives in the Configuration Suite (upkeep/schedules).
export default async function Page(props: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  return redirectIntoSuite(props.params, props.searchParams, "upkeep/schedules");
}
