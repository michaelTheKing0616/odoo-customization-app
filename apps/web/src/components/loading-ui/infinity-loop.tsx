import type { ComponentProps } from "react";
import { cn } from "@/lib/cn";

function InfinityLoop({ className, ...props }: ComponentProps<"svg">) {
  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="xMidYMid"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("studio-loader-infinity", className)}
      {...props}
    >
      {props["aria-hidden"] ? null : <title>Loading...</title>}
      <path
        className="studio-loader-infinity-path"
        d="M24.3 30C11.4 30 5 43.3 5 50s6.4 20 19.3 20c19.3 0 32.1-40 51.4-40C88.6 30 95 43.3 95 50s-6.4 20-19.3 20C56.4 70 43.6 30 24.3 30z"
        stroke="currentColor"
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray="205.271142578125 51.317785644531256"
      />
    </svg>
  );
}

export { InfinityLoop };
