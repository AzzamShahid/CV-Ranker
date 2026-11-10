# CV Ranker — Supervisor Edition (historical release chronicle; superseded)

**Interface V4.9.42 · 10 November 2026 · Clear completion and human-review states**

V4.9.42 removes the alarming **Provisional assessment** banner from completed
candidate reviews. A successful final assessment with one or more Transferable
or review-flagged criteria retains its score and ranking; each affected
requirement now explains its human-review flag inside the evidence details.
The leaderboard distinguishes **Complete**, **Review suggested (N)** and
genuinely unverified/unranked candidates. The downloadable weighted leaderboard
and per-candidate ranking summary use the same status language.

This is a presentation-only change. The legacy `Provisional` field is retained
in raw decisions JSON for older integrations but is not interpreted as an
assessment failure. Source verification, all decisions, score weightages,
assessment retry logic, and model prompts are unchanged. The assessment build
identity remains V4.9.39 / protocol 31 to preserve paid-run checkpoints.
See `docs/RELEASE_NOTES_V4_9_42.md` for tests and the compatibility details.

**Previous: Interface V4.9.41 · Supervisor readability and audit separation**

**Interface V4.9.41 · 10 November 2026 · Supervisor readability and audit separation**

**V4.9.41 simplifies the results screen for supervisors.** Instead of a grid
of repeated candidate cards, overlapping comparisons and another duplicated
evidence summary, the leaderboard now shows one full-width explanation per
candidate: rank, candidate, verified match percentage and why that position
was earned. A single optional comparison lets the reviewer select one other
candidate and see each side's verified advantages. The individual-CV panel
still retains the complete ranking explanation, the strongest credited
requirements and unmet criteria. Each JD criterion's original source evidence
and separate **Why this decision** remain accessible in simple expandable
rows and exports.

The cryptic `Reasoning reliability check · structurally_valid` has been removed
from normal results. Explanation consistency status, source diagnostics and
repair notices now live under **Technical details → Reasoning verification ·
internal audit**. Actual explanation problems still produce a plain-language
warning beside the candidate; incomplete assessments never receive a made-up
rank. Routine JD omissions such as an unspecified degree or minimum years are
now neutral notes, not misleading warning banners.

**This remains presentation-only.** The validated assessment build
`phase7g-v4-9-39-individual-criterion-why-restored-2026-11-10` and protocol
version 31 remain unchanged to avoid replaying paid cloud calls or invalidating
saved work. No model prompts, JD allocations, scoring, evidence acceptance, or
decision statuses were changed. See `docs/RELEASE_NOTES_V4_9_41.md`.

**Previous: Interface V4.9.40 · Supervisor visual refresh**

**Interface V4.9.40 · 10 November 2026 · Supervisor visual refresh**

**V4.9.40 redesigns how screening results are presented** without changing
candidate classifications, JD allocations, evidence citations, validation,
or cloud assessment requests. The interface now uses a coordinated navy/teal
identity, clearer numbered workflow headings, polished metric and table
surfaces, responsive explanatory cards, and a more prominent individual
**Why this CV received its ranking** section. That section separates the
overall ranking explanation from strongest credited evidence, highest-impact
gaps, and each individual requirement's **Why this decision**. The leaderboard
also contains concise, visually distinct per-candidate placement explanations.
Candidate and JD text embedded in new HTML cards is escaped.

The assessment build and protocol remain **V4.9.39 / protocol 31** on purpose:
a purely visual update must not invalidate completed checkpoints or cause paid
cloud re-assessments. The sidebar shows the separate interface version.
See `docs/RELEASE_NOTES_V4_9_40.md` for details and verification.

**Previous: Interface V4.9.39 · Individual per-criterion Why explanations**

**Phase 7G V4.9.39 · 10 November 2026 · Independent per-criterion Why explanations restored**

**V4.9.39 restores the individual requirement's `Why this decision` separately
from the leaderboard's `Why this rank`.** The visible JD-to-CV requirements
table now contains the full per-criterion explanation. As a result, even the
Streamlit table's built-in CSV export includes it; the dedicated final-decisions
CSV continues to provide its existing `Why` field. Every expanded requirement
also has an explicitly titled **Why this decision** paragraph before the cited
source passages. This does not add a model request, change weights or alter the
underlying decision status.

The experience validator additionally preserves a readable, source-derived
reason when an exact numeric CV claim rescues a false negative. For example,
the bundled Bilal PDF now states that its 4 years 5 months of professional
AI/ML delivery meets a 3-year JD minimum, with the original professional
summary as its source. Earlier generic or contradictory `does not establish`
reasoning no longer accompanies such a rescued Found result. Professional
field names and candidate identities are never hardcoded. See
`docs/RELEASE_NOTES_V4_9_39.md` for the scope and tests.

**Note:** A previously downloaded CSV cannot gain missing columns retroactively.
Restart the updated app, run a new assessment, and export the table again.
Prior-version assessment checkpoints are invalidated by the build change.

**Previous: Phase 7G V4.9.38 · Compound professional-tenure parser correction**

**Phase 7G V4.9.38 · 10 November 2026 · Compound professional-tenure parser correction**

**V4.9.38 fixes a regression in the experience check for compound work-scope
phrases such as `4 years 5 months of professional AI/ML delivery`.** The previous
parser did not accept `/` or `&` within a professional field description,
discarded the candidate's valid numeric experience statement and fell back to
dated role headings that require independently cited duties. That produced an
incorrect `role_semantic`/Not Found result for the supplied Bilal CV. The parser
now accepts compound punctuation in the existing general grammatical tenure
rule while continuing to reject historical datasets as years of employment.
Real-PDF and cross-industry regression tests verify source-ledger citations,
status reconciliation and preservation of the dataset safeguard. No candidate,
JD requirement ID, profession, or technology is special-cased. See
`docs/RELEASE_NOTES_V4_9_38.md` for the reproduced cause and limitations.

**Existing in-memory assessment checkpoints from previous builds are not
reused** after the version change, because they can contain old validator
decisions. Re-run the assessment under the new build ID. This fix was verified
offline; it does not guarantee independent cloud-model decisions on unrelated
requirements or remove the need for human verification of CV claims.

