"use client";

import { useState, type KeyboardEvent } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import type { EngineViewType, ViewComment } from "@/lib/api/view-engine";
import { orphanThreads, threadsByNode, type Thread } from "@/lib/viewDesigner2a";
import { nodeName, type TreeIndex } from "@/lib/viewEngineOps";
import styles from "./ViewDesigner.module.css";

type Props = {
  connectionId: string;
  model: string;
  viewType: EngineViewType;
  nodeId: string | null;
  index: TreeIndex;
  comments: ViewComment[];
  onChanged: () => void;
  errorText: (err: unknown) => string;
};

function sendOnCmdEnter(e: KeyboardEvent<HTMLTextAreaElement>, send: () => void) {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
    e.preventDefault();
    send();
  }
}

/** Comments pinned to items. ⌘⏎ sends. Threads can be resolved and reopened. */
export function CommentsPanel({ connectionId, model, viewType, nodeId, index, comments, onChanged, errorText }: Props) {
  const [draft, setDraft] = useState("");
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const threads = nodeId ? threadsByNode(comments).get(nodeId) ?? [] : [];
  const orphans = orphanThreads(comments, index);
  const node = nodeId ? index.byId.get(nodeId) : undefined;

  const add = async (body: string, parent: string | null) => {
    if (!nodeId || !body.trim()) return;
    try {
      await api.commentsAdd(connectionId, { model, view_type: viewType, node_id: nodeId, body: body.trim(), parent_id: parent });
      onChanged();
    } catch (err) {
      toast.error(errorText(err));
    }
  };

  const act = (p: Promise<unknown>) => void p.then(onChanged).catch((err) => toast.error(errorText(err)));

  const renderThread = (t: Thread) => (
    <li key={t.root.id} className={styles.thread} data-resolved={t.root.resolved || undefined} data-testid="vd-thread">
      <p>
        <strong>{t.root.author}</strong> {t.root.body}
      </p>
      {t.replies.map((r) => (
        <p key={r.id} className={styles.reply}>
          <strong>{r.author}</strong> {r.body}
        </p>
      ))}
      {replyTo === t.root.id ? (
        <form
          className={styles.stack}
          onSubmit={(e) => {
            e.preventDefault();
            void add(reply, t.root.id).then(() => { setReply(""); setReplyTo(null); });
          }}
        >
          <textarea
            className={styles.textarea}
            aria-label="Reply"
            value={reply}
            maxLength={2000}
            onChange={(e) => setReply(e.target.value)}
            onKeyDown={(e) => sendOnCmdEnter(e, () => void add(reply, t.root.id).then(() => { setReply(""); setReplyTo(null); }))}
          />
          <Button size="sm" type="submit" disabled={!reply.trim()}>Reply</Button>
        </form>
      ) : null}
      <div className={styles.row}>
        <Button size="sm" variant="ghost" onClick={() => setReplyTo(t.root.id)}>Reply</Button>
        <Button size="sm" variant="ghost" onClick={() => act(api.commentsResolve(connectionId, t.root.id, !t.root.resolved))}>
          {t.root.resolved ? "Reopen" : "Resolve"}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => act(api.commentsDelete(connectionId, t.root.id))}>Delete</Button>
      </div>
    </li>
  );

  return (
    <div className={styles.panelBody} data-testid="vd-comments">
      {node ? <h3 className={styles.sectionTitle}>Comments on {nodeName(node)}</h3> : <p className={styles.muted}>Select an item to comment on it.</p>}
      {node ? (
        <form
          className={styles.stack}
          onSubmit={(e) => {
            e.preventDefault();
            void add(draft, null).then(() => setDraft(""));
          }}
        >
          <textarea
            className={styles.textarea}
            aria-label="New comment"
            placeholder="Leave a note for your team. ⌘⏎ to send."
            value={draft}
            maxLength={2000}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => sendOnCmdEnter(e, () => void add(draft, null).then(() => setDraft("")))}
          />
          <Button size="sm" type="submit" disabled={!draft.trim()}>Comment</Button>
        </form>
      ) : null}
      <ul className={styles.list}>{threads.map(renderThread)}</ul>
      {orphans.length ? (
        <>
          <h3 className={styles.sectionTitle}>On items no longer on this screen</h3>
          <ul className={styles.list}>
            {orphans.map((o) => renderThread({ root: o, replies: comments.filter((c) => c.parent_id === o.id) }))}
          </ul>
        </>
      ) : null}
    </div>
  );
}
