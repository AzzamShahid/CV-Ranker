# V4.9.26 — Include Preferred criteria in the overall JD score

## Corrected default calculation

The previous unsplit JD scoring allocation gave 100% of the JD weight to
Required criteria and zero to Preferred criteria. This contradicted the
supervisor's intended default: all JD criteria except separately weighted
Experience and Education must contribute.

In the default **unsplit** setting, JD coverage is now:

`(Required JD Found + Preferred JD Found) / (Required JD total + Preferred JD total)`

The resulting coverage receives the configured JD weight (80% by default).
For example, Experience 1/1, Education 0/1, Required JD 8/9, and Preferred JD
0/7 yields `10 + 0 + 80 * 8/16 = 50.00` out of 100, not 81.11.

The optional **Split JD** control remains available for an employer who wants
to explicitly weight Required and Preferred differently. Empty buckets still
follow the established applicable-weight normalization, and Transferable
does not receive direct credit.

The results page and both summary CSV / complete ZIP exports all use the
same corrected scoring projection, including previous assessments loaded
into the current session. No model reassessment is needed solely to update
the final weighted score.

Regression tests cover the reported 8/9 and 0/7 case, a positive Preferred
Found criterion, optional custom split, JD-only denominators and ZIP export.
