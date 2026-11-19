import { jsxs, jsx, Fragment } from "react/jsx-runtime";
import { createContext, useState, useCallback, useEffect, useRef } from "react";
import { Link, useOutletContext, useParams } from "react-router-dom";
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
const document$1 = z.object({
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
  breakdown: z.record(z.string(), z.unknown()),
  placement_reason: z.string().nullable().optional(),
  score_gap: z.number().nullable().optional()
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
const reasoningItem = z.union([
  z.object({
    requirement_id: z.string().default(""),
    requirement: z.string().default(""),
    priority: z.string().default(""),
    category: z.string().nullable().optional(),
    decision: z.string().default(""),
    points: z.number().nullable().optional(),
    why: z.string().default("")
  }),
  z.string().transform((str) => ({
    requirement_id: "",
    requirement: str,
    priority: "",
    category: null,
    decision: "",
    points: null,
    why: ""
  }))
]);
const headToHeadComparison = z.object({
  against_candidate_index: z.number(),
  against: z.string(),
  rank: z.number().nullable().optional(),
  score_gap: z.number().nullable().optional(),
  top_candidate_advantages: z.array(reasoningItem).default([]),
  other_candidate_advantages: z.array(reasoningItem).default([]),
  is_tie: z.boolean().default(false)
});
const rankingReasoning = z.object({
  summary: z.string().default(""),
  placement_reason: z.string().default(""),
  rank: z.number().nullable().optional(),
  score: z.number().nullable().optional(),
  strengths: z.array(reasoningItem).default([]),
  gaps: z.array(reasoningItem).default([]),
  transferable: z.array(reasoningItem).default([]),
  head_to_head_summary: z.string().default(""),
  top_candidate_advantages: z.array(reasoningItem).default([]),
  other_candidate_advantages: z.array(reasoningItem).default([]),
  score_gap: z.number().nullable().optional(),
  all_comparisons: z.array(headToHeadComparison).default([])
}).optional().nullable();
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
  }).passthrough()),
  ranking_reasoning: rankingReasoning
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
const API = "/api/v1";
const object = z.record(z.string(), z.unknown());
async function request(path, options = {}) {
  const method = options.method ?? "GET";
  const headers = {};
  if (method !== "GET") {
    throw new ApiError(401, "session_required", "Reload to initialize local session");
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
  const text = await response.text();
  let raw = {};
  if (text && text.trim().length > 0) {
    try {
      raw = JSON.parse(text);
    } catch {
      if (!response.ok) {
        throw new ApiError(response.status, "server_error", text.slice(0, 300) || `HTTP ${response.status}`);
      }
      if (text.includes("<!DOCTYPE") || text.includes("<html")) {
        throw new ApiError(response.status, "backend_offline", "The backend service is unavailable or restarting. Please try again.");
      }
      throw new ApiError(response.status, "unreadable_response", "The service returned an unexpected response format.");
    }
  }
  if (!response.ok) {
    const record = raw && typeof raw === "object" ? raw : {};
    const code = typeof record.code === "string" ? record.code : typeof record.detail === "string" ? "request_error" : "http_error";
    const message = typeof record.message === "string" ? record.message : typeof record.detail === "string" ? record.detail : `HTTP ${response.status}`;
    throw new ApiError(response.status, code, message);
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
  listDocuments: async (id) => z.object({ items: z.array(document$1) }).parse(await request(ws(id) + "/documents")).items,
  upload: async (id, kind, file) => {
    const form = new FormData();
    form.append("file", file, file.name);
    return document$1.parse(await request(ws(id) + "/documents?kind=" + kind, { method: "POST", body: form }));
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
      unfinished_count: z.number().optional().default(0),
      comparative_summary: z.string().nullable().optional()
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
      unfinishedCount: result.unfinished_count,
      comparativeSummary: result.comparative_summary ?? null
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
const terminalStates = /* @__PURE__ */ new Set(["completed", "completed_with_errors", "failed", "cancelled"]);
function isTerminalJob(state2) {
  return terminalStates.has(state2);
}
function newerSnapshot(previous, next) {
  if (!previous || previous.id !== next.id) return next;
  if (next.sequence < previous.sequence) return previous;
  if (next.sequence === previous.sequence && next.result_revision < previous.result_revision) return previous;
  return next;
}
function consumeSequence(last, incoming) {
  if (!Number.isSafeInteger(incoming) || incoming < 1 || incoming <= last) return null;
  return incoming;
}
function nextReconnectMs(consecutiveErrors) {
  return Math.min(3e4, 1e3 * 2 ** Math.max(0, Math.min(5, consecutiveErrors)));
}
const prefix = "textilehr:submission-intent:v1:";
function locationFor(workspace2, kind) {
  return `${prefix}${workspace2}:${kind}`;
}
function epochFor(workspace2, kind) {
  return `${prefix}epoch:${workspace2}:${kind}`;
}
function startDistinctIntent(workspace2, kind) {
  const old = Number(localStorage.getItem(epochFor(workspace2, kind)) ?? "0");
  localStorage.setItem(epochFor(workspace2, kind), String(Number.isSafeInteger(old) && old >= 0 ? old + 1 : 1));
  localStorage.removeItem(locationFor(workspace2, kind));
}
const ROUTES = {
  overview: "",
  uploads: "uploads",
  jd: "jd",
  weights: "weights",
  run: "run",
  progress: "progress/:jobId",
  rankings: "rankings/:jobId",
  candidate: "candidate/:jobId/:candidateId",
  reports: "reports",
  settings: "settings"
};
const idPattern = /^[0-9A-Za-z_-]{1,150}$/;
function workspacePath(workspaceId, page, params = {}) {
  if (!idPattern.test(workspaceId)) throw new Error("Invalid workspace identifier");
  const suffix = ROUTES[page].split("/").filter(Boolean).map((segment2) => {
    if (!segment2.startsWith(":")) return segment2;
    const key = segment2.slice(1);
    const value = params[key];
    if (!value || !idPattern.test(value)) throw new Error(`Invalid or missing ${key}`);
    return value;
  }).join("/");
  return `/w/${workspaceId}` + (suffix ? `/${suffix}` : "");
}
function RefreshIcon({ size = 16, ...props }) {
  return /* @__PURE__ */ jsxs("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true", ...props, children: [
    /* @__PURE__ */ jsx("path", { d: "M21.5 2v6h-6" }),
    /* @__PURE__ */ jsx("path", { d: "M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.19" })
  ] });
}
function DownloadIcon({ size = 16, ...props }) {
  return /* @__PURE__ */ jsxs("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true", ...props, children: [
    /* @__PURE__ */ jsx("path", { d: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" }),
    /* @__PURE__ */ jsx("polyline", { points: "7 10 12 15 17 10" }),
    /* @__PURE__ */ jsx("line", { x1: "12", y1: "15", x2: "12", y2: "3" })
  ] });
}
function ChartBarIcon({ size = 16, ...props }) {
  return /* @__PURE__ */ jsxs("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true", ...props, children: [
    /* @__PURE__ */ jsx("line", { x1: "18", y1: "20", x2: "18", y2: "10" }),
    /* @__PURE__ */ jsx("line", { x1: "12", y1: "20", x2: "12", y2: "4" }),
    /* @__PURE__ */ jsx("line", { x1: "6", y1: "20", x2: "6", y2: "14" }),
    /* @__PURE__ */ jsx("line", { x1: "3", y1: "20", x2: "21", y2: "20" })
  ] });
}
function SparkleIcon({ size = 16, ...props }) {
  return /* @__PURE__ */ jsx("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true", ...props, children: /* @__PURE__ */ jsx("path", { d: "m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z" }) });
}
function CloseIcon({ size = 16, ...props }) {
  return /* @__PURE__ */ jsxs("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true", ...props, children: [
    /* @__PURE__ */ jsx("line", { x1: "18", y1: "6", x2: "6", y2: "18" }),
    /* @__PURE__ */ jsx("line", { x1: "6", y1: "6", x2: "18", y2: "18" })
  ] });
}
function ChevronLeftIcon({ size = 16, ...props }) {
  return /* @__PURE__ */ jsx("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true", ...props, children: /* @__PURE__ */ jsx("polyline", { points: "15 18 9 12 15 6" }) });
}
function ChevronRightIcon({ size = 16, ...props }) {
  return /* @__PURE__ */ jsx("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true", ...props, children: /* @__PURE__ */ jsx("polyline", { points: "9 18 15 12 9 6" }) });
}
function ArrowUpIcon({ size = 16, ...props }) {
  return /* @__PURE__ */ jsxs("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true", ...props, children: [
    /* @__PURE__ */ jsx("line", { x1: "12", y1: "19", x2: "12", y2: "5" }),
    /* @__PURE__ */ jsx("polyline", { points: "5 12 12 5 19 12" })
  ] });
}
function ArrowRightIcon({ size = 16, ...props }) {
  return /* @__PURE__ */ jsxs("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true", ...props, children: [
    /* @__PURE__ */ jsx("line", { x1: "5", y1: "12", x2: "19", y2: "12" }),
    /* @__PURE__ */ jsx("polyline", { points: "12 5 19 12 12 19" })
  ] });
}
function SearchIcon({ size = 16, ...props }) {
  return /* @__PURE__ */ jsxs("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true", ...props, children: [
    /* @__PURE__ */ jsx("circle", { cx: "11", cy: "11", r: "8" }),
    /* @__PURE__ */ jsx("line", { x1: "21", y1: "21", x2: "16.65", y2: "16.65" })
  ] });
}
function EmptyStateIcon({ size = 32, ...props }) {
  return /* @__PURE__ */ jsxs("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "1.5", strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true", ...props, children: [
    /* @__PURE__ */ jsx("path", { d: "M22 12h-6l-2 3h-4l-2-3H2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-7z" }),
    /* @__PURE__ */ jsx("path", { d: "M5.45 5.11 2 12v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-7l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" })
  ] });
}
function Panel({ children, className = "", style, id }) {
  return /* @__PURE__ */ jsx("section", { id, style, className: "card " + className, children });
}
function PageHeader({ title, description, actions }) {
  return /* @__PURE__ */ jsxs("header", { className: "pageheading", children: [
    /* @__PURE__ */ jsxs("div", { children: [
      /* @__PURE__ */ jsx("div", { className: "eyebrow", children: "Reliance Weaving Mills AI · Recruitment Intelligence" }),
      /* @__PURE__ */ jsx("h1", { children: title }),
      /* @__PURE__ */ jsx("p", { children: description })
    ] }),
    actions
  ] });
}
function Button({ children, kind = "default", size = "regular", ...rest }) {
  return /* @__PURE__ */ jsx("button", { type: "button", ...rest, className: "btn " + (kind === "default" ? "" : kind) + " " + (size === "small" ? "small" : "") + " " + (rest.className ?? ""), children });
}
function ActionLink({ children, to, kind = "default", size = "regular", className = "", style }) {
  return /* @__PURE__ */ jsx(Link, { style, className: "btn " + (kind === "default" ? "" : kind) + " " + (size === "small" ? "small" : "") + " " + className, to, children });
}
function Status({ value }) {
  const raw = value ?? "Not ready";
  const css = raw.toLowerCase().replace(/[^a-z]+/g, "-");
  return /* @__PURE__ */ jsx("span", { className: "badge " + css, children: raw.replaceAll("_", " ") });
}
function FormField({ id, label, children, note }) {
  return /* @__PURE__ */ jsxs("div", { className: "field", children: [
    /* @__PURE__ */ jsx("label", { htmlFor: id, children: label }),
    children,
    note ? /* @__PURE__ */ jsx("div", { className: "help", children: note }) : null
  ] });
}
function Blank({ title, description, action }) {
  return /* @__PURE__ */ jsxs("div", { className: "empty", children: [
    /* @__PURE__ */ jsx(EmptyStateIcon, { size: 32, style: { margin: "0 auto 10px", display: "block", opacity: 0.6 } }),
    /* @__PURE__ */ jsx("strong", { children: title }),
    /* @__PURE__ */ jsx("p", { children: description }),
    action
  ] });
}
function Message({ kind = "info", children, style, className = "" }) {
  return /* @__PURE__ */ jsx("div", { style, className: "alert " + (kind === "info" ? "" : kind) + " " + className, role: kind === "error" ? "alert" : "status", children });
}
function Loading() {
  return /* @__PURE__ */ jsx("p", { className: "muted", role: "status", children: "Loading saved local records…" });
}
function ErrorState({ error, retry }) {
  return /* @__PURE__ */ jsxs(Message, { kind: "error", children: [
    typeof error === "string" ? error : error.message,
    " ",
    retry ? /* @__PURE__ */ jsx(Button, { onClick: retry, size: "small", children: "Retry" }) : null
  ] });
}
function confirmDestructive(noun) {
  return window.confirm(`Delete ${noun}? This action cannot be undone and referenced records will be protected.`);
}
function dateString(timestamp) {
  const result = new Date(timestamp);
  return Number.isNaN(result.getTime()) ? timestamp : result.toLocaleString();
}
createContext(null);
function useWorkspace() {
  return useOutletContext();
}
function useSavedJob(explicitJobId) {
  const { workspaceId } = useWorkspace();
  const params = useParams();
  const jobId = explicitJobId ?? params.jobId;
  const [job2, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const generation = useRef(0);
  const inflight = useRef(null);
  const refreshQueued = useRef(false);
  const apply = useCallback((value) => setJob((previous) => newerSnapshot(previous, value)), []);
  const load = useCallback(async () => {
    if (!jobId) return;
    if (inflight.current) {
      refreshQueued.current = true;
      return inflight.current;
    }
    const current = ++generation.current;
    const task = (async () => {
      try {
        const value = await client.getJob(workspaceId, jobId);
        if (generation.current === current) {
          apply(value);
          setError(null);
        }
      } catch (e) {
        if (generation.current === current) setError(e instanceof Error ? e : new Error("Job not available"));
      } finally {
        if (generation.current === current) setLoading(false);
      }
    })();
    inflight.current = task;
    try {
      await task;
    } finally {
      if (inflight.current === task) {
        inflight.current = null;
        if (refreshQueued.current) {
          refreshQueued.current = false;
          void load();
        }
      }
    }
  }, [workspaceId, jobId, apply]);
  useEffect(() => {
    const gen = generation;
    gen.current++;
    inflight.current = null;
    refreshQueued.current = false;
    setJob(null);
    setLoading(true);
    void load();
    return () => {
      gen.current++;
    };
  }, [load]);
  return { jobId, job: job2, error, loading, load, apply };
}
function useRankings(jobId, offset = 0, search = "") {
  const { workspaceId } = useWorkspace();
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);
  const [resultRevision, setRevision] = useState(0);
  const [weightRevision, setWeightRevision] = useState(0);
  const [total, setTotal] = useState(0);
  const [officialCount, setOfficialCount] = useState(0);
  const [unfinishedCount, setUnfinishedCount] = useState(0);
  const generation = useRef(0);
  const inFlight = useRef(null);
  const refreshQueued = useRef(false);
  const pinned = useRef(null);
  const resetPin = useCallback(() => {
    pinned.current = null;
  }, []);
  const refresh = useCallback(async (forceReplacePin = false) => {
    if (!jobId) return;
    const identity = `${workspaceId}:${jobId}:${search}`;
    if (pinned.current?.identity !== identity || forceReplacePin || offset === 0) {
      pinned.current = null;
    }
    if (inFlight.current) {
      refreshQueued.current = true;
      return inFlight.current;
    }
    const current = ++generation.current;
    const task = (async () => {
      try {
        const pin = pinned.current;
        const result = await client.listRankings(workspaceId, jobId, {
          offset,
          limit: 50,
          search,
          expectedResultRevision: offset > 0 && pin ? pin.resultRevision : void 0,
          expectedWeightRevision: offset > 0 && pin ? pin.weightRevision : void 0
        });
        if (offset === 0 && result.resultRevision !== null && result.weightRevision !== null) {
          pinned.current = { identity, resultRevision: result.resultRevision, weightRevision: result.weightRevision };
        } else if (!pin && result.resultRevision !== null && result.weightRevision !== null) {
          pinned.current = { identity, resultRevision: result.resultRevision, weightRevision: result.weightRevision };
        }
        if (pin && offset > 0 && (result.resultRevision !== pin.resultRevision || result.weightRevision !== pin.weightRevision)) {
          pinned.current = null;
          throw new Error("The ranking changed while you were browsing. Return to page one to load the new revision.");
        }
        if (current === generation.current) {
          setRows(result.items);
          setRevision(result.resultRevision ?? 0);
          setWeightRevision(result.weightRevision ?? 0);
          setTotal(result.total);
          setOfficialCount(result.officialCount);
          setUnfinishedCount(result.unfinishedCount);
          setError(null);
        }
      } catch (e) {
        if (current === generation.current) {
          setRows([]);
          setError(e instanceof Error ? e : new Error("Rankings unavailable"));
        }
      }
    })();
    inFlight.current = task;
    try {
      await task;
    } finally {
      if (inFlight.current === task) {
        inFlight.current = null;
        if (refreshQueued.current) {
          refreshQueued.current = false;
          void refresh();
        }
      }
    }
  }, [workspaceId, jobId, offset, search]);
  useEffect(() => {
    const gen = generation;
    gen.current++;
    inFlight.current = null;
    refreshQueued.current = false;
    setRows([]);
    void refresh();
    return () => {
      gen.current++;
    };
  }, [refresh]);
  return { rows, total, officialCount, unfinishedCount, error, resultRevision, weightRevision, refresh, resetPin };
}
function ProgressBar({ completed, total }) {
  const percent = total > 0 ? Math.min(100, Math.max(0, Math.round(completed / total * 100))) : 0;
  return /* @__PURE__ */ jsx(
    "div",
    {
      className: "progress",
      role: "progressbar",
      "aria-valuemin": 0,
      "aria-valuemax": total,
      "aria-valuenow": completed,
      "aria-label": "Candidates committed",
      children: /* @__PURE__ */ jsx("span", { style: { width: percent + "%" } })
    }
  );
}
function ProgressPage() {
  const { workspaceId } = useWorkspace();
  const { jobId, job: job2, error, loading, load } = useSavedJob();
  const rows = useRankings(jobId);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [notice, setNotice] = useState("");
  const [online, setOnline] = useState(true);
  const [observationEpoch, setObservationEpoch] = useState(0);
  const stopObservation = useRef(() => {
  });
  const actionLock = useRef(false);
  const [ack, setAck] = useState("");
  const lastSeq = useRef(0);
  const refreshRef = useRef(load);
  refreshRef.current = load;
  const ranksRef = useRef(rows.refresh);
  ranksRef.current = rows.refresh;
  useEffect(() => {
    if (!jobId) return;
    let mounted = true;
    let stream = null;
    let poller = null;
    let reconnect = null;
    let refreshTimer = null;
    let errors = 0;
    let healthy = false;
    let stopped = false;
    lastSeq.current = 0;
    const endpoint = `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/jobs/${encodeURIComponent(jobId)}/events`;
    const clean = () => {
      if (stream) {
        stream.close();
        stream = null;
      }
      if (poller !== null) {
        window.clearInterval(poller);
        poller = null;
      }
      if (reconnect !== null) {
        window.clearTimeout(reconnect);
        reconnect = null;
      }
      if (refreshTimer !== null) {
        window.clearTimeout(refreshTimer);
        refreshTimer = null;
      }
    };
    stopObservation.current = () => {
      stopped = true;
      clean();
    };
    const fetchAuthoritative = async () => {
      if (!mounted || stopped) return;
      await refreshRef.current();
      await ranksRef.current();
    };
    const scheduleRefresh = () => {
      if (refreshTimer !== null) return;
      refreshTimer = window.setTimeout(() => {
        refreshTimer = null;
        void fetchAuthoritative();
      }, 140);
    };
    const connect = () => {
      if (!mounted || stopped) return;
      if (stream) {
        stream.close();
        stream = null;
      }
      stream = new EventSource(endpoint, { withCredentials: true });
      stream.onopen = () => {
        if (!mounted) return;
        healthy = true;
        errors = 0;
        setOnline(true);
      };
      const update = (e) => {
        if (!mounted || stopped) return;
        const message = e;
        if (message.type === "snapshot") {
          try {
            const record = JSON.parse(message.data);
            if (record && typeof record === "object" && "sequence" in record && "id" in record && record.id === jobId) {
              const snap = record;
              if (typeof snap.sequence === "number" && snap.sequence >= lastSeq.current) {
                lastSeq.current = snap.sequence;
                scheduleRefresh();
                if (typeof snap.state === "string" && isTerminalJob(snap.state)) {
                  stopped = true;
                  void Promise.all([refreshRef.current(), ranksRef.current()]);
                  clean();
                }
              }
            }
          } catch {
            scheduleRefresh();
          }
          return;
        }
        if (message.type === "replay_expired") {
          scheduleRefresh();
          return;
        }
        const seq = Number(message.lastEventId);
        const newer = consumeSequence(lastSeq.current, seq);
        if (newer === null) return;
        lastSeq.current = newer;
        scheduleRefresh();
        if (["completed", "completed_with_errors", "failed", "cancelled"].includes(message.type)) {
          void Promise.all([refreshRef.current(), ranksRef.current()]);
          stopped = true;
          clean();
        }
      };
      for (const name of [
        "snapshot",
        "queued",
        "running",
        "progress",
        "candidate_committed",
        "paused",
        "completed",
        "completed_with_errors",
        "failed",
        "cancelled",
        "worker_lost",
        "recovery_acknowledged",
        "replay_expired"
      ]) {
        stream.addEventListener(name, update);
      }
      stream.onerror = () => {
        if (!mounted || stopped) return;
        healthy = false;
        setOnline(false);
        errors++;
        if (stream) {
          stream.close();
          stream = null;
        }
        if (reconnect !== null) window.clearTimeout(reconnect);
        reconnect = window.setTimeout(() => {
          reconnect = null;
          connect();
        }, nextReconnectMs(errors));
      };
    };
    connect();
    poller = window.setInterval(() => {
      if (mounted && !healthy && !stopped) void fetchAuthoritative();
    }, 12e3);
    return () => {
      mounted = false;
      stopped = true;
      clean();
    };
  }, [workspaceId, jobId, observationEpoch]);
  const jobState = job2?.state;
  useEffect(() => {
    if (jobState && ["completed", "completed_with_errors", "failed", "cancelled", "paused"].includes(jobState))
      stopObservation.current();
  }, [jobState]);
  const action = async (fn) => {
    if (actionLock.current) return;
    actionLock.current = true;
    setBusy(true);
    setActionError(null);
    setNotice("");
    try {
      await fn();
      await load();
      await rows.refresh();
    } catch (e) {
      setActionError(e instanceof Error ? e : new Error("Action failed"));
    } finally {
      actionLock.current = false;
      setBusy(false);
    }
  };
  const canResume = job2?.state === "paused" || job2?.state === "failed" || job2?.state === "cancelled" || job2?.state === "completed_with_errors";
  const cooldown = job2?.eligible_at !== null && job2?.eligible_at !== void 0 && job2.eligible_at * 1e3 > Date.now();
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx(
      PageHeader,
      {
        title: "Assessment progress",
        description: "The worker commits each candidate independently. Closing or refreshing this page does not create another job.",
        actions: /* @__PURE__ */ jsx(ActionLink, { to: workspacePath(workspaceId, "reports"), children: "Saved jobs" })
      }
    ),
    error ? /* @__PURE__ */ jsx(ErrorState, { error, retry: () => {
      void load();
    } }) : null,
    rows.error ? /* @__PURE__ */ jsx(ErrorState, { error: rows.error, retry: () => {
      void rows.refresh();
    } }) : null,
    actionError ? /* @__PURE__ */ jsx(ErrorState, { error: actionError }) : null,
    notice ? /* @__PURE__ */ jsx(Message, { kind: "success", children: notice }) : null,
    !online ? /* @__PURE__ */ jsx(Message, { kind: "warn", children: "Live connection interrupted. Saved progress is still readable through periodic polling." }) : null,
    loading && !job2 ? /* @__PURE__ */ jsx(Loading, {}) : !job2 ? /* @__PURE__ */ jsx(Blank, { title: "Job not found", description: "This job is unavailable in the current workspace." }) : /* @__PURE__ */ jsxs(Fragment, { children: [
      /* @__PURE__ */ jsxs(Panel, { children: [
        /* @__PURE__ */ jsxs("div", { className: "card-header", children: [
          /* @__PURE__ */ jsx("h2", { children: job2.kind === "assess" ? "Candidate evaluation" : "Job-description extraction" }),
          /* @__PURE__ */ jsx(Status, { value: job2.state })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "row between", children: [
          /* @__PURE__ */ jsxs("b", { children: [
            job2.progress,
            " of ",
            job2.total,
            " committed"
          ] }),
          /* @__PURE__ */ jsx("span", { className: "mono small", children: job2.id.slice(0, 16) })
        ] }),
        /* @__PURE__ */ jsx(ProgressBar, { completed: job2.progress, total: job2.total }),
        /* @__PURE__ */ jsxs("div", { className: "grid cols3", style: { marginTop: 19 }, children: [
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("small", { children: "Started" }),
            /* @__PURE__ */ jsx("p", { children: dateString(job2.created) })
          ] }),
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("small", { children: "Result revision" }),
            /* @__PURE__ */ jsx("p", { children: job2.result_revision })
          ] }),
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("small", { children: "Event sequence" }),
            /* @__PURE__ */ jsx("p", { children: job2.sequence })
          ] })
        ] }),
        job2.error_code ? /* @__PURE__ */ jsxs(Message, { kind: "warn", children: [
          /* @__PURE__ */ jsx("strong", { children: job2.error_code }),
          " · ",
          job2.error_message ?? "Inspect the saved failure before retrying."
        ] }) : null,
        cooldown ? /* @__PURE__ */ jsxs(Message, { kind: "warn", children: [
          "Next retry eligible at ",
          new Date((job2.eligible_at ?? 0) * 1e3).toLocaleString(),
          "."
        ] }) : null,
        /* @__PURE__ */ jsxs("div", { className: "toolbar", style: { marginTop: 15 }, children: [
          job2.kind === "assess" ? /* @__PURE__ */ jsx(
            ActionLink,
            {
              to: workspacePath(workspaceId, "rankings", { jobId: job2.id }),
              kind: "primary",
              children: "View candidate rankings"
            }
          ) : /* @__PURE__ */ jsx(ActionLink, { to: workspacePath(workspaceId, "jd"), kind: "primary", children: "Review extracted JD" }),
          ["queued", "running", "cancelling"].includes(job2.state) ? /* @__PURE__ */ jsx(Button, { kind: "danger", disabled: busy || job2.state === "cancelling", onClick: () => {
            void action(async () => {
              await client.controlJob(workspaceId, job2.id, "cancel");
              setNotice("Cancellation requested. In-flight paid calls may still complete.");
            });
          }, children: "Request cancellation" }) : null,
          canResume && job2.error_code !== "worker_unknown_delivery" ? /* @__PURE__ */ jsx(Button, { kind: "subtle", disabled: busy || cooldown, onClick: () => {
            void action(async () => {
              await client.controlJob(workspaceId, job2.id, "resume");
              setObservationEpoch((v) => v + 1);
              setNotice("Job requeued with existing checkpoints preserved.");
            });
          }, children: "Resume eligible work" }) : null
        ] })
      ] }),
      job2.error_code === "worker_unknown_delivery" ? /* @__PURE__ */ jsxs(Panel, { children: [
        /* @__PURE__ */ jsx("h2", { children: "Uncertain worker delivery — operator resolution required" }),
        /* @__PURE__ */ jsx(Message, { kind: "warn", children: "A model request might have been sent before the worker stopped. Retrying could incur a duplicate provider charge. Committed candidates remain preserved." }),
        /* @__PURE__ */ jsx(Button, { onClick: () => {
          void action(async () => {
            const result = await client.resolveUnknown(workspaceId, job2.id, "inspect");
            if (typeof result === "object" && result !== null && "committed_candidates" in result)
              setNotice(`Saved candidate checkpoint count: ${String(result.committed_candidates)}. No provider call was made.`);
          });
        }, children: "Inspect saved checkpoints" }),
        /* @__PURE__ */ jsx(
          FormField,
          {
            id: "duplicate-cost-ack",
            label: "To authorize a possible duplicate paid request, enter the exact acknowledgement phrase",
            note: "I ACCEPT THE RISK OF DUPLICATE PROVIDER CHARGES",
            children: /* @__PURE__ */ jsx("input", { id: "duplicate-cost-ack", value: ack, onChange: (e) => setAck(e.target.value), autoComplete: "off" })
          }
        ),
        /* @__PURE__ */ jsx(
          Button,
          {
            kind: "danger",
            disabled: busy || ack !== "I ACCEPT THE RISK OF DUPLICATE PROVIDER CHARGES",
            onClick: () => {
              if (window.confirm("Permit a retry that may duplicate a paid provider operation?")) void action(async () => {
                await client.resolveUnknown(workspaceId, job2.id, "accept_duplicate_risk", ack);
                setObservationEpoch((v) => v + 1);
                setNotice("Operator acknowledgement recorded. Only incomplete candidates will be rescheduled.");
              });
            },
            children: "Acknowledge risk and requeue"
          }
        )
      ] }) : null,
      /* @__PURE__ */ jsxs(Panel, { children: [
        /* @__PURE__ */ jsxs("div", { className: "card-header", children: [
          /* @__PURE__ */ jsx("h2", { children: "Committed candidates" }),
          /* @__PURE__ */ jsx(Status, { value: rows.total + " saved results" })
        ] }),
        rows.rows.length ? /* @__PURE__ */ jsx("div", { className: "table-scroller", children: /* @__PURE__ */ jsxs("table", { children: [
          /* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsxs("tr", { children: [
            /* @__PURE__ */ jsx("th", { children: "Candidate" }),
            /* @__PURE__ */ jsx("th", { children: "Official score" }),
            /* @__PURE__ */ jsx("th", { children: "Assessment state" }),
            /* @__PURE__ */ jsx("th", { children: "Evidence" })
          ] }) }),
          /* @__PURE__ */ jsx("tbody", { children: rows.rows.map((row) => /* @__PURE__ */ jsxs("tr", { children: [
            /* @__PURE__ */ jsx("td", { children: row.candidate }),
            /* @__PURE__ */ jsx("td", { children: /* @__PURE__ */ jsx("b", { children: row.weighted_score === null ? "Unavailable" : row.weighted_score.toFixed(2) + "%" }) }),
            /* @__PURE__ */ jsx("td", { children: /* @__PURE__ */ jsx(Status, { value: row.score_status }) }),
            /* @__PURE__ */ jsx("td", { children: /* @__PURE__ */ jsx(ActionLink, { to: workspacePath(workspaceId, "candidate", { jobId: job2.id, candidateId: row.candidate_id }), children: "Inspect" }) })
          ] }, row.candidate_id)) })
        ] }) }) : /* @__PURE__ */ jsx(Blank, { title: "No committed candidates yet", description: "The worker has not completed its first candidate checkpoint." }),
        rows.total > rows.rows.length ? /* @__PURE__ */ jsxs("p", { className: "help", children: [
          "Showing the first ",
          rows.rows.length,
          " of ",
          rows.total,
          ". Open Rankings to page through every candidate."
        ] }) : null
      ] })
    ] })
  ] });
}
function RankingsPage() {
  const { workspaceId, data } = useWorkspace();
  const { jobId, job: job2, error, loading } = useSavedJob();
  const [nameFilter, setNameFilter] = useState("");
  const [page, setPage] = useState(0);
  const result = useRankings(jobId, page * 50, nameFilter);
  const [busy, setBusy] = useState(false);
  const [exportError, setExportError] = useState(null);
  const [usage, setUsage] = useState(null);
  const [showUsage, setShowUsage] = useState(false);
  const [shadow, setShadow] = useState(null);
  const [showShadow, setShowShadow] = useState(false);
  const [shadowLoading, setShadowLoading] = useState(false);
  const filtered = result.rows;
  const handleRefreshRankings = () => {
    setPage(0);
    result.resetPin();
    void result.refresh(true);
  };
  const loadUsage = async () => {
    if (!job2) return;
    try {
      const u = await client.getJobUsage(workspaceId, job2.id);
      setUsage(u);
      setShowUsage(true);
    } catch (e) {
      setExportError(e instanceof Error ? e : new Error("Failed to load usage metrics"));
    }
  };
  const loadShadow = async () => {
    if (!job2) return;
    setShadowLoading(true);
    try {
      const s = await client.runSemanticShadow(workspaceId, job2.id);
      setShadow(s);
      setShowShadow(true);
    } catch (e) {
      setExportError(e instanceof Error ? e : new Error("Failed to load semantic shadow"));
    } finally {
      setShadowLoading(false);
    }
  };
  const createExport = async () => {
    if (!job2 || !data.weights || busy) return;
    setBusy(true);
    setExportError(null);
    try {
      const latest = await client.getJob(workspaceId, job2.id);
      if (latest.result_revision !== result.resultRevision || data.weights.revision !== result.weightRevision)
        throw new Error("Result or weight revision changed. Reload before export.");
      const file = await client.export(workspaceId, job2.id, latest.result_revision, data.weights.revision);
      const link = document.createElement("a");
      link.href = `/api/v1/workspaces/${workspaceId}/exports/${file.id}/download`;
      link.download = "Reliance_Weaving_Mills_Assessment.zip";
      document.body.append(link);
      link.click();
      link.remove();
    } catch (e) {
      setExportError(e instanceof Error ? e : new Error("Export failed"));
    } finally {
      setBusy(false);
    }
  };
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx(
      PageHeader,
      {
        title: "Candidate rankings",
        description: "Canonical, source-grounded ranking from the existing Python engine. An incomplete candidate has no official score.",
        actions: /* @__PURE__ */ jsx(ActionLink, { to: workspacePath(workspaceId, "reports"), children: "Saved results" })
      }
    ),
    error ? /* @__PURE__ */ jsx(ErrorState, { error }) : null,
    result.error ? /* @__PURE__ */ jsxs(Panel, { className: "error-panel", children: [
      /* @__PURE__ */ jsxs(Message, { kind: "warn", children: [
        /* @__PURE__ */ jsx("strong", { children: "Revision notice:" }),
        " ",
        result.error.message
      ] }),
      /* @__PURE__ */ jsx("div", { className: "toolbar", style: { marginTop: 8 }, children: /* @__PURE__ */ jsx(Button, { kind: "primary", onClick: handleRefreshRankings, children: "Refresh rankings (load latest revision)" }) })
    ] }) : null,
    exportError ? /* @__PURE__ */ jsx(ErrorState, { error: exportError }) : null,
    loading && !job2 ? /* @__PURE__ */ jsx(Loading, {}) : !job2 ? /* @__PURE__ */ jsx(Blank, { title: "Job unavailable", description: "Open a saved assessment from Reports." }) : /* @__PURE__ */ jsxs(Fragment, { children: [
      /* @__PURE__ */ jsxs("div", { className: "grid cols3 stat-grid", children: [
        /* @__PURE__ */ jsxs(Panel, { className: "stat-card", children: [
          /* @__PURE__ */ jsx("small", { className: "stat-title", children: nameFilter ? "Filtered" : "Total Evaluated" }),
          /* @__PURE__ */ jsx("div", { className: "stat-value", children: result.total }),
          /* @__PURE__ */ jsx("span", { className: "small text-muted stat-desc", children: nameFilter ? "Matches search query" : "All candidates in run" })
        ] }),
        /* @__PURE__ */ jsxs(Panel, { className: "stat-card", children: [
          /* @__PURE__ */ jsx("small", { className: "stat-title", children: "Official Scores" }),
          /* @__PURE__ */ jsx("div", { className: "stat-value", children: result.officialCount }),
          /* @__PURE__ */ jsx("span", { className: "small text-muted stat-desc", children: nameFilter ? "Matching completed" : "Completed evaluations" })
        ] }),
        /* @__PURE__ */ jsxs(Panel, { className: "stat-card", children: [
          /* @__PURE__ */ jsx("small", { className: "stat-title", children: "Unfinished" }),
          /* @__PURE__ */ jsx("div", { className: "stat-value", children: result.unfinishedCount }),
          /* @__PURE__ */ jsx("span", { className: "small text-muted stat-desc", children: nameFilter ? "Matching incomplete" : "Incomplete or pending" })
        ] })
      ] }),
      showUsage && usage ? /* @__PURE__ */ jsxs(Panel, { children: [
        /* @__PURE__ */ jsxs("div", { className: "card-header", children: [
          /* @__PURE__ */ jsx("h2", { children: "Provider Usage & Cost Metrics" }),
          /* @__PURE__ */ jsx(Button, { size: "small", onClick: () => setShowUsage(false), children: "Close" })
        ] }),
        /* @__PURE__ */ jsxs("p", { className: "small", children: [
          "Job scope: ",
          /* @__PURE__ */ jsx("span", { className: "mono", children: usage.job_id }),
          " · Provider: ",
          /* @__PURE__ */ jsx("strong", { children: usage.provider }),
          " · Model: ",
          /* @__PURE__ */ jsx("strong", { children: usage.model })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "grid cols3", style: { marginTop: 12, marginBottom: 12 }, children: [
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("small", { children: "Logical model calls" }),
            /* @__PURE__ */ jsx("p", { children: usage.logical_model_calls })
          ] }),
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("small", { children: "HTTP request attempts" }),
            /* @__PURE__ */ jsx("p", { children: usage.actual_model_request_attempts })
          ] }),
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("small", { children: "Prompt reuses" }),
            /* @__PURE__ */ jsx("p", { children: usage.reused_prompt_calls })
          ] })
        ] }),
        /* @__PURE__ */ jsxs("p", { children: [
          /* @__PURE__ */ jsx("strong", { children: "Tokens:" }),
          " ",
          usage.token_usage.prompt_tokens !== null && usage.token_usage.prompt_tokens !== void 0 ? `Prompt: ${usage.token_usage.prompt_tokens} · Completion: ${usage.token_usage.completion_tokens} · Total: ${usage.token_usage.total_tokens}` : "Preserved as unknown (provider did not report)"
        ] }),
        /* @__PURE__ */ jsxs("p", { children: [
          /* @__PURE__ */ jsx("strong", { children: "Cost:" }),
          " ",
          usage.cost_label
        ] }),
        /* @__PURE__ */ jsx("small", { className: "help", children: "All provider credentials and keys remain strictly server-side and are excluded from UI, logs and exports." })
      ] }) : null,
      showShadow && shadow ? /* @__PURE__ */ jsxs(Panel, { children: [
        /* @__PURE__ */ jsxs("div", { className: "card-header", children: [
          /* @__PURE__ */ jsx("h2", { children: "Optional Semantic Shadow Diagnostics" }),
          /* @__PURE__ */ jsx(Button, { size: "small", onClick: () => setShowShadow(false), children: "Close" })
        ] }),
        /* @__PURE__ */ jsx(Message, { kind: "warn", children: shadow.notice }),
        shadow.items.length ? /* @__PURE__ */ jsx("div", { className: "table-scroller", style: { marginTop: 12 }, children: /* @__PURE__ */ jsxs("table", { children: [
          /* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsxs("tr", { children: [
            /* @__PURE__ */ jsx("th", { children: "Requirement" }),
            /* @__PURE__ */ jsx("th", { children: "Candidate" }),
            /* @__PURE__ */ jsx("th", { children: "Similarity" }),
            /* @__PURE__ */ jsx("th", { children: "Diagnostic Finding" })
          ] }) }),
          /* @__PURE__ */ jsx("tbody", { children: shadow.items.map((item, idx) => /* @__PURE__ */ jsxs("tr", { children: [
            /* @__PURE__ */ jsx("td", { children: item.requirement_id }),
            /* @__PURE__ */ jsx("td", { children: /* @__PURE__ */ jsx("span", { className: "mono", children: item.candidate_id.slice(0, 12) }) }),
            /* @__PURE__ */ jsxs("td", { children: [
              (item.similarity * 100).toFixed(1),
              "%"
            ] }),
            /* @__PURE__ */ jsx("td", { children: item.finding })
          ] }, idx)) })
        ] }) }) : /* @__PURE__ */ jsx(Blank, { title: "No shadow findings", description: "Semantic shadow returned no diagnostic findings." })
      ] }) : null,
      /* @__PURE__ */ jsxs(Panel, { children: [
        /* @__PURE__ */ jsxs("div", { className: "card-header", children: [
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("h2", { children: "Verified weighted leaderboard" }),
            /* @__PURE__ */ jsx("span", { className: "small text-muted", children: "Authoritative ranking snapshot from Python assessment engine" })
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "row", style: { gap: 8 }, children: [
            /* @__PURE__ */ jsx(Status, { value: "Weights revision " + result.weightRevision }),
            /* @__PURE__ */ jsxs(Button, { kind: "primary", size: "small", onClick: () => {
              void createExport();
            }, disabled: busy || result.resultRevision === 0, children: [
              /* @__PURE__ */ jsx(DownloadIcon, { size: 14, style: { marginRight: 4 } }),
              "Export this result + weight revision"
            ] })
          ] })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "leaderboard-toolbar", children: [
          /* @__PURE__ */ jsxs("div", { className: "search-field-container", style: { position: "relative" }, children: [
            /* @__PURE__ */ jsx(SearchIcon, { size: 15, style: { position: "absolute", left: 12, top: 13, color: "var(--text-muted)", pointerEvents: "none" } }),
            /* @__PURE__ */ jsx(
              "input",
              {
                id: "candidate-filter",
                value: nameFilter,
                onChange: (e) => {
                  setNameFilter(e.target.value);
                  setPage(0);
                },
                placeholder: "Search all evaluated candidates...",
                style: { paddingLeft: 36 },
                className: "search-input",
                "aria-label": "Filter candidates by filename or name"
              }
            )
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "toolbar-actions", children: [
            /* @__PURE__ */ jsxs(Button, { size: "small", onClick: handleRefreshRankings, children: [
              /* @__PURE__ */ jsx(RefreshIcon, { size: 14, style: { marginRight: 4 } }),
              "Refresh rankings"
            ] }),
            /* @__PURE__ */ jsxs(Button, { size: "small", onClick: () => void loadUsage(), children: [
              /* @__PURE__ */ jsx(ChartBarIcon, { size: 14, style: { marginRight: 4 } }),
              "Usage & costs"
            ] }),
            /* @__PURE__ */ jsxs(Button, { size: "small", disabled: shadowLoading, onClick: () => void loadShadow(), children: [
              /* @__PURE__ */ jsx(SparkleIcon, { size: 14, style: { marginRight: 4 } }),
              shadowLoading ? "Running shadow..." : "Semantic shadow"
            ] }),
            /* @__PURE__ */ jsx(ActionLink, { to: workspacePath(workspaceId, "weights"), className: "btn small", children: "Edit weights" }),
            /* @__PURE__ */ jsx(ActionLink, { to: workspacePath(workspaceId, "progress", { jobId: job2.id }), className: "btn small", children: "Progress" })
          ] })
        ] }),
        filtered.length ? /* @__PURE__ */ jsx("div", { className: "table-scroller", children: /* @__PURE__ */ jsxs("table", { className: "cockpit-table", children: [
          /* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsxs("tr", { children: [
            /* @__PURE__ */ jsx("th", { children: "Rank" }),
            /* @__PURE__ */ jsx("th", { children: "Candidate" }),
            /* @__PURE__ */ jsx("th", { children: "Score" }),
            /* @__PURE__ */ jsx("th", { children: "Required" }),
            /* @__PURE__ */ jsx("th", { children: "Preferred" }),
            /* @__PURE__ */ jsx("th", { children: "Experience" }),
            /* @__PURE__ */ jsx("th", { children: "Education" }),
            /* @__PURE__ */ jsx("th", { children: "State" }),
            /* @__PURE__ */ jsx("th", { children: "Why" })
          ] }) }),
          /* @__PURE__ */ jsx("tbody", { children: filtered.map((row) => /* @__PURE__ */ jsxs("tr", { className: "cockpit-table-row", children: [
            /* @__PURE__ */ jsx("td", { className: "font-bold", children: row.rank === null ? "—" : "#" + row.rank }),
            /* @__PURE__ */ jsx("td", { children: /* @__PURE__ */ jsx("strong", { children: row.candidate }) }),
            /* @__PURE__ */ jsx("td", { className: "font-bold mono", children: row.weighted_score === null ? "Not ready" : row.weighted_score.toFixed(2) + "%" }),
            /* @__PURE__ */ jsx("td", { children: row.required }),
            /* @__PURE__ */ jsx("td", { children: row.preferred }),
            /* @__PURE__ */ jsx("td", { children: row.experience }),
            /* @__PURE__ */ jsx("td", { children: row.education }),
            /* @__PURE__ */ jsx("td", { children: /* @__PURE__ */ jsx(Status, { value: row.score_status }) }),
            /* @__PURE__ */ jsx("td", { children: /* @__PURE__ */ jsxs(ActionLink, { to: workspacePath(workspaceId, "candidate", { jobId: job2.id, candidateId: row.candidate_id }), children: [
              "Why ",
              /* @__PURE__ */ jsx(ArrowRightIcon, { size: 12, style: { marginLeft: 3 } })
            ] }) })
          ] }, row.candidate_id)) })
        ] }) }) : /* @__PURE__ */ jsx(Blank, { title: "No matching results", description: "Try a different filter or review job progress." }),
        /* @__PURE__ */ jsxs("div", { className: "cockpit-pagination", children: [
          /* @__PURE__ */ jsxs("span", { className: "small text-muted", children: [
            "Showing ",
            filtered.length ? page * 50 + 1 : 0,
            "–",
            Math.min((page + 1) * 50, result.total),
            " of ",
            result.total,
            " matching candidates (page ",
            page + 1,
            " of ",
            Math.max(1, Math.ceil(result.total / 50)),
            ")"
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "pagination-buttons", children: [
            /* @__PURE__ */ jsxs(Button, { size: "small", disabled: page === 0, onClick: () => setPage((v) => Math.max(0, v - 1)), children: [
              /* @__PURE__ */ jsx(ChevronLeftIcon, { size: 13, style: { marginRight: 4 } }),
              "Previous page"
            ] }),
            /* @__PURE__ */ jsxs(Button, { size: "small", disabled: (page + 1) * 50 >= result.total, onClick: () => setPage((v) => v + 1), children: [
              "Next page",
              /* @__PURE__ */ jsx(ChevronRightIcon, { size: 13, style: { marginLeft: 4 } })
            ] })
          ] })
        ] })
      ] }),
      filtered?.length ? /* @__PURE__ */ jsxs(Panel, { children: [
        /* @__PURE__ */ jsx("div", { className: "card-header", children: /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("div", { className: "eyebrow", style: { marginBottom: 4 }, children: "Evidence-Based Ranking Rationale" }),
          /* @__PURE__ */ jsx("h2", { style: { margin: "0 0 4px 0" }, children: "Ranking explained · Why candidates ranked this way" }),
          /* @__PURE__ */ jsx("p", { className: "small text-muted", style: { margin: 0 }, children: "One clear explanation per candidate under approved JD priorities. Detailed evidence is available in candidate view." })
        ] }) }),
        /* @__PURE__ */ jsx("div", { className: "stack", style: { gap: 12, marginTop: 14 }, children: filtered.map((row) => /* @__PURE__ */ jsxs("div", { className: "why", style: { margin: 0, padding: "14px 18px" }, children: [
          /* @__PURE__ */ jsxs("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 6 }, children: [
            /* @__PURE__ */ jsxs("div", { style: { display: "flex", alignItems: "center", gap: 10 }, children: [
              /* @__PURE__ */ jsx("span", { className: "num", style: { padding: "3px 8px", fontSize: 13, fontWeight: 700, borderRadius: 6 }, children: row.rank === null ? "—" : `#${row.rank}` }),
              /* @__PURE__ */ jsx("strong", { style: { fontSize: 14 }, children: row.candidate })
            ] }),
            /* @__PURE__ */ jsxs("div", { style: { display: "flex", alignItems: "center", gap: 8 }, children: [
              /* @__PURE__ */ jsx("strong", { style: { fontSize: 14, color: "var(--brand-green)" }, children: row.weighted_score === null ? "Not ready" : `${row.weighted_score.toFixed(2)}%` }),
              /* @__PURE__ */ jsxs(ActionLink, { size: "small", to: workspacePath(workspaceId, "candidate", { jobId: job2.id, candidateId: row.candidate_id }), children: [
                "Why ",
                /* @__PURE__ */ jsx(ArrowRightIcon, { size: 12, style: { marginLeft: 3 } })
              ] })
            ] })
          ] }),
          /* @__PURE__ */ jsx("p", { style: { margin: 0, fontSize: 13, lineHeight: 1.5, color: "var(--text-secondary)" }, children: row.placement_reason || "Verified match score under approved employer priorities." })
        ] }, row.candidate_id)) })
      ] }) : null,
      /* @__PURE__ */ jsx("div", { className: "compliance-disclaimer-card", children: /* @__PURE__ */ jsx("small", { className: "disclaimer-text", children: "These are evidence-grounded CV comparisons, not independent verification of professional competence. Transferable evidence earns no direct requirement credit." }) })
    ] })
  ] });
}
function CandidateDetailView({
  workspaceId,
  jobId,
  candidateId,
  onClose,
  onBackToLeaderboard,
  onFocusedReviewComplete
}) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  const [weighted, setWeighted] = useState(null);
  const [weightRevision, setWeightRevision] = useState(null);
  const [focusedBusy, setFocusedBusy] = useState(null);
  const [focusedNotice, setFocusedNotice] = useState(null);
  const [history, setHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [activeTab, setActiveTab] = useState("all");
  const [compareCandidateIndex, setCompareCandidateIndex] = useState(null);
  const reload = useCallback(() => {
    void Promise.all([
      client.getCandidate(workspaceId, jobId, candidateId),
      client.candidateWeighted(workspaceId, jobId, candidateId),
      client.getReviewHistory(workspaceId, jobId, candidateId)
    ]).then(([candidate2, weightedResult, historyItems]) => {
      if (candidate2.result_revision !== weightedResult.resultRevision) {
        setError(new Error("Assessment changed during loading. Refresh the candidate details."));
        return;
      }
      setDetail(candidate2);
      setWeighted(weightedResult.result);
      setWeightRevision(weightedResult.weightRevision);
      setHistory(historyItems);
      setError(null);
    }).catch((e) => {
      setError(e instanceof Error ? e : new Error("Candidate evidence not found"));
    });
  }, [workspaceId, jobId, candidateId]);
  useEffect(() => {
    reload();
    const refocus = () => {
      if (!document.hidden) reload();
    };
    window.addEventListener("focus", refocus);
    return () => window.removeEventListener("focus", refocus);
  }, [reload]);
  const handleFocusedReview = async (reqId) => {
    if (focusedBusy || !detail) return;
    setFocusedBusy(reqId);
    setFocusedNotice(null);
    try {
      const res = await client.runFocusedReview(workspaceId, jobId, candidateId, reqId, void 0, void 0, detail.result_revision);
      setFocusedNotice(`Focused review completed: ${res.new_verdict} (revision ${res.result_revision}). ${res.explanation}`);
      reload();
      onFocusedReviewComplete?.();
    } catch (e) {
      setError(e instanceof Error ? e : new Error("Focused review failed"));
    } finally {
      setFocusedBusy(null);
    }
  };
  if (error) return /* @__PURE__ */ jsx(ErrorState, { error });
  if (!detail) return /* @__PURE__ */ jsx(Loading, {});
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsxs(Panel, { children: [
      /* @__PURE__ */ jsx("div", { className: "eyebrow", style: { marginBottom: 4 }, children: "INDIVIDUAL CANDIDATE REVIEW" }),
      /* @__PURE__ */ jsx("h2", { style: { margin: "0 0 4px 0" }, children: "Final JD-to-CV assessment" }),
      /* @__PURE__ */ jsx("p", { className: "small text-muted", style: { margin: "0 0 16px 0" }, children: "Inspect each candidate's decisions, supporting evidence, and reasoning." }),
      /* @__PURE__ */ jsxs("div", { className: "card-header", style: { padding: "12px 16px", background: "var(--surface-strong)", borderRadius: 12, border: "1px solid var(--border-soft)" }, children: [
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("h3", { style: { margin: 0, fontSize: 16 }, children: detail.candidate.candidate_name }),
          /* @__PURE__ */ jsxs("span", { className: "mono small text-muted", children: [
            "Document source: ",
            detail.candidate.candidate_source
          ] })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "row", style: { gap: 8 }, children: [
          onBackToLeaderboard ? /* @__PURE__ */ jsxs(Button, { size: "small", kind: "primary", onClick: onBackToLeaderboard, children: [
            /* @__PURE__ */ jsx(ArrowUpIcon, { size: 13, style: { marginRight: 4 } }),
            "Back to Leaderboard"
          ] }) : null,
          /* @__PURE__ */ jsx(Status, { value: !weighted || weighted.weighted_score === null ? "Assessment incomplete" : "Weighted score " + weighted.weighted_score.toFixed(2) + "%" }),
          candidateId ? /* @__PURE__ */ jsxs("a", { className: "btn small subtle", href: `/api/v1/workspaces/${workspaceId}/documents/${candidateId}/download`, children: [
            /* @__PURE__ */ jsx(DownloadIcon, { size: 14, style: { marginRight: 4 } }),
            "Download source"
          ] }) : null,
          onClose ? /* @__PURE__ */ jsxs(Button, { size: "small", onClick: onClose, "aria-label": "Close candidate evidence", children: [
            /* @__PURE__ */ jsx(CloseIcon, { size: 14, style: { marginRight: 4 } }),
            "Close"
          ] }) : null
        ] })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "candidate-metric-grid", style: { marginTop: 14 }, children: [
        /* @__PURE__ */ jsxs("div", { className: "candidate-metric-box", children: [
          /* @__PURE__ */ jsx("span", { className: "metric-label", children: "Weighted Score" }),
          /* @__PURE__ */ jsx("span", { className: "metric-val", children: weighted?.weighted_score != null ? `${weighted.weighted_score.toFixed(1)}%` : "—" }),
          /* @__PURE__ */ jsx("span", { className: "metric-sub", children: weighted?.rank ? `Official Rank #${weighted.rank}` : "Incomplete" })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "candidate-metric-box", children: [
          /* @__PURE__ */ jsx("span", { className: "metric-label", children: "JD Matched" }),
          /* @__PURE__ */ jsxs("span", { className: "metric-val", children: [
            detail.candidate.matched_required + detail.candidate.matched_preferred,
            " / ",
            detail.candidate.total_required + detail.candidate.total_preferred
          ] }),
          /* @__PURE__ */ jsx("span", { className: "metric-sub", children: "Verified Found criteria" })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "candidate-metric-box", children: [
          /* @__PURE__ */ jsx("span", { className: "metric-label", children: "Transferable" }),
          /* @__PURE__ */ jsx("span", { className: "metric-val", children: detail.final.Transferable ?? 0 }),
          /* @__PURE__ */ jsx("span", { className: "metric-sub", children: "Not counted as matched" })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "candidate-metric-box", children: [
          /* @__PURE__ */ jsx("span", { className: "metric-label", children: "Required / Preferred" }),
          /* @__PURE__ */ jsxs("span", { className: "metric-val", style: { fontSize: 18 }, children: [
            detail.candidate.matched_required,
            "/",
            detail.candidate.total_required,
            " · ",
            detail.candidate.matched_preferred,
            "/",
            detail.candidate.total_preferred
          ] }),
          /* @__PURE__ */ jsxs("span", { className: "metric-sub", children: [
            "Engine: ",
            detail.candidate.evaluation_mode
          ] })
        ] })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "small", style: { marginTop: 12, color: "var(--text-muted)" }, children: [
        "Scoring projection revision ",
        weightRevision ?? "not ready",
        " · Primary engine score ",
        detail.candidate.primary_score === null ? "unavailable" : detail.candidate.primary_score.toFixed(2) + "%",
        " · Official weighted rank ",
        weighted?.rank === null || !weighted ? "unavailable" : "#" + weighted.rank
      ] }),
      (() => {
        const rawNotices = [
          ...detail.candidate.errors || [],
          ...detail.final.Notices || []
        ];
        const unique = Array.from(new Set(rawNotices)).filter(
          (msg) => !msg.includes("contradicted the declared source relationship") && !msg.includes("education ambiguous") && !msg.includes("unresolved after grouped correction")
        );
        if (!unique.length) return null;
        return /* @__PURE__ */ jsx(Message, { kind: "warn", style: { marginTop: 12 }, children: unique.slice(0, 3).join(" · ") });
      })(),
      focusedNotice ? /* @__PURE__ */ jsx(Message, { kind: "success", style: { marginTop: 12 }, children: focusedNotice }) : null,
      detail.ranking_reasoning ? /* @__PURE__ */ jsxs("div", { className: "evidence-explanation-block", style: { marginTop: 20 }, children: [
        /* @__PURE__ */ jsx("div", { className: "section-eyebrow", children: "EVIDENCE-BASED RANKING EXPLANATION" }),
        /* @__PURE__ */ jsx("h2", { className: "section-title", style: { margin: "4px 0 6px 0" }, children: "Why this CV received its ranking" }),
        /* @__PURE__ */ jsx("p", { className: "section-subtitle", style: { margin: "0 0 16px 0", color: "var(--text-muted)" }, children: "What helped this candidate's score, and what held it back." }),
        /* @__PURE__ */ jsxs("div", { className: "assessment-summary-card", children: [
          /* @__PURE__ */ jsxs("div", { className: "summary-card-header", children: [
            /* @__PURE__ */ jsx("span", { className: "summary-card-eyebrow", children: "ASSESSMENT SUMMARY" }),
            /* @__PURE__ */ jsxs("span", { className: "summary-card-rank-badge mono", children: [
              "Rank #",
              detail.ranking_reasoning.rank ?? "—",
              " · ",
              detail.ranking_reasoning.score != null ? `${detail.ranking_reasoning.score.toFixed(2)}%` : "—"
            ] })
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "summary-candidate-title", children: [
            detail.candidate.candidate_name,
            " · ranking rationale"
          ] }),
          /* @__PURE__ */ jsx("p", { className: "summary-rationale-text", children: detail.ranking_reasoning.summary })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "score-factors-grid", style: { marginTop: 18 }, children: [
          /* @__PURE__ */ jsxs("div", { className: "score-factor-column positive", children: [
            /* @__PURE__ */ jsxs("div", { className: "factor-column-header positive", children: [
              /* @__PURE__ */ jsx("span", { className: "factor-check-icon", children: "✓" }),
              " WHAT HELPED THIS CV"
            ] }),
            /* @__PURE__ */ jsx("div", { className: "factor-cards-list", children: detail.ranking_reasoning.strengths.length > 0 ? detail.ranking_reasoning.strengths.map((item, idx) => /* @__PURE__ */ jsxs("div", { className: "factor-card positive", children: [
              /* @__PURE__ */ jsx("div", { className: "factor-card-title", children: item.requirement }),
              /* @__PURE__ */ jsxs("div", { className: "factor-card-points positive mono", children: [
                "+",
                item.points != null ? item.points.toFixed(2) : "0.00",
                " points"
              ] }),
              /* @__PURE__ */ jsx("div", { className: "factor-card-why", children: item.why })
            ] }, idx)) : /* @__PURE__ */ jsx("div", { className: "factor-card-empty", children: "No positive points earned from verified Found criteria." }) })
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "score-factor-column negative", children: [
            /* @__PURE__ */ jsxs("div", { className: "factor-column-header negative", children: [
              /* @__PURE__ */ jsx("span", { className: "factor-cross-icon", children: "◇" }),
              " WHAT REDUCED THE MATCH"
            ] }),
            /* @__PURE__ */ jsx("div", { className: "factor-cards-list", children: detail.ranking_reasoning.gaps.length > 0 ? detail.ranking_reasoning.gaps.map((item, idx) => /* @__PURE__ */ jsxs("div", { className: "factor-card negative", children: [
              /* @__PURE__ */ jsx("div", { className: "factor-card-title", children: item.requirement }),
              /* @__PURE__ */ jsxs("div", { className: "factor-card-points negative mono", children: [
                item.points != null ? item.points.toFixed(2) : "0.00",
                " points unearned"
              ] }),
              /* @__PURE__ */ jsx("div", { className: "factor-card-why", children: item.why })
            ] }, idx)) : /* @__PURE__ */ jsx("div", { className: "factor-card-empty", children: "No unmet criteria identified." }) })
          ] })
        ] })
      ] }) : null,
      (() => {
        if (!detail.ranking_reasoning) return null;
        const comps = detail.ranking_reasoning.all_comparisons || [];
        const activeComp = comps.length > 0 ? comps.find((c) => c.against_candidate_index === compareCandidateIndex) || comps[0] : null;
        const hasAdvantages = (activeComp?.top_candidate_advantages?.length ?? 0) > 0 || (activeComp?.other_candidate_advantages?.length ?? 0) > 0 || detail.ranking_reasoning.top_candidate_advantages.length > 0;
        if (!activeComp && !hasAdvantages && !detail.ranking_reasoning.head_to_head_summary) {
          return null;
        }
        const scoreDiff = activeComp?.score_gap ?? detail.ranking_reasoning.score_gap;
        const leaderAdvantages = activeComp?.top_candidate_advantages ?? detail.ranking_reasoning.top_candidate_advantages;
        const otherAdvantages = activeComp?.other_candidate_advantages ?? detail.ranking_reasoning.other_candidate_advantages;
        return /* @__PURE__ */ jsxs("div", { className: "head-to-head-block", style: { marginTop: 28, marginBottom: 20 }, children: [
          /* @__PURE__ */ jsx("div", { className: "section-eyebrow", children: "HEAD-TO-HEAD COMPARISON" }),
          /* @__PURE__ */ jsx("h2", { className: "section-title", style: { margin: "4px 0 6px 0" }, children: detail.ranking_reasoning.rank === 1 ? "Why this candidate ranks first" : "Head-to-head comparative analysis" }),
          /* @__PURE__ */ jsx("p", { className: "head-to-head-summary-text", style: { margin: "0 0 16px 0", color: "var(--text-secondary)" }, children: detail.ranking_reasoning.head_to_head_summary }),
          comps.length > 1 ? /* @__PURE__ */ jsxs("div", { className: "head-to-head-selector-row", style: { marginBottom: 14 }, children: [
            /* @__PURE__ */ jsx("label", { htmlFor: "compare-candidate-select", className: "compare-label", style: { marginRight: 8, fontSize: 13, fontWeight: 600 }, children: "Compare against" }),
            /* @__PURE__ */ jsx(
              "select",
              {
                id: "compare-candidate-select",
                className: "compare-select",
                value: activeComp?.against_candidate_index ?? "",
                onChange: (e) => setCompareCandidateIndex(Number(e.target.value)),
                children: comps.map((c) => /* @__PURE__ */ jsxs("option", { value: c.against_candidate_index, children: [
                  c.against,
                  " ",
                  c.rank ? `(Rank #${c.rank})` : ""
                ] }, c.against_candidate_index))
              }
            )
          ] }) : null,
          scoreDiff != null ? /* @__PURE__ */ jsxs("div", { className: "score-diff-banner", children: [
            /* @__PURE__ */ jsx("div", { className: "score-diff-label", children: "Weighted score difference" }),
            /* @__PURE__ */ jsxs("div", { className: "score-diff-number mono", children: [
              scoreDiff.toFixed(2),
              " points"
            ] })
          ] }) : null,
          /* @__PURE__ */ jsxs("div", { className: "head-to-head-columns-grid", children: [
            /* @__PURE__ */ jsxs("div", { className: "head-to-head-column", children: [
              /* @__PURE__ */ jsx("h3", { className: "comparison-col-title", children: "Where the leader has additional verified matches" }),
              /* @__PURE__ */ jsx("div", { className: "comparison-items-list", children: leaderAdvantages.length > 0 ? leaderAdvantages.map((item, idx) => /* @__PURE__ */ jsxs("div", { className: "comparison-advantage-item", children: [
                /* @__PURE__ */ jsx("span", { className: "advantage-req-name font-bold", children: item.requirement }),
                item.points != null ? /* @__PURE__ */ jsxs("span", { className: "advantage-points mono", children: [
                  " · ",
                  item.points.toFixed(2),
                  " points"
                ] }) : null,
                /* @__PURE__ */ jsx("span", { className: "advantage-sep", children: " — " }),
                /* @__PURE__ */ jsx("span", { className: "advantage-why", children: item.why })
              ] }, idx)) : /* @__PURE__ */ jsx("div", { className: "comparison-empty-text", children: "No additional Found requirements in this comparison." }) })
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "head-to-head-column", children: [
              /* @__PURE__ */ jsx("h3", { className: "comparison-col-title", children: "Where the other candidate has additional verified matches" }),
              /* @__PURE__ */ jsx("div", { className: "comparison-items-list", children: otherAdvantages.length > 0 ? otherAdvantages.map((item, idx) => /* @__PURE__ */ jsxs("div", { className: "comparison-advantage-item", children: [
                /* @__PURE__ */ jsx("span", { className: "advantage-req-name font-bold", children: item.requirement }),
                item.points != null ? /* @__PURE__ */ jsxs("span", { className: "advantage-points mono", children: [
                  " · ",
                  item.points.toFixed(2),
                  " points"
                ] }) : null,
                /* @__PURE__ */ jsx("span", { className: "advantage-sep", children: " — " }),
                /* @__PURE__ */ jsx("span", { className: "advantage-why", children: item.why })
              ] }, idx)) : /* @__PURE__ */ jsx("div", { className: "comparison-empty-text", children: "No additional Found requirements in this comparison." }) })
            ] })
          ] })
        ] });
      })(),
      /* @__PURE__ */ jsxs("div", { className: "detail-subnav", children: [
        /* @__PURE__ */ jsx("button", { type: "button", className: `detail-subnav-btn ${activeTab === "all" ? "active" : ""}`, onClick: () => setActiveTab("all"), children: "Stacked View (All Sections)" }),
        /* @__PURE__ */ jsxs("button", { type: "button", className: `detail-subnav-btn ${activeTab === "verdicts" ? "active" : ""}`, onClick: () => setActiveTab("verdicts"), children: [
          "Requirement Verdicts (",
          detail.final.Criteria.length,
          ")"
        ] }),
        /* @__PURE__ */ jsxs("button", { type: "button", className: `detail-subnav-btn ${activeTab === "passages" ? "active" : ""}`, onClick: () => setActiveTab("passages"), children: [
          "Original Extracted Passages (",
          detail.original_segments.length,
          ")"
        ] })
      ] })
    ] }),
    activeTab === "all" || activeTab === "verdicts" ? /* @__PURE__ */ jsxs(Panel, { children: [
      /* @__PURE__ */ jsxs("div", { className: "card-header", children: [
        /* @__PURE__ */ jsx("h2", { children: "Requirement verdicts and reasoning" }),
        /* @__PURE__ */ jsxs("span", { className: "small text-muted", children: [
          detail.final.Criteria.length,
          " evaluated criteria"
        ] })
      ] }),
      /* @__PURE__ */ jsx("div", { className: "criteria-cards-list", children: detail.final.Criteria.map((row) => /* @__PURE__ */ jsxs("div", { className: "criterion-verdict-card", children: [
        /* @__PURE__ */ jsxs("div", { className: "criterion-header", children: [
          /* @__PURE__ */ jsxs("div", { className: "criterion-title-wrap", children: [
            /* @__PURE__ */ jsx("span", { className: "criterion-id-tag mono", children: row.ID }),
            /* @__PURE__ */ jsx("h3", { className: "criterion-title", children: row.Requirement })
          ] }),
          /* @__PURE__ */ jsx(Status, { value: row.Result })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "criterion-tags", children: [
          /* @__PURE__ */ jsx("span", { className: `badge small ${row.Priority.toLowerCase() === "required" ? "primary" : ""}`, children: row.Priority }),
          /* @__PURE__ */ jsx("span", { className: "badge small", children: row.Kind }),
          /* @__PURE__ */ jsx("span", { className: "badge small text-muted", children: row["Evidence level"] }),
          /* @__PURE__ */ jsx("span", { className: `badge small ${row["Review recommended"] ? "warning" : "subtle"}`, children: row["Review recommended"] ? "Review suggested" : "Source assessed" })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "criterion-body", children: [
          /* @__PURE__ */ jsx("div", { className: "criterion-section-label", children: "Assessment Reasoning" }),
          /* @__PURE__ */ jsx("p", { className: "criterion-why-text", children: row.Why })
        ] }),
        row["JD source"] ? /* @__PURE__ */ jsxs("details", { className: "criterion-jd-quote", children: [
          /* @__PURE__ */ jsx("summary", { className: "criterion-jd-summary", children: "Original employer requirement" }),
          /* @__PURE__ */ jsx("blockquote", { className: "criterion-quote-content", children: row["JD source"] })
        ] }) : null,
        row["Processing state"] !== "completed" && row["Processing state"] !== "legacy" ? /* @__PURE__ */ jsxs(Message, { kind: "warn", children: [
          "Processing: ",
          row["Processing state"],
          " · ",
          row["Failure code"] || "No completed result"
        ] }) : null,
        row.Checkpoints.length ? /* @__PURE__ */ jsxs("div", { className: "criterion-checkpoints", children: [
          /* @__PURE__ */ jsxs("div", { className: "criterion-section-label", children: [
            "Cited CV Evidence (",
            row.Checkpoints.length,
            ")"
          ] }),
          /* @__PURE__ */ jsx("div", { className: "checkpoints-list", children: row.Checkpoints.map((source) => /* @__PURE__ */ jsxs("div", { className: "checkpoint-item", children: [
            /* @__PURE__ */ jsxs("div", { className: "checkpoint-header", children: [
              /* @__PURE__ */ jsx("span", { className: "badge small mono", children: source.Segment }),
              /* @__PURE__ */ jsx("span", { className: "checkpoint-section", children: source.Section }),
              /* @__PURE__ */ jsx("span", { className: `checkpoint-status ${source["Validated against CV"] ? "valid" : "review"}`, children: source["Validated against CV"] ? "✓ Matched original source" : "Citation requires review" })
            ] }),
            /* @__PURE__ */ jsx("blockquote", { className: "checkpoint-text", children: source.Text })
          ] }, source.Segment)) })
        ] }) : /* @__PURE__ */ jsx("p", { className: "small text-muted", style: { margin: "8px 0 0" }, children: "No affirmative source citation is recorded for this criterion." }),
        /* @__PURE__ */ jsx("div", { className: "criterion-actions", children: /* @__PURE__ */ jsx(Button, { size: "small", disabled: focusedBusy === row.ID, onClick: () => void handleFocusedReview(row.ID), children: focusedBusy === row.ID ? "Evaluating..." : "Focused review" }) })
      ] }, row.ID)) }),
      history.length ? /* @__PURE__ */ jsxs("div", { style: { marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border-soft)" }, children: [
        /* @__PURE__ */ jsx(Button, { size: "small", onClick: () => setShowHistory((v) => !v), children: showHistory ? "Hide review history" : "Show review history (" + history.length + ")" }),
        showHistory ? /* @__PURE__ */ jsx("div", { style: { marginTop: 12 }, children: history.map((item) => /* @__PURE__ */ jsxs("div", { className: "why", style: { marginBottom: 8 }, children: [
          /* @__PURE__ */ jsxs("strong", { children: [
            item.requirement_id,
            ": ",
            item.prior_verdict,
            " ",
            /* @__PURE__ */ jsx(ArrowRightIcon, { size: 12, style: { margin: "0 4px", display: "inline-block" } }),
            " ",
            item.new_verdict
          ] }),
          /* @__PURE__ */ jsxs("p", { className: "small", children: [
            dateString(item.created),
            " · ",
            item.explanation
          ] })
        ] }, item.id)) }) : null
      ] }) : null
    ] }) : null,
    activeTab === "all" || activeTab === "passages" ? /* @__PURE__ */ jsxs(Panel, { className: "extracted-passages-panel", id: "extracted-cv-passages", children: [
      /* @__PURE__ */ jsxs("div", { className: "card-header", children: [
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("h2", { children: "Original extracted CV passages" }),
          /* @__PURE__ */ jsxs("span", { className: "small text-muted", children: [
            detail.original_segments.length,
            " verified candidate text segments extracted from source document"
          ] })
        ] }),
        candidateId ? /* @__PURE__ */ jsxs("a", { className: "btn small subtle", href: `/api/v1/workspaces/${workspaceId}/documents/${candidateId}/download`, children: [
          /* @__PURE__ */ jsx(DownloadIcon, { size: 14, style: { marginRight: 4 } }),
          "Download source"
        ] }) : null
      ] }),
      detail.original_segments.length ? /* @__PURE__ */ jsx("div", { className: "passages-stream", children: detail.original_segments.map((source) => /* @__PURE__ */ jsxs("div", { className: "passage-card", children: [
        /* @__PURE__ */ jsxs("div", { className: "passage-header", children: [
          /* @__PURE__ */ jsx("span", { className: "badge small mono", children: source.segment_id }),
          /* @__PURE__ */ jsx("span", { className: "passage-section-tag", children: source.section })
        ] }),
        /* @__PURE__ */ jsx("div", { className: "passage-body", children: source.text })
      ] }, source.segment_id)) }) : /* @__PURE__ */ jsx(Blank, { title: "No original segments", description: "Source extraction coverage may be incomplete; do not infer absence from missing material." })
    ] }) : null
  ] });
}
function CandidatePage() {
  const { workspaceId } = useWorkspace();
  const { jobId, candidateId } = useParams();
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx(
      PageHeader,
      {
        title: "Candidate details & Why",
        description: "Original cited evidence, three completed verdicts, and separate technical processing states.",
        actions: jobId ? /* @__PURE__ */ jsx(ActionLink, { to: workspacePath(workspaceId, "rankings", { jobId }), children: "Back to rankings" }) : null
      }
    ),
    jobId && candidateId ? /* @__PURE__ */ jsx(CandidateDetailView, { workspaceId, jobId, candidateId }, `${jobId}:${candidateId}`) : /* @__PURE__ */ jsx(Blank, { title: "Candidate not specified", description: "Return to rankings and choose a candidate to inspect." })
  ] });
}
function ReportsPage() {
  const { workspaceId, data, refresh } = useWorkspace();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState("");
  const [retentionDays, setRetentionDays] = useState(30);
  const [retention, setRetention] = useState(null);
  useEffect(() => {
    let mounted = true;
    client.getRetentionSummary(workspaceId, retentionDays).then((res) => {
      if (mounted) setRetention(res);
    }).catch(() => {
    });
    return () => {
      mounted = false;
    };
  }, [workspaceId, retentionDays]);
  const doAction = async (task) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    setNotice("");
    try {
      await task();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e : new Error("Action failed"));
    } finally {
      setBusy(false);
    }
  };
  const purgeOldData = async () => {
    if (confirmDestructive(`data older than ${retentionDays} days`)) {
      void doAction(async () => {
        const res = await client.purgeRetention(workspaceId, retentionDays);
        setNotice(`Retention purge completed: ${res.purged_jobs} jobs, ${res.purged_exports} exports, ${res.purged_documents} documents purged.`);
        const updated = await client.getRetentionSummary(workspaceId, retentionDays);
        setRetention(updated);
      });
    }
  };
  const importReport = (files) => {
    if (!files?.length) return;
    const file = files[0];
    void doAction(async () => {
      await client.importHistory(workspaceId, file);
      setNotice("Historical report archived read-only, not revalidated under the current protocol.");
    });
  };
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx(PageHeader, { title: "Saved results & exports", description: "Resume durable jobs, download exact result revisions, and inspect historical imports without reprocessing them." }),
    error ? /* @__PURE__ */ jsx(ErrorState, { error }) : null,
    notice ? /* @__PURE__ */ jsx(Message, { kind: "success", children: notice }) : null,
    /* @__PURE__ */ jsxs(Panel, { children: [
      /* @__PURE__ */ jsx("h2", { children: "Saved assessment jobs" }),
      data.jobs.length ? /* @__PURE__ */ jsx("div", { className: "table-scroller", children: /* @__PURE__ */ jsxs("table", { children: [
        /* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsxs("tr", { children: [
          /* @__PURE__ */ jsx("th", { children: "Job" }),
          /* @__PURE__ */ jsx("th", { children: "Created" }),
          /* @__PURE__ */ jsx("th", { children: "Progress" }),
          /* @__PURE__ */ jsx("th", { children: "State" }),
          /* @__PURE__ */ jsx("th", { children: "Job Controls & Details" })
        ] }) }),
        /* @__PURE__ */ jsx("tbody", { children: data.jobs.map((job2) => /* @__PURE__ */ jsxs("tr", { children: [
          /* @__PURE__ */ jsxs("td", { children: [
            /* @__PURE__ */ jsx("strong", { children: job2.kind === "assess" ? "Candidate assessment" : "JD extraction" }),
            /* @__PURE__ */ jsx("br", {}),
            /* @__PURE__ */ jsx("small", { className: "mono", children: job2.id.slice(0, 12) })
          ] }),
          /* @__PURE__ */ jsx("td", { children: dateString(job2.created) }),
          /* @__PURE__ */ jsxs("td", { children: [
            job2.progress,
            "/",
            job2.total
          ] }),
          /* @__PURE__ */ jsx("td", { children: /* @__PURE__ */ jsx(Status, { value: job2.state }) }),
          /* @__PURE__ */ jsx("td", { children: /* @__PURE__ */ jsxs("div", { className: "toolbar", style: { gap: 6 }, children: [
            /* @__PURE__ */ jsx(ActionLink, { size: "small", to: workspacePath(workspaceId, "progress", { jobId: job2.id }), children: "Progress" }),
            job2.kind === "assess" ? /* @__PURE__ */ jsx(ActionLink, { size: "small", to: workspacePath(workspaceId, "rankings", { jobId: job2.id }), children: "Rankings" }) : null,
            /* @__PURE__ */ jsx(Button, { kind: "danger", size: "small", disabled: busy, onClick: () => {
              if (confirmDestructive("saved job " + job2.id.slice(0, 8))) void doAction(async () => {
                await client.removeJob(workspaceId, job2.id);
                startDistinctIntent(workspaceId, job2.kind === "assess" ? "assess" : "jd_extract");
                setNotice("Saved job, candidate results and associated exports deleted.");
              });
            }, children: "Delete" })
          ] }) })
        ] }, job2.id)) })
      ] }) }) : /* @__PURE__ */ jsx(Blank, { title: "No saved jobs", description: "Start a JD extraction or candidate assessment." })
    ] }),
    /* @__PURE__ */ jsxs(Panel, { children: [
      /* @__PURE__ */ jsx("h2", { children: "Generated ZIP reports" }),
      data.exports.length ? /* @__PURE__ */ jsx("div", { className: "table-scroller", children: /* @__PURE__ */ jsxs("table", { children: [
        /* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsxs("tr", { children: [
          /* @__PURE__ */ jsx("th", { children: "Created" }),
          /* @__PURE__ */ jsx("th", { children: "Result revision" }),
          /* @__PURE__ */ jsx("th", { children: "Weight revision" }),
          /* @__PURE__ */ jsx("th", { children: "Size" }),
          /* @__PURE__ */ jsx("th", { children: "Export Actions" })
        ] }) }),
        /* @__PURE__ */ jsx("tbody", { children: data.exports.map((item) => /* @__PURE__ */ jsxs("tr", { children: [
          /* @__PURE__ */ jsx("td", { children: dateString(item.created) }),
          /* @__PURE__ */ jsx("td", { children: item.result_revision }),
          /* @__PURE__ */ jsx("td", { children: item.weight_revision }),
          /* @__PURE__ */ jsxs("td", { children: [
            (item.size / 1024).toFixed(1),
            " KB"
          ] }),
          /* @__PURE__ */ jsx("td", { children: /* @__PURE__ */ jsxs("div", { className: "toolbar", style: { gap: 6 }, children: [
            /* @__PURE__ */ jsx("a", { className: "btn small", href: `/api/v1/workspaces/${workspaceId}/exports/${item.id}/download`, children: "Download ZIP" }),
            /* @__PURE__ */ jsx(Button, { kind: "danger", size: "small", disabled: busy, onClick: () => {
              if (confirmDestructive("export " + item.id.slice(0, 8))) void doAction(async () => {
                await client.removeExport(workspaceId, item.id);
                setNotice("Export record and file deleted. External backups are unaffected.");
              });
            }, children: "Delete" })
          ] }) })
        ] }, item.id)) })
      ] }) }) : /* @__PURE__ */ jsx(Blank, { title: "No exports", description: "Export a completed assessment from its rankings page." })
    ] }),
    /* @__PURE__ */ jsxs(Panel, { children: [
      /* @__PURE__ */ jsx("h2", { children: "Data Retention Policy & Purge Automation" }),
      /* @__PURE__ */ jsx("p", { className: "small", children: "Configurable local retention. Active jobs and unknown provider deliveries are strictly protected from purge." }),
      retention ? /* @__PURE__ */ jsxs("div", { className: "grid cols3", style: { marginTop: 12, marginBottom: 12 }, children: [
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("small", { children: "Eligible terminal jobs" }),
          /* @__PURE__ */ jsx("p", { children: retention.eligible_jobs })
        ] }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("small", { children: "Eligible exports" }),
          /* @__PURE__ */ jsx("p", { children: retention.eligible_exports })
        ] }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("small", { children: "Protected active / unknown" }),
          /* @__PURE__ */ jsx("p", { children: retention.protected_active_jobs + retention.protected_unknown_delivery_jobs })
        ] })
      ] }) : null,
      /* @__PURE__ */ jsxs("div", { className: "toolbar", style: { alignItems: "flex-end" }, children: [
        /* @__PURE__ */ jsx("div", { style: { width: 160 }, children: /* @__PURE__ */ jsx(FormField, { id: "retention-days", label: "Retention period (days)", children: /* @__PURE__ */ jsx(
          "input",
          {
            id: "retention-days",
            type: "number",
            min: 1,
            max: 3650,
            value: retentionDays,
            onChange: (e) => setRetentionDays(Math.max(1, parseInt(e.target.value) || 30))
          }
        ) }) }),
        /* @__PURE__ */ jsxs(Button, { kind: "danger", disabled: busy, onClick: () => void purgeOldData(), children: [
          "Purge eligible data (",
          retentionDays,
          "d)"
        ] })
      ] })
    ] }),
    /* @__PURE__ */ jsxs(Panel, { children: [
      /* @__PURE__ */ jsx("h2", { children: "Historical assessment imports" }),
      /* @__PURE__ */ jsx(Message, { kind: "warn", children: "Imported historical results remain historical. Old results are never silently certified under protocol 58." }),
      /* @__PURE__ */ jsx(FormField, { id: "historic-report", label: "Import supported historical JSON or TextileHR ZIP", children: /* @__PURE__ */ jsx(
        "input",
        {
          id: "historic-report",
          type: "file",
          accept: ".json,.zip",
          onChange: (e) => {
            importReport(e.currentTarget.files);
            e.currentTarget.value = "";
          }
        }
      ) }),
      data.history.map((item) => /* @__PURE__ */ jsxs("div", { className: "step", children: [
        /* @__PURE__ */ jsxs("div", { style: { flex: 1 }, children: [
          /* @__PURE__ */ jsx("strong", { children: item.source_name }),
          /* @__PURE__ */ jsxs("small", { children: [
            "Source build ",
            item.source_build,
            " · ",
            dateString(item.created)
          ] })
        ] }),
        /* @__PURE__ */ jsx(Status, { value: "Historical" })
      ] }, item.id))
    ] })
  ] });
}
export {
  CandidateDetailView,
  CandidatePage,
  ProgressBar,
  ProgressPage,
  RankingsPage,
  ReportsPage,
  client,
  useRankings,
  useSavedJob
};
