"use client";

/**
 * Touch 132: email previews framed as the clients people actually read in. The frames are chrome only;
 * the body is Odoo's own rendered HTML. Dark mode is an approximation of how dark-mode clients repaint.
 */
export type MailClient = "gmail" | "outlook" | "iphone" | "dark";

export const CLIENTS: { id: MailClient; label: string; width: "desktop" | "phone"; note?: string }[] = [
  { id: "gmail", label: "Gmail", width: "desktop" },
  { id: "outlook", label: "Outlook", width: "desktop" },
  { id: "iphone", label: "iPhone Mail", width: "phone" },
  { id: "dark", label: "Dark-mode mail", width: "phone", note: "Approximate: dark clients repaint light backgrounds." },
];

export function darkDoc(html: string): string {
  const head = '<meta name="color-scheme" content="dark"><style>:root{color-scheme:dark}html{filter:invert(1) hue-rotate(180deg);background:#fff}img,picture,video{filter:invert(1) hue-rotate(180deg)}</style>';
  return /<head[^>]*>/i.test(html) ? html.replace(/<head[^>]*>/i, (m) => m + head) : head + html;
}

export function MailClientFrames({ html, subject, from, widths }: { html: string; subject: string; from?: string; widths: { desktop: number; phone: number } }) {
  return (
    <div className="mail-frames" data-testid="mail-frames">
      {CLIENTS.map((c) => (
        <figure key={c.id} className="mail-frame" data-client={c.id}>
          <figcaption className="mail-frame-bar"><span>{c.label}</span>{c.note ? <span className="mail-frame-note">{c.note}</span> : null}</figcaption>
          <div className="mail-frame-head">
            <p className="mail-frame-subject">{subject}</p>
            {from ? <p className="mail-frame-from">{from}</p> : null}
          </div>
          <iframe title={`Email in ${c.label}`} srcDoc={c.id === "dark" ? darkDoc(html) : html} sandbox=""
            style={{ width: widths[c.width], maxWidth: "100%", minHeight: c.width === "phone" ? 480 : 360 }} />
        </figure>
      ))}
    </div>
  );
}
