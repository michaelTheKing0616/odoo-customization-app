"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { EngineNode, Marker, PreviewAsOut, Role, ViewComment } from "@/lib/api/view-engine";
import { openCounts } from "@/lib/viewDesigner2a";
import { messageOf, type ViewDesignerState } from "./useViewDesigner";

/** Stage 2a state around the designer: roles, preview, markers, history scrub, comments. */
export function useDesigner2a(s: ViewDesignerState, connectionId: string) {
  const [roles, setRoles] = useState<Role[]>([]);
  const [previewRole, setPreviewRole] = useState<string>("");
  const [preview, setPreview] = useState<PreviewAsOut | null>(null);
  const [markers, setMarkers] = useState<Record<string, Marker> | null>(null);
  const [scrub, setScrub] = useState<{ tree: EngineNode; label: string } | null>(null);
  const [comments, setComments] = useState<ViewComment[]>([]);
  const [commentsOn, setCommentsOn] = useState(false);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [accessOpen, setAccessOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);

  useEffect(() => {
    let live = true;
    api.roles(connectionId).then((out) => live && setRoles(out.roles)).catch(() => undefined);
    return () => {
      live = false;
    };
  }, [connectionId]);

  // Role preview follows pending changes.
  useEffect(() => {
    if (!previewRole || !s.base) {
      setPreview(null);
      return;
    }
    let live = true;
    const t = window.setTimeout(() => {
      api
        .previewAs(connectionId, { model: s.model, view_type: s.viewType, ops: s.ops }, { role: previewRole })
        .then((out) => live && setPreview(out))
        .catch(() => live && setPreview(null));
    }, 250);
    return () => {
      live = false;
      window.clearTimeout(t);
    };
  }, [previewRole, s.base, s.model, s.viewType, s.ops, connectionId]);

  const loadComments = useCallback(async () => {
    try {
      const out = await api.commentsList(connectionId, s.model, s.viewType);
      setComments(out.comments);
    } catch {
      setComments([]);
    }
  }, [connectionId, s.model, s.viewType]);

  useEffect(() => {
    void loadComments();
    setMarkers(null);
    setScrub(null);
  }, [loadComments]);

  return {
    roles,
    previewRole,
    setPreviewRole,
    preview,
    markers,
    setMarkers,
    scrub,
    setScrub,
    comments,
    commentCounts: openCounts(comments),
    reloadComments: loadComments,
    commentsOn,
    setCommentsOn,
    versionsOpen,
    setVersionsOpen,
    accessOpen,
    setAccessOpen,
    commandOpen,
    setCommandOpen,
    errorText: messageOf,
  };
}
