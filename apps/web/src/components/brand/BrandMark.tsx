"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { useThemeOptional } from "@/components/theme/ThemeProvider";

type Props = {
  href?: string;
  withWordmark?: boolean;
  className?: string;
  size?: number;
  priority?: boolean;
  variant?: "color" | "mono" | "auto";
};

const MARK = {
  color: "/brand/ingenium-mark.png",
  mono: "/brand/ingenium-mark-mono.png",
} as const;

function readDomTheme(): "light" | "dark" {
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

/** Ingenium product mark — mono on light chrome, color on dark. */
export function BrandMark({
  href = "/",
  withWordmark = true,
  className,
  size = 28,
  priority = false,
  variant = "auto",
}: Props) {
  const themeCtx = useThemeOptional();
  const [domTheme, setDomTheme] = useState<"light" | "dark">("light");
  useEffect(() => {
    setDomTheme(readDomTheme());
  }, [themeCtx?.resolved]);

  const resolved = themeCtx?.resolved ?? domTheme;
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
