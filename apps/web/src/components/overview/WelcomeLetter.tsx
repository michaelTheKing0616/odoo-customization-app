"use client";

import * as React from "react";

/**
 * Touch 127: a short signed welcome note from Tope, shown once.
 * UNPUBLISHED: TOPE_LETTER is a placeholder until Tope supplies his own words.
 * While `published` is false the component renders nothing for anyone.
 */
export const TOPE_LETTER = {
  published: false,
  // PLACEHOLDER — replace with Tope's own text. Do not ship invented words.
  paragraphs: ["[Tope's welcome letter goes here.]"],
  signature: "Tope",
};

const SEEN_KEY = "ingenium.welcome-letter.seen";

export function shouldShowLetter(letter: typeof TOPE_LETTER, seen: boolean): boolean {
  return letter.published && !seen && letter.paragraphs.every((p) => !p.startsWith("[")) && letter.paragraphs.length > 0;
}

export function WelcomeLetter({ letter = TOPE_LETTER }: { letter?: typeof TOPE_LETTER }) {
  const [show, setShow] = React.useState(false);
  React.useEffect(() => {
    let seen = true;
    try { seen = localStorage.getItem(SEEN_KEY) === "1"; } catch { /* storage off: never show */ }
    setShow(shouldShowLetter(letter, seen));
  }, [letter]);
  if (!show) return null;
  const close = () => { try { localStorage.setItem(SEEN_KEY, "1"); } catch { /* ignore */ } setShow(false); };
  return (
    <article className="welcome-letter" data-testid="welcome-letter" aria-label="A note from Tope">
      {letter.paragraphs.map((p) => <p key={p}>{p}</p>)}
      <p className="welcome-letter-sign">{letter.signature}</p>
      <button type="button" className="text-sm underline underline-offset-2" onClick={close}>Close</button>
    </article>
  );
}
