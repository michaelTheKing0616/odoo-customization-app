import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { StatusPill } from "@/components/ui/StatusPill";

const features = [
  {
    title: "Build",
    body: "Models, fields, views, menus, and automations — live on your Odoo via public RPC.",
  },
  {
    title: "Operate",
    body: "Bulk tools, snapshots, sandbox validation, and module export when you need an escape hatch.",
  },
  {
    title: "Expert",
    body: "Grounded answers from Odoo docs with citations — explain fields, triggers, and errors in context.",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-surface">
      <div className="mx-auto flex min-h-screen max-w-5xl flex-col justify-center px-6 py-16 sm:px-10">
        <p className="font-[family-name:var(--font-display)] text-sm uppercase tracking-widest text-accent">
          Odoo Custom
        </p>
        <h1 className="mt-4 max-w-2xl font-[family-name:var(--font-display)] text-4xl leading-tight text-ink sm:text-5xl">
          No-code Odoo customization for Community — without Enterprise Studio.
        </h1>
        <p className="mt-5 max-w-xl text-base leading-relaxed text-muted sm:text-lg">
          Connect any Odoo 17–19 instance. Build models, fields, views, and automations.
          Sandbox-test, then export a real installable module.
        </p>

        <div className="mt-8 flex flex-wrap items-center gap-2">
          <StatusPill kind="ga" />
          <StatusPill kind="hosting-onprem" />
          <StatusPill kind="hosting-sh" />
          <StatusPill kind="experimental" />
          <span className="text-xs text-muted">
            Community GA on 17–19 · 16 experimental · Online/sh/on-prem supported where RPC allows
          </span>
        </div>

        <div className="mt-10 flex flex-wrap gap-3">
          <Button variant="primary" size="md" asChild>
            <Link href="/connect">Connect your Odoo</Link>
          </Button>
          <Button variant="secondary" size="md" asChild>
            <Link href="/pipelines">Multi-env promote</Link>
          </Button>
          <Button variant="ghost" size="md" asChild>
            <Link href="/settings">API settings</Link>
          </Button>
        </div>

        <div className="mt-16 grid gap-4 sm:grid-cols-3">
          {features.map((f) => (
            <Card key={f.title} className="p-5">
              <h2 className="text-md font-semibold text-ink">{f.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-muted">{f.body}</p>
            </Card>
          ))}
        </div>

        <footer className="mt-16 border-t border-border-subtle pt-6 text-sm text-muted">
          <Link href="/connect" className="text-accent hover:underline">
            Get started
          </Link>
          {" · "}
          <a
            href="https://www.odoo.com/documentation/19.0/"
            className="hover:text-ink"
            target="_blank"
            rel="noreferrer"
          >
            Odoo 19 docs
          </a>
        </footer>
      </div>
    </main>
  );
}
