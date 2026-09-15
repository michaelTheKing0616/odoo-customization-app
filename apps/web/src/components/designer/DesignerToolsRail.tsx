"use client";

import type { ReactNode } from "react";
import { Tabs } from "@/components/ui/Tabs";
import { cn } from "@/lib/cn";

export type DesignerRailTabId = "fields" | "properties" | "structure" | "overlay" | "advanced";

export type DesignerRailTab = {
  id: DesignerRailTabId;
  label: string;
  content: ReactNode;
  hidden?: boolean;
};

type DesignerToolsRailProps = {
  tabs: DesignerRailTab[];
  value: DesignerRailTabId;
  onValueChange: (value: DesignerRailTabId) => void;
  className?: string;
};

export function DesignerToolsRail({
  tabs,
  value,
  onValueChange,
  className,
}: DesignerToolsRailProps) {
  const visible = tabs.filter((tab) => !tab.hidden);
  return (
    <div className={cn("flex min-h-0 flex-1 flex-col p-3", className)} data-testid="designer-tools-rail-inner">
      <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted">
        Modification tools
      </p>
      <Tabs
        className="designer-tools-tabs min-h-0 flex-1"
        value={value}
        onValueChange={(next) => onValueChange(next as DesignerRailTabId)}
        items={visible.map((tab) => ({
          value: tab.id,
          label: tab.label,
          content: tab.content,
        }))}
      />
    </div>
  );
}
