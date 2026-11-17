# CV Ranker Supervisor Edition v4.9.56 — Phase 1–4 reliability release

Date: 11 November 2026  
Protocol: `segment_ids_semantic_llm` v42

## Scope delivered

1. **Evidence-validation repair.** An independently, source-cited semantic finding may use substantive completed work even when CV extraction assigns an unexpected section, or the sentence contains a verb outside the old finite action list. Bare titles, JD copies, non-candidate material, and negative/learning-only wording are still subject to their guards. The code does **not** treat an arbitrary performed action as proof of any requirement.
2. **Named-condition safety.** An affirmative model finding for a longer JD with explicit named entities (such as Terraform or AWS IAM) cannot rely solely on citations that omit those named conditions. The check is derived from the frozen JD wording, not a profession/technology lookup table. Consecutive source words spelling out an acronym (e.g., *Identity and Access Management*) can also count as the name's source anchor. It is deliberately conservative and may require review for uncommon abbreviations.
3. **Retrieval and final-review changes.** Completed-duty recall considers substantive original passages in unexpectedly classified sections. Broad past-action wording can create retrieval leads without awarding credit. Final independent review checks context fit against its own system prompt, which can retain additional relevant CV context. Existing bounded-retry limits remain in place.
4. **Non-blocking comparison.** The weighted leaderboard includes candidates with technically unverified criteria. Their `P#` position and numeric score are explicitly *provisional lower bounds* based only on already verified Found criteria. The possible upper bound is shown separately. Unverified, Transferable and Not Found criteria receive no direct credit. Official backend completion (`primary_score=None` for incomplete candidates) is retained so a resumed run will not silently skip unresolved criteria.
5. **Transparent review leads.** The unfinished-requirement panel now distinguishes retrieved passages from validated evidence instead of describing them ambiguously as evidence examined.
6. **Generic JD action wording.** The source-backed type classifier recognizes a wider set of imperative task verbs, including `run` and `execute`; it does not contain role-specific matching answers.

## Mariam Abbas regression coverage

- R005: general Linux operations must not prove named Terraform modules.
- R009: alerting/Kubernetes operations must not prove named AWS IAM roles.
- R010: documented restore exercise work must be admissible even if a PDF parser labels it `skills`; related recovery drills can be presented as Transferable without direct Found credit, when the model makes that source-grounded distinction.
- A candidate with a combination of Found, Not Found and technically Unverified items appears in the weighted leaderboard with a provisional score, a provisional position and a possible ceiling.

These cases are **synthetic offline regressions based on the reported excerpts**, not an inspection of Mariam's original PDF or a live OpenRouter/Ollama assessment. No claim of real-world model accuracy is made.

## Safety and current limits

- A semantic model still makes the substantive JD-to-CV equivalence judgment. Original citation checks and specific deterministic guards cannot prove every possible semantic claim correct.
- A provisional position can change after further evidence is verified; supervisors should not use it as a final hiring recommendation.
- Source-hash checks remain optional for editable local mode and mandatory for remote exposure.
- The release does not change previously approved JD weighting, Required/Preferred pooling, or zero credit for Transferable.

## Update and verification

Extract this ZIP into a **separate folder**. Run `run_runtime_check.cmd`, `run_tests.cmd`, then `run_ui.cmd`. Start Ollama before AI-assisted assessment. Because the evidence-acceptance protocol changed from v41 to v42, run a **fresh assessment** using the approved JD and original CVs; do not treat old v41 final decisions as newly validated.

Offline automated checks, source manifest integrity, deployment preflight, and archive integrity are performed before packaging. A live screening pass with original Mariam PDF, DevOps JD and available execution details remains a separate acceptance step.

## Windows-only offline test compatibility update (12 November 2026)

- Corrected `test_signing_key_survives_restart_without_entering_recovery_file` to assert POSIX owner-only mode bits only on POSIX systems. Windows `Path.stat().st_mode` does **not** report NTFS file ACL privileges, so a UNIX `0o077` bitmask must not be used as an ACL security assertion on Windows.
- The test **still checks** key persistence across calls, random key length, stored bytes, and symbolic-link rejection on hosts that permit creating test symlinks. On Windows accounts lacking `SeCreateSymbolicLinkPrivilege`, only the symlink setup portion is skipped (Windows error 1314). No application source, scoring logic, assessment protocol, or recovery signing operation changed.
- **Security limitation:** this test change does not prove that the Windows key file has a private NTFS ACL. For multi-user Windows hosts, administrators should restrict access to the working directory and `.cv_ranker_cache` using appropriate Windows ACLs. A separate Windows-specific ACL hardening and verification task may be appropriate before a shared-host deployment.
- This is a test portability correction only; v4.9.56 assessment identity remains unchanged and **does not require reassessing CVs**.
