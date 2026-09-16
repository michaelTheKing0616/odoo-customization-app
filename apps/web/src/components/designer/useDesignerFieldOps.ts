"use client";

import type { Dispatch, SetStateAction } from "react";
import type { Connection, FieldRow } from "@/lib/api";
import { ConfirmationRequiredError } from "@/lib/api";
import {
  connectionSupports,
  connectionUnsupportedReason,
  injectStrategyCapabilityId,
} from "@/lib/capabilities";
import {
  uid,
  type DesignerField,
  type FormChild,
  type SelectedField,
  type ViewType,
} from "@/components/designer/designer-model";
import type { NicheWidgetEntry } from "@/components/designer/NicheWidgetPalette";

const CONFIRM_PHRASE = "I understand the risks";

export type DesignerFieldOpsDeps = {
  model: string;
  connectionId: string;
  connection: Connection | null;
  viewType: ViewType;
  api: any;
  fields: FieldRow[];
  setFields: Dispatch<SetStateAction<FieldRow[]>>;
  setFieldsModel: (v: string) => void;
  setBusy: (v: boolean) => void;
  setError: (v: string | null) => void;
  setNotice: (v: string | null) => void;
  confirmPhrase: string;
  setConfirmPhrase: (v: string) => void;
  injectStrategy: "inherit" | "mutate";
  newFieldName: string;
  setNewFieldName: (v: string) => void;
  newFieldLabel: string;
  newFieldType: string;
  formChildren: FormChild[];
  setFormChildren: Dispatch<SetStateAction<FormChild[]>>;
  listColumns: DesignerField[];
  setListColumns: Dispatch<SetStateAction<DesignerField[]>>;
  kanbanFields: DesignerField[];
  setKanbanFields: Dispatch<SetStateAction<DesignerField[]>>;
  setSelected: Dispatch<SetStateAction<SelectedField | null>>;
  announceAction: (message: string, flashId?: string | null, toolbarKey?: string) => void;
  appendFieldToCurrentLayout: (name: string, rows: FieldRow[]) => void;
  refreshModelFieldsOnly: (target: string) => Promise<FieldRow[]>;
  setConfirmMutateOpen: (v: boolean) => void;
};

