export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[radial-gradient(ellipse_at_top,_#3d2a38_0%,_#1a1218_45%,_#0c090b_100%)] text-[#f4eef2]">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.12]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(244,238,242,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(244,238,242,0.08) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
          maskImage: "radial-gradient(ellipse at center, black 20%, transparent 75%)",
        }}
      />
      <div className="relative mx-auto flex min-h-screen max-w-5xl flex-col justify-center px-6 py-16 sm:px-10">
        <p className="font-[family-name:var(--font-display)] text-5xl tracking-tight text-[#c9a9c0] sm:text-7xl">
          Odoo Custom
        </p>
        <h1 className="mt-6 max-w-2xl font-[family-name:var(--font-display)] text-3xl leading-tight text-[#faf6f9] sm:text-5xl">
          No-code Odoo customization for Community — without Enterprise Studio.
        </h1>
        <p className="mt-5 max-w-xl font-[family-name:var(--font-sans)] text-base leading-relaxed text-[#d4c4ce] sm:text-lg">
          Connect any Odoo 19 instance. Build models, fields, views, and
          automations. Sandbox-test, then export a real installable module.
        </p>
        <div className="mt-10 flex flex-wrap gap-3 font-[family-name:var(--font-sans)]">
          <a
            href="/connect"
            className="inline-flex h-12 items-center justify-center bg-[#714B67] px-6 text-sm font-semibold text-white transition hover:bg-[#5d3e55]"
          >
            Connect your Odoo
          </a>
          <a
            href="/pipelines"
            className="inline-flex h-12 items-center justify-center border border-[#3d2a38] px-6 text-sm text-[#d4c4ce] transition hover:border-[#c9a9c0] hover:text-[#c9a9c0]"
          >
            Multi-env promote
          </a>
          <a
            href="/settings"
            className="inline-flex h-12 items-center justify-center border border-[#3d2a38] px-6 text-sm text-[#d4c4ce] transition hover:border-[#c9a9c0] hover:text-[#c9a9c0]"
          >
            API settings
          </a>
        </div>
      </div>
    </main>
  );
}
