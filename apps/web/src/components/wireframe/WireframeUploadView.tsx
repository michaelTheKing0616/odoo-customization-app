"use client";

import { StockMapPanel } from "@/components/wireframe/StockMapPanel";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import { toast } from "sonner";
import { ClarifyInterstitial } from "@/components/studio/ClarifyInterstitial";
import { StudioPreviewPane } from "@/components/studio/StudioPreviewPane";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Input } from "@/components/ui/Input";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import { DURATION, seconds } from "@/components/ui/motion/constants";
import { resolveMotionStyle } from "@/components/ui/motion/resolve";
import { usePrefersReducedMotion } from "@/components/ui/motion/usePrefersReducedMotion";
import { api } from "@/lib/api";
import { reportApiError } from "@/lib/api-error";
import { residualFormPreviewFromDraft } from "@/lib/draft-form-preview";
import type { WireframeOutcome, WireframeStatus } from "@/lib/api/wireframe";

type WireframeUploadViewProps = {
  connectionId: string;
};

export function WireframeUploadView({ connectionId }: WireframeUploadViewProps) {
  const reduced = usePrefersReducedMotion();
  const [status, setStatus] = useState<WireframeStatus | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<WireframeOutcome | null>(null);

  useEffect(() => {
    api
      .wireframeStatus(connectionId)
      .then(setStatus)
      .catch((err: unknown) => {
        reportApiError(err, undefined, { fallback: "Could not check Gemini", toast: true });
      });
  }, [connectionId]);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const formPreview = useMemo(() => {
    if (!outcome?.spec) return outcome?.form_preview ?? null;
    return outcome.form_preview ?? residualFormPreviewFromDraft(outcome.spec);
  }, [outcome]);

  const fade = resolveMotionStyle({ opacity: 1, y: 8 }, reduced);
  const rest = resolveMotionStyle({ opacity: 1, y: 0 }, reduced);
  const transition = {
    type: "tween" as const,
    duration: seconds(reduced ? DURATION.reducedMotionMs : DURATION.dropdownMs),
  };

  async function onRead() {
    if (!file) return;
    setBusy(true);
    try {
      const result = await api.wireframeRead(connectionId, file);
      setOutcome(result);
      if (result.status === "not_connected") {
        toast.error(result.message || "Gemini is not connected");
      } else if (result.status === "error") {
        toast.error(result.message || "Could not read the photograph");
      }
    } catch (err) {
      reportApiError(err, undefined, { fallback: "Could not read the photograph", toast: true });
    } finally {
      setBusy(false);
    }
  }

  async function onClarify(mergeKey: string, answerId: string, answerText?: string) {
    if (!outcome?.sketch) return;
    setBusy(true);
    try {
      const result = await api.wireframeClarify(connectionId, {
        sketch: outcome.sketch,
        merge_key: mergeKey,
        answer_id: answerId,
        answer_text: answerText,
      });
      setOutcome(result);
    } catch (err) {
      reportApiError(err, undefined, { fallback: "Could not apply that answer", toast: true });
    } finally {
      setBusy(false);
    }
  }

  const geminiMissing = status !== null && !status.connected;

  return (
    <div className="studio-refinement" data-testid="wireframe-upload">
      <div className="studio-page">
        <PageHeader
          title="Sketch upload"
          description="Read a photographed form. Review the layout preview. This screen does not apply."
          actions={
            <Link
              href={`/connections/${connectionId}/studio`}
              className="text-ui-body text-muted hover:text-ink"
              data-testid="wireframe-back-studio"
            >
              App Studio
            </Link>
          }
        />

        {geminiMissing ? (
          <Callout variant="warning" title="Gemini is not connected" testId="wireframe-gemini-missing">
            {status?.message || "Add GEMINI_API_KEY to read a photographed sketch."}
          </Callout>
        ) : null}

        <Card className="mt-4 space-y-4 p-4">
          <Input
            id="wireframe-photo"
            label="Photograph"
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif,image/heic,image/heif,application/pdf"
            hint="JPEG, PNG, WebP, or GIF. Keyboard-reachable file input."
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setOutcome(null);
            }}
            data-testid="wireframe-file"
          />
          <Button
            type="button"
            variant="primary"
            disabled={!file || busy || geminiMissing}
            onClick={() => void onRead()}
            data-testid="wireframe-read"
          >
            {busy ? "Reading…" : "Read sketch"}
          </Button>
          <p className="text-xs text-muted" data-testid="wireframe-frontier-note">
            Claude can be selected later. It is not the provider in use today.
          </p>
        </Card>

        {previewUrl && file?.type.startsWith("image/") ? (
          <motion.div
            className="mt-4"
            initial={fade}
            animate={rest}
            transition={transition}
            data-testid="wireframe-image"
          >
            <Card className="p-3">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={previewUrl}
                alt="Uploaded sketch"
                className="max-h-64 w-auto rounded-md border border-border-subtle"
              />
            </Card>
          </motion.div>
        ) : null}

        {outcome?.status === "clarify" && outcome.clarification ? (
          <motion.div
            className="mt-4"
            initial={fade}
            animate={rest}
            transition={transition}
            data-testid="wireframe-clarify"
          >
            <ClarifyInterstitial
              clarification={outcome.clarification}
              busy={busy}
              onAnswer={(mergeKey, answerId, answerText) =>
                void onClarify(mergeKey, answerId, answerText)
              }
            />
          </motion.div>
        ) : null}

        {outcome?.status === "review" && outcome.spec ? (
          <motion.div
            className="mt-4"
            initial={fade}
            animate={rest}
            transition={transition}
            data-testid="wireframe-stage-h"
          >
            <p className="mb-2 text-sm text-muted">
              Form preview. Nothing is written to Odoo from this screen.
            </p>
            <StudioPreviewPane
              draft={outcome.spec}
              preview={formPreview}
              breadcrumb="Sketch"
            />
            {outcome.sketch ? (
              <StockMapPanel
                connectionId={connectionId}
                sketch={outcome.sketch}
                imageUrl={file && file.type.startsWith("image/") ? previewUrl : null}
              />
            ) : null}
          </motion.div>
        ) : null}
      </div>
    </div>
  );
}
