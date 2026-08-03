"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Props = {
  onScan: (value: string) => void;
  onError?: (message: string) => void;
  className?: string;
};

export function BarcodeScanner({ onScan, onError, className }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const readerRef = useRef<{ reset?: () => void } | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [active, setActive] = useState(false);
  const [torchOn, setTorchOn] = useState(false);
  const [busy, setBusy] = useState(false);

  const stop = useCallback(() => {
    readerRef.current?.reset?.();
    readerRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setActive(false);
    setTorchOn(false);
  }, []);

  useEffect(() => () => stop(), [stop]);

  const start = useCallback(async () => {
    setBusy(true);
    try {
      const { BrowserMultiFormatReader } = await import("@zxing/browser");
      const reader = new BrowserMultiFormatReader();
      readerRef.current = reader as { reset?: () => void };
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
      });
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) {
        throw new Error("Video element not ready");
      }
      video.srcObject = stream;
      await video.play();
      setActive(true);
      reader.decodeFromVideoDevice(undefined, video, (result) => {
        if (result) {
          onScan(result.getText());
          stop();
        }
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      onError?.(msg);
      stop();
    } finally {
      setBusy(false);
    }
  }, [onError, onScan, stop]);

  async function toggleTorch() {
    const track = streamRef.current?.getVideoTracks()[0];
    if (!track?.getCapabilities) {
      onError?.("Torch not supported on this device/browser");
      return;
    }
    const caps = track.getCapabilities() as MediaTrackCapabilities & { torch?: boolean };
    if (!caps.torch) {
      onError?.("Torch not supported on this camera");
      return;
    }
    const next = !torchOn;
    await track.applyConstraints({ advanced: [{ torch: next }] as unknown as MediaTrackConstraintSet[] });
    setTorchOn(next);
  }

  return (
    <div className={className ?? "space-y-3"}>
      <video
        ref={videoRef}
        className="w-full max-w-md aspect-video rounded border bg-black object-cover"
        playsInline
        muted
      />
      <div className="flex flex-wrap gap-2">
        {!active ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void start()}
            className="h-10 bg-accent px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            {busy ? "Starting…" : "Start camera"}
          </button>
        ) : (
          <button
            type="button"
            onClick={stop}
            className="h-10 border px-4 text-sm font-semibold"
          >
            Stop
          </button>
        )}
        {active && (
          <button type="button" onClick={() => void toggleTorch()} className="h-10 border px-4 text-sm">
            Torch {torchOn ? "off" : "on"}
          </button>
        )}
      </div>
      <p className="text-xs text-[#6C757D]">
        Supports common 1D/2D formats via ZXing (Apache-2.0). Grant camera permission when prompted.
      </p>
    </div>
  );
}
