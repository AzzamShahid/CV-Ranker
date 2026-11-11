# V4.9.27 — One pooled JD group in every mode

The Required/Preferred sidebar button is a **display-only** grouping control.
No JD category weight is allocated to Required or Preferred independently.

The score is always:

`Experience weight × experience Found/total`
`+ Education weight × education Found/total`
`+ JD weight × (Required Found + Preferred Found)/(Required total + Preferred total)`

Each individual JD criterion contributes the same portion of the JD weight,
whether Required or Preferred. The counts exclude duration-gated Experience
and degree-based Education, which retain their own configured weights. If a
whole category is absent from the JD, its weight follows the existing
applicable-weight normalization rule. Transferable earns no direct credit.

Examples with the default 10% Experience / 10% Education / 80% JD weights:

| Experience | Education | JD Required | JD Preferred | Final |
| --- | --- | --- | --- | --- |
| 1/1 | 1/1 | 9/9 | 0/1 | 92.00% |
| 1/1 | 1/1 | 9/9 | 1/1 | 100.00% |
| 1/1 | 0/1 | 8/9 | 0/7 | 50.00% |

The weighted output exposes only **Experience, Education and combined JD**
effective percentages; it no longer displays separate JD Required/Preferred
weight allocations. The leaderboard and candidate view put `JD matched`
first. The optional sidebar button displays the Required/Preferred counts,
without changing any numeric score. The complete ZIP export always retains
the combined and separate counts, the original JD, source evidence and all
candidate decisions. The previous Required/Preferred share input is retired
from the UI; legacy stored values are ignored by the scorer.

Equal combined weighted scores also receive the same rank, regardless of
whether the candidate's matched JD items were Required or Preferred. The
former Preferred-based weighted leaderboard tie-break no longer applies.

The full test suite verifies individual per-criterion impact, zero-to-full
legacy split-share values, missing categories, and CSV/ZIP consistency.