**Previous: Phase 7G V4.9.37 · Original-source-ID verification recovery**

**Phase 7G V4.9.37 · 10 November 2026 · Original-source-ID verification recovery**

**V4.9.37 addresses the live R008 `LLM integrations` validation deadlock.**
The user-provided diagnostics showed two repeated first-stage failures because
the model wrote a `matched_term` not present verbatim in its actual source,
followed by a final-review rejection of a paraphrased `proof_excerpt`.
Actual original CV passages contained a reported hosted LLM API integration
skill and an LLM-enabled service. A model-created highlight is not evidence:
when the *only* defect is that optional highlight, the pipeline now bypasses
the identical grouped correction and requests its one already-budgeted
independent review. The final reviewer cites immutable original segment IDs;
the program attaches their exact source text rather than asking the model to
copy it again. Missing `proof_excerpt` is valid, a non-verbatim excerpt with
substantial lexical overlap is discarded (with a diagnostic), and an
unrelated invented excerpt is still rejected. Invalid source IDs, contradictory
relations, negations and unsupported positive citations still fail closed.
No JD ID, candidate, skill or profession is hardcoded. See
`docs/RELEASE_NOTES_V4_9_37.md` for exact regressions and limitations.

**Cloud limitation:** The actual OpenRouter payload was not available; tests
replay the reported failure classes against the bundled Bilal PDF using
controlled model responses. Live model judgments may still be incorrect or
be affected by provider errors, and are not claimed to be verified here.

**Previous: Phase 7G V4.9.36 · Experience duration and JD-scope correction**

**V4.9.36 fixes two real-PDF ranking regressions.** The experience validator
previously treated an unrelated two-year research dataset as two years of
employment simply because it appeared under the Experience section. That
false duration conflicted with a separate explicit 5 years 9 months of
professional work, causing the candidate's 3-year requirement to be marked
Not Found/uncertain. Numeric years now require a grammatical relation to
employment, work, professional research or tenure, independent of section
headings or generic verbs appearing elsewhere in the text. An additional
independent source-grounded review is now triggered when a model calls
completed named-skill research merely Transferable because of commercial
deployment or production standards **not stated in the frozen JD**. The review
may find either Found or Transferable based on actual original-source evidence;
the Python gate does not automatically award skill points. No CV, skill, role,
or requirement ID is special-cased. See `docs/RELEASE_NOTES_V4_9_36.md`.

**Provider limitation:** The bundled PDF regressions and simulated model
review pass offline. Actual cloud answers still depend on the configured
model, provider responses and available credits; this release does not claim
to have exercised the user's live OpenRouter account.

**Previous: Phase 7G V4.9.35 · R008 proof validation and structured recovery**

**V4.9.35 fixes reproducible false rejection in the last independent
verification stage.** The prior verifier required the model's proof quote to
be a character-perfect substring of the extracted PDF. Simple punctuation
changes such as `held-out` versus `held out` and `recall@5` versus `recall 5`
caused legitimate, cited evidence to remain Unverified. It now accepts only
contiguous source-identical word sequences (minimum four substantive words)
after punctuation normalization, while still rejecting invented quotations.
Each final-stage rejection is recorded against the exact requirement ID,
including schema/transport failures and unsupported citations. A malformed
strict-schema cloud reply is retried using a different JSON response format,
with the same local strict validation and existing HTTP budget. The redundant
long final-verification task prompt has been shortened; the comprehensive
system evidence policies remain unchanged. No hardcoded skills, candidate
exceptions, new ranking credit, or additional repair loops were added. See
`docs/RELEASE_NOTES_V4_9_35.md` for the regression tests and limits.

**Important:** The exact OpenRouter payload that failed in the user's Windows
session was not available. Offline tests demonstrate a concrete failure mode
with the bundled Bilal CV, but a live provider run is still needed to verify
the provider-specific cause of any remaining R008 error.

**V4.9.34 makes incomplete reviews explainable without weakening evidence rules.**
If a particular criterion such as R008 remains Unverified, final model
verification prioritizes it above optional overlap reviews and includes its
validation feedback. The results display the exact requirement name,
source-validation notices and reviewed passages instead of only a generic
withheld-score message. A visible running-status widget remains active during
background assessments even when Streamlit's toolbar spinner is idle.
The setup page has six consistent, prominent headings. The leaderboard now
shows a short explanation of **every** candidate's ranking, contrasting top
strengths and gaps. Internal source IDs are retained for audit but omitted
from supervisor-facing reasoning paragraphs. The bundled Bilal PDF's model-
evaluation passages were exercised with a source-grounded offline judgment;
no live cloud provider result is implied. See `docs/RELEASE_NOTES_V4_9_34.md`.

**V4.9.33 fixes late-batch provider failures on multi-CV assessments.** A
failed cloud or model-response batch no longer discards valid decisions from
earlier batches of that candidate. Interrupted criteria stay Unverified with
zero ranking credit, and subsequent recovery sends only unfinished IDs. An
exhausted malformed JSON/schema response is retried as smaller groups; an
OpenRouter route that rejects strict JSON Schema is remembered for later calls
in the same assessment, avoiding repeated 400/422 requests. The background
status shows the current CV, JD batch, actual HTTP attempt and elapsed time.
Repeating identical invalid evidence judgments pauses automatic recovery with
the affected IDs instead of silently burning more cloud calls; temporary 429
limits continue to respect provider cooldown. This was verified with offline
two-CV and provider-failure tests; live OpenRouter success depends on the
actual service response and remaining credits. See
`docs/RELEASE_NOTES_V4_9_33.md`.

**Latest reliability update:** Incomplete CVs now resume only unfinished JD
criteria while retaining separately verified evidence. Cloud responses that
hit the output-token limit are divided into smaller batches, provider
Retry-After delays are not shortened, and an approved JD/CV checkpoint has a
configurable cumulative HTTP attempt ceiling (default 128, excluding JD
extraction). Initial candidate assessment and manual Resume now run in a
non-blocking in-memory worker, with result publication checked against the
original frozen inputs. See `docs/RELEASE_NOTES_V4_9_30.md`,
`docs/PROJECT_STATUS.md`, and `docs/DEMO_GUIDE.md`.

