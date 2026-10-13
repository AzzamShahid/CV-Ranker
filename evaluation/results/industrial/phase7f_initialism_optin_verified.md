# Phase 7E — Independent Synthetic Benchmark Report

- Build: `evidence-integrity-repair-2026-10-13`
- Mode: `fallback`
- Dataset: `phase7e-synthetic-v1`
- Dataset SHA-256: `29df6dadc386097db86de01ad233a8fde50da74ff3eac2f9432d268854ef9357`
- Exact initialism recovery: `True`

**Scope warning:** Hand-authored synthetic labels are not external HR adjudications, real hiring outcomes, or production accuracy. The fallback run contains no Qwen inference. The live run represents the combined Qwen/Python system, not pure Qwen accuracy.

## Aggregate

- Scenarios / candidates / labelled decisions: **8 / 40 / 200**
- Exact requirement status accuracy: **99.50%** (199/200)
- Matched precision / recall / F1: **100.00% / 99.16% / 99.58%**
- False-positive matched: **0**; missed matches: **1**
- Uncertain recall: **100.00%**
- JD extraction precision / recall: **100.00% / 100.00%**
- JD priority accuracy: **100.00%**
- Mean pairwise ranking agreement, including ties: **100.00%**
- Mean nDCG@3: **100.00%**
- Pipeline / candidate failures: **0 / 0**

## Per-department results

| Department | Requirement accuracy | Matched precision | Matched recall | Pairwise ranking | JD recall |
|---|---:|---:|---:|---:|---:|
| backend | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| ai_ml | 96.00% | 100.00% | 92.86% | 100.00% | 100.00% |
| hr | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| finance | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| manufacturing | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| procurement | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| customer_support | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| healthcare | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |

## Highest-priority errors

These failures should be reviewed before tuning any model or Python rule:

- `ai_ml/abbreviations/R005` **Google Cloud**: expected `matched`, predicted `not_matched`. Gold excerpt: GCP

## Known limitations

- Every CV and JD is a short text fixture; PDF/DOCX/OCR quality is NOT measured.
- The manually authored labels are not independently reviewed by HR domain experts.
- No protected characteristics or actual applicant data were used; fairness and real-world validity are NOT established.
- Gold ranking derives from the same documented required-coverage policy; it is not a hiring-outcome ground truth.
- Eligibility labels and external credential authenticity are outside this benchmark.
- For live runs, preserve the JSON and note that Python validators and fallback can change Qwen statuses.
