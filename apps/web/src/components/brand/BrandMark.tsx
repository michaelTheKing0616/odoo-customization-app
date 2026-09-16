"use client";

import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/cn";

type Props = {
  href?: string;
  /** Show wordmark next to the mark */
  withWordmark?: boolean;
  className?: string;
  /** Pixel size of the square mark */
  size?: number;
  priority?: boolean;
};

/** Ingenium product mark — neural-brain logo + optional lowercase wordmark. */
export function BrandMark({
  href = "/",
  withWordmark = true,
  className,
  size = 28,
  priority = false,
}: Props) {
  const inner = (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <Image
        src="/brand/ingenium-logo.png"
        alt="Ingenium"
        width={size}
        height={size}
        priority={priority}
        className="rounded-sm object-contain"
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
