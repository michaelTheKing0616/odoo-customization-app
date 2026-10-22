"use client";

import Link from "next/link";
import { BuildSpineBar } from "@/components/build/BuildSpineBar";
import { Menu } from "@base-ui/react/menu";
import { Button } from "@/components/ui/Button";
import { SampleCompanyCard } from "@/components/overview/SampleCompanyCard";
import { WelcomeLetter } from "@/components/overview/WelcomeLetter";
import { FirstRunCard } from "@/components/overview/FirstRunCard";
import { Greeting } from "@/components/overview/Greeting";
import { InstanceFingerprintCard } from "@/components/overview/InstanceFingerprintCard";
import type { OverviewPageModel } from "./use-overview-page";

const MORE_LINKS = [
  { href: "client", label: "Client command", testId: "overview-client-command" },
  { href: "builder", label: "Open Builder", testId: "overview-builder" },
  { href: "projects", label: "Projects", testId: "overview-projects" },
] as const;

/** Header actions: App Studio is the one primary CTA; the rest live in an accessible "More" menu. */
export function OverviewActions({ connectionId }: { connectionId: string }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Menu.Root>
        <Menu.Trigger
          data-testid="overview-more"
          className="inline-flex h-8 items-center gap-1 rounded-md border border-border-subtle bg-surface-raised px-3 text-ui-body text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          More <span aria-hidden>▾</span>
        </Menu.Trigger>
        <Menu.Portal>
          <Menu.Positioner sideOffset={6} align="end">
            <Menu.Popup className="z-50 min-w-44 rounded-md border border-border-subtle bg-surface-overlay p-1 shadow-lg outline-none">
              {MORE_LINKS.map((l) => (
                <Menu.Item
                  key={l.href}
                  render={<Link href={`/connections/${connectionId}/${l.href}`} data-testid={l.testId} />}
                  className="block rounded px-2.5 py-1.5 text-ui-body text-ink outline-none data-[highlighted]:bg-accent-subtle"
                >
                  {l.label}
                </Menu.Item>
              ))}
            </Menu.Popup>
          </Menu.Positioner>
        </Menu.Portal>
      </Menu.Root>
      <Button variant="primary" size="sm" asChild>
        <Link href={`/connections/${connectionId}/studio`} data-testid="overview-draft-with-ai">
          App Studio
        </Link>
      </Button>
    </div>
  );
}

/** What is unique from the old chrome: the build spine, first-run help and instance fingerprint. */
export function OverviewHomeChrome({ vm, modelCount }: { vm: OverviewPageModel; modelCount: number | null }) {
  return (
    <>
      <Greeting />
      <WelcomeLetter />
      <div className="mt-8" data-testid="overview-build-spine">
        <BuildSpineBar connectionId={vm.connectionId} />
      </div>
      {modelCount !== null ? <FirstRunCard connectionId={vm.connectionId} modelCount={modelCount} /> : null}
      <SampleCompanyCard connectionId={vm.connectionId} />
      <InstanceFingerprintCard connectionId={vm.connectionId} context="overview" />
    </>
  );
}
