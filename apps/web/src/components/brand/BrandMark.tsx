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
  /**
   * auto — white on dark chrome, dark mono on light (default).
   * white — always white (known-dark surfaces).
   * mono — always dark ink (known-light surfaces).
   * color — legacy color mark (avoid for chrome; washes out on dark).
   */
  variant?: "auto" | "white" | "mono" | "color";
};

const MARK = {
  color: "/brand/ingenium-mark.png",
  mono: "/brand/ingenium-mark-mono.png",
} as const;

function readDomTheme(): "light" | "dark" {
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

/**
 * Ingenium product mark.
 * Dark backgrounds need a white mark — the color PNG washes out on navy/dark chrome.
 */
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
  const wantWhite =
    variant === "white" || (variant === "auto" && resolved === "dark");
  const useColor = variant === "color";
  const src = useColor ? MARK.color : MARK.mono;
  const mode = useColor ? "color" : wantWhite ? "white" : "mono";

  const inner = (
    <span
      className={cn("inline-flex items-center gap-2", className)}
      data-brand-variant={mode}
    >
      <Image
        src={src}
        alt="Ingenium"
        width={size}
        height={size}
        priority={priority}
        className={cn(
          "rounded-sm object-contain",
          // Mono asset is dark ink; invert to white for dark chrome.
          wantWhite && "brightness-0 invert",
        )}
        data-testid="brand-mark-image"
      />
      {withWordmark ? (
        <span
          className={cn(
            "font-[family-name:var(--font-display)] text-sm font-semibold tracking-wide lowercase",
            wantWhite ? "text-white" : "text-ink",
          )}
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