**Limitations:** This is not a durable queue across Streamlit restarts.
Active provider calls cannot be forcibly canceled after they begin. Live
model quality and provider quotas remain dependent on local configuration.

This is an independent copy of the approved V4.7 release. In AI mode the
existing local EmbeddingGemma retriever runs **before** a grouped LLM assessment.
No BM25 or new search was added, and the approved scoring rules remain in force.
See `docs/V48_UNIFIED_SEMANTIC_PLAN.md` for architecture, request budgets,
limits and verification. Employment-gap analysis remains out of scope for
this build.

**V4.9.32 corrects withheld-result rendering and the six-step setup sequence.**
An unverified candidate can have source-backed Found evidence but still has
no weighted point contributions or rank. The individual and overall Why
panels now label those missing values as withheld rather than trying to
format `None` as a percentage, which previously crashed the results page.
The displayed setup steps are now numbered 1 through 6, explicitly including
JD extraction as Step 2. See `docs/RELEASE_NOTES_V4_9_32.md`.

**V4.9.31 restores individual and overall ranking explanations and makes JD
weightage allocation editable after JD approval.** The reviewer now extracts
and freezes a JD first, then adjusts the Experience / Education / JD category
totals (100% altogether) and independently adjusts every frozen requirement's
share *within its own category*. Changing a share proportionally rebalances
only that category's other requirements. Required and Preferred criteria still
form **one pooled JD category**; the sidebar split only changes displayed
counts. Defaults remain equal shares, so untouched scores are unchanged.
The results recalculate immediately from already verified decisions, without
LLM calls or reevaluation. Individual candidates show **Why this CV received
its ranking**; the leaderboard adds a top-priority comparison, explanations of
the other positions, and source IDs. A deterministic reliability audit repairs
missing, contradictory, or invalidly cited explanations from stored verified
results; it cannot establish the semantic truth of every LLM sentence and
requires human review for that. Repairs never change scores or issue API calls.
The complete ZIP now contains allocation contributions, per-CV ranking Why,
and overall comparative reasoning. See `docs/RELEASE_NOTES_V4_9_31.md`.

**V4.9.29 repairs incomplete cloud assessment recovery.** After the first
assessment, an opted-in automatic retry runs on an isolated background worker;
the browser can continue displaying saved results. The retry scheduler does
not submit duplicate calls while the worker is running. It pauses after three
rate-limited retries without a newly verified CV, two other no-progress
attempts, or a provider-requested wait longer than one hour. An authorized
evaluator can pause retries, inspect partial results, and manually resume
after resolving provider limits. All worker results are checked against the
original JD, CVs and assessment settings before publication; completed CVs
and scoring rules remain unchanged. A live browser session is still required
to schedule *later* attempts; a server restart does not preserve jobs.
See `docs/RELEASE_NOTES_V4_9_29.md`.

**V4.9.28 restores the YAKE candidate phrases limit** inside the collapsed
sidebar section **Extraction limits & cloud recovery**. Its default is 40,
and reviewers can choose 10–200 suggestions. The selected value is passed to
the actual JD YAKE extractor and participates in the assessment input
identity; the scored frozen JD and combined 10/10/80 weighting are otherwise
unchanged. YAKE results remain searchable and downloadable on page 04.
See `docs/RELEASE_NOTES_V4_9_28.md`.

**V4.9.27 makes JD scoring a single, permanent pool.** All Required and
Preferred JD criteria have equal credit per item, no matter how the sidebar
groups their counts. The JD share is not split 50/50 or allocated a fixed
percentage to either subgroup: it uses `JD Found / JD total` for every
criterion other than separately weighted numeric Experience and Education.
For 9 Required plus 1 Preferred, one missing Preferred criterion means a JD
match of 9/10, not a loss of half the JD weight. The default weighted score
would be 92/100 when Experience and Education are both Found. Page 01 has
the same three weights, page 02 shows combined JD matches as the primary
count, and the optional sidebar split only reveals the subgroup breakdown.
Exports include both combined and subgroup counts; each candidate still has
one score out of 100%. See `docs/RELEASE_NOTES_V4_9_27.md`.

**V4.9.26 fixes the default JD scoring denominator.** When the optional
Required/Preferred split is OFF, the JD percentage is calculated using
**all approved Required + Preferred JD criteria**, excluding only the
separately weighted Experience and Education buckets. Every eligible JD
criterion earns equal default weight. For example, Required 8/9 and
Preferred 0/7 means JD 8/16 (50%), not 8/9. With default 10/10/80
weights and Experience 1/1, Education 0/1, the final score is 50/100.
Both the UI and complete-results export reuse the same calculation. The
earlier split-weighting option has been superseded in V4.9.27 by a
display-only Required/Preferred grouping. See `docs/RELEASE_NOTES_V4_9_26.md`.

**V4.9.25 makes the JD Required/Preferred denominators disjoint from
Experience and Education.** A duration-gated tenure criterion is counted only
in Experience; a degree/field criterion only in Education; all other JD
requirements are counted under JD Required or JD Preferred, including
qualitative performed-work competencies with no numeric duration threshold.
The page 01 approval banner, results overview, leaderboard, candidate details,
downloadable ranking summaries and complete-results leaderboard now follow
the same four-bucket counting convention. Each candidate retains one final
weighted score out of 100%; no second Required percentage is displayed. The
original full-priority totals remain inside the raw audit data for backward
compatibility and independent validation. See `docs/RELEASE_NOTES_V4_9_25.md`.

**V4.9.24 further simplifies the supervisor UI.** Weightage is now inside one
collapsed section on **01 Analyze**, with sliders, numeric controls, an
exact-100-mark check, and no presets. The Required / Preferred split button
has moved to the sidebar. The leaderboard and its CSV and ZIP summary now
show **one weighted score**, not an additional Required percentage; Required
and Preferred match counts remain. The sidebar retains the JD processing
guardrail and optional cloud recovery, but no longer exposes routine YAKE
phrase count, literal-initials, or ambiguous-type controls. Specialized HR
policy file uploads are tucked into a collapsed sidebar section. On page
**04 Technical details**, YAKE phrases now have a clearly ranked, searchable,
downloadable view with a visible lower-is-stronger explanation. See
`docs/RELEASE_NOTES_V4_9_24.md`.

