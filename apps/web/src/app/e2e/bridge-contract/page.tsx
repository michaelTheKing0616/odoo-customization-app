"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { BridgeContractStudio, type ValidateFn } from "@/components/bridge/BridgeContractStudio";
import {
  EMPTY_FORM,
  classifyResult,
  networkErrorGuide,
  type ContractForm,
  type FieldErrors,
  type Outcome,
} from "@/lib/bridgeContractScreen";
import "@/components/bridge/bridge-operate.css";

const STATES = [
  "empty",
  "two-way",
  "invalid",
  "validating",
  "passed",
  "refused",
  "error",
  "risk",
  "request",
  "live",
] as const;
type HarnessState = (typeof STATES)[number];

const FILLED: ContractForm = {
  odooId: "odoo-main",
  thirdId: "shopify-store",
  direction: "inbound",
  conflict: "",
  money: true,
  moneyPolicy: "odoo_wins",
};

const TWO_WAY: ContractForm = { ...FILLED, direction: "two_way", conflict: "manual" };

type Fixture = {
  form: ContractForm;
  outcome: Outcome | null;
  errors?: FieldErrors;
  pending?: boolean;
  tab?: "contract" | "request";
};

/** Fixed check time so captures are stable (20:24 UTC). */
const CHECKED_AT = new Date("2026-10-05T20:24:00Z");

function fixtureFor(state: HarnessState): Fixture {
  switch (state) {
    case "two-way":
      return { form: { ...FILLED, direction: "two_way", conflict: "" }, outcome: null };
    case "invalid":
      return {
        form: { ...EMPTY_FORM, odooId: "odoo-main", direction: "two_way" },
        outcome: null,
        errors: {
          thirdId: "Enter the third-party connection id.",
          conflict: "Choose who wins when both sides change the same order.",
        },
      };
    case "validating":
      return { form: FILLED, outcome: null, pending: true };
    case "passed":
      return {
        form: TWO_WAY,
        outcome: classifyResult({ ok: true, tier: "I", direction: "two_way", entities: 1 }),
      };
    case "refused":
      return {
        form: FILLED,
        outcome: classifyResult({
          ok: false,
          tier: "I",
          error:
            "Tier I requires verified connections (verified_at set): odoo:odoo-main (missing), third_party:shopify-store (unverified)",
        }),
      };
    case "error":
      return { form: FILLED, outcome: { kind: "error", guide: networkErrorGuide(502) } };
    case "risk":
      return {
        form: { ...TWO_WAY, conflict: "remote_wins", moneyPolicy: "remote_wins" },
        outcome: null,
      };
    case "request":
      return { form: TWO_WAY, outcome: null, tab: "request" };
    case "live":
    case "empty":
    default:
      return { form: EMPTY_FORM, outcome: null };
  }
}

/** Deterministic Tier I twin for the live harness: unverified unless ids start with "verified-". */
const harnessValidate: ValidateFn = async (contract) => {
  await new Promise((r) => setTimeout(r, 300));
  const odoo = String(contract.odoo_connection_id ?? "");
  const third = String(contract.third_party_connection_id ?? "");
  if (odoo === "offline" || third === "offline") return { status: 503, body: null };
  const refused = [
    !odoo.startsWith("verified-") ? `odoo:${odoo} (unverified)` : null,
    !third.startsWith("verified-") ? `third_party:${third} (unverified)` : null,
  ].filter(Boolean);
  if (refused.length) {
    return {
      status: 200,
      body: {
        ok: false,
        tier: "I",
        error: `Tier I requires verified connections (verified_at set): ${refused.join(", ")}`,
      },
    };
  }
  return {
    status: 200,
    body: { ok: true, tier: "I", direction: String(contract.direction), entities: 1 },
  };
};

function BridgeContractHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const raw = searchParams.get("state") || "empty";
  const state = (STATES.includes(raw as HarnessState) ? raw : "empty") as HarnessState;

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  const fx = fixtureFor(state);
  return (
    <div data-harness-state={state}>
      <BridgeContractStudio
        key={state}
        initialForm={fx.form}
        initialOutcome={fx.outcome}
        initialErrors={fx.errors}
        initialPending={fx.pending}
        initialCheckedAt={CHECKED_AT}
        initialTab={fx.tab}
        validateContract={harnessValidate}
      />
    </div>
  );
}

export default function BridgeContractHarnessPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading harness…</main>}>
      <BridgeContractHarnessInner />
    </Suspense>
  );
}
