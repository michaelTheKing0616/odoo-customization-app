import { redirect } from "next/navigation";

/**
 * There is no separate connections list route yet — the hub lives on /connect
 * (form + saved connections). Keep /connections as a stable URL that lands there.
 */
export default function ConnectionsIndexPage() {
  redirect("/connect");
}