**V4.9.23 places weightage configuration on 01 Analyze and uses the attached
supervisor prototype as its UX reference.** The three editable allocations
start at Experience 10%, Education 10%, JD requirements 80%, with synchronized
sliders and numeric controls. Allocation must total **exactly 100 marks**;
the user can apply presets, fill the remaining marks, or split the JD share
into Required and Preferred. The complete assessment is then opened through
**Continue to Results →**, a button displayed after a ranking is available.
Stateful page navigation preserves source uploads. Sample/demo selectors have
been removed from the interface, and session controls now live in the sidebar.
Only real, approved candidate assessments contribute to visible scores. See
`docs/RELEASE_NOTES_V4_9_23.md`.

**V4.9.22 introduces configurable supervisor scoring and a complete export.**
The results screen now ranks candidates on a 0–100 weighted score using
Experience 10%, Education 10%, and JD criteria 80% by default. Weights are
adjustable using both sliders and numeric +/- inputs; one button switches JD
weight between Required-only and a configurable Required/Preferred split.
Each JD criterion contributes to exactly one category, and a category not
requested by the approved JD is excluded with its weight renormalized over
the remaining applicable categories. Unverified assessments still have no
score or rank; Transferable remains non-scoring. The original required-only
coverage is preserved next to the weighted score for audit.

The new **Download everything** button produces one ZIP with the original
JD text, approved requirements, all candidate decisions and reasons, exact
CV source segments, weighted leaderboard, model run diagnostics and weight
configuration. Existing older reports lacking stored JD text say so honestly
rather than manufacturing it. See `docs/RELEASE_NOTES_V4_9_22.md`.

**V4.9.21 fixes under-retrieval of performed-work evidence shared by multiple
JD criteria.** Numeric professional tenure still requires role dates and
related duties, but qualitative experience (e.g., APIs or deliverable services)
is explicitly distinguished from years-gated experience in the model schema.
The first-pass evidence selection prioritizes original dated role headings,
performed duties and completed deliverables; one already-bounded independent
review may reconsider missed overlap without lexical auto-credit. Explicit
OR alternatives are evaluated separately. The Streamlit interface now keeps
technical detail, demos, full sources and audit files behind focused controls,
while retaining all reviewer, scoring, and citation workflows. See
`docs/RELEASE_NOTES_V4_9_21.md`.

**V4.9.20 adds an explicit JD extraction review and approval stage.** The
supervisor can inspect the exact extracted criteria, edit their names,
required/preferred classifications and source-supported types, add or remove
requirements, and approve the finalized set **before any CV assessment**.
The score denominator is frozen from the reviewer-approved set; no second
JD extraction can silently undo edits. Changing the JD, model, settings or
policy resets approval, and changing approved criteria invalidates any
candidate result reuse. This applies to real uploads and synthetic demos.
Also, Not Found explanations no longer show internal model-citation recovery
wording; relevant original CV passages stay visible as non-scoring review
context, with their provenance preserved in audit data. See
`docs/RELEASE_NOTES_V4_9_20.md`.

**V4.9.19 makes Not Found source visibility a validated output guarantee.**
All grouped model prompts now direct the AI to cite closest original CV
passages—including denials and relevant but insufficient claims—for Not Found.
When a model still emits `evidence_ids: []`, the final evidence boundary keeps
up to three actual CV source checkpoints from the literal/skills recall and
retrieval context. Recovered entries are explicitly labeled *review leads,
not model-cited or accepted evidence*. This does not modify a negative verdict,
skill match, percentage, eligibility, or ranking. No made-up source IDs or
occupation-specific exceptions are introduced. See
`docs/RELEASE_NOTES_V4_9_19.md`.

**V4.9.18 repairs evidence omission and the model's skill-list blind spot.**
When a plain JD lists a skill, affirmative CV skill-list claims can establish
it without a separate professional-use example. Original positive skill-list
source segments are recalled into the first assessment from generic word
overlap, even when the model or embedding retriever missed a nonliteral
service or platform term. This only retrieves evidence: semantically different
names still require model adjudication, never an automatic alias or point.
The prompt now explicitly checks verified constituent-service relationships;
the negative-result evidence contract preserves cited original segments as
**reviewed checkpoints, not accepted proof**. This prevents the UI from
silently hiding a real source merely because the model chose Not Found.
Negation and learning-only safeguards remain active, and old report builds
are visibly marked so a stale session cannot masquerade as a rerun.
See `docs/RELEASE_NOTES_V4_9_18.md`.

**V4.9.17 enforces the JD's evidence standard at the final validation
boundary.** An ordinary named-skill criterion can be established by an
affirmative CV skills-list claim or completed directly relevant work, without
an additional professional-employment or commercial-deployment condition.
The policy is derived from the frozen JD type and original quotation; explicit
experience/deployment/tenure requirements remain strict. Existing exact-source
validation may recover a literal positive skill without a second LLM call.
For semantic acronyms, services and related tools, no new Python equivalence
table or automatic credit is introduced. When a model nevertheless cites a
positive skill lead and rejects it only for an unstated professional-work
threshold, the candidate's original source stays visible and the ONE grouped
independent verification call can resolve it. A repeated contradictory reason
remains Unverified rather than producing a false scored decision. Plain-skill
negative explanations without relevant source leads no longer misstate an
unrequested professional-work condition. See
`docs/RELEASE_NOTES_V4_9_17.md`.

