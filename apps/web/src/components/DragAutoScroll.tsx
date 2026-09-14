"use client";

import { useEffect } from "react";
import { attachDragAutoScroll } from "@/lib/drag-auto-scroll";

/** Global HTML5 drag edge auto-scroll for every page. */
export function DragAutoScroll() {
  useEffect(() => attachDragAutoScroll(), []);
  return null;
}
