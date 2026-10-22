"use client";

import { useEffect, useRef, useState } from "react";
import { BrandMark, celebrateKeystone } from "@/components/brand/BrandMark";
import styles from "./ViewDesigner.module.css";

/** The one publish moment (SPEC 7): the first time someone publishes on this connection the
 * Keystone settles once (400ms), then the note goes away. Never again after that. */
export function PublishMoment({ connectionId, count }: { connectionId: string; count: number }) {
  const [show, setShow] = useState(false);
  const seen = useRef(count);
  useEffect(() => {
    if (count <= seen.current) return;
    seen.current = count;
    const key = `ingenium.vd.firstPublish.${connectionId}`;
    try {
      if (window.localStorage.getItem(key)) return;
      window.localStorage.setItem(key, new Date().toISOString());
    } catch {
      return;
    }
    setShow(true);
    celebrateKeystone();
    const t = window.setTimeout(() => setShow(false), 2400);
    return () => window.clearTimeout(t);
  }, [count, connectionId]);
  if (!show) return null;
  return (
    <div className={styles.publishMoment} role="status" data-testid="vd-publish-moment">
      <BrandMark href="" size={20} />
      <span>Your first change is live.</span>
    </div>
  );
}
