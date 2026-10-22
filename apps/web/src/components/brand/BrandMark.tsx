"use client";

import type React from "react";
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
   * auto — colour Keystone for light/dark chrome (default).
   * white — on-dark colour mark (known-dark surfaces).
   * mono — basalt mono mark (known-light surfaces).
   * color — dark-chrome colour mark (legacy alias).
   */
  variant?: "auto" | "white" | "mono" | "color";
};

const MARK = {
  light: "/brand/ingenium-mark-light.png",
  dark: "/brand/ingenium-mark.png",
  mono: "/brand/ingenium-mark-mono.png",
  smallLight: "/brand/ingenium-mark-small-color.svg",
  smallDark: "/brand/ingenium-mark-small-on-dark.svg",
  smallMono: "/brand/ingenium-mark-small-black.svg",
} as const;

function readDomTheme(): "light" | "dark" {
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

function resolveMark(
  variant: NonNullable<Props["variant"]>,
  resolved: "light" | "dark",
  size: number,
): { src: string; mode: "light" | "white" | "mono" | "color"; wantWhite: boolean } {
  const small = size < 32;

  if (variant === "mono") {
    return {
      src: small ? MARK.smallMono : MARK.mono,
      mode: "mono",
      wantWhite: false,
    };
  }
  if (variant === "white") {
    return {
      src: small ? MARK.smallDark : MARK.dark,
      mode: "white",
      wantWhite: true,
    };
  }
  if (variant === "color") {
    return {
      src: small ? MARK.smallDark : MARK.dark,
      mode: "color",
      wantWhite: false,
    };
  }
  // auto — full-colour Keystone in both themes (no invert).
  if (resolved === "dark") {
    return {
      src: small ? MARK.smallDark : MARK.dark,
      mode: "white",
      wantWhite: true,
    };
  }
  return {
    src: small ? MARK.smallLight : MARK.light,
    mode: "light",
    wantWhite: false,
  };
}

/**
 * Ingenium product mark (Keystone v2).
 * Light chrome → mark-light; dark chrome → mark (on-dark). Below 32px → small SVG.
 */
/** Make every on-screen logo do a short keystone settle (e.g. after a publish). */
export function celebrateKeystone() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event("ingenium:keystone"));
}

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

  const [wobble, setWobble] = useState(false);
  useEffect(() => {
    let t: ReturnType<typeof setTimeout> | undefined;
    const on = () => {
      setWobble(true);
      t = setTimeout(() => setWobble(false), 900);
    };
    window.addEventListener("ingenium:keystone", on);
    return () => {
      window.removeEventListener("ingenium:keystone", on);
      if (t) clearTimeout(t);
    };
  }, []);

  const resolved = themeCtx?.resolved ?? domTheme;
  const { src, mode, wantWhite } = resolveMark(variant, resolved, size);
  const isSvg = src.endsWith(".svg");

  const inner = (
    <span
      className={cn("inline-flex items-center gap-2", className)}
      data-brand-variant={mode}
    >
      <span className="relative inline-flex">
      <Image
        src={src}
        alt="Ingenium"
        width={size}
        height={size}
        priority={priority}
        unoptimized={isSvg}
        className={cn("rounded-sm object-contain", wobble && "keystone-wobble")}
        data-testid="brand-mark-image"
      />
      {/* Touch 71: a dozen fine stone-dust particles fall from the keystone, once (0.6 s). */}
      {wobble ? <span className="stone-dust" aria-hidden data-testid="stone-dust">{Array.from({ length: 12 }, (_, i) => <i key={i} style={{ ["--i" as string]: i } as React.CSSProperties} />)}</span> : null}
      </span>
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
