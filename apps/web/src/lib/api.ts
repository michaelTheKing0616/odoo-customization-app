export {
  API_BASE,
  getApiBase,
  getStoredApiKey,
  setStoredApiKey,
  ConfirmationRequiredError,
  ClarificationRequiredError,
  FeatureGatedError,
} from "./api/client";
export type { ConfirmationRequiredDetail } from "./api/client";

export type * from "./api/types-gating";
export type * from "./api/types-schema";
export type * from "./api/types-catalog";
export type * from "./api/types-actions";
export type * from "./api/types-ingest";
export type * from "./api/types-job";
export type * from "./api/types-bulk";
export type * from "./api/types-batch";
export type { WireframeOutcome, WireframeStatus } from "./api/wireframe";
export type * from "./api/auth";
export type * from "./api/expert";
export type * from "./api/view-engine";

import { authApi } from "./api/auth";
import { studioDraftApi } from "./api/studio-draft";
import { studioSpecApi } from "./api/studio-spec";
import { jobAutopilotApi } from "./api/job-autopilot";
import { connectionsApi } from "./api/connections";
import { schemaApi } from "./api/schema";
import { builderApi } from "./api/builder";
import { modulesSecurityApi } from "./api/modules-security";
import { designerApi } from "./api/designer";
import { automationsApi } from "./api/automations";
import { ingestApi } from "./api/ingest";
import { bulkApi } from "./api/bulk";
import { packsApi } from "./api/packs";
import { configApi } from "./api/config";
import { surfacesApi } from "./api/surfaces";
import { expertApi } from "./api/expert";
import { progressApi } from "./api/progress";
import { wireframeApi } from "./api/wireframe";
import { inboxApi } from "./api/inbox";
import { snapshotApi } from "./api/snapshot";
import { viewEngineApi } from "./api/view-engine";
import { viewEngine2bApi } from "./api/view-engine-2b";
import { viewEngine2cApi } from "./api/view-engine-2c";
import { viewEngine2dApi } from "./api/view-engine-2d";

export type { InboxPlan } from "./api/inbox";
export type {
  AttentionItem,
  AttentionSeverity,
  ExplorerTab,
  LiveSnapshot,
  OverviewSectionId,
  SnapshotModelDetail,
} from "./api/snapshot";

export const api = {
  ...authApi,
  ...studioDraftApi,
  ...studioSpecApi,
  ...jobAutopilotApi,
  ...connectionsApi,
  ...schemaApi,
  ...snapshotApi,
  ...builderApi,
  ...modulesSecurityApi,
  ...designerApi,
  ...automationsApi,
  ...ingestApi,
  ...bulkApi,
  ...packsApi,
  ...configApi,
  ...surfacesApi,
  ...expertApi,
  ...progressApi,
  ...wireframeApi,
  ...inboxApi,
  ...viewEngineApi,
  ...viewEngine2bApi,
  ...viewEngine2cApi,
  ...viewEngine2dApi,
};
