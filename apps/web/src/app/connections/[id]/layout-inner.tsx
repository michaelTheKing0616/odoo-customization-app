"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/shell/AppShell";
import { ShellProvider } from "@/context/ShellContext";

export default function ConnectionLayoutInner({ children }: { children: React.ReactNode }) {
  const params = useParams<{ id: string }>();
  return (
    <ShellProvider connectionId={params.id}>
      <AppShell connectionId={params.id}>{children}</AppShell>
    </ShellProvider>
  );
}