export function useDesignerFieldOps(deps: DesignerFieldOpsDeps) {
  const {
    model,
    connectionId,
    connection,
    viewType,
    api,
    fields,
    setFields,
    setFieldsModel,
    setBusy,
    setError,
    setNotice,
    confirmPhrase,
    setConfirmPhrase,
    injectStrategy,
    newFieldName,
    setNewFieldName,
    newFieldLabel,
    newFieldType,
    formChildren,
    setFormChildren,
    listColumns,
    setListColumns,
    kanbanFields,
    setKanbanFields,
    setSelected,
    announceAction,
    appendFieldToCurrentLayout,
    refreshModelFieldsOnly,
    setConfirmMutateOpen,
  } = deps;

  async function addNicheWidget(entry: NicheWidgetEntry) {
    if (!model) {
      setError("Select a model first");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let fieldName: string | undefined;
      const support = entry.supporting_field;
      let fieldRows = fields;

      const existing = fields.find(
        (f) =>
          entry.recommended_ttypes.includes(f.ttype) &&
          (!support || f.name === support.name),
      );
      if (existing) {
        fieldName = existing.name;
      } else if (support) {
        if (!fields.some((f) => f.name === support.name)) {
          await api.createField(connectionId, {
            model,
            name: support.name,
            field_description: support.string || support.name,
            ttype: support.ttype,
            inject_into_views: false,
            inject_strategy: "inherit",
            confirm_advanced: true,
            confirm_phrase: CONFIRM_PHRASE,
            ...(support.relation ? { relation: support.relation } : {}),
            ...(support.ttype === "selection"
              ? {
                  selection: [
                    { value: "normal", label: "Normal" },
                    { value: "done", label: "Done" },
                    { value: "blocked", label: "Blocked" },
                  ],
                }
              : {}),
          });
          fieldRows = await api.listFields(connectionId, model);
          setFields(fieldRows);
          setFieldsModel(model);
        }
        fieldName = support.name;
      } else {
        const match = fields.find((f) => entry.recommended_ttypes.includes(f.ttype));
        if (!match) {
          setNotice(
            `Add a ${entry.recommended_ttypes.join("/")} field first for ${entry.label}`,
          );
          return;
        }
        fieldName = match.name;
      }

      const meta = fieldRows.find((f) => f.name === fieldName);
      const node: DesignerField = {
        kind: "field",
        id: uid("f"),
        name: fieldName,
        string: meta?.field_description,
        widget: entry.id,
      };

      if (viewType === "kanban") {
        if (kanbanFields.some((c) => c.name === fieldName && c.widget === entry.id)) return;
        setKanbanFields((cols) => [...cols, node]);
        setSelected({ scope: "kanban", fieldId: node.id });
      } else if (viewType === "list") {
        if (listColumns.some((c) => c.name === fieldName && c.widget === entry.id)) return;
        setListColumns((cols) => [...cols, node]);
        setSelected({ scope: "list", fieldId: node.id });
      } else if (viewType === "form") {
        const firstGroup = formChildren.find((c) => c.kind === "group");
        if (!firstGroup) {
          setNotice("Add a form group before niche widgets");
          return;
        }
        setFormChildren((children) =>
          children.map((child) =>
            child.kind === "group" && child.id === firstGroup.id
              ? { ...child, children: [...child.children, node] }
              : child,
          ),
        );
        setSelected({ scope: "form-group", groupId: firstGroup.id, fieldId: node.id });
      } else {
        setNotice(`${entry.label} is available on form, list, and kanban views`);
        return;
      }
      announceAction(`Added ${entry.label} (${entry.id})`, node.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add niche widget");
    } finally {
      setBusy(false);
    }
  }

  function removeFormField(
    container: "group" | "page",
    containerId: string,
    fieldId: string,
    notebookId?: string,
  ) {
    setFormChildren((children) =>
      children.map((child) => {
        if (container === "group" && child.kind === "group" && child.id === containerId) {
          return { ...child, children: child.children.filter((f) => f.id !== fieldId) };
        }
        if (
          container === "page" &&
          child.kind === "notebook" &&
          child.id === notebookId
        ) {
          return {
            ...child,
            pages: child.pages.map((p) =>
              p.id === containerId
                ? { ...p, children: p.children.filter((f) => f.id !== fieldId) }
                : p,
            ),
          };
        }
        return child;
      }),
    );
    setSelected((sel) => (sel?.fieldId === fieldId ? null : sel));
  }

  async function createNewFieldWithInject(opts?: {
    confirm_advanced?: boolean;
    confirm_phrase?: string;
  }) {
    if (!model || !newFieldName.startsWith("x_")) return;
    const strategyCap = injectStrategyCapabilityId(injectStrategy);
    if (!connectionSupports(connection, strategyCap)) {
      setError(
        connectionUnsupportedReason(connection, strategyCap) ??
          "Inject strategy unavailable on this Odoo version",
      );
      return;
    }
    if (injectStrategy === "mutate" && !opts?.confirm_advanced) {
      setConfirmMutateOpen(true);
      return;
    }
    setBusy(true);
    setError(null);
    const createdName = newFieldName;
    try {
      await api.createField(connectionId, {
        model,
        name: createdName,
        field_description: newFieldLabel || createdName,
        ttype: newFieldType,
        inject_into_views: true,
        inject_strategy: injectStrategy,
        ...(injectStrategy === "mutate"
          ? {
              confirm_advanced: true,
              confirm_phrase:
                opts?.confirm_phrase || confirmPhrase || CONFIRM_PHRASE,
            }
          : {
              confirm_advanced: true,
              confirm_phrase: confirmPhrase || CONFIRM_PHRASE,
            }),
        ...(newFieldType === "many2one" ? { relation: "res.partner" } : {}),
        ...(newFieldType === "selection"
          ? {
              selection: [
                { value: "a", label: "A" },
                { value: "b", label: "B" },
              ],
            }
          : {}),
      });
      setNewFieldName("");
      setConfirmMutateOpen(false);
      // Soft refresh: keep loaded Form layout; do not call loadModelFields (that reseeds/wipes).
      const rows = await refreshModelFieldsOnly(model);
      appendFieldToCurrentLayout(createdName, rows);
      setNotice(
        `Created ${createdName}` +
          (injectStrategy === "mutate" ? " (mutate inject)" : " (inherit inject)") +
          ". Field list and layout kept — no need to reload the view.",
      );
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmMutateOpen(true);
        setError(`${err.warning} Type “${err.confirm_phrase}” and retry.`);
        setConfirmPhrase(err.confirm_phrase || CONFIRM_PHRASE);
      } else {
        setError(err instanceof Error ? err.message : "Create field failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return {
    addNicheWidget,
    removeFormField,
    createNewFieldWithInject,
  };
}
