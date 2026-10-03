"use client";

import { useParams } from "next/navigation";
import { useWizardPage } from "@/components/wizard/use-wizard-page";
import { WizardPageView } from "@/components/wizard/WizardPageView";
import "@/styles/studio-refinement.css";

export default function AppWizardPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const vm = useWizardPage(connectionId);
  return <WizardPageView {...vm} />;
}
