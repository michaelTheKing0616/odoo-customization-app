"use client";

import Link from "next/link";

const TILES = [
  { href: "/approvals", title: "Approvals", detail: "Plans waiting on a fingerprint." },
  { href: "/bridge/contracts/new", title: "Bridge", detail: "Tier I contract check." },
  { href: "/connect", title: "Connections", detail: "Odoo instances in this workspace." },
  { href: "/settings", title: "Settings", detail: "Keys, sign-in, and audit." },
];

export default function CommandCenterPage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-10">
      <header>
        <h1 className="text-lg font-semibold text-ink">Command center</h1>
        <p className="text-sm text-muted">One place for plans, connections, and the bridge. Counts load on each destination.</p>
      </header>
      <ul className="grid gap-3 sm:grid-cols-2">
        {TILES.map((tile) => (
          <li key={tile.href}>
            <Link
              href={tile.href}
              className="block rounded-md border border-border bg-surface px-4 py-3 transition-colors duration-150 hover:bg-muted"
            >
              <span className="text-sm font-medium text-ink">{tile.title}</span>
              <span className="mt-1 block text-sm text-muted">{tile.detail}</span>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
