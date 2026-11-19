import { jsxs, jsx, Fragment } from "react/jsx-runtime";
import { createContext, useState, useEffect, useRef, useCallback } from "react";
import { Link, useOutletContext, useNavigate } from "react-router-dom";
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
function parseMinimumYears(text) {
  const trimmed = text.trim();
  if (trimmed === "") return null;
  if (!/^(?:\d+(?:\.\d+)?|\.\d+)$/.test(trimmed))
    throw new Error("Minimum years must be a non-negative number (decimals allowed).");
  const value = Number(trimmed);
  if (!Number.isFinite(value) || value < 0)
    throw new Error("Minimum years must be a finite non-negative number.");
  return value;
}
let clientSequence = 0;
function generateClientKey(existingId) {
  clientSequence += 1;
  const base = existingId && existingId.trim() ? existingId.trim() : "new";
  return `row-identity-${base}-${clientSequence}-${Math.random().toString(36).slice(2, 7)}`;
}
function createEditableRow(initial) {
  const minYears = initial?.["Minimum years"];
  const text = minYears == null ? "" : String(minYears);
  return {
    _clientKey: generateClientKey(initial?.ID),
    ID: initial?.ID ?? "",
    Requirement: initial?.Requirement ?? "",
    Priority: initial?.Priority ?? "required",
    Type: initial?.Type ?? "skill",
    "JD source": initial?.["JD source"] ?? "",
    "Mandatory JD parts": initial?.["Mandatory JD parts"],
    "Alternative groups JSON": initial?.["Alternative groups JSON"],
    "Complete JD expression JSON": initial?.["Complete JD expression JSON"],
    "Minimum years": minYears ?? null,
    "Degree level": initial?.["Degree level"],
    "Field of study": initial?.["Field of study"],
    "Evidence standard": initial?.["Evidence standard"],
    "Duration subject": initial?.["Duration subject"],
    yearText: text,
    yearError: null,
    isDirty: false
  };
}
function rowsToEditable(rows) {
  return rows.map((r) => createEditableRow(r));
}
function updateRowField(rows, clientKey, field, value) {
  return rows.map((row) => {
    if (row._clientKey !== clientKey) return row;
    return {
      ...row,
      [field]: value,
      isDirty: true
    };
  });
}
function updateRowYearText(rows, clientKey, text) {
  return rows.map((row) => {
    if (row._clientKey !== clientKey) return row;
    let parsed = null;
    let error = null;
    try {
      parsed = parseMinimumYears(text);
    } catch (e) {
      error = e instanceof Error ? e.message : "Invalid years input";
    }
    return {
      ...row,
      yearText: text,
      yearError: error,
      "Minimum years": error ? row["Minimum years"] : parsed,
      isDirty: true
    };
  });
}
function removeRow(rows, clientKey) {
  return rows.filter((row) => row._clientKey !== clientKey);
}
function moveRow(rows, fromIndex, toIndex) {
  if (fromIndex < 0 || fromIndex >= rows.length || toIndex < 0 || toIndex >= rows.length) {
    return rows;
  }
  const next = [...rows];
  const [removed] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, removed);
  return next;
}
function hasRowValidationErrors(rows) {
  return rows.some((r) => r.yearError !== null);
}
function editableToCanonical(rows) {
  return rows.map((row) => {
    let finalYears = null;
    try {
      finalYears = parseMinimumYears(row.yearText);
    } catch {
      throw new Error(
        `Requirement ${row.ID || row.Requirement || "criterion"} has invalid minimum years: "${row.yearText}".`
      );
    }
    return {
      ID: row.ID,
      Requirement: row.Requirement,
      Priority: row.Priority,
      Type: row.Type,
      "JD source": row["JD source"],
      "Mandatory JD parts": row["Mandatory JD parts"],
      "Alternative groups JSON": row["Alternative groups JSON"],
      "Complete JD expression JSON": row["Complete JD expression JSON"],
      "Minimum years": finalYears,
      "Degree level": row["Degree level"],
      "Field of study": row["Field of study"],
      "Evidence standard": row["Evidence standard"],
      "Duration subject": row["Duration subject"]
    };
  });
}
const prefix = "textilehr:submission-intent:v1:";
function locationFor(workspace2, kind) {
  return `${prefix}${workspace2}:${kind}`;
}
function epochFor(workspace2, kind) {
  return `${prefix}epoch:${workspace2}:${kind}`;
}
function jsonStable(value) {
  if (Array.isArray(value)) return `[${value.map(jsonStable).join(",")}]`;
  if (value && typeof value === "object") {
    const fields = Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0);
    return `{${fields.map(([key, item]) => `${JSON.stringify(key)}:${jsonStable(item)}`).join(",")}}`;
  }
  return JSON.stringify(value) ?? "null";
}
async function sha256(value) {
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(hash), (part) => part.toString(16).padStart(2, "0")).join("");
}
async function submissionIntent(workspace2, kind, payload) {
  const epoch = localStorage.getItem(epochFor(workspace2, kind)) ?? "0";
  const fingerprint = await sha256(jsonStable({ workspace: workspace2, kind, payload, epoch }));
  const path = locationFor(workspace2, kind);
  const old = readPendingIntent(workspace2, kind);
  if (old?.fingerprint === fingerprint) return old;
  const intent = { version: 1, workspace: workspace2, kind, fingerprint, key: `ui-${fingerprint}`, state: "pending", created: Date.now() };
  localStorage.setItem(path, JSON.stringify(intent));
  return intent;
}
function readPendingIntent(workspace2, kind) {
  try {
    const raw = localStorage.getItem(locationFor(workspace2, kind));
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (!value || typeof value !== "object") return null;
    const row = value;
    if (row.version !== 1 || row.workspace !== workspace2 || row.kind !== kind || typeof row.key !== "string" || !/^ui-[a-f0-9]{64}$/.test(row.key) || typeof row.fingerprint !== "string" || row.fingerprint.length !== 64 || row.state !== "pending" && row.state !== "accepted") return null;
    return row;
  } catch {
    return null;
  }
}
function markAccepted(intent, jobId) {
  const latest = readPendingIntent(intent.workspace, intent.kind);
  if (latest?.key !== intent.key) return;
  localStorage.setItem(locationFor(intent.workspace, intent.kind), JSON.stringify({ ...intent, state: "accepted", jobId }));
}
function startDistinctIntent(workspace2, kind) {
  const old = Number(localStorage.getItem(epochFor(workspace2, kind)) ?? "0");
  localStorage.setItem(epochFor(workspace2, kind), String(Number.isSafeInteger(old) && old >= 0 ? old + 1 : 1));
  localStorage.removeItem(locationFor(workspace2, kind));
}
async function submitOnce(workspace2, kind, payload, lookup, submit) {
  let intent = await submissionIntent(workspace2, kind, payload);
  let missing = false;
  try {
    const existing = await lookup(intent.key);
    markAccepted(intent, existing.id);
    return existing;
  } catch (error) {
    const isConflict = Boolean(error && typeof error === "object" && ("status" in error && error.status === 409 || "message" in error && typeof error.message === "string" && error.message.includes("deliberately deleted")));
    if (isConflict) {
      startDistinctIntent(workspace2, kind);
      intent = await submissionIntent(workspace2, kind, payload);
      const job2 = await submit(intent.key);
      markAccepted(intent, job2.id);
      return job2;
    }
    missing = Boolean(error && typeof error === "object" && "status" in error && error.status === 404);
    if (!missing) throw error;
  }
  try {
    const job2 = await submit(intent.key);
    markAccepted(intent, job2.id);
    return job2;
  } catch (original) {
    const isConflict = Boolean(original && typeof original === "object" && ("status" in original && original.status === 409 || "message" in original && typeof original.message === "string" && original.message.includes("deliberately deleted")));
    if (isConflict) {
      startDistinctIntent(workspace2, kind);
      const freshIntent = await submissionIntent(workspace2, kind, payload);
      const job2 = await submit(freshIntent.key);
      markAccepted(freshIntent, job2.id);
      return job2;
    }
    try {
      const job2 = await lookup(intent.key);
      markAccepted(intent, job2.id);
      return job2;
    } catch {
      throw original;
    }
  }
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
function PlusIcon({ size = 16, ...props }) {
  return /* @__PURE__ */ jsxs("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true", ...props, children: [
    /* @__PURE__ */ jsx("line", { x1: "12", y1: "5", x2: "12", y2: "19" }),
    /* @__PURE__ */ jsx("line", { x1: "5", y1: "12", x2: "19", y2: "12" })
  ] });
}
function ArrowUpIcon({ size = 16, ...props }) {
  return /* @__PURE__ */ jsxs("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true", ...props, children: [
    /* @__PURE__ */ jsx("line", { x1: "12", y1: "19", x2: "12", y2: "5" }),
    /* @__PURE__ */ jsx("polyline", { points: "5 12 12 5 19 12" })
  ] });
}
function ArrowDownIcon({ size = 16, ...props }) {
  return /* @__PURE__ */ jsxs("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true", ...props, children: [
    /* @__PURE__ */ jsx("line", { x1: "12", y1: "5", x2: "12", y2: "19" }),
    /* @__PURE__ */ jsx("polyline", { points: "19 12 12 19 5 12" })
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
createContext(null);
function useWorkspace() {
  return useOutletContext();
}
function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const lock = useRef(false);
  const [notice, setNotice] = useState("");
  const run = useCallback(async (action) => {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError(null);
    setNotice("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e : new Error("Action rejected"));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }, []);
  return { run, busy, error, notice, setNotice };
}
function Feedback({ error, notice }) {
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    error ? /* @__PURE__ */ jsx(ErrorState, { error }) : null,
    notice ? /* @__PURE__ */ jsx(Message, { kind: "success", children: notice }) : null
  ] });
}
function DocumentsPage() {
  const { workspaceId, data, refresh } = useWorkspace();
  const action = useAction();
  const upload = async (kind, files) => {
    if (!files) return;
    await action.run(async () => {
      let success = 0;
      const issues = [];
      for (const file of Array.from(files)) try {
        await client.upload(workspaceId, kind, file);
        success++;
      } catch (e) {
        issues.push(file.name + ": " + (e instanceof Error ? e.message : "upload failed"));
      }
      await refresh();
      action.setNotice(`${success} file(s) accepted.${issues.length ? " Errors: " + issues.join("; ") : ""}`);
    });
  };
  const remove = (file) => void action.run(async () => {
    if (!confirmDestructive(file.filename)) return;
    await client.removeDocument(workspaceId, file.id);
    await refresh();
    action.setNotice("Unreferenced document deleted");
  });
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx(PageHeader, { title: "Documents & uploads", description: "Original job descriptions and applicant CVs are stored with immutable, distinct source identifiers." }),
    /* @__PURE__ */ jsx(Feedback, { error: action.error, notice: action.notice }),
    /* @__PURE__ */ jsx("div", { className: "grid cols2", style: { marginBottom: 19 }, children: ["jd", "cv"].map((kind) => /* @__PURE__ */ jsxs(Panel, { children: [
      /* @__PURE__ */ jsx("h2", { children: kind === "jd" ? "Employer job description" : "Candidate resumes" }),
      /* @__PURE__ */ jsxs("div", { className: "drop", children: [
        /* @__PURE__ */ jsx("strong", { children: kind === "jd" ? "Upload the employer JD" : "Upload candidate evidence" }),
        /* @__PURE__ */ jsx("p", { children: "TXT · MD · PDF · DOCX · up to 20 MB per document" }),
        /* @__PURE__ */ jsx(FormField, { id: "upload-" + kind, label: "Choose files", children: /* @__PURE__ */ jsx(
          "input",
          {
            id: "upload-" + kind,
            type: "file",
            accept: ".txt,.md,.pdf,.docx",
            multiple: kind === "cv",
            disabled: action.busy,
            onChange: (e) => {
              void upload(kind, e.currentTarget.files);
              e.currentTarget.value = "";
            }
          }
        ) })
      ] })
    ] }, kind)) }),
    /* @__PURE__ */ jsxs(Panel, { children: [
      /* @__PURE__ */ jsx("h2", { children: "Workspace documents" }),
      data.documents.length ? /* @__PURE__ */ jsx("div", { className: "table-scroller", children: /* @__PURE__ */ jsxs("table", { children: [
        /* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsxs("tr", { children: [
          /* @__PURE__ */ jsx("th", { scope: "col", children: "Original filename" }),
          /* @__PURE__ */ jsx("th", { scope: "col", children: "Kind" }),
          /* @__PURE__ */ jsx("th", { scope: "col", children: "Size" }),
          /* @__PURE__ */ jsx("th", { scope: "col", children: "Source ID" }),
          /* @__PURE__ */ jsx("th", { scope: "col", children: "Actions" })
        ] }) }),
        /* @__PURE__ */ jsx("tbody", { children: data.documents.map((file) => /* @__PURE__ */ jsxs("tr", { children: [
          /* @__PURE__ */ jsx("td", { children: /* @__PURE__ */ jsx("strong", { children: file.filename }) }),
          /* @__PURE__ */ jsx("td", { children: /* @__PURE__ */ jsx(Status, { value: file.kind.toUpperCase() }) }),
          /* @__PURE__ */ jsxs("td", { children: [
            (file.byte_size / 1024).toFixed(1),
            " KB"
          ] }),
          /* @__PURE__ */ jsx("td", { className: "mono small", children: file.id.slice(0, 12) }),
          /* @__PURE__ */ jsxs("td", { children: [
            /* @__PURE__ */ jsx("a", { className: "btn small", href: `/api/v1/workspaces/${workspaceId}/documents/${file.id}/download`, children: "Original" }),
            " ",
            /* @__PURE__ */ jsx(Button, { size: "small", kind: "danger", disabled: action.busy, onClick: () => remove(file), children: "Delete" })
          ] })
        ] }, file.id)) })
      ] }) }) : /* @__PURE__ */ jsx(Blank, { title: "No uploaded files", description: "Begin by providing a job description and one or more CVs." })
    ] })
  ] });
}
function defaultRunSettings(provider) {
  return { provider: provider === "openrouter" ? "openrouter" : "ollama", use_llm: true, unified: true, yake_top_k: 40 };
}
function JDPage() {
  const { workspaceId, data, settings, refresh } = useWorkspace();
  const navigate = useNavigate();
  const action = useAction();
  const jds = data.documents.filter((file) => file.kind === "jd");
  const [selectedJD, setSelectedJD] = useState("");
  const activeJD = selectedJD || (jds.length ? jds[0].id : "");
  const [provider, setProvider] = useState(settings.configured_provider === "openrouter" ? "openrouter" : "ollama");
  const [llm, setLLM] = useState(true);
  const [yake, setYake] = useState(settings.yake_top_k_default);
  const [draftRows, setDraftRows] = useState([]);
  const [draftError, setDraftError] = useState(null);
  const [editingDraftId, setEditingDraftId] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [reloadCount, reloadDraft] = useState(0);
  const reloadRequested = useRef(false);
  const lastLoad = useRef(0);
  const dirtyRef = useRef(false);
  const editingRef = useRef(null);
  const isStaleDraft = Boolean(dirty && editingDraftId && data.draft && editingDraftId !== data.draft.id);
  useEffect(() => {
    let mounted = true;
    const pending = readPendingIntent(workspaceId, "jd_extract");
    if (pending?.state === "pending") void client.getSubmission(workspaceId, pending.key).then((job2) => {
      markAccepted(pending, job2.id);
      if (mounted) navigate(workspacePath(workspaceId, "progress", { jobId: job2.id }));
    }).catch(() => {
    });
    return () => {
      mounted = false;
    };
  }, [workspaceId, navigate]);
  useEffect(() => {
    void refresh();
    const onFocus = () => {
      if (!document.hidden) void refresh();
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [refresh]);
  useEffect(() => {
    const server = data.draft;
    if (!server) return;
    if (dirtyRef.current && editingRef.current && editingRef.current !== server.id) {
      return;
    }
    if (editingRef.current === server.id && !reloadRequested.current) return;
    const token = ++lastLoad.current;
    let live = true;
    void client.getDraft(workspaceId, server.id).then((result) => {
      if (!live || lastLoad.current !== token) return;
      if (dirtyRef.current && editingRef.current && editingRef.current !== server.id) {
        return;
      }
      const rows = rowsToEditable(result.rows ?? []);
      setDraftRows(rows);
      editingRef.current = server.id;
      setEditingDraftId(server.id);
      reloadRequested.current = false;
      dirtyRef.current = false;
      setDirty(false);
      setDraftError(null);
    }).catch((e) => {
      if (live) setDraftError(e instanceof Error ? e : new Error("Cannot load JD draft"));
    });
    return () => {
      live = false;
    };
  }, [workspaceId, data.draft, reloadCount]);
  const modifyField = (clientKey, field, value) => {
    dirtyRef.current = true;
    setDirty(true);
    setDraftRows((rows) => updateRowField(rows, clientKey, field, value));
  };
  const modifyYears = (clientKey, text) => {
    dirtyRef.current = true;
    setDirty(true);
    setDraftRows((rows) => updateRowYearText(rows, clientKey, text));
  };
  const removeCriterion = (clientKey) => {
    dirtyRef.current = true;
    setDirty(true);
    setDraftRows((rows) => removeRow(rows, clientKey));
  };
  const moveCriterion = (fromIndex, toIndex) => {
    dirtyRef.current = true;
    setDirty(true);
    setDraftRows((rows) => moveRow(rows, fromIndex, toIndex));
  };
  const addCriterion = () => {
    dirtyRef.current = true;
    setDirty(true);
    setDraftRows((rows) => [...rows, createEditableRow({
      ID: "",
      Requirement: "",
      Priority: "required",
      Type: "skill",
      "JD source": ""
    })]);
  };
  const forceReload = () => {
    reloadRequested.current = true;
    dirtyRef.current = false;
    editingRef.current = null;
    setDirty(false);
    reloadDraft((n) => n + 1);
  };
  useEffect(() => {
    if (!dirty) return;
    const beforeUnload = (event2) => {
      event2.preventDefault();
      event2.returnValue = "";
    };
    const intercept = (event2) => {
      const target = event2.target;
      if (!(target instanceof Element)) return;
      const link = target.closest("a[href]");
      if (!link || new URL(link.href).origin !== window.location.origin) return;
      if (!window.confirm("Discard unsaved JD review changes?")) {
        event2.preventDefault();
        event2.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", intercept, true);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("click", intercept, true);
    };
  }, [dirty]);
  const outgoingRows = () => {
    if (hasRowValidationErrors(draftRows)) {
      throw new Error("Please resolve highlighted minimum experience validation errors before saving.");
    }
    return editableToCanonical(draftRows);
  };
  const start = () => void action.run(async () => {
    if (!activeJD) throw new Error("Choose a JD");
    const request2 = { document_id: activeJD, provider, use_llm: llm, unified: false, yake_top_k: yake };
    const job2 = await submitOnce(
      workspaceId,
      "jd_extract",
      request2,
      (key) => client.getSubmission(workspaceId, key),
      (key) => client.startJD(workspaceId, activeJD, request2, key)
    );
    navigate(workspacePath(workspaceId, "progress", { jobId: job2.id }));
  });
  const save = (approve) => void action.run(async () => {
    if (!data.draft || !editingDraftId) throw new Error("Extract a JD first");
    if (isStaleDraft || data.draft.id !== editingDraftId)
      throw new Error("A newer JD draft exists. Reload and review before modifying it.");
    const rows = outgoingRows();
    if (approve) {
      if (dirty && data.approved?.draft_id === data.draft.id)
        throw new Error("This JD is already frozen. Save a new draft revision before approving changes.");
      await client.approveJD(workspaceId, editingDraftId, data.draft.revision, rows);
      dirtyRef.current = false;
      setDirty(false);
      await refresh();
      navigate(workspacePath(workspaceId, "weights"));
    } else {
      await client.reviseJD(workspaceId, editingDraftId, data.draft.revision, rows);
      dirtyRef.current = false;
      editingRef.current = null;
      setDirty(false);
      await refresh();
      action.setNotice("New draft revision saved. Review it before approval.");
    }
  });
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx(
      PageHeader,
      {
        title: "JD extraction, review & approval",
        description: "Validate all employer-stated obligations against original source quotations before freezing a JD revision."
      }
    ),
    /* @__PURE__ */ jsx(Feedback, { error: action.error ?? draftError, notice: action.notice }),
    isStaleDraft ? /* @__PURE__ */ jsxs(Message, { kind: "warn", children: [
      "A newer JD revision was published while you were editing. Your unsaved edits are preserved locally; reload the server revision before another save. ",
      /* @__PURE__ */ jsx(Button, { onClick: forceReload, children: "Discard edits and load latest" })
    ] }) : null,
    dirty && !isStaleDraft ? /* @__PURE__ */ jsx(Message, { kind: "warn", children: "Unsaved JD review changes. Save a successor revision before navigating away." }) : null,
    /* @__PURE__ */ jsxs(Panel, { children: [
      /* @__PURE__ */ jsx("h2", { children: "Source and extraction settings" }),
      /* @__PURE__ */ jsxs("div", { className: "grid cols3", children: [
        /* @__PURE__ */ jsx(FormField, { id: "jd-source", label: "Job description", children: /* @__PURE__ */ jsxs("select", { id: "jd-source", value: activeJD, onChange: (e) => setSelectedJD(e.target.value), children: [
          /* @__PURE__ */ jsx("option", { value: "", children: "Choose uploaded JD" }),
          jds.map((d) => /* @__PURE__ */ jsx("option", { value: d.id, children: d.filename }, d.id))
        ] }) }),
        /* @__PURE__ */ jsx(FormField, { id: "jd-model", label: "Provider", children: /* @__PURE__ */ jsxs("select", { id: "jd-model", value: provider, onChange: (e) => setProvider(e.target.value), children: [
          /* @__PURE__ */ jsx("option", { value: "ollama", children: "Ollama · local" }),
          /* @__PURE__ */ jsx("option", { value: "openrouter", children: "OpenRouter · cloud" })
        ] }) }),
        /* @__PURE__ */ jsx(FormField, { id: "yake-count", label: "YAKE candidates", children: /* @__PURE__ */ jsx(
          "input",
          {
            type: "number",
            id: "yake-count",
            min: 1,
            max: 150,
            value: yake,
            onChange: (e) => setYake(Number(e.target.value))
          }
        ) })
      ] }),
      /* @__PURE__ */ jsxs("label", { className: "row", children: [
        /* @__PURE__ */ jsx("input", { type: "checkbox", checked: llm, onChange: (e) => setLLM(e.target.checked) }),
        "Enable LLM-based JD extraction"
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "toolbar", style: { marginTop: 14 }, children: [
        /* @__PURE__ */ jsx(Button, { kind: "primary", disabled: !activeJD || action.busy, onClick: start, children: "Extract JD in worker" }),
        /* @__PURE__ */ jsx(Button, { onClick: () => {
          startDistinctIntent(workspaceId, "jd_extract");
          action.setNotice("A separate extraction intent has been created. Click Extract to submit.");
        }, children: "New independent extraction" }),
        /* @__PURE__ */ jsx(ActionLink, { to: workspacePath(workspaceId, "uploads"), children: "Upload additional JD" })
      ] })
    ] }),
    data.draft ? /* @__PURE__ */ jsxs(Panel, { className: "review-panel", children: [
      /* @__PURE__ */ jsxs("div", { className: "card-header", children: [
        /* @__PURE__ */ jsx("h2", { children: "Review requirement meaning" }),
        /* @__PURE__ */ jsx(Status, { value: "Draft " + data.draft.revision })
      ] }),
      /* @__PURE__ */ jsx("p", { children: "Required, Preferred and unresolved priorities must reflect employer wording. Experience and education restrictions and compound AND/OR obligations stay source-bound." }),
      draftRows.map((row, index) => /* @__PURE__ */ jsxs("div", { className: "why", children: [
        /* @__PURE__ */ jsxs("div", { className: "card-header", children: [
          /* @__PURE__ */ jsxs("strong", { children: [
            row.ID || "NEW",
            " · Requirement ",
            index + 1
          ] }),
          /* @__PURE__ */ jsx(Status, { value: row.Priority })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "stack", style: { gap: 12 }, children: [
          /* @__PURE__ */ jsx(FormField, { id: `req-${row._clientKey}`, label: "Requirement text", children: /* @__PURE__ */ jsx("textarea", { id: `req-${row._clientKey}`, rows: 2, style: { minHeight: 54 }, value: row.Requirement, onChange: (e) => modifyField(row._clientKey, "Requirement", e.target.value) }) }),
          /* @__PURE__ */ jsxs("div", { className: "grid cols2", children: [
            /* @__PURE__ */ jsx(FormField, { id: `prio-${row._clientKey}`, label: "Priority", children: /* @__PURE__ */ jsxs("select", { id: `prio-${row._clientKey}`, value: row.Priority, onChange: (e) => modifyField(row._clientKey, "Priority", e.target.value), children: [
              /* @__PURE__ */ jsx("option", { value: "required", children: "Required" }),
              /* @__PURE__ */ jsx("option", { value: "preferred", children: "Preferred" }),
              /* @__PURE__ */ jsx("option", { value: "unknown", children: "Unknown — supervisor review" })
            ] }) }),
            /* @__PURE__ */ jsx(FormField, { id: `kind-${row._clientKey}`, label: "Requirement type", children: /* @__PURE__ */ jsx("select", { id: `kind-${row._clientKey}`, value: row.Type, onChange: (e) => modifyField(row._clientKey, "Type", e.target.value), children: ["skill", "experience", "education", "certification", "license", "responsibility", "eligibility", "other"].map((t) => /* @__PURE__ */ jsx("option", { value: t, children: t }, t)) }) })
          ] }),
          /* @__PURE__ */ jsx(FormField, { id: `source-${row._clientKey}`, label: "Exact employer quotation", children: /* @__PURE__ */ jsx("textarea", { id: `source-${row._clientKey}`, rows: 2, style: { minHeight: 54 }, value: row["JD source"], onChange: (e) => modifyField(row._clientKey, "JD source", e.target.value) }) })
        ] }),
        /* @__PURE__ */ jsxs("details", { children: [
          /* @__PURE__ */ jsx("summary", { children: "Approved compound conditions and qualification constraints" }),
          /* @__PURE__ */ jsxs("div", { className: "grid cols2", children: [
            /* @__PURE__ */ jsx(FormField, { id: `mandatory-${row._clientKey}`, label: "Mandatory JD parts ( | separated)", children: /* @__PURE__ */ jsx(
              "textarea",
              {
                id: `mandatory-${row._clientKey}`,
                value: row["Mandatory JD parts"] ?? "",
                onChange: (e) => modifyField(row._clientKey, "Mandatory JD parts", e.target.value)
              }
            ) }),
            /* @__PURE__ */ jsx(FormField, { id: `alts-${row._clientKey}`, label: "Alternative groups (JSON)", children: /* @__PURE__ */ jsx(
              "textarea",
              {
                id: `alts-${row._clientKey}`,
                value: row["Alternative groups JSON"] ?? "",
                onChange: (e) => modifyField(row._clientKey, "Alternative groups JSON", e.target.value)
              }
            ) }),
            /* @__PURE__ */ jsx(FormField, { id: `expr-${row._clientKey}`, label: "Complete condition expression (JSON)", children: /* @__PURE__ */ jsx(
              "textarea",
              {
                id: `expr-${row._clientKey}`,
                value: row["Complete JD expression JSON"] ?? "",
                onChange: (e) => modifyField(row._clientKey, "Complete JD expression JSON", e.target.value)
              }
            ) }),
            /* @__PURE__ */ jsxs("div", { children: [
              /* @__PURE__ */ jsx(FormField, { id: `minimum-years-${row._clientKey}`, label: "Minimum experience (years; blank = derive from JD)", children: /* @__PURE__ */ jsx(
                "input",
                {
                  id: `minimum-years-${row._clientKey}`,
                  inputMode: "decimal",
                  value: row.yearText,
                  onChange: (e) => modifyYears(row._clientKey, e.target.value)
                }
              ) }),
              row.yearError ? /* @__PURE__ */ jsx("p", { className: "small", style: { color: "var(--color-danger, #ef4444)", marginTop: 4 }, children: row.yearError }) : null,
              /* @__PURE__ */ jsx("strong", { children: "Degree level / field" }),
              /* @__PURE__ */ jsxs("p", { children: [
                row["Degree level"] || "—",
                " · ",
                row["Field of study"] || "—"
              ] })
            ] })
          ] })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "toolbar", style: { marginTop: 8 }, children: [
          /* @__PURE__ */ jsx(Button, { size: "small", kind: "danger", disabled: draftRows.length <= 1, onClick: () => removeCriterion(row._clientKey), children: "Remove criterion" }),
          /* @__PURE__ */ jsxs(Button, { size: "small", disabled: index === 0, onClick: () => moveCriterion(index, index - 1), children: [
            /* @__PURE__ */ jsx(ArrowUpIcon, { size: 13, style: { marginRight: 4 } }),
            "Move up"
          ] }),
          /* @__PURE__ */ jsxs(Button, { size: "small", disabled: index === draftRows.length - 1, onClick: () => moveCriterion(index, index + 1), children: [
            /* @__PURE__ */ jsx(ArrowDownIcon, { size: 13, style: { marginRight: 4 } }),
            "Move down"
          ] })
        ] })
      ] }, row._clientKey)),
      /* @__PURE__ */ jsxs("div", { className: "toolbar", style: { marginTop: 20, marginBottom: 8, gap: 12 }, children: [
        /* @__PURE__ */ jsxs(Button, { onClick: addCriterion, children: [
          /* @__PURE__ */ jsx(PlusIcon, { size: 14, style: { marginRight: 6 } }),
          "Add source-backed criterion"
        ] }),
        /* @__PURE__ */ jsx(Button, { disabled: action.busy || draftRows.length === 0 || isStaleDraft, onClick: () => save(false), children: "Save new revision" }),
        /* @__PURE__ */ jsx(Button, { kind: "primary", disabled: action.busy || draftRows.length === 0 || isStaleDraft || Boolean(dirty && data.approved?.draft_id === data.draft.id), onClick: () => save(true), children: "Approve and freeze JD" })
      ] })
    ] }) : /* @__PURE__ */ jsx("div", { style: { marginTop: 18 }, children: /* @__PURE__ */ jsx(Blank, { title: "No extracted JD draft", description: "Choose a source, then use the worker to extract employer requirements." }) }),
    data.approved ? /* @__PURE__ */ jsxs(Message, { kind: "success", children: [
      "Approved revision ",
      data.approved.revision,
      ": ",
      data.approved.body.requirements.length,
      " frozen criteria. Existing jobs retain the revision they started with."
    ] }) : null
  ] });
}
function WeightEditor({
  current,
  workspaceId,
  refresh,
  action,
  requirements
}) {
  const [draft, setDraft] = useState(() => ({
    experience: current.body.experience,
    education: current.body.education,
    jd: current.body.jd,
    split_jd: current.body.split_jd,
    jd_allocation: current.body.jd_allocation,
    jd_required_share: current.body.jd_required_share ?? 80,
    requirement_shares_percent_of_category: { ...current.body.requirement_shares_percent_of_category }
  }));
  const total = draft.experience + draft.education + draft.jd;
  const change = (key, value) => setDraft((w) => ({ ...w, [key]: value }));
  const save = () => void action.run(async () => {
    await client.saveWeights(workspaceId, current.revision, draft);
    await refresh();
    action.setNotice("Saved authoritative weight projection; no model assessment was dispatched.");
  });
  const rebalance = (id, value) => void action.run(async () => {
    const shares = await client.rebalance(workspaceId, id, value, draft.requirement_shares_percent_of_category);
    setDraft((w) => ({ ...w, requirement_shares_percent_of_category: shares }));
  });
  const even = () => void action.run(async () => {
    const shares = await client.rebalance(workspaceId);
    setDraft((w) => ({ ...w, requirement_shares_percent_of_category: shares }));
  });
  const getCategory = (req) => {
    const c = req.constraint;
    if (c?.kind === "experience") return "experience";
    if (c?.kind === "education") return "education";
    const lower = req.name.toLowerCase();
    if (lower.includes("years of") || lower.includes("years professional") || lower.includes("full-time professional experience")) return "experience";
    if (lower.includes("bachelor's") || lower.includes("master's") || lower.includes("degree") || lower.includes("bachelor") || lower.includes("phd")) return "education";
    return "jd";
  };
  const byCategory = {
    experience: requirements.filter((r) => getCategory(r) === "experience"),
    education: requirements.filter((r) => getCategory(r) === "education"),
    jd: requirements.filter((r) => getCategory(r) === "jd")
  };
  const categoryWeights = {
    experience: draft.experience,
    education: draft.education,
    jd: draft.jd
  };
  const activeWeight = (byCategory.experience.length ? categoryWeights.experience : 0) + (byCategory.education.length ? categoryWeights.education : 0) + (byCategory.jd.length ? categoryWeights.jd : 0);
  const calculatePotential = (req, cat, share) => {
    const catEntries = byCategory[cat];
    if (!catEntries.length || activeWeight <= 0) return 0;
    if (cat === "jd" && draft.jd_allocation === "weighted_split") {
      const isReq = req.priority.toLowerCase() === "required";
      const sameGroup = catEntries.filter((r) => r.priority.toLowerCase() === "required" === isReq);
      const sameGroupSum = sameGroup.reduce((acc, r) => {
        const s = draft.requirement_shares_percent_of_category[r.requirement_id] ?? 100 / catEntries.length;
        return acc + s;
      }, 0);
      const selected = draft.jd_required_share ?? 80;
      const groupAlloc = isReq ? selected : 100 - selected;
      const hasReq = catEntries.some((r) => r.priority.toLowerCase() === "required");
      const hasPref = catEntries.some((r) => r.priority.toLowerCase() !== "required");
      const activeAlloc = (hasReq ? selected : 0) + (hasPref ? 100 - selected : 0);
      const normGroupAlloc = activeAlloc > 0 ? groupAlloc / activeAlloc : 1;
      return 100 * categoryWeights[cat] / activeWeight * normGroupAlloc * (sameGroupSum > 0 ? share / sameGroupSum : 0);
    }
    return 100 * categoryWeights[cat] / activeWeight * (share / 100);
  };
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsxs(Panel, { children: [
      /* @__PURE__ */ jsxs("div", { className: "card-header", children: [
        /* @__PURE__ */ jsx("h2", { children: "Category weights" }),
        /* @__PURE__ */ jsx(Status, { value: "Revision " + current.revision })
      ] }),
      /* @__PURE__ */ jsx("div", { className: "grid cols3", children: ["experience", "education", "jd"].map((key) => /* @__PURE__ */ jsx(
        FormField,
        {
          id: "weight-" + key,
          label: (key === "jd" ? "Other JD criteria" : key === "education" ? "Education" : "Experience") + " (%)",
          children: /* @__PURE__ */ jsx(
            "input",
            {
              id: "weight-" + key,
              type: "number",
              min: 0,
              max: 100,
              step: 1,
              value: draft[key],
              onChange: (e) => change(key, Number(e.target.value))
            }
          )
        },
        key
      )) }),
      /* @__PURE__ */ jsxs(Message, { kind: total === 100 ? "success" : "warn", children: [
        "Category total: ",
        total,
        "%. Must equal 100%."
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "grid cols2", children: [
        /* @__PURE__ */ jsx(FormField, { id: "weight-policy", label: "JD allocation policy", children: /* @__PURE__ */ jsxs(
          "select",
          {
            id: "weight-policy",
            value: draft.jd_allocation,
            onChange: (e) => change("jd_allocation", e.target.value),
            children: [
              /* @__PURE__ */ jsx("option", { value: "pooled", children: "Combined Required + Preferred" }),
              /* @__PURE__ */ jsx("option", { value: "weighted_split", children: "Explicit Required/Preferred split" })
            ]
          }
        ) }),
        draft.jd_allocation === "weighted_split" ? /* @__PURE__ */ jsx(FormField, { id: "weight-required", label: "Required share (%)", children: /* @__PURE__ */ jsx(
          "input",
          {
            id: "weight-required",
            type: "number",
            min: 0,
            max: 100,
            step: 1,
            value: draft.jd_required_share,
            onChange: (e) => change("jd_required_share", Number(e.target.value))
          }
        ) }) : null
      ] })
    ] }),
    /* @__PURE__ */ jsxs(Panel, { children: [
      /* @__PURE__ */ jsx("div", { className: "card-header", children: /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("div", { className: "eyebrow", style: { marginBottom: 4 }, children: "Review & prioritize" }),
        /* @__PURE__ */ jsx("h2", { style: { margin: "0 0 4px 0" }, children: "Step 5 · Edit individual JD allocations" }),
        /* @__PURE__ */ jsx("p", { className: "small text-muted", style: { margin: 0 }, children: "Give individual requirements more or less influence within their category." })
      ] }) }),
      /* @__PURE__ */ jsx("div", { style: { marginTop: 12, padding: "12px 14px", background: "var(--bg-soft)", borderRadius: 10, fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }, children: "Changing one share automatically rebalances the other items in its category. Items keep their reviewed shares of their category. In pooled mode, Required and Preferred share one Requirements pool; in weighted-split mode, their groups receive the selected allocation before item shares are normalized." }),
      /* @__PURE__ */ jsx("div", { className: "allocation-categories-container", style: { marginTop: 18 }, children: ["experience", "education", "jd"].map((cat) => {
        const entries = byCategory[cat];
        if (!entries.length) return null;
        const catLabel = cat === "jd" ? "Jd" : cat.charAt(0).toUpperCase() + cat.slice(1);
        return /* @__PURE__ */ jsxs("div", { className: "allocation-category-card", style: { marginBottom: 18 }, children: [
          /* @__PURE__ */ jsxs("div", { className: "allocation-category-header font-bold", style: { fontSize: 14, marginBottom: 10, color: "var(--text-primary)" }, children: [
            catLabel,
            " · ",
            entries.length,
            " requirement(s) · 100% of this category"
          ] }),
          /* @__PURE__ */ jsx("div", { className: "allocation-items-list", style: { display: "flex", flexDirection: "column", gap: 10 }, children: entries.map((req) => {
            const defaultShare = Number((100 / entries.length).toFixed(2));
            const currentShare = draft.requirement_shares_percent_of_category[req.requirement_id] ?? defaultShare;
            const potential = calculatePotential(req, cat, currentShare);
            return /* @__PURE__ */ jsxs(
              "div",
              {
                className: "allocation-item-card",
                style: {
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 16,
                  padding: "12px 16px",
                  background: "var(--surface-strong)",
                  border: "1px solid var(--border-soft)",
                  borderRadius: 10
                },
                children: [
                  /* @__PURE__ */ jsxs("div", { className: "allocation-item-info", style: { flex: 1, minWidth: 0 }, children: [
                    /* @__PURE__ */ jsxs("div", { className: "allocation-item-title", style: { fontSize: 13, fontWeight: 600, color: "var(--text-primary)", lineHeight: 1.4 }, children: [
                      /* @__PURE__ */ jsx("span", { className: "mono", style: { color: "var(--text-muted)", marginRight: 6 }, children: req.requirement_id }),
                      /* @__PURE__ */ jsx("span", { children: req.name }),
                      cat === "jd" ? /* @__PURE__ */ jsx("span", { className: "badge small", style: { marginLeft: 8 }, children: req.priority.charAt(0).toUpperCase() + req.priority.slice(1) }) : null
                    ] }),
                    /* @__PURE__ */ jsxs("div", { className: "allocation-item-potential mono", style: { fontSize: 12, color: "var(--accent)", marginTop: 4 }, children: [
                      "Possible overall score: ",
                      potential.toFixed(2),
                      " / 100 points"
                    ] })
                  ] }),
                  /* @__PURE__ */ jsxs("div", { className: "allocation-item-stepper", style: { display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }, children: [
                    /* @__PURE__ */ jsx(
                      "button",
                      {
                        type: "button",
                        className: "stepper-btn",
                        disabled: action.busy || entries.length === 1,
                        onClick: () => {
                          const nextVal = Math.max(0, Math.round((currentShare - 1) * 100) / 100);
                          rebalance(req.requirement_id, nextVal);
                        },
                        "aria-label": "Decrease share",
                        children: "−"
                      }
                    ),
                    /* @__PURE__ */ jsx(
                      "input",
                      {
                        type: "number",
                        className: "stepper-input mono",
                        "aria-label": `Share of ${req.name}`,
                        min: 0,
                        max: 100,
                        step: 0.01,
                        value: Number(currentShare.toFixed(2)),
                        onChange: (e) => {
                          const val = Number(e.target.value);
                          setDraft((w) => ({
                            ...w,
                            requirement_shares_percent_of_category: {
                              ...w.requirement_shares_percent_of_category,
                              [req.requirement_id]: val
                            }
                          }));
                        },
                        onBlur: (e) => {
                          const val = Number(e.target.value);
                          if (Number.isFinite(val)) {
                            rebalance(req.requirement_id, val);
                          }
                        }
                      }
                    ),
                    /* @__PURE__ */ jsx(
                      "button",
                      {
                        type: "button",
                        className: "stepper-btn",
                        disabled: action.busy || entries.length === 1,
                        onClick: () => {
                          const nextVal = Math.min(100, Math.round((currentShare + 1) * 100) / 100);
                          rebalance(req.requirement_id, nextVal);
                        },
                        "aria-label": "Increase share",
                        children: "+"
                      }
                    )
                  ] })
                ]
              },
              req.requirement_id
            );
          }) })
        ] }, cat);
      }) })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "toolbar", style: { marginTop: 24, marginBottom: 44, gap: 12 }, children: [
      /* @__PURE__ */ jsx(Button, { disabled: action.busy, onClick: even, children: "Reset to equal shares" }),
      /* @__PURE__ */ jsx(Button, { kind: "primary", disabled: action.busy || total !== 100, onClick: save, children: "Save weight revision" }),
      /* @__PURE__ */ jsx(
        ActionLink,
        {
          to: workspacePath(workspaceId, "run"),
          style: {
            border: "1.5px solid var(--brand-green)",
            color: "var(--brand-green)",
            background: "transparent",
            fontWeight: 600,
            borderRadius: 8,
            padding: "9px 18px",
            display: "inline-flex",
            alignItems: "center",
            minHeight: 40,
            textDecoration: "none"
          },
          children: "Proceed to assessment →"
        }
      )
    ] })
  ] });
}
function WeightsPage() {
  const { workspaceId, data, refresh } = useWorkspace();
  const action = useAction();
  const current = data.weights;
  if (!current) return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx(PageHeader, { title: "Weight allocation", description: "Use the engine's existing weighting policy." }),
    /* @__PURE__ */ jsx(Blank, { title: "No weights ready", description: "Load or approve a JD first." })
  ] });
  const requirements = data.approved?.body.requirements ?? [];
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx(PageHeader, { title: "Weight allocation", description: "Recalculate scores from existing verified decisions; weight changes never call the assessment provider." }),
    /* @__PURE__ */ jsx(Feedback, { error: action.error, notice: action.notice }),
    !data.approved ? /* @__PURE__ */ jsx(Blank, { title: "Approve JD first", description: "A frozen JD is required for individual requirement shares." }) : /* @__PURE__ */ jsx(WeightEditor, { current, workspaceId, refresh, action, requirements }, `${workspaceId}:${current.revision}`)
  ] });
}
function AssessmentPage() {
  const { workspaceId, data, settings } = useWorkspace();
  const navigate = useNavigate();
  const action = useAction();
  const [selected, setSelected] = useState([]);
  const [config, setConfig] = useState(() => defaultRunSettings(settings.configured_provider));
  const cvs = data.documents.filter((d) => d.kind === "cv");
  useEffect(() => {
    let mounted = true;
    const pending = readPendingIntent(workspaceId, "assess");
    if (pending?.state === "pending") void client.getSubmission(workspaceId, pending.key).then((job2) => {
      markAccepted(pending, job2.id);
      if (mounted) navigate(workspacePath(workspaceId, "progress", { jobId: job2.id }));
    }).catch(() => {
    });
    return () => {
      mounted = false;
    };
  }, [workspaceId, navigate]);
  const start = () => void action.run(async () => {
    if (!data.approved) throw new Error("Approve the JD before assessment");
    if (!selected.length) throw new Error("Select at least one CV");
    const request2 = { candidate_ids: selected, approved_revision_id: data.approved.id, ...config };
    const result = await submitOnce(
      workspaceId,
      "assess",
      request2,
      (key) => client.getSubmission(workspaceId, key),
      (key) => client.startAssessment(workspaceId, selected, data.approved.id, config, key)
    );
    navigate(workspacePath(workspaceId, "progress", { jobId: result.id }));
  });
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx(PageHeader, { title: "New candidate assessment", description: "Submit a bounded batch with frozen JD meaning and model settings. The worker runs independently of your browser." }),
    /* @__PURE__ */ jsx(Feedback, { error: action.error, notice: action.notice }),
    /* @__PURE__ */ jsxs("div", { className: "split", children: [
      /* @__PURE__ */ jsxs(Panel, { children: [
        /* @__PURE__ */ jsxs("div", { className: "card-header", children: [
          /* @__PURE__ */ jsx("h2", { children: "Candidate CVs" }),
          /* @__PURE__ */ jsx(Status, { value: `${selected.length} selected` })
        ] }),
        cvs.length ? cvs.map((doc) => /* @__PURE__ */ jsxs("label", { className: "step row", children: [
          /* @__PURE__ */ jsx("input", { type: "checkbox", checked: selected.includes(doc.id), onChange: (e) => setSelected((previous) => e.target.checked ? [.../* @__PURE__ */ new Set([...previous, doc.id])] : previous.filter((id) => id !== doc.id)) }),
          /* @__PURE__ */ jsxs("span", { children: [
            /* @__PURE__ */ jsx("strong", { children: doc.filename }),
            /* @__PURE__ */ jsx("small", { className: "mono", children: doc.id.slice(0, 12) })
          ] })
        ] }, doc.id)) : /* @__PURE__ */ jsx(Blank, { title: "No CVs yet", description: "Upload one or more candidate documents before creating an assessment." }),
        /* @__PURE__ */ jsxs("div", { className: "toolbar", style: { marginTop: 14 }, children: [
          /* @__PURE__ */ jsx(Button, { size: "small", onClick: () => setSelected(cvs.map((c) => c.id)), children: "Select all" }),
          /* @__PURE__ */ jsx(Button, { size: "small", onClick: () => setSelected([]), children: "Clear" })
        ] })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "stack", children: [
        /* @__PURE__ */ jsxs(Panel, { children: [
          /* @__PURE__ */ jsx("h2", { children: "Assessment configuration" }),
          /* @__PURE__ */ jsx(FormField, { id: "run-provider", label: "Model provider", children: /* @__PURE__ */ jsxs(
            "select",
            {
              id: "run-provider",
              value: config.provider,
              onChange: (e) => setConfig((v) => ({ ...v, provider: e.target.value })),
              children: [
                /* @__PURE__ */ jsx("option", { value: "ollama", children: "Local Ollama" }),
                /* @__PURE__ */ jsx("option", { value: "openrouter", children: "OpenRouter cloud" })
              ]
            }
          ) }),
          /* @__PURE__ */ jsxs("details", { style: { marginTop: 12 }, children: [
            /* @__PURE__ */ jsx("summary", { style: { cursor: "pointer", fontWeight: 600, fontSize: 13, color: "var(--accent)" }, children: "Engine and evaluation settings" }),
            /* @__PURE__ */ jsxs("div", { style: { marginTop: 12, display: "grid", gap: 12 }, children: [
              /* @__PURE__ */ jsxs("label", { className: "row", children: [
                /* @__PURE__ */ jsx("input", { type: "checkbox", checked: config.use_llm, onChange: (e) => setConfig((v) => ({ ...v, use_llm: e.target.checked, unified: e.target.checked && v.unified })) }),
                "Enable AI evaluation"
              ] }),
              /* @__PURE__ */ jsxs("label", { className: "row", children: [
                /* @__PURE__ */ jsx(
                  "input",
                  {
                    type: "checkbox",
                    checked: config.unified,
                    disabled: !config.use_llm,
                    onChange: (e) => setConfig((v) => ({ ...v, unified: e.target.checked }))
                  }
                ),
                "Unified assessment mode"
              ] }),
              /* @__PURE__ */ jsx(FormField, { id: "run-yake", label: "YAKE candidate-phrase limit", children: /* @__PURE__ */ jsx(
                "input",
                {
                  type: "number",
                  id: "run-yake",
                  min: 1,
                  max: 150,
                  value: config.yake_top_k,
                  onChange: (e) => setConfig((v) => ({ ...v, yake_top_k: Number(e.target.value) }))
                }
              ) }),
              config.provider === "openrouter" && config.use_llm ? /* @__PURE__ */ jsxs(Fragment, { children: [
                /* @__PURE__ */ jsx(Message, { kind: "warn", children: "Cloud mode can transmit authorized applicant evidence and incur charges. Limits cannot exceed server safety settings." }),
                /* @__PURE__ */ jsxs("div", { className: "grid cols2", children: [
                  /* @__PURE__ */ jsx(FormField, { id: "cloud-context", label: "Context token ceiling", children: /* @__PURE__ */ jsx(
                    "input",
                    {
                      id: "cloud-context",
                      type: "number",
                      min: 2048,
                      max: settings.openrouter_context_tokens,
                      value: config.openrouter_context_tokens ?? settings.openrouter_context_tokens,
                      onChange: (e) => setConfig((v) => ({ ...v, openrouter_context_tokens: Number(e.target.value) }))
                    }
                  ) }),
                  /* @__PURE__ */ jsx(FormField, { id: "cloud-output", label: "Output token ceiling", children: /* @__PURE__ */ jsx(
                    "input",
                    {
                      id: "cloud-output",
                      type: "number",
                      min: 1,
                      max: settings.openrouter_output_tokens,
                      value: config.openrouter_output_tokens ?? settings.openrouter_output_tokens,
                      onChange: (e) => setConfig((v) => ({ ...v, openrouter_output_tokens: Number(e.target.value) }))
                    }
                  ) }),
                  /* @__PURE__ */ jsx(FormField, { id: "cloud-requests", label: "Maximum requests per assessment", children: /* @__PURE__ */ jsx(
                    "input",
                    {
                      id: "cloud-requests",
                      type: "number",
                      min: 1,
                      max: settings.openrouter_max_requests_per_assessment,
                      value: config.openrouter_max_requests_per_assessment ?? settings.openrouter_max_requests_per_assessment,
                      onChange: (e) => setConfig((v) => ({ ...v, openrouter_max_requests_per_assessment: Number(e.target.value) }))
                    }
                  ) })
                ] })
              ] }) : null
            ] })
          ] })
        ] }),
        /* @__PURE__ */ jsxs(Panel, { children: [
          /* @__PURE__ */ jsx("h2", { children: "Submission summary" }),
          /* @__PURE__ */ jsxs("div", { className: "step", children: [
            /* @__PURE__ */ jsx("strong", { children: "Approved JD revision" }),
            /* @__PURE__ */ jsx(Status, { value: data.approved ? String(data.approved.revision) : "Not approved" })
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "step", children: [
            /* @__PURE__ */ jsx("strong", { children: "Candidate files" }),
            selected.length
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "toolbar", style: { marginTop: 18, marginBottom: 14, gap: 12 }, children: [
            /* @__PURE__ */ jsx(Button, { kind: "primary", disabled: action.busy || selected.length === 0 || !data.approved, onClick: start, children: "Start assessment" }),
            /* @__PURE__ */ jsx(Button, { disabled: action.busy, onClick: () => {
              startDistinctIntent(workspaceId, "assess");
              action.setNotice("A new independent run has been authorized; submit again to create it.");
            }, children: "Create separate run with same inputs" })
          ] }),
          /* @__PURE__ */ jsx("p", { className: "help", style: { marginTop: 12, lineHeight: 1.5 }, children: "The same submission intent always reopens its existing job, including after a lost response or browser restart. Explicitly create a separate run to reassess identical inputs. Refresh, theme and progress never start assessment calls." })
        ] })
      ] })
    ] })
  ] });
}
export {
  AssessmentPage,
  DocumentsPage,
  Feedback,
  JDPage,
  WeightEditor,
  WeightsPage,
  client,
  useAction
};
