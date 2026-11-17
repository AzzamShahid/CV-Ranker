# v4.9.65: source-grounded condition-review contract

**Application build:** `phase7g-v4-9-65-source-grounded-compound-review-2026-11-13`  
**Assessment protocol:** v51. This is a controlled local-supervisor engineering release, not a demonstrated universal model-accuracy or production-security qualification.

## Repaired defect and previous behavior

The v4.9.64 compound parser could map a legitimate, original-source-supported Found proposal to `uncertain` because a JD used "including" or a compound "and", and final reconciliation could then turn it into **verified Not Found**. In a second case, a partial fabric-defect observation without evidence of correction suffered the same parser-driven negative. These are *different semantic situations*, so merely deleting the validator or trusting the first model proposal would be unsafe.

Reproduced before change:

| Approved JD | Original CV evidence | Pre-repair result | Intended handling |
|---|---|---|---|
| Interpretation of woven fabric construction, including weave pattern, EPI and PPI | Checked weave patterns, EPI, PPI and density against style sheets | `complex → uncertain → verified Not Found` | Syntax ambiguity must not erase original evidence; independently assess mandatory JD facets |
| Fabric defect identification and corrective action during weaving | Recorded defect observations at shift handover | `all_of → uncertain → verified Not Found` | Observation is not corrective action; a grounded relation can be Transferable, not Found |

## Actual implementation

- `cv_ranker/compound_validation.py`: syntactic inability to interpret a compound no longer becomes a completed verified candidate failure. Preserve cited original sources and a technical/meaning review signal.
- `cv_ranker/pipeline.py`: invoke one **bounded independent review** for eligible syntax-blocked rows, retain correct scoring ownership, keep completed siblings intact and avoid an identical semantic-review attempt on a compatible saved resume.
- `cv_ranker/condition_review.py`: independently requests condition-level relations using the frozen JD and actually transmitted candidate-specific source segments, checks citations, JD spans and missing parts, prevents whole-JD catch-all facet responses from passing ambiguous expressions, keeps unresolved or malformed responses Unverified, and respects specialist tenure/degree guards. A successful independently adjudicated row carries a transition trace and reviewer flag.
- `cv_ranker/assessor.py` and `cv_ranker/unified.py`: a **second, independent source-bound** positive may resolve zero shared lexical prefixes. The first model response, with only its own unsupported semantic assertion, still fails the legacy broad subject check. The identical-source error path skips a redundant correction when no different original evidence has been found.
- `cv_ranker/schemas.py`: optional frozen mandatory JD parts, alternative groups and a stable review-attempt signature; `cv_ranker/jd_review.py`: review/edit/approve the actual JD fragments with validation against original source; no new scored criteria. `cv_ranker/resume.py` includes the new decision module in the assessment fingerprint.
- `cv_ranker/ui/dashboard.py`: the company label comes from escaped `CVR_ORGANIZATION_NAME`, default TextileHR AI. This is display-only and does not influence ranking.

## Source and decision rules

1. A verified direct **Found** requires original source IDs actually sent to the model, positive claimant attribution and all mandatory employer conditions or one permitted alternative in an approved OR group. Full points apply **once** per original R criterion, not per split facet.
2. A verified **Transferable** requires cited real related completed work plus an explicit material direct gap, without granting direct scoring credit.
3. **Not Found** requires enough original source to evaluate and no supported direct or meaningful adjacent work. Incomplete extraction or syntax alone never proves absence.
4. Invalid/foreign/missing source IDs, unsupported/fabricated JD spans, an incomplete mandatory report, a provider failure, unreadable source or over-budget request retains technical **Unverified** until a legitimate reviewer/source repair.
5. The model's explanation remains a **proposal**, not an external verification of truth or qualifications. Even a perfectly source-bound but semantically *false* model interpretation is possible; human review remains essential for hiring.
6. The existing direct gross-mismatch guard still blocks a lone unsupported model positive. Source-bounded independent review with additional analysis may permit semantically equivalent descriptions with zero shared stems. No candidate name, requirement ID or domain-specific test outcome is a production rule.
7. The independent step is bounded by the existing provider's prompt-fit/cost/attempt controls; a model call costs time and potentially money. The v51 source signature prevents identical review repeats after a *saved failed review* but does not guarantee cross-process exactly-once delivery after an unexpected kill between network send and durable checkpoint. That separate reliability milestone remains open.

## Example controlled replays (not measured model accuracy)

- Full weaving construction evidence: **Found, 100** on a single 100-point requirement; **3 stub calls**, including independent relation and condition-level semantic review.
- Defect-observation-only evidence: **Transferable, 0**; correction work is not invented, even when initial model mistakenly asserts direct Found.
- Independent paraphrase, "Resolve customer complaints end-to-end" versus "Handled client grievances from intake through closure": **Found, 100**, **2 stub calls**; bypassing the original subject-guard lexical suspicion requires independent source-grounded review.
- Fake source ID, empty facets, a single catch-all JD quote, missing provider, or over-budget source: no awarded positive; Unverified or explicit blocker.
- Saved failed condition review with unchanged source/JD/provider/prompt/as-of date: **zero repeated semantic calls** on normal compatible resume.

## Migration and limitations

Protocol v51 changes decision semantics. v50 and earlier checkpoints are historical; don't claim old stored decisions were reassessed under v51 without actually running a new assessment. The default combined Required+Preferred weights, optional explicitly weighted split, Found full item credit, Transferable zero, and existing provisional score policy have **not** changed. The uploaded original source remains the authority. Tests use invented documents and scripted provider replies: no clinical/financial/employment judgment is independently certified. The complete full-suite and Windows/live-model sign-offs remain separate.
