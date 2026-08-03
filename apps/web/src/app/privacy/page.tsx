import { Card, PageHeader } from "@/components/ui/layout-primitives";

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <PageHeader title="Privacy Policy" description="Placeholder structure — not legal advice." />
      <Card className="space-y-4 p-6 text-sm text-muted">
        <section>
          <h2 className="font-semibold text-ink">1. Data we collect</h2>
          <p>[Your counsel completes this — account email, Odoo connection metadata, audit logs.]</p>
        </section>
        <section>
          <h2 className="font-semibold text-ink">2. How we use data</h2>
          <p>[Your counsel completes this — service delivery, billing, support.]</p>
        </section>
        <section>
          <h2 className="font-semibold text-ink">3. Processors</h2>
          <p>[Your counsel completes this — Stripe, Paystack, hosting provider.]</p>
        </section>
        <section>
          <h2 className="font-semibold text-ink">4. Your rights</h2>
          <p>[Your counsel completes this — access, deletion, regional rights.]</p>
        </section>
      </Card>
    </main>
  );
}
