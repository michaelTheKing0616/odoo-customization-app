"use client";

import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { useTheme } from "@/components/theme/ThemeProvider";

type Props = {
  href?: string;
  /** Show wordmark next to the mark */
  withWordmark?: boolean;
  className?: string;
  /** Pixel size of the square mark */
  size?: number;
  priority?: boolean;
  /** Force a variant; default follows resolved theme */
  variant?: "color" | "mono" | "auto";
};

const MARK = {
  color: "/brand/ingenium-mark.png",
  mono: "/brand/ingenium-mark-mono.png",
} as const;

/** Ingenium product mark — theme-aware; mono on light chrome, color on dark. */
export function BrandMark({
  href = "/",
  withWordmark = true,
  className,
  size = 28,
  priority = false,
  variant = "auto",
}: Props) {
  const { resolved } = useTheme();
  const mode = variant === "auto" ? (resolved === "light" ? "mono" : "color") : variant;
  const src = MARK[mode];

  const inner = (
    <span className={cn("inline-flex items-center gap-2", className)} data-brand-variant={mode}>
      <Image
        src={src}
        alt="Ingenium"
        width={size}
        height={size}
        priority={priority}
        className="rounded-sm object-contain"
        data-testid="brand-mark-image"
      />
      {withWordmark ? (
        <span
          className="font-[family-name:var(--font-display)] text-sm font-semibold tracking-wide text-ink lowercase"
          data-testid="brand-wordmark"
        >
          ingenium
        </span>
      ) : (
        <span className="sr-only">Ingenium</span>
      )}
    </span>
  );

  if (!href) return inner;
  return (
    <Link href={href} className="hover:opacity-90" data-testid="brand-mark">
      {inner}
    </Link>
  );
}
