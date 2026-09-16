"use client";

import type { Dispatch, DragEvent, SetStateAction } from "react";
import type { ActivityTypeRow, Connection, FieldRow, MailTemplateRow } from "@/lib/api";
import type { BindableAction } from "@/components/designer/DesignerBindPanel";
import { ConfirmationRequiredError } from "@/lib/api";
import {
  bindModeSupported,
  bindModeUnsupportedReason,
} from "@/lib/capabilities";
import {
  uid,
  type BindDialogMode,
  type ButtonPlacement,
  type DesignerButton,
  type DesignerField,
  type FormChild,
  type SelectedField,
} from "@/components/designer/designer-model";
import type { DesignerFieldInspectorValues } from "@/components/designer/DesignerFieldInspector";
import type { DesignerRailTabId } from "@/components/designer/DesignerToolsRail";
import { insertAt } from "@/lib/designer-dnd";

const CONFIRM_PHRASE = "I understand the risks";

export type DesignerCanvasMutationsDeps = {
  model: string;
  connectionId: string;
  connection: Connection | null;
  selected: SelectedField | null;
  setSelected: Dispatch<SetStateAction<SelectedField | null>>;
  setRailTab: (v: DesignerRailTabId) => void;
  formChildren: FormChild[];
  setFormChildren: Dispatch<SetStateAction<FormChild[]>>;
  listColumns: DesignerField[];
  setListColumns: Dispatch<SetStateAction<DesignerField[]>>;
  searchFields: DesignerField[];
  setSearchFields: Dispatch<SetStateAction<DesignerField[]>>;
  kanbanFields: DesignerField[];
  setKanbanFields: Dispatch<SetStateAction<DesignerField[]>>;
  headerButtons: DesignerButton[];
  setHeaderButtons: Dispatch<SetStateAction<DesignerButton[]>>;
  buttonBox: DesignerButton[];
  setButtonBox: Dispatch<SetStateAction<DesignerButton[]>>;
  setBusy: (v: boolean) => void;
  setError: (v: string | null) => void;
  setNotice: (v: string | null) => void;
  pendingCoalesceRef: { current: string | undefined };
  pendingHistoryLabelRef: { current: string | undefined };
  dragField: string | null;
  setDragField: (v: string | null) => void;
  bindMode: BindDialogMode;
  setBindMode: (v: BindDialogMode) => void;
  bindPlacement: ButtonPlacement;
  setBindPlacement: (v: ButtonPlacement) => void;
  bindLabel: string;
  setBindLabel: (v: string) => void;
  bindFieldName: string;
  bindValue: string;
  bindTargetModel: string;
  bindRelationField: string;
  bindIcon: string;
  bindCreateCountField: boolean;
  bindOne2manyField: string;
  bindCountFieldName: string;
  bindSmartConfirmPhrase: string;
  setBindSmartConfirmPhrase: (v: string) => void;
  selectedActionId: number | "";
  bindActivityTypeId: number | "";
  bindActivitySummary: string;
  bindActivityNote: string;
  bindMailTemplateId: number | "";
  bindMailMethod: "email" | "comment" | "note";
  bindMailSubject: string;
  bindMailBody: string;
  bindMailEmailTo: string;
  fields: FieldRow[];
  setBindableActions: Dispatch<SetStateAction<BindableAction[]>>;
  setSelectedActionId: Dispatch<SetStateAction<number | "">>;
  setActivityTypes: Dispatch<SetStateAction<ActivityTypeRow[]>>;
  setBindActivityTypeId: Dispatch<SetStateAction<number | "">>;
  setMailTemplates: Dispatch<SetStateAction<MailTemplateRow[]>>;
  setBindMailTemplateId: Dispatch<SetStateAction<number | "">>;
  api: any;
  announceAction: (message: string, flashId?: string | null, toolbarKey?: string) => void;
};

