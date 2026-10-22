import type { ComponentProps } from "react";
import { cn } from "@/lib/cn";

/** Touch 1: the keystone loader, the app's only loading mark. The arch stands; the keystone
 * eases down and locks, again and again. It stays invisible for the first second so fast
 * actions never flash it. Name kept as Spokes so every caller moved over at once. */
function Spokes({ className, ...props }: ComponentProps<"svg">) {
  return (
    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={cn("studio-loader-spokes keystone-loader", className)} {...props}>
      {props["aria-hidden"] ? null : <title>Loading...</title>}
      <path d="M4 21v-6.5a8 8 0 0 1 4.2-7M20 21v-6.5a8 8 0 0 0-4.2-7" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
      <path className="kl-stone" d="M9.6 5.4h4.8l-.9 3.6h-3z" fill="currentColor" />
    </svg>
  );
}

export { Spokes };
