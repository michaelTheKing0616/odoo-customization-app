"use client";

import { useCallback, useEffect } from "react";
import { useParams } from "next/navigation";
import { DesignerLiveCanvas } from "@/components/designer/DesignerLiveCanvas";
import { DesignerPageExtras } from "@/components/designer/DesignerPageExtras";
import { DesignerPageNotices } from "@/components/designer/DesignerPageNotices";
import { DesignerSessionBar } from "@/components/designer/DesignerSessionBar";
import { DesignerStudioRail } from "@/components/designer/DesignerStudioRail";
import { DesignerStudioShell } from "@/components/designer/DesignerStudioShell";
import { DesignerStudioToolbar } from "@/components/designer/DesignerStudioToolbar";
import { DesignerStructuralCanvas } from "@/components/designer/DesignerStructuralCanvas";
import { DesignerUiProvider } from "@/components/designer/DesignerUiContext";
import {
  designerLiveCanvasHandlers,
  designerRailProps,
  designerSessionBarProps,
  designerStructuralProps,
  designerToolbarProps,
} from "@/components/designer/designerPageViewProps";
import { useDesignerCanvasMutations } from "@/components/designer/useDesignerCanvasMutations";
import { useDesignerFieldInspector } from "@/components/designer/useDesignerFieldInspector";
import { useDesignerPageModel } from "@/components/designer/useDesignerPageModel";
import { useDesignerPersist } from "@/components/designer/useDesignerPersist";
import { useDesignerViewSpecs } from "@/components/designer/useDesignerViewSpecs";
import { api } from "@/lib/api";

export default function DesignerPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const m = useDesignerPageModel(connectionId);

  const { dateFieldsForSelect, activeViewSpec } = useDesignerViewSpecs({
    ...m.viewSpecsInput,
  });

  const refreshPreview = useCallback(async () => {
    if (!m.model) return;
    try {
      const res = await api.previewViewArch(connectionId, m.viewType, activeViewSpec);
      m.setArch(res.arch);
    } catch (err) {
      m.setError(err instanceof Error ? err.message : "Preview failed");
    }
  }, [connectionId, activeViewSpec, m.model, m.viewType, m.setArch, m.setError]);

  useEffect(() => {
    refreshPreview();
  }, [refreshPreview]);

  const mutations = useDesignerCanvasMutations({
    ...m.mutationsInput,
  });

  const persist = useDesignerPersist({
    ...m.persistInput,
    activeViewSpec,
  });

  const selectedField = mutations.findSelectedField();
  const { fieldInspector } = useDesignerFieldInspector({
    ...m.inspectorInput,
    selectedField,
    updateSelectedField: mutations.updateSelectedField,
    removeSelectedField: mutations.removeSelectedField,
  });

  return (
    <DesignerUiProvider
      selected={m.selected}
      setSelected={m.setSelected}
      railTab={m.railTab}
      setRailTab={m.setRailTab}
      designerV2Shell
    >
      <DesignerStudioShell
        title="View designer"
        description={`${m.connection?.name ?? connectionId} · drag onto the live or layout canvas · Save to Odoo publishes an inherit view`}
        sessionBar={
          <DesignerSessionBar {...designerSessionBarProps(m, persist)} />
        }
        notices={<DesignerPageNotices m={m} />}
        toolbar={
          <DesignerStudioToolbar {...designerToolbarProps(m, persist, dateFieldsForSelect)} />
        }
        canvas={
          <DesignerLiveCanvas
            {...designerLiveCanvasHandlers(m)}
            structural={
              <DesignerStructuralCanvas {...designerStructuralProps(m, mutations)} />
            }
          />
        }
        rail={
          <DesignerStudioRail
            {...designerRailProps(m, persist, fieldInspector, mutations)}
          />
        }
        extras={
          <DesignerPageExtras m={m} mutations={mutations} persist={persist} />
        }
      />
    </DesignerUiProvider>
  );
}
