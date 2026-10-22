# UI-F10 — input-otp for TOTP evidence (2026-10-05)

Scope: the two-factor step on `/login`, in both of its modes.

- Password login (`/login`). The code is optional because two-factor sign-in may be off.
- OAuth second factor (`/login?oauth_totp=1&token=…`). The code is the only field and is required.

The shared field is `components/auth/TotpCodeInput.tsx` (input-otp, D12). Its validation copy lives in `lib/auth/totp.ts`.

Evidence comes from `apps/web/e2e/ui-f10-totp.spec.ts`, which ran against `pnpm dev` on `:3002` with no API mocking. No request reaches the API: the partial-code state is blocked client-side before any call. Desktop is 1280×900 and narrow is 390×844, both full page.

## axe (wcag2a/aa, 21a/aa, 22aa; no rules disabled)

| Route / state | Desktop | 390 |
|---|---|---|
| `/login`, code pasted ("123 456" → 6 slots) | 0 | — |
| `/login`, empty | — | 0 |
| `/login`, partial code error | 0 | — |
| `/login?oauth_totp=1`, 6 digits typed | — | 0 |

The count is serious plus critical violations. This rule set is stricter than `a11y-primary.spec.ts`, which disables `label`.

## Screenshots

- `login-desktop.png`: password login after a pasted code.
- `login-390.png`: password login, empty.
- `login-error-desktop.png`: 3 digits typed, then Sign in, which shows the inline error.
- `login-oauth-390.png`: the OAuth step with 6 digits, so Complete sign-in is enabled.

## UX audit (12 rows, `T7_UI_MOTION_COPY.md`)

| Area | Result | Note |
|---|---|---|
| Hierarchy | Pass | One primary action per mode: full-width primary "Sign in" or "Complete sign-in". OAuth providers are secondary buttons. Sign-up and reset are a muted text row below a divider. |
| IA | Pass | The fields follow sign-in order: email, password, two-factor code. The OAuth step drops the email and password fields and keeps only the code. |
| Interaction | Pass | The code field accepts typing, paste, and password-manager fill (`autocomplete="one-time-code"`). Slots are 40 px, above the 24 px target minimum. Non-digits are rejected, including "12ab34" typed on a keyboard in Playwright. In the OAuth step the field is focused on load. |
| Feedback | Pass | The active slot shows an accent ring. While verifying, the field is disabled, marks itself busy, and the button reads "Signing in…". In the OAuth step, the button turns on as soon as 6 digits are in. |
| Errors | Pass | A partial code shows one sentence under the field, slot borders turn danger, and no API call is made. The error clears on the next keystroke. Server errors still use the existing `ErrorNotice` above the form. |
| Accessibility | Pass | axe reports 0 on all four states. The visible label is tied to the input with `htmlFor`. The input is described by the help text and by the error, the error is announced as an alert, and the field is marked invalid (vitest asserts the accessible description). Screen-reader speech is not observable here. |
| Cognitive load | Pass | The help text says when the code is needed ("Only if two-factor sign-in is on…") and where it comes from (the authenticator app). Paste accepts "123 456" and "123-456", so nothing has to be retyped (WCAG 3.3.8). |
| Trust | Pass | Nothing is pre-filled. No claim is made about the account's two-factor status, because the page cannot know it before sign-in. |
| Copy | Issue | See the critique below. "Forgot password" sits after "New here?", which groups it with sign-up. Moving it is a copy change outside this card. |
| Forms | Pass | Labels sit above fields with even spacing (`space-y-4` inside a `p-5` card). Required is set only in the OAuth step. Values are kept after an error. |
| Performance | Pass | `input-otp` was already a dependency, so the bundle did not grow. There is no spinner. The only animation is the caret blink: opacity, `motion-safe` only, and static under reduced motion. |
| Business goal | Pass | Users with two-factor sign-in can paste or autofill their code, which removes a retype step at sign-in. |

Not observable from screenshots: keyboard traps, screen-reader output, password-manager fill in a real browser profile (the attribute is asserted, but no live manager was run).

## Copy critique (9 dimensions, scored 1/3/5)

Scores are in this order: Clarity, Task fit, Actionability, Accuracy, Tone, Concision, Accessibility, Ethics, Slop-free.

| String | Scores |
|---|---|
| Label "Two-factor code" (was "2FA code (if enabled)") | 5 5 3 5 5 5 5 5 5 |
| Help, password mode: "Only if two-factor sign-in is on for your account. Leave blank otherwise." | 5 5 5 5 5 3 5 5 5 |
| Help, OAuth step: "The 6 digits shown in your authenticator app." | 5 5 5 5 5 5 5 5 5 |
| Error, partial: "Enter all 6 digits of the code from your authenticator app." | 5 5 5 5 5 5 5 5 5 |
| Error, empty when required: "Enter the 6-digit code from your authenticator app." (the button stays disabled, so this message is a fallback) | 5 5 5 5 5 5 5 5 5 |
| Buttons "Sign in" / "Complete sign-in" / "Signing in…" | 5 5 5 5 5 5 5 5 5 |
| Footer "New here? Create an account · Forgot password" (was an info callout) | 5 3 5 3 5 5 5 5 5 |

Accuracy 3 on the footer: "Forgot password" is not a new-user action. Task fit 3: the footer also shows in the OAuth step, where neither link applies. No string scores 1 on Accuracy or Ethics.
