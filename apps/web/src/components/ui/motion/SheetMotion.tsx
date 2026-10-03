"use client";

import { MotionEdgeSurface, type MotionEdgeSurfaceProps } from "./MotionEdgeSurface";

export type SheetMotionProps = Omit<
  MotionEdgeSurfaceProps,
  "closeLabel" | "panelTestId"
> & {
  closeLabel?: string;
};

export function SheetMotion({
  closeLabel = "Close panel",
  testId = "motion-sheet",
  ...props
}: SheetMotionProps) {
  return (
    <MotionEdgeSurface
      {...props}
      testId={testId}
      closeLabel={closeLabel}
      panelTestId="motion-sheet-panel"
    />
  );
}
