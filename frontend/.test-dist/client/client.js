import { z } from "zod";
class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
    this.name = "ApiError";
  }
}
const workspace = z.object({ id: z.string(), title: z.string(), revision: z.number(), created: z.string(), updated: z.string() });
const document = z.object({
  id: z.string(),
  workspace_id: z.string(),
  kind: z.enum(["cv", "jd"]),
  filename: z.string(),
  sha256: z.string(),
  byte_size: z.number(),
  extraction_state: z.string(),
  extraction_error: z.string().nullable().optional(),
  created: z.string()
});
const state = z.enum(["queued", "running", "paused", "completed", "completed_with_errors", "failed", "cancelling", "cancelled"]);
const job = z.object({
  id: z.string(),
  workspace_id: z.string(),
  kind: z.enum(["jd_extract", "assess"]),
  state,
  request: z.record(z.string(), z.unknown()),
  progress: z.number(),
  total: z.number(),
  sequence: z.number(),
  result_revision: z.number(),
  cancel_requested: z.boolean(),
  error_code: z.string().nullable().optional(),
  error_message: z.string().nullable().optional(),
  eligible_at: z.number().nullable().optional(),
  created: z.string(),
  updated: z.string()
});
const weightPolicy = z.object({
  experience: z.number(),
  education: z.number(),
  jd: z.number(),
  split_jd: z.boolean(),
  jd_view: z.string(),
  jd_allocation: z.enum(["pooled", "weighted_split"]),
  jd_required_share: z.number().nullable(),
  jd_preferred_share: z.number().nullable(),
  requirement_shares_percent_of_category: z.record(z.string(), z.number()),
  default_requirement_allocation: z.enum(["equal", "custom"])
});
const weights = z.object({ revision: z.number(), body: weightPolicy });
const ranking = z.object({
  candidate_index: z.number(),
  candidate_id: z.string(),
  candidate: z.string(),
  weighted_score: z.number().nullable(),
  verified_floor: z.number().nullable(),
  provisional: z.boolean(),
  score_status: z.string(),
  unverified_count: z.number(),
  jd_overall: z.string(),
  required: z.string(),
  preferred: z.string(),
  experience: z.string(),
  education: z.string(),
  review: z.string(),
  rank: z.number().nullable(),
  breakdown: z.record(z.string(), z.unknown())
});
const exportRecord = z.object({
  id: z.string(),
  job_id: z.string(),
  workspace_id: z.string(),
  weight_revision: z.number(),
  result_revision: z.number(),
  size: z.number(),
  created: z.string()
});
const historicalRecord = z.object({
  id: z.string(),
  workspace_id: z.string(),
  source_name: z.string(),
  source_build: z.string(),
  created: z.string()
});
const segment = z.object({ segment_id: z.string(), section: z.string(), text: z.string() });
const checkpoint = z.object({
  Segment: z.string(),
  Section: z.string(),
  Text: z.string(),
  Sources: z.array(z.string()),
  Why: z.array(z.string()),
  "Highlight terms": z.array(z.string()),
  "Validated against CV": z.boolean()
});
const criterion = z.object({
  ID: z.string(),
  Requirement: z.string(),
  Priority: z.string(),
  Result: z.enum(["Found", "Transferable", "Not Found", "Assessment incomplete", "Unverified"]),
  Why: z.string(),
  "JD source": z.string(),
  Kind: z.string(),
  "Evidence level": z.string(),
  Checkpoints: z.array(checkpoint),
  "Display checkpoints": z.array(checkpoint),
  "Review recommended": z.boolean(),
  "Processing state": z.string(),
  "Failure code": z.string().nullable()
});
const candidate = z.object({
  candidate_name: z.string(),
  candidate_source: z.string(),
  primary_score: z.number().nullable(),
  matched_required: z.number(),
  total_required: z.number(),
  matched_preferred: z.number(),
  total_preferred: z.number(),
  evaluation_mode: z.string(),
  errors: z.array(z.string()).optional()
}).passthrough();
const candidateDetail = z.object({
  result_revision: z.number(),
  candidate,
  final: z.object({
    Criteria: z.array(criterion),
    Candidate: z.string(),
    Notices: z.array(z.string()),
    "Run warnings": z.array(z.string()),
    Provisional: z.boolean(),
    "Required matched": z.number(),
    "Required total": z.number(),
    "Preferred matched": z.number(),
    "Preferred total": z.number(),
    Transferable: z.number(),
    "Processing incomplete": z.number()
  }).passthrough(),
  original_segments: z.array(segment),
  requirements: z.array(z.object({
    requirement_id: z.string(),
    name: z.string(),
    priority: z.string(),
    jd_evidence: z.string(),
    constraint: z.record(z.string(), z.unknown())
  }).passthrough())
});
const focusedReview = z.object({
  candidate_id: z.string(),
  requirement_id: z.string(),
  prior_verdict: z.string(),
  new_verdict: z.string(),
  explanation: z.string(),
  result_revision: z.number(),
  citations: z.array(z.record(z.string(), z.unknown())).default([])
});
const reviewHistoryItem = z.object({
  id: z.string(),
  job_id: z.string(),
  candidate_id: z.string(),
  requirement_id: z.string(),
  prior_verdict: z.string(),
  new_verdict: z.string(),
  explanation: z.string(),
  sources: z.array(z.record(z.string(), z.unknown())).default([]),
  created: z.string()
});
const semanticShadowItem = z.object({
  requirement_id: z.string(),
  candidate_id: z.string(),
  similarity: z.number(),
  finding: z.string(),
  source_segments: z.array(z.string()).default([])
});
const semanticShadow = z.object({
  ready: z.boolean(),
  scoring_unchanged: z.boolean(),
  notice: z.string(),
  items: z.array(semanticShadowItem).default([])
});
const tokenUsage = z.object({
  prompt_tokens: z.number().nullable().optional(),
  completion_tokens: z.number().nullable().optional(),
  total_tokens: z.number().nullable().optional()
});
const jobUsage = z.object({
  job_id: z.string(),
  provider: z.string(),
  model: z.string(),
  logical_model_calls: z.number(),
  actual_model_request_attempts: z.number(),
  token_usage: tokenUsage,
  estimated_cost_usd: z.number().nullable().optional(),
  cost_label: z.string(),
  reused_prompt_calls: z.number(),
  preserved_unknown: z.boolean()
});
const retentionSummary = z.object({
  workspace_id: z.string(),
  eligible_jobs: z.number(),
  eligible_exports: z.number(),
  eligible_documents: z.number(),
  protected_active_jobs: z.number(),
  protected_unknown_delivery_jobs: z.number(),
  default_retention_days: z.number()
});
const retentionPurgeResult = z.object({
  purged_jobs: z.number(),
  purged_exports: z.number(),
  purged_documents: z.number(),
  retention_days: z.number()
});
const jdDraft = z.object({
  id: z.string(),
  workspace_id: z.string(),
  document_id: z.string(),
  revision: z.number(),
  body: z.unknown(),
  rows: z.array(z.object({
    ID: z.string(),
    Requirement: z.string(),
    Priority: z.string(),
    Type: z.string(),
    "JD source": z.string(),
    "Mandatory JD parts": z.string().optional(),
    "Alternative groups JSON": z.string().optional(),
    "Complete JD expression JSON": z.string().optional(),
    "Minimum years": z.number().nonnegative().nullable().optional(),
    "Degree level": z.string().optional(),
    "Field of study": z.string().optional(),
    "Evidence standard": z.string().optional(),
    "Duration subject": z.string().optional()
  }).passthrough()).optional()
});
const approval = z.object({
  id: z.string(),
  workspace_id: z.string(),
  draft_id: z.string(),
  revision: z.number(),
  body: z.object({ requirements: z.array(z.object({
    requirement_id: z.string(),
    name: z.string(),
    priority: z.string(),
    constraint: z.unknown().optional()
  }).passthrough()), warnings: z.array(z.string()).optional() }).passthrough()
});
let csrf = null;
const API = "/api/v1";
const object = z.record(z.string(), z.unknown());
async function initializeSession() {
  const response = await fetch(API + "/session", { credentials: "same-origin", cache: "no-store" });
  if (!response.ok) throw new ApiError(response.status, "session_unavailable", "Local session unavailable");
  const parsed = z.object({ csrf_token: z.string() }).parse(await response.json());
  csrf = parsed.csrf_token;
}
async function request(path, options = {}) {
  const method = options.method ?? "GET";
  const headers = {};
  if (method !== "GET") {
    if (csrf === null) throw new ApiError(401, "session_required", "Reload to initialize local session");
    headers["X-CSRF-Token"] = csrf;
    if (!(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  }
  if (options.key) headers["Idempotency-Key"] = options.key;
  const response = await fetch(API + path, {
    method,
    headers,
    signal: options.signal,
    credentials: "same-origin",
    cache: "no-store",
    body: options.body === void 0 ? void 0 : options.body instanceof FormData ? options.body : JSON.stringify(options.body)
  });
  const raw = await response.json().catch(() => ({ code: "unreadable_response", message: "Service returned unreadable JSON" }));
  if (!response.ok) {
    const parsed = z.object({ code: z.string().default("http_error"), message: z.string().default("Request failed") }).safeParse(raw);
    throw new ApiError(
      response.status,
      parsed.success ? parsed.data.code : "unexpected_response",
      parsed.success ? parsed.data.message : `HTTP ${response.status}`
    );
  }
  return raw;
}
function ws(id) {
  return "/workspaces/" + encodeURIComponent(id);
}
function jpath(id, jid) {
  return ws(id) + "/jobs/" + encodeURIComponent(jid);
}
const client = {
  listWorkspaces: async () => z.object({ items: z.array(workspace) }).parse(await request("/workspaces")).items,
  createWorkspace: async (title) => workspace.parse(await request("/workspaces", { method: "POST", body: { title } })),
  getWorkspace: async (id) => workspace.parse(await request(ws(id))),
  removeWorkspace: async (id) => {
    z.object({ deleted: z.string() }).parse(await request(ws(id), { method: "DELETE", body: { confirmation: "DELETE WORKSPACE" } }));
  },
  listDocuments: async (id) => z.object({ items: z.array(document) }).parse(await request(ws(id) + "/documents")).items,
  upload: async (id, kind, file) => {
    const form = new FormData();
    form.append("file", file, file.name);
    return document.parse(await request(ws(id) + "/documents?kind=" + kind, { method: "POST", body: form }));
  },
  removeDocument: async (id, docId) => {
    z.object({ deleted: z.string() }).parse(await request(
      ws(id) + "/documents/" + encodeURIComponent(docId),
      { method: "DELETE", body: { confirmation: "DELETE" } }
    ));
  },
  getJD: async (id) => {
    const result = await request(ws(id) + "/jd");
    return z.object({ draft: jdDraft.nullable(), approved: approval.nullable() }).parse(result);
  },
  getDraft: async (id, draftId) => jdDraft.parse(await request(ws(id) + "/jd/drafts/" + encodeURIComponent(draftId))),
  startJD: async (id, documentId, settings, key) => job.parse(
    await request(ws(id) + "/jd/extraction-jobs", { method: "POST", key, body: { document_id: documentId, ...settings } })
  ),
  reviseJD: async (id, draftId, revision, rows) => jdDraft.parse(
    await request(ws(id) + "/jd/drafts/" + encodeURIComponent(draftId), { method: "PUT", body: { draft_id: draftId, revision, rows } })
  ),
  approveJD: async (id, draftId, revision, rows) => approval.parse(
    await request(ws(id) + "/jd/approve", { method: "POST", body: { draft_id: draftId, revision, rows } })
  ),
  getWeights: async (id) => weights.parse(await request(ws(id) + "/weights")),
  saveWeights: async (id, revision, policy) => weights.parse(
    await request(ws(id) + "/weights", { method: "PUT", body: { revision, weights: policy } })
  ),
  rebalance: async (id, requirementId, newShare, shares) => z.object({ shares: z.record(z.string(), z.number()) }).parse(
    await request(ws(id) + "/weights/rebalance", { method: "POST", body: { requirement_id: requirementId, new_share: newShare, shares } })
  ).shares,
  startAssessment: async (id, ids, approvedRevisionId, settings, key) => job.parse(
    await request(ws(id) + "/assessment-jobs", { method: "POST", key, body: { candidate_ids: ids, approved_revision_id: approvedRevisionId, ...settings } })
  ),
  getSubmission: async (id, key) => job.parse(await request(ws(id) + "/submissions/" + encodeURIComponent(key))),
  listJobs: async (id) => z.object({ items: z.array(job) }).parse(await request(ws(id) + "/jobs")).items,
  removeJob: async (id, jid) => {
    z.object({ deleted: z.string() }).parse(await request(jpath(id, jid), { method: "DELETE", body: { confirmation: "DELETE" } }));
  },
  getJob: async (id, jid) => job.parse(await request(jpath(id, jid))),
  controlJob: async (id, jid, action) => job.parse(await request(jpath(id, jid) + "/" + action, { method: "POST", body: {} })),
  resolveUnknown: async (id, jid, choice, acknowledgement) => request(jpath(id, jid) + "/resolve-unknown", { method: "POST", body: { resolution: choice, acknowledgement } }),
  listRankings: async (id, jid, options) => {
    const query = new URLSearchParams();
    if (options?.offset !== void 0) query.set("offset", String(options.offset));
    if (options?.limit !== void 0) query.set("limit", String(options.limit));
    if (options?.search) query.set("search", options.search);
    if (options?.expectedResultRevision !== void 0) query.set("expected_result_revision", String(options.expectedResultRevision));
    if (options?.expectedWeightRevision !== void 0) query.set("expected_weight_revision", String(options.expectedWeightRevision));
    const result = z.object({
      items: z.array(ranking),
      total: z.number(),
      offset: z.number(),
      limit: z.number(),
      search: z.string(),
      result_revision: z.number().nullable(),
      weight_revision: z.number().nullable(),
      official_count: z.number().optional().default(0),
      unfinished_count: z.number().optional().default(0)
    }).parse(
      await request(jpath(id, jid) + "/rankings?" + query.toString())
    );
    return {
      items: result.items,
      total: result.total,
      offset: result.offset,
      limit: result.limit,
      search: result.search,
      resultRevision: result.result_revision,
      weightRevision: result.weight_revision,
      officialCount: result.official_count,
      unfinishedCount: result.unfinished_count
    };
  },
  candidateWeighted: async (id, jid, docId) => {
    const response = z.object({
      candidate_id: z.string(),
      result_revision: z.number(),
      weight_revision: z.number(),
      result: ranking
    }).parse(await request(jpath(id, jid) + "/candidates/" + encodeURIComponent(docId) + "/weighted"));
    return { result: response.result, resultRevision: response.result_revision, weightRevision: response.weight_revision };
  },
  getCandidate: async (id, jid, docId) => candidateDetail.parse(await request(jpath(id, jid) + "/candidates/" + encodeURIComponent(docId))),
  listExports: async (id) => z.object({ items: z.array(exportRecord) }).parse(await request(ws(id) + "/exports")).items,
  export: async (id, jid, resultRev, weightRev) => exportRecord.parse(await request(jpath(id, jid) + "/exports", { method: "POST", body: { revision: resultRev, weight_revision: weightRev } })),
  removeExport: async (id, eid) => {
    z.object({ deleted: z.string() }).parse(await request(
      ws(id) + "/exports/" + encodeURIComponent(eid),
      { method: "DELETE", body: { confirmation: "DELETE" } }
    ));
  },
  listHistory: async (id) => z.object({ items: z.array(historicalRecord) }).parse(
    await request(ws(id) + "/historical-reports")
  ).items,
  importHistory: async (id, file) => {
    const form = new FormData();
    form.append("file", file, file.name);
    await request(ws(id) + "/historical-reports", { method: "POST", body: form });
  },
  getSettings: async () => settingsSchema.parse(await request("/settings")),
  eventHistory: async (id, jid, after = 0) => {
    return z.object({ items: z.array(event), snapshot: job }).parse(await request(jpath(id, jid) + "/event-history?after=" + after));
  },
  runFocusedReview: async (id, jid, docId, reqId, provider, useLlm, expectedResultRevision) => focusedReview.parse(await request(jpath(id, jid) + "/candidates/" + encodeURIComponent(docId) + "/focused-review", {
    method: "POST",
    body: { requirement_id: reqId, provider, use_llm: useLlm, expected_result_revision: expectedResultRevision }
  })),
  getReviewHistory: async (id, jid, docId) => z.object({ items: z.array(reviewHistoryItem) }).parse(
    await request(jpath(id, jid) + "/candidates/" + encodeURIComponent(docId) + "/review-history")
  ).items,
  runSemanticShadow: async (id, jid, topK = 5) => semanticShadow.parse(await request(jpath(id, jid) + "/semantic-shadow", {
    method: "POST",
    body: { top_k: topK }
  })),
  getSemanticShadow: async (id, jid) => semanticShadow.parse(await request(jpath(id, jid) + "/semantic-shadow")),
  getJobUsage: async (id, jid) => jobUsage.parse(await request(jpath(id, jid) + "/usage")),
  getRetentionSummary: async (id, days = 30) => retentionSummary.parse(await request(ws(id) + "/retention?days=" + days)),
  purgeRetention: async (id, days = 30) => retentionPurgeResult.parse(await request(ws(id) + "/retention/purge", {
    method: "POST",
    body: { retention_days: days }
  }))
};
const event = z.object({ job_id: z.string(), seq: z.number(), kind: z.string(), payload: object, created: z.string() });
const settingsSchema = z.object({
  engine_build: z.string(),
  protocol: z.number(),
  available_providers: z.array(z.string()),
  configured_provider: z.string(),
  organization_name: z.string(),
  ollama_model: z.string(),
  openrouter_model: z.string(),
  openrouter_key_configured: z.boolean(),
  yake_top_k_default: z.number(),
  openrouter_context_tokens: z.number(),
  openrouter_output_tokens: z.number(),
  openrouter_max_requests_per_assessment: z.number(),
  local_only: z.boolean()
});
export {
  ApiError,
  client,
  initializeSession
};