**V4.9.16 improves recall for directly reported skills that an LLM
incorrectly rejects for lacking a separate work-history project.** If the
model's own negative explanation acknowledges a skills-list claim, Python
recovers that exact original CV source and includes it in the existing one
grouped independent review per candidate. The independent adjudicator must
still judge whether a differently named product, acronym or service actually
belongs to the frozen JD's requested skill; the source or its wording never
automatically earns Found. Review priorities favor contradictory decisions
before weaker overlap leads without increasing the one-extra-call budget.
Learning intentions, denials, copied JD text and unrelated source snippets
remain excluded. This is domain-neutral and preserves all V4.9.15 scoring,
tenure, education and OpenRouter recovery rules. See
`docs/RELEASE_NOTES_V4_9_16.md`.

**V4.9.15 repairs a semantic consistency gap in the grouped assessment.**
When a model marks an ordinary skill Transferable but its explanation
affirmatively describes completed work in that same named skill, the existing
one-per-CV independent adjudicator revisits the frozen JD scope and cites
the original work. It can return Found only after a separate source-grounded
verdict passes validation; Python does not promote evidence by keyword,
occupation, or textual similarity. The review is selective so genuinely
different tools and merely related functions do not add cloud requests.
Previously cited evidence is prioritized in the independent context, avoiding
the loss of a contested original source. All V4.9.14 OpenRouter recovery
features and scoring rules remain. See `docs/RELEASE_NOTES_V4_9_15.md`.

**V4.9.14 repairs two source/recovery defects and implements the explicitly
authorized continuous OpenRouter recovery mode.** A pasted JD is written using
exact UTF-8 bytes, preventing Windows LF-to-CRLF translation from invalidating
the saved checkpoint and blocking automatic resume. For a plain skill/subject
criterion, completed research pilots and applied prototypes are not rejected
merely because they are not commercial deployments or the candidate's primary
specialization. An original performed-work quote mistakenly dismissed by the
model now triggers the existing one-per-CV source-grounded independent review;
Python never awards a point merely for a retrieved lead.

The historical cloud setting `OPENROUTER_MAX_REQUESTS_PER_RUN=0` means **no local
per-run HTTP-attempt ceiling**; an explicit positive value retains a per-run
cap, but eligible incomplete CVs can resume through later batches. Automatic
recovery continues after HTTP 429 using OpenRouter's `Retry-After` when present
and exponential backoff otherwise, without a two-attempt or 24-request limit.
Already-verified CVs are reused; the frozen LLM-validated JD and source hashes
must still match. Authentication, credit, and access failures stop; V4.9.29
also bounds repeated 429 and non-429 no-progress retries, rather than silently
looping on exhausted quotas. HTTP-200 responses
carrying OpenRouter's typed provider 429 are also recognized as rate limits.
This user-authorized mode can incur ongoing cloud charges, works only while
the browser session remains connected, and cannot bypass provider quotas.
See `docs/RELEASE_NOTES_V4_9_14.md` for safeguards and limitations.
**Current V4.9.30 policy:** a separate
`OPENROUTER_MAX_REQUESTS_PER_ASSESSMENT` limit (default 128) now caps actual
OpenRouter HTTP attempts across the initial candidate pass and all Resumes of
the same frozen JD/CV checkpoint. JD extraction is counted separately from
this limit. The older per-run setting remains an optional additional cap.

**V4.9.13 addresses a reported MSc-versus-BSc transferability omission.**
The grouped assessor and final independent review now explicitly ask TWO
distinct degree questions: whether the CV establishes the exact named award,
and, if not, whether a completed same/higher-level qualification has
substantial subject overlap. A negative answer to the first question must
not automatically become a negative answer to the second. A valid related
qualification is Transferable for HR review and scores no direct point.
An unrelated higher degree must remain Not Found. This strengthens the
provider's instructions; it does not invent academic equivalence through
Python or guarantee that an external model will always answer correctly.
See `docs/RELEASE_NOTES_V4_9_13.md` and the new regression cases.

**V4.9.12 resumes incomplete OpenRouter CV batches automatically while the
browser's Streamlit session remains connected.** The default-enabled checkbox
arms two additional bounded recovery batches, starting after a cooldown; each
automatic batch is limited to 24 HTTP attempts and stops if the provider
continues rejecting calls. Completed CV results and the frozen LLM-validated
JD are reused only if the exact uploaded documents, selected provider/model,
and relevant scoring and HR policies are unchanged. A structural-fallback JD
cannot be resumed as if it were model-validated, and changing or clearing the
inputs cancels the scheduled recovery. Automatic recovery may incur provider
costs. Closing the browser/session or restarting Streamlit stops the scheduler:
there is no server-side durable job queue or raw-CV persistence. For a manual
retry after that, upload the documents again and rerun. This release does not
change source validation, prompts, or scoring. See
`docs/RELEASE_NOTES_V4_9_12.md` and its offline regressions.

**V4.9.11 repairs incomplete multi-CV cloud runs.** A new **Resume unfinished
assessments** button reuses the frozen JD and verified candidate results only
when the uploaded document bytes, provider/model, scoring-relevant settings,
reviewed alias policy, and eligibility policy still match. Failed/unverified
CVs are retried; an unsuccessful retry does not discard a previously more
complete set of verified evidence checkpoints. Resume state is limited to the
current Streamlit session: no CV text is stored in an additional disk cache.
After HTTP 429, the app stops redundant cloud calls, preserves completed
results, honors a bounded cooldown, and reports safe retry diagnostics.
More conservative cloud pacing defaults reduce pressure but cannot defeat an
upstream provider's account-level quota. No score or semantic validator is
relaxed. See `docs/RELEASE_NOTES_V4_9_11.md` and the regression tests.

**V4.9.10 fixes the verified singular degree-category bug.** For a JD that
requires a completed bachelor's degree "in a Computer Program", Python had
incorrectly treated that *category* as an exact academic title, rejecting
both BS Computer Science and BS Software Engineering. Indefinite singular
category wording now follows the existing LLM-grounded family-membership
assessment. The model receives an explicit JD scope hint and may use the
existing one-per-CV independent grouped review for a missed family member.
Python still checks the completed degree level, authentic original CV citation
and explicit negative/pending claims; it never awards a field-family match
from a new hardcoded degree table. Exact named-major requirements retain
their strict behavior. See `docs/RELEASE_NOTES_V4_9_10.md` for safeguards,
regression coverage and the live-model verification limitation.

