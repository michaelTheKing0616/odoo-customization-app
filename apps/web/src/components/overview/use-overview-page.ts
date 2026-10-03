"use client";

import {
  overviewFieldColumns,
  overviewModelColumns,
  overviewModuleColumns,
} from "./overview-columns";
import { useOverviewActions } from "./use-overview-actions";
import { useOverviewPageState } from "./use-overview-page-state";

export function useOverviewPage(connectionId: string) {
  const s = useOverviewPageState(connectionId);
  const actions = useOverviewActions(connectionId, s);

  return {
    connectionId,
    ...s,
    ...actions,
    moduleColumns: overviewModuleColumns(),
    modelColumns: overviewModelColumns(connectionId),
    fieldColumns: overviewFieldColumns(),
  };
}

export type OverviewPageModel = ReturnType<typeof useOverviewPage>;
