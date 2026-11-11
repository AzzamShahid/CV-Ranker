# TextileHR AI / CV Ranker 4.9.49 — qualification alternatives, transferable work, corporate accent

Date: 11 November 2026. Assessment protocol: `segment_ids_semantic_llm` v35.

## Verified defects repaired

1. **Explicit alternative majors in a JD.** The source-verified qualification
   validator previously checked the first extracted academic field while
   rejecting another explicitly permitted field at the same degree level.
   It now reads the employer's named alternatives from the frozen JD itself.
   A CV claiming a *completed BS Textile Technology* directly satisfies the
   written option *Bachelor's degree in Textile Engineering or Textile
   Technology*. This does **not** imply equivalence between other degrees,
   unrelated fields, or separately named diploma/degree types. An AND
   condition is never silently converted to OR. Degree claims still require
   the original source citation; employer verification remains necessary.

2. **Related but different professional work.** When an LLM explanation says
   an applicant has work in another area and not the specifically required
   area, the experience validator can retain **Transferable** for HR review
   if cited affirmative work passages independently show subject overlap.
   It does not credit the required years, alter numeric experience checks,
   or make Transferable earn any points. Original evidence and the reason for
   withholding direct credit stay visible. Unrelated work and observation
   placements do not become equivalent professional work.

3. **Source-faithful reasons.** If a degree result is corrected from Not Found
   to Found, the displayed reason and citation reflect the actual accepted
   qualification instead of leaving the obsolete negative explanation.

4. **Reliance-inspired presentation.** Native Streamlit theme settings and
   guarded CSS adopt a restrained forest-green, cream, white and slate
   corporate palette. The header names Reliance Weaving Mills Limited and
   shows a stylized **RW** initials placeholder; this is **not the official
   company logo**. Replace with an approved brand asset when supplied.
   Styles do not change score calculations, provider requests, retrieval, or
   resume processing. Streamlit static file serving remains disabled.

## Boundaries preserved

- JD extraction and frozen JD content remain user-reviewable and unmodified.
- Required and Preferred share the existing single weighted JD pool; degree
  and experience keep their separately editable categories.
- Only validated **Found** results earn points; Transferable is for reviewer
  context, never a disguised Found.
- No candidate name, profession, employer, industry, hardcoded role vocabulary,
  or criterion ID is used to decide a match.
- No automatic retry loop or extra OpenRouter request was added. Automated
  testing uses synthetic evidence and makes no paid provider calls.
- Existing security posture remains: local loopback access by default, OIDC
  and other remote-deployment gates unchanged, private static serving off.
- Protocol v35 prevents older saved assessment states from being mistaken for
  evidence validated under the new rules. Keep old checkpoint ZIPs as a
  historical record; re-assess with the updated release when necessary.

## Scope and limitations

Regression tests verify the two reported outcomes and their negative
controls. They do not guarantee perfect judgment on arbitrary future CVs,
especially ambiguous, scanned or contradictory resumes. A full live
OpenRouter assessment needs the user's configured credentials and local
Ollama embedding service; it has not been run as part of this offline repair.
This remains human-in-the-loop recruitment **decision support**, not an
unattended hiring or public production service. Consult
`docs/PRODUCTION_SECURITY.md` before exposing applicant data remotely.