**V4.9.9 repairs the remaining conflict between Python source validators,
the LLM's source-grounded semantic assessment, and the UI explanation.**
Exact credential/tenure/AND-OR checks still protect direct score credit,
but a genuinely cited completed related qualification or related work is
preserved for unscored Transferable review when the stricter JD-specific
condition cannot be proven. Academic overlap inferred from a contradictory
model explanation now requires that the explanation identify the actual
CV field and the frozen JD field, rather than a generic claim of similarity.
The UI now displays the *final reconciled reason* without replacing it with
a generic validator diagnostic. Pending degrees do not count as completed.
The AI request budget and score weights are unchanged. See
`docs/RELEASE_NOTES_V4_9_9.md` for tested examples and remaining limits.

V4.9.8 repaired model-format and semantic-decision contracts without
changing scoring weights or the cloud request ceiling.** The JD extractor now
separates independent criteria from conditional alternatives and preserves
source-exact experience and degree clauses. The unified assessor requires
explicit direct/entailed/overlap/absent/uncertain relationships from live
providers, and its prompt differentiates an exact degree match from an
unscored but related completed degree. A fourth *valid, unique* citation for a
normal skill is bounded to three rather than treating the entire decision as
missing. Unsupported optional matched-term quotations are discarded for
source-grounded entailed completed-work decisions, without treating arbitrary
similarity as Found. Role duties can link to their own original dated heading
for numeric-experience validation. See `docs/RELEASE_NOTES_V4_9_8.md` for
verification and known limits.

V4.9.7 added role-date and source-recall improvements: When a CV dates a professional role in its header
and describes the work in subsequent bullets, the LLM now receives the header
AND a completed-work citation together. For an explicitly numeric JD minimum,
it may establish aggregate tenure across up to three dated roles only if the
model cites each role's own work, and Python does not double-count overlapping
calendar months. Completed related degrees at the requested or a higher level
are prioritized for *unscored* Transferable review, never converted into an
exact-major Found automatically. The transfer-retrieval path preserves a CV's
own explicitly named alternative tool plus evidence of independently completed
work with it (e.g. an alternative named in a comparison). Original resume
segments remain deduplicated and only bounded selected excerpts reach the LLM;
the project does **not** transmit every CV segment. Numeric-experience citations
may use up to six original IDs for three roles; other requirements retain the
three-ID maximum. The existing model request budget remains bounded. See
`docs/RELEASE_NOTES_V4_9_7.md` for its previous scope and limitations.

V4.8.1 additionally corrects request-counter initialization when a model
invocation is rejected before sending a request, and refreshes three V4.7-only
UI/runtime assertions for the unified V4.8 path. See
`docs/V48_1_TEST_FIXES.md`.

V4.8.2 fixes the source-segment tab's orphaned shadow-state reference and
improves the single correction request for invalid model rows. A stubborn
invalid row no longer discards every verified decision for that CV: it is
explicitly marked for human review without unsupported match credit. See
`docs/V48_2_LIVE_FIXES.md`.

V4.8.3 calibrates the unified/JD model prompts around source entailment and
transferability, especially time-series anomaly work versus forecasting and
completed comparable orchestration versus direct LangChain/LangGraph usage.
The existing Python compound validator now preserves cited completed-work
evidence for broad non-numeric experience requirements followed by descriptive
"including/such as" examples, with a review flag; true compound skill/degree
rules remain conservative. Candidate notices and run warnings are included in
the full JSON evidence export. See `docs/V48_3_LIVE_CALIBRATION.md`.

V4.8.4 makes the runtime prompts **department-neutral**. All named tool,
technology, and industry-specific examples were removed from the grouped
assessment, grouped correction, JD extraction, retained legacy, and semantic
review prompts. The evidence-entailment rules, frozen JD, and Python guards
from V4.8.3 remain unchanged. The main assessment prompt is shorter than in
V4.8.3 to protect context budget. See `docs/V48_4_DOMAIN_NEUTRAL_PROMPTS.md`.

V4.8.5 reuses the previously approved source-backed comparison-and-performed-
work bridge inside the unified path: a model's Not Found proposal may become
**Transferable for review only**, but never Found, when two independent CV
segments prove explicitly compared overlapping completed functions. First-pass
source-format notices that the ONE grouped correction has resolved are retained
in technical metrics, not misreported as final candidate errors. Verified
descriptive experience clauses keep human-review flags without generating
pipeline-failure notices. Deprecated Streamlit width arguments are updated.
No new search, provider calls, hardcoded profession map, or scoring weight
was introduced. See `docs/V48_5_SOURCE_CONSISTENCY.md`.

V4.8.6 repairs the batch-run failure in which valid source passages received
zero credit because the LLM supplied a malformed optional `matched_term` or
omitted a duplicate assessment row. Broad completed-work judgments keep their
real citations only when independent source/action and multiple JD-word anchors
are present; specifically named items retain strict source-term validation.
Ordinary punctuation and grammatical inflections are handled generically,
without profession or product names in the matching implementation. A directly
recovered stated skill is no longer labeled an unresolved zero-credit failure.
Both negative-control cases and the fictional Aisha PDF are regression tested.
See `docs/V48_6_VALIDATOR_RECOVERY.md`.

**V4.8.7 supersedes the V4.8.6 recovery shortcuts** after a systemic review
showed they did not generalize. A malformed/missing model decision is now
**Unverified**, never an automatically scored Not Found. A candidate with any
unverified criterion has no published percentage or rank; already validated
individual decisions are retained. Grouped JSON responses are checked for
exactly one row per frozen ID, including duplicates and unexpected rows.
Invalid optional quotes are stripped only when their cited source independently
contains the literal JD claim. Broader semantic judgments go to the existing
one grouped correction; a repeated invalid response remains Unverified.
The PDF bullet reader and physical qualification-line normalizer share the
same rules; the live retriever includes explicit source mentions and denials.
Backend, UI and CSV ranking use the same preferred tie-break. Output-aware
batching limits each group and retains several evidence leads before splitting.
`doctor.py --live` now uses the actual unified retrieval-first path. See
`docs/V48_7_SYSTEMIC_CONTRACT_REPAIR.md` for the exact contracts, API budget,
known limitations and deployment checks.