export function useDesignerCanvasMutations(deps: DesignerCanvasMutationsDeps) {
  const {
    model,
    connectionId,
    connection,
    selected,
    setSelected,
    setRailTab,
    formChildren,
    setFormChildren,
    listColumns,
    setListColumns,
    searchFields,
    setSearchFields,
    kanbanFields,
    setKanbanFields,
    headerButtons,
    setHeaderButtons,
    buttonBox,
    setButtonBox,
    setBusy,
    setError,
    setNotice,
    pendingCoalesceRef,
    pendingHistoryLabelRef,
    dragField,
    setDragField,
    bindMode,
    setBindMode,
    bindPlacement,
    setBindPlacement,
    bindLabel,
    setBindLabel,
    bindFieldName,
    bindValue,
    bindTargetModel,
    bindRelationField,
    bindIcon,
    bindCreateCountField,
    bindOne2manyField,
    bindCountFieldName,
    bindSmartConfirmPhrase,
    setBindSmartConfirmPhrase,
    selectedActionId,
    bindActivityTypeId,
    bindActivitySummary,
    bindActivityNote,
    bindMailTemplateId,
    bindMailMethod,
    bindMailSubject,
    bindMailBody,
    bindMailEmailTo,
    fields,
    setBindableActions,
    setSelectedActionId,
    setActivityTypes,
    setBindActivityTypeId,
    setMailTemplates,
    setBindMailTemplateId,
    api,
    announceAction,
  } = deps;

  function moveKanbanField(fieldId: string, dir: -1 | 1) {
    setKanbanFields((cols) => {
      const idx = cols.findIndex((f) => f.id === fieldId);
      if (idx < 0) return cols;
      const next = idx + dir;
      if (next < 0 || next >= cols.length) return cols;
      const copy = [...cols];
      const [item] = copy.splice(idx, 1);
      copy.splice(next, 0, item);
      return copy;
    });
  }

  function findSelectedField(): DesignerField | null {
    if (!selected) return null;
    if (selected.scope === "list") {
      return listColumns.find((f) => f.id === selected.fieldId) ?? null;
    }
    if (selected.scope === "search") {
      return searchFields.find((f) => f.id === selected.fieldId) ?? null;
    }
    if (selected.scope === "kanban") {
      return kanbanFields.find((f) => f.id === selected.fieldId) ?? null;
    }
    if (selected.scope === "form-group") {
      for (const child of formChildren) {
        if (child.kind === "group" && child.id === selected.groupId) {
          const hit = child.children.find((f) => f.id === selected.fieldId);
          return hit && hit.kind === "field" ? hit : null;
        }
      }
      return null;
    }
    for (const child of formChildren) {
      if (child.kind === "notebook" && child.id === selected.notebookId) {
        const page = child.pages.find((p) => p.id === selected.pageId);
        const hit = page?.children.find((f) => f.id === selected.fieldId);
        return hit && hit.kind === "field" ? hit : null;
      }
    }
    return null;
  }

  function removeSelectedField() {
    if (!selected) return;
    const fieldId = selected.fieldId;
    if (selected.scope === "list") {
      setListColumns((cols) => cols.filter((c) => c.id !== fieldId));
    } else if (selected.scope === "search") {
      setSearchFields((cols) => cols.filter((c) => c.id !== fieldId));
    } else if (selected.scope === "kanban") {
      setKanbanFields((cols) => cols.filter((c) => c.id !== fieldId));
    } else if (selected.scope === "form-group") {
      const groupId = selected.groupId;
      setFormChildren((children) =>
        children.map((child) => {
          if (child.kind !== "group" || child.id !== groupId) return child;
          return {
            ...child,
            children: child.children.filter((n) => n.id !== fieldId),
          };
        }),
      );
    } else {
      const { notebookId, pageId } = selected;
      setFormChildren((children) =>
        children.map((child) => {
          if (child.kind !== "notebook" || child.id !== notebookId) return child;
          return {
            ...child,
            pages: child.pages.map((p) =>
              p.id !== pageId
                ? p
                : {
                    ...p,
                    children: p.children.filter((n) => n.id !== fieldId),
                  },
            ),
          };
        }),
      );
    }
    setSelected(null);
  }

  function updateSelectedField(patch: Partial<DesignerFieldInspectorValues>) {
    if (!selected) return;
    pendingCoalesceRef.current = `inspector:${selected.fieldId}`;
    pendingHistoryLabelRef.current = "Edit field properties";
    const { ttype: _ttype, name: _name, ...fieldPatch } = patch;
    if (selected.scope === "list") {
      setListColumns((cols) =>
        cols.map((f) => (f.id === selected.fieldId ? { ...f, ...fieldPatch } : f)),
      );
      return;
    }
    if (selected.scope === "search") {
      setSearchFields((cols) =>
        cols.map((f) => (f.id === selected.fieldId ? { ...f, ...fieldPatch } : f)),
      );
      return;
    }
    if (selected.scope === "kanban") {
      setKanbanFields((cols) =>
        cols.map((f) => (f.id === selected.fieldId ? { ...f, ...fieldPatch } : f)),
      );
      return;
    }
    if (selected.scope === "form-group") {
      setFormChildren((children) =>
        children.map((child) => {
          if (child.kind !== "group" || child.id !== selected.groupId) return child;
          return {
            ...child,
            children: child.children.map((node) => {
              if (node.id !== selected.fieldId || node.kind !== "field") return node;
              return { ...node, ...fieldPatch };
            }),
          };
        }),
      );
      return;
    }
    setFormChildren((children) =>
      children.map((child) => {
        if (child.kind !== "notebook" || child.id !== selected.notebookId) return child;
        return {
          ...child,
          pages: child.pages.map((p) => {
            if (p.id !== selected.pageId) return p;
            return {
              ...p,
              children: p.children.map((node) => {
                if (node.id !== selected.fieldId || node.kind !== "field") return node;
                return { ...node, ...fieldPatch };
              }),
            };
          }),
        };
      }),
    );
  }

  function addGroup() {
    const id = uid("g");
    setFormChildren((c) => [
      ...c,
      { kind: "group", id, string: `Group ${c.length + 1}`, children: [] },
    ]);
    announceAction(`Added group “Group ${formChildren.length + 1}” on the canvas.`, id, "group");
  }

  function addNotebook() {
    const id = uid("n");
    const pageLabel = "Page 1";
    setFormChildren((c) => [
      ...c,
      {
        kind: "notebook",
        id,
        pages: [{ id: uid("p"), string: pageLabel, children: [] }],
      },
    ]);
    announceAction(
      "Added notebook (tab strip) on the canvas below. Prefer “+ Page” on this notebook for another tab — not another notebook.",
      id,
      "notebook",
    );
  }

  function addPageToNotebook(notebookId: string) {
    const pageId = uid("p");
    let pageName = "Page";
    setFormChildren((children) =>
      children.map((child) => {
        if (child.kind !== "notebook" || child.id !== notebookId) return child;
        const n = child.pages.length + 1;
        pageName = `Page ${n}`;
        return {
          ...child,
          pages: [
            ...child.pages,
            { id: pageId, string: pageName, children: [] },
          ],
        };
      }),
    );
    announceAction(`Added tab “${pageName}” to the notebook.`, pageId, "page");
  }

  function removeFormChild(childId: string) {
    const target = formChildren.find((c) => c.id === childId);
    setFormChildren((children) => children.filter((c) => c.id !== childId));
    setSelected((sel) => {
      if (!sel) return null;
      if (sel.scope === "form-group" && sel.groupId === childId) return null;
      if (sel.scope === "form-page" && sel.notebookId === childId) return null;
      return sel;
    });
    announceAction(
      target?.kind === "notebook" ? "Removed notebook from canvas." : "Removed group from canvas.",
      null,
      "remove",
    );
  }

  function removeNotebookPage(notebookId: string, pageId: string) {
    setFormChildren((children) =>
      children
        .map((child) => {
          if (child.kind !== "notebook" || child.id !== notebookId) return child;
          const pages = child.pages.filter((p) => p.id !== pageId);
          if (pages.length === 0) return null;
          return { ...child, pages };
        })
        .filter((c): c is FormChild => c != null),
    );
    setSelected((sel) =>
      sel?.scope === "form-page" && sel.pageId === pageId ? null : sel,
    );
    announceAction("Removed notebook page (tab).", null, "remove");
  }

  function renameNotebookPage(notebookId: string, pageId: string, string: string) {
    setFormChildren((children) =>
      children.map((child) => {
        if (child.kind !== "notebook" || child.id !== notebookId) return child;
        return {
          ...child,
          pages: child.pages.map((p) =>
            p.id === pageId ? { ...p, string: string || p.string } : p,
          ),
        };
      }),
    );
  }

  function renameGroup(groupId: string, string: string) {
    setFormChildren((children) =>
      children.map((child) =>
        child.kind === "group" && child.id === groupId
          ? { ...child, string: string || child.string }
          : child,
      ),
    );
  }

  function openBindDialog(placement: ButtonPlacement, mode: BindDialogMode = "create_update") {
    setBindPlacement(placement);
    setBindMode(mode);
    setError(null);
    if (mode === "bind_existing" && model) {
      void api
        .listBindableActions(connectionId, model)
        .then((rows: BindableAction[]) => {
          setBindableActions(rows);
          setSelectedActionId(rows[0]?.id ?? "");
        })
        .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to list actions"));
    }
    if (mode === "create_activity") {
      void api
        .listActivityTypes(connectionId)
        .then((rows: ActivityTypeRow[]) => {
          setActivityTypes(rows);
          setBindActivityTypeId(rows[0]?.id ?? "");
        })
        .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to list activity types"));
    }
    if (mode === "create_mail" && model) {
      void api
        .listMailTemplates(connectionId, model)
        .then((rows: MailTemplateRow[]) => {
          setMailTemplates(rows);
          setBindMailTemplateId(rows[0]?.id ?? "");
        })
        .catch(() => setMailTemplates([]));
    }
  }

  function placeBoundButton(btn: DesignerButton) {
    if (bindPlacement === "header") {
      setHeaderButtons((all) => [...all, btn]);
    } else if (bindPlacement === "button_box") {
      setButtonBox((all) => [
        ...all,
        {
          ...btn,
          class_name: btn.class_name || "oe_stat_button",
          icon: btn.icon || bindIcon || "fa-list",
        },
      ]);
    } else {
      setFormChildren((children) => {
        if (!children.length) {
          return [{ kind: "group", id: uid("g"), string: "Main", children: [btn] }];
        }
        return children.map((child, idx) => {
          if (idx !== 0 || child.kind !== "group") return child;
          return { ...child, children: [...child.children, btn] };
        });
      });
    }
  }

  async function submitBindDialog(opts?: {
    confirm_advanced?: boolean;
    confirm_phrase?: string;
  }) {
    if (!model) {
      setError("Enter a model first");
      return;
    }
    if (bindMode !== "closed" && !bindModeSupported(connection, bindMode)) {
      setError(
        bindModeUnsupportedReason(connection, bindMode) ??
          "Bind mode unavailable on this Odoo version",
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (bindMode === "create_update") {
        const created = await api.createUpdateFieldAction(connectionId, {
          name: bindLabel,
          model,
          field_name: bindFieldName,
          value: bindValue,
          bind_to_model: true,
        });
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: bindLabel,
          name: String(created.id),
          type: "action",
          class_name: bindPlacement === "header" ? "btn-primary" : undefined,
        });
        setNotice(`Created server action #${created.id} and bound button (${bindPlacement}). Save the view to apply.`);
      } else if (bindMode === "create_related") {
        const created = await api.createRelatedWindowAction(connectionId, {
          name: bindLabel,
          source_model: model,
          target_model: bindTargetModel,
          relation_field: bindRelationField,
        });
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: bindLabel,
          name: String(created.id),
          type: "action",
          class_name: bindPlacement === "button_box" ? "oe_stat_button" : "btn-secondary",
          icon: bindPlacement === "button_box" ? bindIcon : undefined,
        });
        setNotice(`Created window action #${created.id} and bound button (${bindPlacement}). Save the view to apply.`);
      } else if (bindMode === "create_activity") {
        if (bindActivityTypeId === "") {
          setError("Pick an activity type");
          return;
        }
        const created = await api.createNextActivityAction(connectionId, {
          name: bindLabel,
          model,
          activity_type_id: bindActivityTypeId,
          summary: bindActivitySummary || "Follow up",
          note: bindActivityNote || null,
          user_type: "generic",
          user_field_name: undefined,
          bind_to_model: true,
        });
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: bindLabel,
          name: String(created.id),
          type: "action",
          class_name: bindPlacement === "header" ? "btn-primary" : undefined,
        });
        setNotice(`Created next-activity action #${created.id} (${bindPlacement}). Save the view to apply.`);
      } else if (bindMode === "create_mail") {
        const created = await api.createMailPostAction(connectionId, {
          name: bindLabel,
          model,
          template_id: bindMailTemplateId === "" ? null : bindMailTemplateId,
          mail_post_method: bindMailMethod,
          subject: bindMailSubject || null,
          body_html: bindMailBody || null,
          email_to: bindMailEmailTo || null,
          bind_to_model: true,
        });
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: bindLabel,
          name: String(created.id),
          type: "action",
          class_name: bindPlacement === "header" ? "btn-primary" : undefined,
        });
        setNotice(`Created mail-post action #${created.id} (${bindPlacement}). Save the view to apply.`);
      } else if (bindMode === "create_smart") {
        if (bindCreateCountField) {
          const phrase = (opts?.confirm_phrase || bindSmartConfirmPhrase).trim();
          if (phrase !== CONFIRM_PHRASE) {
            setError(`Create count field requires confirm phrase: ${CONFIRM_PHRASE}`);
            return;
          }
          if (!bindOne2manyField.trim()) {
            setError("one2many field on source model is required for count field");
            return;
          }
        }
        const bundle = await api.createSmartButtonBundle(connectionId, {
          name: bindLabel,
          source_model: model,
          target_model: bindTargetModel,
          relation_field: bindRelationField,
          one2many_field: bindOne2manyField.trim() || null,
          count_field_name: bindCountFieldName.trim() || null,
          create_count_field: bindCreateCountField,
          icon: bindIcon || "fa-list",
          confirm_advanced: bindCreateCountField
            ? opts?.confirm_advanced ?? true
            : false,
          confirm_phrase: bindCreateCountField
            ? opts?.confirm_phrase || bindSmartConfirmPhrase || CONFIRM_PHRASE
            : null,
        });
        const spec = bundle.button_spec;
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: String(spec.string || bindLabel),
          name: String(spec.name || bundle.window_action.id),
          type: "action",
          class_name: String(spec.class || "oe_stat_button"),
          icon: String(spec.icon || bindIcon || "fa-list"),
          count_field: bundle.count_field || undefined,
        });
        setNotice(
          `Smart button bundle: window #${bundle.window_action.id}` +
            (bundle.count_field ? ` · count ${bundle.count_field}` : "") +
            `. Save the view to apply.`,
        );
      } else if (bindMode === "bind_existing") {
        if (selectedActionId === "") {
          setError("Pick an existing action");
          return;
        }
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: bindLabel,
          name: String(selectedActionId),
          type: "action",
          class_name:
            bindPlacement === "button_box"
              ? "oe_stat_button"
              : bindPlacement === "header"
                ? "btn-primary"
                : undefined,
          icon: bindPlacement === "button_box" ? bindIcon : undefined,
        });
        setNotice(`Bound button to action #${selectedActionId}. Save the view to apply.`);
      }
      setBindMode("closed");
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setError(`${err.warning} Type “${err.confirm_phrase}” and retry.`);
        setBindSmartConfirmPhrase(err.confirm_phrase || CONFIRM_PHRASE);
      } else {
        setError(err instanceof Error ? err.message : "Failed to bind action");
      }
    } finally {
      setBusy(false);
    }
  }

  function addButtonToFirstGroup() {
    openBindDialog("inline", "create_update");
  }

  function resolveDragFieldName(e?: DragEvent | null): string | null {
    const fromTransfer = e?.dataTransfer?.getData("text/odoo-field")?.trim();
    if (fromTransfer) return fromTransfer;
    return dragField;
  }

  function addFieldToGroup(groupId: string, fieldName: string, index?: number) {
    const meta = fields.find((f) => f.name === fieldName);
    const node: DesignerField = {
      kind: "field",
      id: uid("f"),
      name: fieldName,
      string: meta?.field_description,
    };
    setFormChildren((children) =>
      children.map((child) => {
        if (child.kind === "group" && child.id === groupId) {
          if (child.children.some((n) => n.kind === "field" && n.name === fieldName)) {
            return child;
          }
          const next =
            index == null ? [...child.children, node] : insertAt(child.children, index, node);
          return { ...child, children: next };
        }
        return child;
      }),
    );
    announceAction(
      `Added ${meta?.field_description || fieldName} to group.`,
      groupId,
      "drop",
    );
  }

  function dropOnGroup(groupId: string, e?: DragEvent | null, index?: number) {
    const fieldName = resolveDragFieldName(e);
    if (!fieldName) return;
    addFieldToGroup(groupId, fieldName, index);
    setDragField(null);
  }

  function dropOnPage(notebookId: string, pageId: string, e?: DragEvent | null) {
    const fieldName = resolveDragFieldName(e);
    if (!fieldName) return;
    dropFieldOnPage(notebookId, pageId, fieldName);
    setDragField(null);
  }

  function dropFieldOnPage(
    notebookId: string,
    pageId: string,
    fieldName: string,
    index?: number,
  ) {
    const meta = fields.find((f) => f.name === fieldName);
    const node: DesignerField = {
      kind: "field",
      id: uid("f"),
      name: fieldName,
      string: meta?.field_description,
    };
    setFormChildren((children) =>
      children.map((child) => {
        if (child.kind !== "notebook" || child.id !== notebookId) return child;
        return {
          ...child,
          pages: child.pages.map((p) => {
            if (p.id !== pageId) return p;
            if (p.children.some((n) => n.kind === "field" && n.name === fieldName)) {
              return p;
            }
            const next = index == null ? [...p.children, node] : insertAt(p.children, index, node);
            return { ...p, children: next };
          }),
        };
      }),
    );
    announceAction(
      `Added ${meta?.field_description || fieldName} to notebook tab.`,
      pageId,
      "drop",
    );
  }

  function reorderFormNode(
    fieldId: string,
    dest:
      | { kind: "group"; groupId: string }
      | { kind: "page"; notebookId: string; pageId: string },
    index: number,
  ) {
    setFormChildren((children) => {
      let moved: DesignerField | DesignerButton | null = null;
      const stripped = children.map((child) => {
        if (child.kind === "group") {
          const found = child.children.find((n) => n.id === fieldId);
          if (found) moved = found;
          return { ...child, children: child.children.filter((n) => n.id !== fieldId) };
        }
        return {
          ...child,
          pages: child.pages.map((p) => {
            const found = p.children.find((n) => n.id === fieldId);
            if (found) moved = found;
            return { ...p, children: p.children.filter((n) => n.id !== fieldId) };
          }),
        };
      });
      if (!moved) return children;
      return stripped.map((child) => {
        if (dest.kind === "group" && child.kind === "group" && child.id === dest.groupId) {
          return { ...child, children: insertAt(child.children, index, moved!) };
        }
        if (
          dest.kind === "page" &&
          child.kind === "notebook" &&
          child.id === dest.notebookId
        ) {
          return {
            ...child,
            pages: child.pages.map((p) =>
              p.id === dest.pageId
                ? { ...p, children: insertAt(p.children, index, moved!) }
                : p,
            ),
          };
        }
        return child;
      });
    });
  }

  function selectCanvasField(fieldId: string) {
    for (const child of formChildren) {
      if (child.kind === "group") {
        if (child.children.some((n) => n.kind === "field" && n.id === fieldId)) {
          setSelected({ scope: "form-group", groupId: child.id, fieldId });
          setRailTab("properties");
          return;
        }
      } else {
        for (const page of child.pages) {
          if (page.children.some((n) => n.kind === "field" && n.id === fieldId)) {
            setSelected({
              scope: "form-page",
              notebookId: child.id,
              pageId: page.id,
              fieldId,
            });
            setRailTab("properties");
            return;
          }
        }
      }
    }
  }

  function addListColumn(fieldName: string) {
    if (listColumns.some((c) => c.name === fieldName)) return;
    const meta = fields.find((f) => f.name === fieldName);
    setListColumns((cols) => [
      ...cols,
      {
        kind: "field",
        id: uid("f"),
        name: fieldName,
        string: meta?.field_description,
      },
    ]);
  }

  function addSearchField(fieldName: string) {
    if (searchFields.some((c) => c.name === fieldName)) return;
    const meta = fields.find((f) => f.name === fieldName);
    setSearchFields((cols) => [
      ...cols,
      {
        kind: "field",
        id: uid("f"),
        name: fieldName,
        string: meta?.field_description,
      },
    ]);
  }

  function addKanbanField(fieldName: string) {
    if (kanbanFields.some((c) => c.name === fieldName)) return;
    const meta = fields.find((f) => f.name === fieldName);
    setKanbanFields((cols) => [
      ...cols,
      {
        kind: "field",
        id: uid("f"),
        name: fieldName,
        string: meta?.field_description,
      },
    ]);
  }

  return {
    moveKanbanField,
    findSelectedField,
    removeSelectedField,
    updateSelectedField,
    addGroup,
    addNotebook,
    addPageToNotebook,
    removeFormChild,
    removeNotebookPage,
    renameNotebookPage,
    renameGroup,
    openBindDialog,
    placeBoundButton,
    submitBindDialog,
    addButtonToFirstGroup,
    resolveDragFieldName,
    addFieldToGroup,
    dropOnGroup,
    dropOnPage,
    dropFieldOnPage,
    reorderFormNode,
    selectCanvasField,
    addListColumn,
    addSearchField,
    addKanbanField,
  };
}
