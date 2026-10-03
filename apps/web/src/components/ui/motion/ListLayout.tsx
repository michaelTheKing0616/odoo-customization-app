"use client";

import { createContext, useContext, type ReactNode } from "react";
import { LayoutGroup, motion } from "motion/react";
import { cn } from "@/lib/cn";
import { listItemInitial, listItemRest, listItemTransition } from "./resolve";
import { usePrefersReducedMotion } from "./usePrefersReducedMotion";

type ListLayoutContextValue = {
  stagger: boolean;
  reduced: boolean;
};

const ListLayoutContext = createContext<ListLayoutContextValue>({
  stagger: false,
  reduced: false,
});

export type ListLayoutProps = {
  children: ReactNode;
  className?: string;
  /** Approval inbox and table-like diffs pass false. Default is the 30–80 ms stagger. */
  stagger?: boolean;
  as?: "ul" | "div";
};

export type ListLayoutItemProps = {
  children: ReactNode;
  className?: string;
  index?: number;
  as?: "li" | "div";
};

export function ListLayout({
  children,
  className,
  stagger = true,
  as = "ul",
}: ListLayoutProps) {
  const reduced = usePrefersReducedMotion();
  const Tag = as;

  return (
    <LayoutGroup>
      <ListLayoutContext.Provider value={{ stagger, reduced }}>
        <Tag className={className} data-testid="motion-list-layout">
          {children}
        </Tag>
      </ListLayoutContext.Provider>
    </LayoutGroup>
  );
}

export function ListLayoutItem({
  children,
  className,
  index = 0,
  as = "li",
}: ListLayoutItemProps) {
  const { stagger, reduced } = useContext(ListLayoutContext);
  const MotionTag = as === "div" ? motion.div : motion.li;

  return (
    <MotionTag
      layout={!reduced}
      initial={listItemInitial(reduced)}
      animate={listItemRest(reduced)}
      transition={listItemTransition(index, stagger, reduced)}
      className={cn(className)}
    >
      {children}
    </MotionTag>
  );
}