**V4.8.8 repairs missing/duplicated grouped assessment IDs** observed in a
five-CV run of V4.8.7 (only two candidates were fully assessed; the final
criterion of a batch was omitted or duplicated despite an additional model
correction). The model now receives a **dynamic JSON schema with one required
property per frozen JD ID** instead of an unrestricted array of decisions.
The Pydantic schema is generated from the uploaded JD's actual IDs for every
base and correction batch, so there are no candidate-, skill-, or industry-
specific patches. OpenRouter JSON parsing also rejects repeated object keys
instead of silently keeping one. The batching/retry ceilings and Found /
Transferable / Not Found evidence requirements are unchanged. Valid results
remain subject to source verification and human review. The offline five-
candidate, 18-criterion response-contract benchmark exercises full rankings
and a deliberately broken final-row citation; it is **not** a live model
accuracy benchmark. See `docs/V48_8_REQUIRED_ID_CONTRACT.md`.

**V4.8.9 repairs a different V4.8.8 problem:** one fictional five-CV run
reached **4/5 assessed**, but a negative-control CV's AI application duty
remained Unverified after an invalid citation and an unsuccessful correction.
Forensic inspection of the source parser showed that explicitly copied job-ad
text wrapped across a PDF line break and its middle line became eligible
project evidence. Separately, general negative sentences (such as "I have not
developed...") were misclassified as positive-toned evidence, triggering
unnecessary corrections. A scoped generic PDF continuation rule now keeps all
physical lines of that one copied paragraph in the non-candidate source
section; later real CV bullets remain available. A domain-neutral denial
recognizer prevents negative-only citations from being rejected as lacking
positive capability cues. Rejected citation IDs now produce a specific
diagnostic instead of inaccurately blaming missing/duplicated requirement
IDs. No scoring formula, skills dictionary, candidate override, new embedding,
or extra model request was introduced. See
`docs/V48_9_COPIED_SOURCE_NEGATION_REPAIR.md`.

**V4.8.10 separates tentative CV evidence from invalid positive citations.**
Another five-CV Cloud run of V4.8.9 reached 4/5: an applicant's explicit
"currently exploring ... tutorials" entry was repeatedly rejected as lacking
professional capability evidence. That source **should not grant Found**, but
it is a valid *learning-only* checkpoint, so the failure was in validation,
not the candidate. The verifier now checks the exact frozen requirement's
source-scoped tentative/negative tone **before** the positive-capability
guard. True tentative citations stay valid non-scoring outcomes; bare titles
or unrelated degrees still fail. Multiple citations are evaluated separately:
independent skills-list claims are not negated by learning-more notes, while
explicit positive-versus-negative contradictions trigger review. No extra
model call, candidate-specific rule, named-skill mapping, or score weight was
introduced. The PDF fixture and cross-department tests verify these
contracts. See `docs/V48_10_TENTATIVE_EVIDENCE_CONTRACT.md`.

Upload one job description and multiple CVs, rank the candidates, and inspect **one final evidence-based decision for every JD requirement**. Supports software, HR, operations, and other departments; criteria are extracted from the supplied JD, not a fixed skills catalogue.

## Start on Windows

1. Extract the ZIP into its own folder. Install **Python 3.11** and open PowerShell in the extracted `CV_Ranker_Supervisor_Edition` folder.
2. Run:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   Copy-Item .env.example .env
   notepad .env
   .\run_runtime_check.cmd
   .\run_ui.cmd
   ```

3. Configure **both assessment models once in `.env`**. Put your OpenRouter key in the same private file if you plan to use Cloud. Select **Cloud (OpenRouter)** or **Local (Ollama)** in the sidebar; no model IDs are entered in the UI. `CVR_LLM_PROVIDER` controls only the initial sidebar selection. The `.env.example` model IDs are examples, not availability guarantees. Do **not** share `.env`, API keys, real candidate CVs, or generated private outputs.
4. For the **required retrieval-first AI workflow**, install and start local **Ollama** and pull the model named by `EMBEDDING_MODEL` in `.env` (default `embeddinggemma-2:latest`). `OLLAMA_BASE_URL`, the embedding timeout, and embedding batch size are also configured in `.env`. This local step is required even with Cloud LLM selected. Cloud LLM assessment transmits authorized CV/JD excerpts to the chosen provider.

**V4.6 reliability repairs:** Explicit degree claims after combined education headings are now discovered; relevant years written as words (such as "four years") count when tied to the same JD-described professional work; the compound-criteria checker no longer erases verified numeric tenure or qualifications. Ollama embeddings use the configured URL/model and small ordered batches, and corrupted individual derived vectors are recomputed. OpenRouter calls are paced, honor capped `Retry-After` hints, and stop repeated calls after exhausting the retry budget. A provider's hard quota cannot be bypassed. Local semantic retrieval remains independently inspectable in **04 Technical details** even if later cloud adjudication fails.

**V4.7 supervisor-clarity repairs:** A named-tool denial no longer automatically hides completed comparable work: an explicit source comparison plus an independent performed-work passage can justify a **Transferable** review result, never a direct match or a point. For extensive Not Found searches (such as Node.js), the UI displays up to four representative checkpoints and discloses the full examined count; the JSON export and tab 03 retain all original evidence. Incomplete semantic verification, earlier citation notices, and transferable outcomes are visibly marked for human review. The legacy time-series matching rule was deliberately left unchanged in this release.

You can disable AI-assisted assessment in the sidebar for an offline, conservative exact-match fallback. Fallback and AI outcomes are not interchangeable.
The chosen provider determines the JD and grouped CV assessment for the next **Analyze** run; local EmbeddingGemma retrieval is part of every AI-assisted CV assessment. An existing report is not silently rescored when switching; the UI prompts you to reanalyze. Cloud assessment needs an OpenRouter API key; Local needs the configured Ollama model installed and running.
For a strict provider readiness check, use `run_supervisor_demo.cmd`; it runs `doctor.py --live` first and stops if an external service is unavailable.

## Present the results

1. **01 Analyze** — upload a JD and CVs, **extract and review/edit the JD first**, then approve/freeze it. Only then assign the three category weight totals (10/10/80 initially) and set each requirement's percent **within its own category**. Changing one item automatically redistributes its category peers to preserve 100%. Then assess candidates. You can readjust weights later without rerunning the API; go to **Continue to Results →**.
2. **02 Rankings & evidence** — the candidate leaderboard appears **above** individual details, ranked by the configured 0–100 weighted score. Each row shows **one final weighted percentage**, `Required JD Found/Total` (e.g. `8/9`), `Preferred JD Found/Total` (e.g. `3/7`), separate Experience/Education coverage when present, **Transferable** count, assessment mode, and review flags. The **overall ranking Why** section explains top-versus-alternative differences, ties, and every candidate's strengths/gaps. Download the table as CSV, or the complete run including all explanations and allocations using **Download everything**.
3. Select a candidate to inspect **Why this CV received its ranking** (including weighted impact, reasoning, and source IDs), its reliability check, and the **single final JD-to-CV table**. Each completed assessment is **Found**, **Transferable**, or **Not Found**; an invalid model/source response is explicitly **Unverified** until rerun. An incomplete candidate never receives a falsely low percentage or rank. Reasons and original source passages remain inspectable; detail counts and leaderboard come from the same validated decisions.
   For a nonmatch with a large evidence search, the expandable panel shows a small, varied sample of actual passages. The full citations remain in **Download all final evidence (JSON)**.
4. **03 CV source segments** — see the unfiltered source ledger, including passages not accepted as matches.
5. **04 Technical details** — inspect grouped request counts, source extraction, retrieval metrics, and assessment/validation diagnostics for audit.

**Scoring:** The configurable final score is weighted to 100% using only verified Found criteria. Required and Preferred totals remain visible as counts, without a second Required percentage. By default, **both Required and Preferred JD criteria earn equal per-criterion credit**. Once the JD is approved, every individual JD item has a configurable percent of the *single JD pool*, with separate per-criterion shares for numeric Experience and Education requirements. Example: Python at 25% of an 80% JD category contributes 20 overall points if Found. Selecting **Split JD into Required / Preferred** changes only the visible counts, never the allocation or scoring formula. Experience and Education remain separately weighted. Transferable is reported separately; it never earns direct-match points. A non-negated, affirmative skills-list claim can establish an ordinary skill, clearly labelled as self-reported; demanding an unrelated project example is not necessary. Evidence of doing an equivalent function without the exact tool may be **Transferable**, with its reasoning and source citations. Incomplete technical verification withholds the candidate score and rank, not just a provisional review note.

**Experience and studies:** An explicit minimum professional tenure becomes its own JD requirement; merely listing the requested skill does not satisfy that minimum. An explicit academic degree and field becomes a separate JD criterion. For example, with a *fictional JD that specifically requires a completed bachelor's degree in Computer Science*, a reported BS Computer Science can be **Found**, a reported BS Software Engineering can be **Transferable** when a source-grounded AI explanation establishes a genuinely related field (but earns no point), and an unrelated BS Fine Arts is **Not Found**. The AI does not make degree authenticity determinations. No degree/years criterion is generated if the uploaded JD does not ask for one. The UI warns when such a criterion is missing from the frozen JD.

The package still contains fictional `sample_data/` fixtures for developer regression tests, but the Streamlit interface does not offer a demo-candidate selector. Your uploaded, approved JD always controls the actual criterion counts and score.

This is **decision support**, not automatic hiring approval. The tool does not independently authenticate qualifications or experience.

## Organized project structure

| Folder/file | What it contains |
| --- | --- |
| `app.py`, `run_supervisor_demo.cmd`, `run_ui.cmd` | UI and simple Windows launchers |
| `cv_ranker/` | JD extraction, source-bound assessment, scoring, reconciliation |
| `cv_ranker/ui/` | Leaderboard, unified evidence table, CV source viewer |
| `cv_ranker/semantic/` | Optional local EmbeddingGemma retrieval and functional review |
| `sample_data/` | **Fictional** example JDs and resumes, including multi-candidate demo |
| `docs/` | Current setup, technical explanation, and presentation notes |
| `docs/history/` | Earlier Phase 4–7G investigation/release documents, retained for reference |
| `tests/` | Automated regressions including final-leaderboard checks |
| `evaluation/`, `scripts/`, `tools/` | Benchmarks, optional utilities and diagnostics |
| `cv_ranker/build_manifest.json` | SHA-256 release integrity list checked at startup |

### Further reading

- [Supervisor walkthrough](docs/SUPERVISOR_WALKTHROUGH.md)
- [OpenRouter setup](docs/OPENROUTER_SETUP.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Project map](docs/PROJECT_MAP.md)
- [V4.9.6 cloud failure attribution and no-fallback safeguards](docs/RELEASE_NOTES_V4_9_6.md)
- [V4.9.5 higher-level qualification and job-title parser repair](docs/RELEASE_NOTES_V4_9_5.md)
- [V4.9.4 source-recall and related-qualification repairs](docs/RELEASE_NOTES_V4_9_4.md)
- [V4.9.3 field-category, tenure scope and saved-session fixes](docs/RELEASE_NOTES_V4_9_3.md)
- [V4.9.2 consolidated evidence-contract changes and limits](docs/RELEASE_NOTES_V4_9_2.md)
- [Earlier V4.7 release notes](docs/RELEASE_NOTES_V4_7.md)
- [Pre-supervisor verification checklist](docs/SUPERVISOR_V47_CHECKLIST.md)
- [Archived V4.1 decisions](docs/history/PHASE_7G_V4_1_FAVORABLE_EVIDENCE_REPAIR.md)

## Verify the installed release

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live
.\.venv\Scripts\python.exe doctor.py --provider ollama --live
.\.venv\Scripts\python.exe doctor.py --provider openrouter --live
```

`doctor.py --live` checks external providers and may need network/model availability. The unit tests do not require your private OpenRouter key. Always extract a new release into a **new folder** rather than mixing Python files from previous releases; startup validates the build manifest.

