import Link from "next/link";
import { ChevronRight } from "@/components/ui/icons";

/** After an App Studio / Draft Studio apply: carry on in View Designer on the real, installed screen. */
export function viewDesignerHref(connectionId: string, model: string, type: "form" | "list" | "kanban" = "form"): string {
  return `/connections/${encodeURIComponent(connectionId)}/view-designer?model=${encodeURIComponent(model)}&type=${type}`;
}

export function OpenInViewDesigner({ connectionId, model, type = "form" }: { connectionId: string; model: string; type?: "form" | "list" | "kanban" }) {
  return (
    <Link href={viewDesignerHref(connectionId, model, type)} data-testid="open-in-view-designer">
      Open in View Designer <ChevronRight size={14} aria-hidden />
    </Link>
  );
}
