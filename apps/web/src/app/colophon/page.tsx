import Link from "next/link";

/** Touch 152: a colophon. */
export default function ColophonPage() {
  return (
    <main className="mx-auto max-w-xl px-6 py-16 text-ink">
      <h1 className="text-2xl font-semibold">Colophon</h1>
      <p className="mt-4 text-muted">
        Ingenium is named for the engineer&apos;s gift for making things that hold. Its mark is a keystone: the last
        stone set in an arch, the one that locks the others in place. Every change Ingenium makes is checked, approved
        and locked in the same way, and every one can be undone.
      </p>
      <h2 className="mt-10 text-lg font-semibold">Type</h2>
      <ul className="mt-3 space-y-1 text-muted">
        <li>Titles in Libre Franklin, the wordmark&apos;s own family.</li>
        <li>Interface in Geist.</li>
        <li>Technical names in Geist Mono.</li>
      </ul>
      <h2 className="mt-10 text-lg font-semibold">Sound</h2>
      <p className="mt-3 text-muted">
        Stone and wood recordings from Kenney&apos;s Impact Sounds, released into the public domain (CC0). Off unless
        you turn them on in Settings.
      </p>
      <p className="mt-10">
        <Link href="/" className="underline underline-offset-4">
          Back home
        </Link>
      </p>
    </main>
  );
}
