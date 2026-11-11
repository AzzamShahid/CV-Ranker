# Phase 7G V4.9.13 — Two-question degree overlap review

Build `phase7g-v4-9-13-degree-overlap-two-question-review-2026-10-28`.

## Reported failure

For an exact JD criterion **Completed Bachelor's degree in Computer Science**, a CV with **MSc Artificial Intelligence, 2022** received **Not Found** with a reason stating only that no matching bachelor's degree appeared. That reason establishes absence of an *exact* claim but does not resolve whether the stated higher qualification has substantially related subject matter.

## Correction

- The main grouped assessment prompt now requires two **independent** findings: whether the named degree is directly established and whether a separately cited, completed same/higher-level qualification has substantial subject overlap.
- The existing one-per-CV independent final verification now stresses the same distinction and rejects a literal degree-name mismatch as a complete answer to the transferability question.
- A related higher qualification still never automatically earns **Found** or direct scoring credit for a missing exact lower-level degree. Only a source-cited positive semantic finding is eligible for **Transferable**, with human review recommended.
- A higher degree in an unrelated subject remains **Not Found**. No academic-major whitelist, guessed degree equivalence, or new scoring percentage was added.
- Automatic bounded recovery from V4.9.12 remains available with the same session-only limits.

## Verification and limitation

Focused offline tests cover the reported MSc AI / BS CS case entering the independent semantic review, source-cited related MSc becoming unscored Transferable, an unrelated PhD remaining Not Found, and the two-question prompt contract. The full regression suite and manifest check must pass before distribution.

**Provider-dependent outcome:** The live OpenRouter model can still make a wrong semantic judgment. This build improves the decision instructions and confirms that Python can preserve a correctly returned related-degree judgment; it cannot prove that every future provider response will be accurate. Verify the exact CV/JD combination with the selected live provider before relying on its screening label.
