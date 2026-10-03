"use client";

import { MotionEdgeSurface, type MotionEdgeSurfaceProps } from "./MotionEdgeSurface";

export type DrawerProps = Omit<
  MotionEdgeSurfaceProps,
  "closeLabel" | "panelTestId"
> & {
  closeLabel?: string;
};

export function Drawer({
  closeLabel = "Close drawer",
  testId = "motion-drawer",
  ...props
}: DrawerProps) {
  return (
    <MotionEdgeSurface
      {...props}
      testId={testId}
      closeLabel={closeLabel}
      panelTestId="motion-drawer-panel"
    />
  );
}
