# TextileHR AI CV Ranker v4.9.65 — Source-Grounded Compound Review

**Release date:** 13 November 2026  
**Build:** `phase7g-v4-9-65-source-grounded-compound-review-2026-11-13`  
**Assessment protocol:** `segment_ids_semantic_llm` **v51**  
**Release class:** Partial engineering candidate, **not a complete R0–R9 / live accuracy / Windows-qualified release**.

### Fixed in source

1. A compound JD parser's inability to determine mandatory facets is no longer accepted as a **verified candidate Not Found**. Original source citations and a technical/reviewer signal are retained.
2. Added a **bounded, independent condition-level review**, using original candidate-specific source IDs, frozen JD spans and validated facet coverage, to distinguish a complete task from meaningful but incomplete related work. Invalid/unsent evidence, a catch-all facet, missing credentials/dates and provider-context refusal never earn a fabricated direct score.
3. Preserve legitimate supported Transferable when only part of a compound employer duty is shown, with **zero direct points**.
4. Allow independently reviewed source-based direct semantic equivalence without five-character word overlap; primary unsupported positives still pass through normal gross-mismatch checks. Skip one redundant unchanged-source correction when only the subject anchor is missing.
5. Store signature after failed compound review; compatible resume does not repeat the identical paid review request. This is **not** exactly-once dispatch across a crash.
6. JD review can freeze source-quoted mandatory facets and alternative groups. Invalid and duplicate fragments are rejected; splitting never creates extra score items.
7. Neutral, escaped organization display from `CVR_ORGANIZATION_NAME`, default `TextileHR AI`, independent of model/scoring.
8. New versioned regression modules for the original failing transitions, positive and negative provider-stub decisions, ZIP score parity, source forgery, call counts and resume reuse.

### Synthetic-before/after controls

| JD/source | v50 before | v51 controlled evaluation |
|---|---|---|
| Construction interpretation with original EPI/PPI pattern checks | syntax-uncertain → verified Not Found | **Found, 100** after source-bound independent facet review, 3 stubbed model calls |
| Defect observation without corrective action | syntax-uncertain → verified Not Found | **Transferable, zero direct points** with model-confirmed missing corrective action |
| Defect identification **and documented corrective action** | previously parser-dependent | **Found** under complete independently validated facet review |
| Resolve customer complaints / handled client grievances | original lexical guard rejects primary unrelated stems | independent source review **Found**, 2 stubbed calls, no redundant identical-source correction |
| Foreign `S###`, insufficient facets, over-budget context | not appropriate for credit | **no direct credit**, technical/unverified output |

The model is still **capable of a semantic mistake** even with valid source IDs. These tests use programmed model responses and cannot certify general equivalence accuracy.

### Verification and deployment

See `docs/V4965_IMPLEMENTATION_LEDGER.md` for verified test commands/counts and remaining gates. The unmodified original v50 release is the rollback source. No live external model calls were made, no real applicant CVs were processed, and a Windows runtime is not available here. Current Linux Python lacks Streamlit/LangChain; unresolved full-suite failures and collection errors must be disclosed. Public/remote deployment remains blocked by separate security requirements.

### Actual tested development result

Linux Python 3.13.5: **114 focused passes; 1,449 broader passes, 22 failures and 10 collection errors** (mostly missing Streamlit/LangChain, plus two unconfigured-LLM test errors). The full suite is **not passing**. The two controlled supervisor runners remain **7/7** and **15/15** with synthetic provider outputs; these are not independent accuracy scores. See implementation ledger for commands and limitations.
