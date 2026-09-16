"use client";

import { useMemo, useState } from "react";
import Markdown from "react-markdown";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ExternalLink } from "@/components/ui/icons";
import { api, type ExpertAskResponse } from "@/lib/api";
import { expertGroundingLabel, linkifyCitationMarkers } from "@/lib/expert-journey";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { ExpertCautionFlags } from "./ExpertCautionFlags";
import { CitationChip, ExpertSources } from "./ExpertSources";

function CopyAnswerButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      type="button"
      onClick={() => void copy()}
      data-testid="expert-copy-answer"
    >
      {copied ? "Copied" : "Copy"}
    </Button>
  );
}

function LogToChatterButton({
  connectionId,
  model,
  resId,
  body,
}: {
  connectionId: string;
  model: string;
  resId: number;
  body: string;
}) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  async function post(phrase: string) {
    setBusy(true);
    setNote(null);
    try {
      const res = await api.expertPostToChatter({
        connection_id: connectionId,
        model,
        res_id: resId,
        body_markdown: body,
        confirmed: true,
      });
      setNote(res.message);
      setConfirmOpen(false);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Failed to post note");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        loading={busy}
        data-testid="expert-log-chatter"
        onClick={() => setConfirmOpen(true)}
      >
        Log as Odoo note
      </Button>
      {note ? <span className="text-xs text-muted">{note}</span> : null}
      <ConfirmDialogV2
        open={confirmOpen}
        riskLevel="danger"
        title="Log Expert answer to Odoo?"
        warning={`Posts an internal note on ${model} #${resId}.`}
        risks={[
          "Creates a chatter message on the live Odoo record",
          "Visible to users who can read that record",
        ]}
        blastRadius={[`Model ${model}`, `Record id ${resId}`, "Internal note (not email)"]}
        phrase="I understand the risks"
        busy={busy}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) => void post(phrase)}
      />
    </div>
  );
}

function ExpertAnswerMarkdown({
  markdown,
  citations,
}: {
  markdown: string;
  citations: ExpertAskResponse["citations"];
}) {
  const citationByIndex = useMemo(
    () => new Map(citations.map((c) => [c.source_index, c])),
    [citations],
  );
  const linked = useMemo(() => linkifyCitationMarkers(markdown), [markdown]);

  return (
    <Markdown
      components={{
        a: ({ href, children }) => {
          if (href?.startsWith("#cite-")) {
            const idx = Number.parseInt(href.slice("#cite-".length), 10);
            const citation = citationByIndex.get(idx);
            if (citation) {
              return <CitationChip citation={citation} index={idx} />;
            }
          }
          return (
            <a href={href} className="text-accent hover:underline">
              {children}
            </a>
          );
        },
      }}
    >
      {linked}
    </Markdown>
  );
}

type ExpertAnswerCardProps = {
  response: ExpertAskResponse;
  connectionId: string;
  chatterModel?: string;
  chatterResId?: number;
};

export function ExpertAnswerCard({
  response,
  connectionId,
  chatterModel,
  chatterResId,
}: ExpertAnswerCardProps) {
  const grounding = expertGroundingLabel(response);
  const canLogToChatter = Boolean(chatterModel && chatterResId && chatterResId > 0);

  return (
    <div className="expert-answer-card">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          {grounding ? <Badge variant={grounding.variant}>{grounding.label}</Badge> : null}
        </div>
        <CopyAnswerButton text={response.answer_markdown} />
      </div>
      <ExpertCautionFlags flags={response.caution_flags ?? []} />
      {canLogToChatter ? (
        <div className="mb-2">
          <LogToChatterButton
            connectionId={connectionId}
            model={chatterModel!}
            resId={chatterResId!}
            body={response.answer_markdown}
          />
        </div>
      ) : null}
      <div className="prose prose-sm max-w-none dark:prose-invert" data-testid="expert-answer">
        <ExpertAnswerMarkdown
          markdown={response.answer_markdown}
          citations={response.citations ?? []}
        />
      </div>
      <ExpertSources citations={response.citations ?? []} />
      {response.suggested_tools?.length ? (
        <div className="expert-tool-links" data-testid="expert-suggested-tools">
          {response.suggested_tools.map((tool) => (
            <a
              key={tool.id ?? tool.label}
              href={tool.deep_link ?? "#"}
              className="flex items-center gap-1 text-xs text-accent hover:underline"
            >
              <ExternalLink className="h-3 w-3" />
              {tool.label ?? tool.id}
            </a>
          ))}
        </div>
      ) : null}
    </div>
  );
}
