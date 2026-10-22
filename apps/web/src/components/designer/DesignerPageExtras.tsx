"use client";

import { DesignerAdvancedFieldsAside } from "@/components/designer/DesignerAdvancedFieldsAside";
import { DesignerAdvancedMetaAside } from "@/components/designer/DesignerAdvancedMetaAside";
import { DesignerAdvancedStructureCanvas } from "@/components/designer/DesignerAdvancedStructureCanvas";
import { DesignerBindPanel } from "@/components/designer/DesignerBindPanel";
import { DesignerDangerConfirms } from "@/components/designer/DesignerDangerConfirms";
import { DesignerReportingFieldsPanel } from "@/components/designer/DesignerReportingFieldsPanel";
import type { DesignerPageModel } from "@/components/designer/useDesignerPageModel";
import type { useDesignerCanvasMutations } from "@/components/designer/useDesignerCanvasMutations";
import type { useDesignerPersist } from "@/components/designer/useDesignerPersist";
import { Callout } from "@/components/ui/Callout";
import { Disclosure } from "@/components/ui/Disclosure";

const CONFIRM_PHRASE = "I understand the risks";

type Mutations = ReturnType<typeof useDesignerCanvasMutations>;
type Persist = ReturnType<typeof useDesignerPersist>;

export function DesignerPageExtras({
  m,
  mutations,
  persist,
}: {
  m: DesignerPageModel;
  mutations: Mutations;
  persist: Persist;
}) {
  return (
    <>
      <Callout variant="info" title="Production defaults" className="mx-4 mt-4 md:mx-6">
        <details>
          <summary className="cursor-pointer text-sm text-muted">
            Show save / button / preview notes
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-sm">
            <li>
              Save strategy defaults to <strong>Inherit</strong> (extension view) — safe for
              installed modules.
            </li>
            <li>
              On stock models (e.g. <code>account.move</code>), Inherit saves only{" "}
              <strong>new custom fields/groups</strong> — it does not re-emit Send/Print/Pay or
              notebook tabs (that caused duplicates on Bills).
            </li>
            <li>
              Vendor bills open as <strong>Bills</strong> in Odoo; customer invoices as{" "}
              <strong>Invoices</strong> — same model <code>account.move</code>.
            </li>
            <li>
              <strong>Overwrite</strong> requires confirm and snapshots the primary view first.
            </li>
            <li>
              Buttons bind to real <code>ir.actions.server</code> /{" "}
              <code>ir.actions.act_window</code> (type=action). Python object methods need custom code.
            </li>
            <li>
              Prefer <strong>Open in Odoo</strong> for truth; iframe preview is best-effort via
              authenticated proxy.
            </li>
            <li>
              Create field requires the confirm phrase and injects via inherit xpath.
            </li>
          </ul>
        </details>
      </Callout>

      <DesignerReportingFieldsPanel
        viewType={m.viewType}
        model={m.model}
        fields={m.fields}
        calendarFields={m.calendarFields}
        setCalendarFields={m.setCalendarFields}
        mapFields={m.mapFields}
        setMapFields={m.setMapFields}
        activityFields={m.activityFields}
        setActivityFields={m.setActivityFields}
        ganttFields={m.ganttFields}
        setGanttFields={m.setGanttFields}
        gridFields={m.gridFields}
        setGridFields={m.setGridFields}
        graphFields={m.graphFields}
        setGraphFields={m.setGraphFields}
        pivotFields={m.pivotFields}
        setPivotFields={m.setPivotFields}
      />

      {m.bindMode !== "closed" && (
        <DesignerBindPanel
          connection={m.connection}
          fields={m.fields}
          bindMode={m.bindMode}
          bindPlacement={m.bindPlacement}
          bindLabel={m.bindLabel}
          setBindLabel={m.setBindLabel}
          bindFieldName={m.bindFieldName}
          setBindFieldName={m.setBindFieldName}
          bindValue={m.bindValue}
          setBindValue={m.setBindValue}
          bindTargetModel={m.bindTargetModel}
          setBindTargetModel={m.setBindTargetModel}
          bindRelationField={m.bindRelationField}
          setBindRelationField={m.setBindRelationField}
          bindIcon={m.bindIcon}
          setBindIcon={m.setBindIcon}
          bindCreateCountField={m.bindCreateCountField}
          setBindCreateCountField={m.setBindCreateCountField}
          bindOne2manyField={m.bindOne2manyField}
          setBindOne2manyField={m.setBindOne2manyField}
          bindCountFieldName={m.bindCountFieldName}
          setBindCountFieldName={m.setBindCountFieldName}
          bindSmartConfirmPhrase={m.bindSmartConfirmPhrase}
          setBindSmartConfirmPhrase={m.setBindSmartConfirmPhrase}
          selectedActionId={m.selectedActionId}
          setSelectedActionId={m.setSelectedActionId}
          bindableActions={m.bindableActions}
          activityTypes={m.activityTypes}
          mailTemplates={m.mailTemplates}
          bindActivityTypeId={m.bindActivityTypeId}
          setBindActivityTypeId={m.setBindActivityTypeId}
          bindActivitySummary={m.bindActivitySummary}
          setBindActivitySummary={m.setBindActivitySummary}
          bindActivityNote={m.bindActivityNote}
          setBindActivityNote={m.setBindActivityNote}
          bindMailTemplateId={m.bindMailTemplateId}
          setBindMailTemplateId={m.setBindMailTemplateId}
          bindMailMethod={m.bindMailMethod}
          setBindMailMethod={m.setBindMailMethod}
          bindMailSubject={m.bindMailSubject}
          setBindMailSubject={m.setBindMailSubject}
          bindMailBody={m.bindMailBody}
          setBindMailBody={m.setBindMailBody}
          bindMailEmailTo={m.bindMailEmailTo}
          setBindMailEmailTo={m.setBindMailEmailTo}
          busy={m.busy}
          confirmPhrase={CONFIRM_PHRASE}
          openBindDialog={mutations.openBindDialog}
          onSubmitBind={(opts) => void mutations.submitBindDialog(opts)}
          onClose={() => m.setBindMode("closed")}
        />
      )}

      <Disclosure title="Advanced layout & field inject" testId="designer-advanced-layout" className="mx-4 mb-4 md:mx-6">
        <div className="grid gap-6 lg:grid-cols-[220px_1fr_280px]">
          <DesignerAdvancedFieldsAside
            connection={m.connection}
            model={m.model}
            viewType={m.viewType}
            fields={m.fields}
            newFieldName={m.newFieldName}
            setNewFieldName={m.setNewFieldName}
            newFieldLabel={m.newFieldLabel}
            setNewFieldLabel={m.setNewFieldLabel}
            newFieldType={m.newFieldType}
            setNewFieldType={m.setNewFieldType}
            injectStrategy={m.injectStrategy}
            setInjectStrategy={m.setInjectStrategy}
            confirmPhrase={m.confirmPhrase}
            setConfirmPhrase={m.setConfirmPhrase}
            busy={m.busy}
            setDragField={m.setDragField}
            addListColumn={mutations.addListColumn}
            addSearchField={mutations.addSearchField}
            addKanbanField={mutations.addKanbanField}
            nicheWidgets={m.nicheWidgets}
            colorPalette={m.colorPalette}
            onCreateAndInject={(opts) => void m.createNewFieldWithInject(opts)}
            onPickNicheWidget={(w) => void m.addNicheWidget(w)}
          />

          <DesignerAdvancedStructureCanvas
            viewType={m.viewType}
            connection={m.connection}
            model={m.model}
            title={m.title}
            toolbarFlash={m.toolbarFlash}
            canvasFlashId={m.canvasFlashId}
            previewTheme={m.previewTheme}
            viewSample={m.viewSample}
            setViewSample={m.setViewSample}
            formChildren={m.formChildren}
            headerButtons={m.headerButtons}
            buttonBox={m.buttonBox}
            setHeaderButtons={m.setHeaderButtons}
            setButtonBox={m.setButtonBox}
            statusbarField={m.statusbarField}
            setStatusbarField={m.setStatusbarField}
            statusbarVisible={m.statusbarVisible}
            setStatusbarVisible={m.setStatusbarVisible}
            formCanCreate={m.formCanCreate}
            formCanEdit={m.formCanEdit}
            formCanDelete={m.formCanDelete}
            formCanDuplicate={m.formCanDuplicate}
            setFormCanCreate={m.setFormCanCreate}
            setFormCanEdit={m.setFormCanEdit}
            setFormCanDelete={m.setFormCanDelete}
            setFormCanDuplicate={m.setFormCanDuplicate}
            listColumns={m.listColumns}
            setListColumns={m.setListColumns}
            listDecorationDanger={m.listDecorationDanger}
            listDecorationInfo={m.listDecorationInfo}
            listDecorationMuted={m.listDecorationMuted}
            setListDecorationDanger={m.setListDecorationDanger}
            setListDecorationInfo={m.setListDecorationInfo}
            setListDecorationMuted={m.setListDecorationMuted}
            listCanCreate={m.listCanCreate}
            listCanEdit={m.listCanEdit}
            listCanDelete={m.listCanDelete}
            listMultiEdit={m.listMultiEdit}
            listDefaultOrder={m.listDefaultOrder}
            setListCanCreate={m.setListCanCreate}
            setListCanEdit={m.setListCanEdit}
            setListCanDelete={m.setListCanDelete}
            setListMultiEdit={m.setListMultiEdit}
            setListDefaultOrder={m.setListDefaultOrder}
            searchFields={m.searchFields}
            setSearchFields={m.setSearchFields}
            searchFilters={m.searchFilters}
            setSearchFilters={m.setSearchFilters}
            searchGroupByFilters={m.searchGroupByFilters}
            setSearchGroupByFilters={m.setSearchGroupByFilters}
            editingFilterId={m.editingFilterId}
            setEditingFilterId={m.setEditingFilterId}
            kanbanFields={m.kanbanFields}
            setKanbanFields={m.setKanbanFields}
            kanbanGroupBy={m.kanbanGroupBy}
            kanbanCanCreate={m.kanbanCanCreate}
            kanbanQuickCreate={m.kanbanQuickCreate}
            setKanbanCanCreate={m.setKanbanCanCreate}
            setKanbanQuickCreate={m.setKanbanQuickCreate}
            moveKanbanField={mutations.moveKanbanField}
            addKanbanField={mutations.addKanbanField}
            fields={m.fields}
            selected={m.selected}
            setSelected={m.setSelected}
            addGroup={mutations.addGroup}
            addNotebook={mutations.addNotebook}
            addButtonToFirstGroup={mutations.addButtonToFirstGroup}
            openBindDialog={mutations.openBindDialog}
            dropOnGroup={mutations.dropOnGroup}
            dropOnPage={mutations.dropOnPage}
            removeFormChild={mutations.removeFormChild}
            removeNotebookPage={mutations.removeNotebookPage}
            renameNotebookPage={mutations.renameNotebookPage}
            renameGroup={mutations.renameGroup}
            addPageToNotebook={mutations.addPageToNotebook}
            removeFormField={m.removeFormField}
            announceAction={m.announceAction}
          />

          <DesignerAdvancedMetaAside
            arch={m.arch}
            snapshots={m.snapshots}
            snapshotsHydrated={m.snapshotsHydrated}
            busy={m.busy}
            onRefreshSnapshots={() => void m.refreshSnapshots()}
            onRollback={(id) => void persist.onRollback(id)}
          />
        </div>
      </Disclosure>
      <DesignerDangerConfirms
        model={m.model}
        viewType={m.viewType}
        confirmPhrase={CONFIRM_PHRASE}
        busy={m.busy}
        confirmOverwriteOpen={m.confirmOverwriteOpen}
        setConfirmOverwriteOpen={m.setConfirmOverwriteOpen}
        confirmUnlinkInheritOpen={m.confirmUnlinkInheritOpen}
        setConfirmUnlinkInheritOpen={m.setConfirmUnlinkInheritOpen}
        confirmMutateOpen={m.confirmMutateOpen}
        setConfirmMutateOpen={m.setConfirmMutateOpen}
        onOverwrite={(phrase) => void persist.onSave({ strategy: "overwrite", confirm_phrase: phrase })}
        onUnlinkInherit={(phrase) => void persist.onUnlinkDesignerInherit(phrase)}
        onMutateParent={(phrase) =>
          void m.createNewFieldWithInject({
            confirm_advanced: true,
            confirm_phrase: phrase,
          })
        }
      />
    </>
  );
}
