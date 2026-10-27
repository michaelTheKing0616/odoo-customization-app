"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useThemeOptional } from "@/components/theme/ThemeProvider";
import {
  acquireAvatarGl,
  displayName,
  glbSrc,
  previewSrc,
  releaseAvatarGl,
  stateLabel,
  type BotRole,
  type BotState,
} from "@/lib/avatars/playback";
import styles from "./BotAvatar.module.css";

const BotAvatarCanvas = dynamic(
  () => import("./BotAvatarCanvas").then((mod) => mod.BotAvatarCanvas),
  { ssr: false },
);

function hasWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

/** 3D Ingenium Bot. The GLB loads in a separate chunk. Small sizes, reduced motion, and missing WebGL use the preview PNG. */
export function BotAvatar({
  role,
  state = "idle",
  size = 48,
  accent,
  ttsAmplitude = 0,
}: {
  role: BotRole;
  state?: BotState;
  size?: number;
  accent?: string;
  ttsAmplitude?: number;
}) {
  const theme = useThemeOptional();
  const variant = theme?.resolved === "dark" ? "navy" : "light";
  const [reduced, setReduced] = useState(false);
  const [webgl, setWebgl] = useState(false);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [slot, setSlot] = useState(false);

  useEffect(() => {
    setMounted(true);
    setWebgl(hasWebGL());
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReduced(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  useEffect(() => {
    setReady(false);
    setFailed(false);
  }, [role, accent]);

  const eligible = mounted && size > 32 && !reduced && webgl && !failed;
  useEffect(() => {
    if (!eligible) return;
    if (!acquireAvatarGl()) return;
    setSlot(true);
    return () => {
      releaseAvatarGl();
      setSlot(false);
    };
  }, [eligible]);

  const showModel = slot && !failed;
  const label = `${displayName(role)}: ${stateLabel(state)}`;

  return (
    <span
      className={styles.frame}
      style={{ width: size, height: size }}
      role="img"
      aria-label={label}
      data-bot-role={role}
      data-bot-state={state}
      data-bot-mode={showModel && ready ? "glb" : "preview"}
    >
      <img className={styles.media} src={previewSrc(role, variant)} alt="" hidden={showModel && ready} />
      {showModel ? (
        <span className={styles.canvas}>
          <BotAvatarCanvas
            role={role}
            state={state}
            url={glbSrc(role)}
            accent={accent}
            ttsAmplitude={ttsAmplitude}
            onReady={() => setReady(true)}
            onError={() => setFailed(true)}
          />
        </span>
      ) : null}
    </span>
  );
}

export function BotPresenceChip({
  role,
  state = "idle",
}: {
  role: BotRole;
  state?: BotState;
}) {
  return (
    <span className={styles.chip}>
      <BotAvatar role={role} state={state} size={24} />
      <span>{displayName(role)}</span>
      <span className={styles.chipState}>{stateLabel(state)}</span>
    </span>
  );
}
