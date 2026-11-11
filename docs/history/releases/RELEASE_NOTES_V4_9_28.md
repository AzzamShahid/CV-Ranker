# V4.9.28 — Restore YAKE candidate phrases limit

The YAKE candidate phrases limit has been restored to the sidebar under
**Extraction limits & cloud recovery**. It defaults to 40 and may be set
from 10 to 200 in increments of five. The chosen value is passed into
`Settings.yake_top_k`, which the existing YAKE keyword extractor uses as
its actual `top` argument.

This is an extraction-discovery control, not a scoring criterion or a JD
requirement limit. YAKE candidate phrases remain suggestions; the JD must
still be extracted, reviewed and approved. The existing frozen requirement
processing limit stays alongside it, and page 04 retains the ranked YAKE
results table and CSV download.

Regression checks verify the sidebar-to-settings binding and the extractor's
handling of multiple limits. The V4.9.27 one-pooled-JD scoring formula and
Required/Preferred display-only split remain unchanged.
