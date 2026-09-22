"use client";

import { useEffect, useState } from "react";
import {
  readBuildSpineHandoff,
  type BuildSpineHandoff,
} from "./build-spine-handoff";

/** Client-only handoff read — avoids SSR/hydration mismatch. */
export function useBuildSpineHandoff(connectionId: string): BuildSpineHandoff | null {
  const [handoff, setHandoff] = useState<BuildSpineHandoff | null>(null);
  useEffect(() => {
    setHandoff(readBuildSpineHandoff(connectionId));
  }, [connectionId]);
  return handoff;
}
