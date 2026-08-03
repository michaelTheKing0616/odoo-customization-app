import { Card, PageHeader } from "@/components/ui/layout-primitives";

export default function TermsPage() {
  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <PageHeader title="Terms of Service" description="Placeholder structure — not legal advice." />
      <Card className="space-y-4 p-6 text-sm text-muted">
        <section>
          <h2 className="font-semibold text-ink">1. Agreement</h2>
          <p>[Your counsel completes this section — binding terms between you and your customers.]</p>
        </section>
        <section>
          <h2 className="font-semibold text-ink">2. Service description</h2>
          <p>[Your counsel completes this — Odoo customization platform, no ERP hosting.]</p>
        </section>
        <section>
          <h2 className="font-semibold text-ink">3. Acceptable use</h2>
          <p>[Your counsel completes this — prohibited uses, account termination.]</p>
        </section>
        <section>
          <h2 className="font-semibold text-ink">4. Limitation of liability</h2>
          <p>[Your counsel completes this.]</p>
        </section>
      </Card>
    </main>
  );
}
