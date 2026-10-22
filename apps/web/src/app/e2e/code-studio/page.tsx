"use client";

import { CodeStudioScreen } from "@/components/code-studio/CodeStudioScreen";
import "@/components/code-studio/code-studio-operate.css";
import { installFakeApi } from "./fakeApi";

/**
 * UI-S-18 vision harness: the real Code Studio screen without the app shell.
 * Callers may mock the API (docs/vision-verify/UI-S-18/capture.cjs, e2e/code-studio.spec.ts); without
 * that, a built-in fake connection answers the load reads (see fakeApi.ts).
 */
export default function CodeStudioHarnessPage() {
  if (process.env.NEXT_PUBLIC_E2E !== "1") {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }
  installFakeApi(); // before the screen's first effects run
  return (
    <main className="mx-auto w-full max-w-[1200px] px-4 py-6 sm:px-6" data-testid="code-studio-harness">
      <CodeStudioScreen connectionId="demo-conn" />
    </main>
  );
}
