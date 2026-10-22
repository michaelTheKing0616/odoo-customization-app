"use client";
import { useThemeMaybe, type Theme } from "@/components/theme/ThemeProvider";

import * as React from "react";
import { request } from "@/lib/api/client";
import { playSound, setSoundEnabled, soundEnabled } from "@/lib/sound";

/** Opt-in stone sounds (design touches 50-53). Off by default; per browser. */
export function SoundToggle() {
  const [on, setOn] = React.useState(false);
  React.useEffect(() => setOn(soundEnabled()), []);
  return (
    <label className="flex items-start gap-3" data-testid="settings-sound">
      <input
        type="checkbox"
        className="mt-1"
        checked={on}
        onChange={(e) => {
          setSoundEnabled(e.target.checked);
          setOn(e.target.checked);
          if (e.target.checked) playSound("toggle");
        }}
      />
      <span>
        <span className="block font-medium text-ink">Sounds</span>
        <span className="block text-sm text-muted">
          Soft stone sounds when a change is locked in, an approval arrives, or something fails. Everyday clicks stay
          silent. Muted while you present.
        </span>
      </span>
    </label>
  );
}

/** 138: reading comfort, more letter and line spacing in long text. */
/** Touches 121/139: three densities; text never shrinks, hit areas stay large. */
export function DensityPicker() {
  const [v, setV] = React.useState("comfortable");
  React.useEffect(() => setV(localStorage.getItem("ingenium.density") ?? "comfortable"), []);
  return (
    <label className="mt-4 flex items-center gap-3" data-testid="settings-density">
      <span className="font-medium text-ink">List density</span>
      <select
        value={v}
        onChange={(e) => {
          const d = e.target.value;
          localStorage.setItem("ingenium.density", d);
          if (d === "comfortable") document.documentElement.removeAttribute("data-density");
          else document.documentElement.setAttribute("data-density", d);
          setV(d);
        }}
        className="rounded border border-border bg-background px-2 py-1 text-sm"
      >
        <option value="comfortable">Comfortable</option>
        <option value="compact">Compact</option>
        <option value="dense">Dense (spreadsheet-like)</option>
      </select>
    </label>
  );
}

export function ReadingComfortToggle() {
  const [on, setOn] = React.useState(false);
  React.useEffect(() => setOn(localStorage.getItem("ingenium.readingComfort") === "on"), []);
  return (
    <label className="mt-4 flex items-start gap-3" data-testid="settings-reading-comfort">
      <input
        type="checkbox"
        className="mt-1"
        checked={on}
        onChange={(e) => {
          const v = e.target.checked;
          localStorage.setItem("ingenium.readingComfort", v ? "on" : "off");
          document.documentElement.toggleAttribute("data-reading-comfort", v);
          setOn(v);
        }}
      />
      <span>
        <span className="block font-medium text-ink">Reading comfort</span>
        <span className="block text-sm text-muted">More space between letters and lines in long text.</span>
      </span>
    </label>
  );
}

/** Touch 119: follow the computer, or switch at Lagos sunset. */
export function ThemePicker() {
  const ctx = useThemeMaybe();
  if (!ctx) return null;
  const { theme, setTheme } = ctx;
  return (
    <label className="mt-4 flex items-center gap-3" data-testid="settings-theme">
      <span className="font-medium text-ink">Light and dark</span>
      <select value={theme} onChange={(e) => setTheme(e.target.value as Theme)} className="rounded border border-border bg-background px-2 py-1 text-sm">
        <option value="system">Follow my computer</option>
        <option value="sunset">Dark from Lagos sunset to sunrise</option>
        <option value="light">Always light</option>
        <option value="dark">Always dark</option>
      </select>
    </label>
  );
}

/** Touch 117: soften bright Odoo previews when the app is dark. */
export function OdooDimToggle() {
  const [on, setOn] = React.useState(false);
  React.useEffect(() => setOn(localStorage.getItem("ingenium.odooDim") === "on"), []);
  return (
    <label className="mt-4 flex items-start gap-3" data-testid="settings-odoo-dim">
      <input
        type="checkbox"
        className="mt-1"
        checked={on}
        onChange={(e) => {
          const v = e.target.checked;
          localStorage.setItem("ingenium.odooDim", v ? "on" : "off");
          document.documentElement.toggleAttribute("data-odoo-dim", v);
          setOn(v);
        }}
      />
      <span>
        <span className="block font-medium text-ink">Dim Odoo previews in dark mode</span>
        <span className="block text-sm text-muted">Odoo screens stay light, as in Odoo, but glare less at night.</span>
      </span>
    </label>
  );
}

/** Touch 93: the name used in greetings. Empty means no name. */
export function DisplayNameField() {
  const [v, setV] = React.useState("");
  const [state, setState] = React.useState<"idle" | "saving" | "saved" | "error" | "signed_out">("idle");
  React.useEffect(() => {
    request<{ signed_in: boolean; display_name: string | null }>("/api/accounts/whoami").then(
      (r) => { setV(r.display_name ?? ""); if (!r.signed_in) setState("signed_out"); },
      () => undefined,
    );
  }, []);
  const save = async () => {
    setState("saving");
    try {
      const r = await request<{ display_name: string | null }>("/api/accounts/me/display-name", { method: "PATCH", body: JSON.stringify({ display_name: v }) });
      setV(r.display_name ?? "");
      setState("saved");
    } catch {
      setState("error");
    }
  };
  return (
    <form className="mt-4 flex flex-wrap items-center gap-3" data-testid="settings-display-name" onSubmit={(e) => { e.preventDefault(); void save(); }}>
      <label htmlFor="settings-display-name-input" className="font-medium text-ink">What should we call you?</label>
      <input id="settings-display-name-input" value={v} maxLength={60} disabled={state === "signed_out"} onChange={(e) => { setV(e.target.value); setState("idle"); }} placeholder="Leave empty for no name" className="rounded border border-border bg-background px-2 py-1 text-sm" />
      <button type="submit" className="text-sm underline underline-offset-2" disabled={state === "saving" || state === "signed_out"}>{state === "saving" ? "Saving…" : "Save"}</button>
      <span className="text-sm text-muted" role="status">
        {state === "saved" ? (v ? `Saved. We'll call you ${v}.` : "Saved. No name in greetings.") : state === "error" ? "Couldn't save. Try again." : state === "signed_out" ? "Sign in to set a name." : ""}
      </span>
    </form>
  );
}
