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
export type * from "./api/auth";
export type * from "./api/expert";

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

export const api = {
  ...authApi,
  ...studioDraftApi,
  ...studioSpecApi,
  ...jobAutopilotApi,
  ...connectionsApi,
  ...schemaApi,
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
};
