import { describe, expect, it } from "vitest";
import { TOPE_LETTER, shouldShowLetter } from "./WelcomeLetter";

describe("WelcomeLetter (touch 127)", () => {
  it("stays unpublished with the placeholder", () => {
    expect(shouldShowLetter(TOPE_LETTER, false)).toBe(false);
    expect(shouldShowLetter({ ...TOPE_LETTER, published: true }, false)).toBe(false);
  });
  it("shows once when Tope's real text is in", () => {
    const real = { published: true, paragraphs: ["Hello."], signature: "Tope" };
    expect(shouldShowLetter(real, false)).toBe(true);
    expect(shouldShowLetter(real, true)).toBe(false);
  });
});
