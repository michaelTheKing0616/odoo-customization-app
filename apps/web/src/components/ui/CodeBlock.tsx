"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import { highlightCode, type HighlightLanguage } from "@/lib/highlight";

type CodeBlockProps = {
  code: string;
  language?: HighlightLanguage;
  className?: string;
};

export function CodeBlock({ code, language = "text", className }: CodeBlockProps) {
  const [wrap, setWrap] = useState(false);
  const [copied, setCopied] = useState(false);

  const highlighted = useMemo(() => highlightCode(code, language), [code, language]);

  async function copy() {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div
      className={cn("rounded-md border border-border-subtle bg-surface-muted", className)}
      data-testid="code-block"
    >
      <div className="flex items-center justify-between border-b border-border-subtle px-3 py-1.5">
        <span className="font-mono text-xs uppercase text-muted">{language}</span>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" type="button" onClick={() => setWrap((v) => !v)}>
            {wrap ? "No wrap" : "Wrap lines"}
          </Button>
          <Button variant="ghost" size="sm" type="button" onClick={copy}>
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
      </div>
      <pre
        className={cn(
          "code-block-highlight overflow-auto p-3 font-mono text-xs text-ink",
          wrap ? "whitespace-pre-wrap break-all" : "whitespace-pre",
        )}
      >
        <code dangerouslySetInnerHTML={{ __html: highlighted }} />
      </pre>
    </div>
  );
}
