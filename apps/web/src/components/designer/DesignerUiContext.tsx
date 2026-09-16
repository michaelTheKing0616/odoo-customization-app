"use client";

import {
  createContext,
  useContext,
  useMemo,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";
import type { DesignerRailTabId } from "@/components/designer/DesignerToolsRail";
import type { SelectedField } from "@/components/designer/designer-model";

export type DesignerUiContextValue = {
  selected: SelectedField | null;
  setSelected: Dispatch<SetStateAction<SelectedField | null>>;
  railTab: DesignerRailTabId;
  setRailTab: Dispatch<SetStateAction<DesignerRailTabId>>;
  /** Feature flag — progressive shell extractions behind this. */
  designerV2Shell: boolean;
};

const DesignerUiContext = createContext<DesignerUiContextValue | null>(null);

export function DesignerUiProvider({
  children,
  designerV2Shell = true,
  selected: selectedControlled,
  setSelected: setSelectedControlled,
  railTab: railTabControlled,
  setRailTab: setRailTabControlled,
}: {
  children: ReactNode;
  designerV2Shell?: boolean;
  /** Optional controlled selection — page owns state during strangler. */
  selected?: SelectedField | null;
  setSelected?: Dispatch<SetStateAction<SelectedField | null>>;
  railTab?: DesignerRailTabId;
  setRailTab?: Dispatch<SetStateAction<DesignerRailTabId>>;
}) {
  const [selectedInternal, setSelectedInternal] = useState<SelectedField | null>(null);
  const [railTabInternal, setRailTabInternal] = useState<DesignerRailTabId>("fields");

  const selected = selectedControlled !== undefined ? selectedControlled : selectedInternal;
  const setSelected = setSelectedControlled ?? setSelectedInternal;
  const railTab = railTabControlled !== undefined ? railTabControlled : railTabInternal;
  const setRailTab = setRailTabControlled ?? setRailTabInternal;

  const value = useMemo(
    () => ({
      selected,
      setSelected,
      railTab,
      setRailTab,
      designerV2Shell,
    }),
    [selected, setSelected, railTab, setRailTab, designerV2Shell],
  );

  return <DesignerUiContext.Provider value={value}>{children}</DesignerUiContext.Provider>;
}

export function useDesignerUi(): DesignerUiContextValue {
  const ctx = useContext(DesignerUiContext);
  if (!ctx) {
    throw new Error("useDesignerUi must be used within DesignerUiProvider");
  }
  return ctx;
}

/** Safe optional read for panels that may render outside the provider during migration. */
export function useDesignerUiOptional(): DesignerUiContextValue | null {
  return useContext(DesignerUiContext);
}
