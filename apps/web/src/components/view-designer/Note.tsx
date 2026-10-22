import { Spokes } from "@/components/loading-ui/spokes";
import type { ElementType, ReactNode } from "react";
import { AlertTriangle, Check, CircleAlert, Info } from "@/components/ui/icons";
import styles from "./ViewDesigner.module.css";

export type NoteTone = "info" | "success" | "warning" | "danger" | "busy";

const ICON = { info: Info, success: Check, warning: AlertTriangle, danger: CircleAlert, busy: Spokes } as const;

/** Status line for the builders: icon + text, so status is never colour only (SPEC 8, 10). */
export function Note({
  tone = "info",
  as: Tag = "p",
  className,
  children,
  ...rest
}: { tone?: NoteTone; as?: ElementType; className?: string; children?: ReactNode } & Record<string, unknown>) {
  const Icon = ICON[tone];
  const Body: ElementType = typeof Tag === "string" && ["p", "span", "li", "label"].includes(Tag) ? "span" : "div";
  return (
    <Tag className={[styles.note, className].filter(Boolean).join(" ")} data-tone={tone} {...rest}>
      <Icon aria-hidden />
      <Body className={styles.noteBody}>{children}</Body>
    </Tag>
  );
}
