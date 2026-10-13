# Phase 7E — Independent Synthetic Benchmark Report

- Build: `industrial-benchmark-v1-2026-10-13`
- Mode: `fallback`
- Dataset: `phase7e-synthetic-v1`
- Dataset SHA-256: `29df6dadc386097db86de01ad233a8fde50da74ff3eac2f9432d268854ef9357`

**Scope warning:** Hand-authored synthetic labels are not external HR adjudications, real hiring outcomes, or production accuracy. The fallback run contains no Qwen inference. The live run represents the combined Qwen/Python system, not pure Qwen accuracy.

## Aggregate

- Scenarios / candidates / labelled decisions: **8 / 40 / 200**
- Exact requirement status accuracy: **74.00%** (148/200)
- Matched precision / recall / F1: **96.20% / 63.87% / 76.77%**
- False-positive matched: **3**; missed matches: **43**
- Uncertain recall: **72.22%**
- JD extraction precision / recall: **100.00% / 100.00%**
- JD priority accuracy: **100.00%**
- Mean pairwise ranking agreement, including ties: **76.25%**
- Mean nDCG@3: **98.91%**
- Pipeline / candidate failures: **0 / 0**

## Per-department results

| Department | Requirement accuracy | Matched precision | Matched recall | Pairwise ranking | JD recall |
|---|---:|---:|---:|---:|---:|
| backend | 80.00% | 100.00% | 71.43% | 90.00% | 100.00% |
| ai_ml | 80.00% | 90.91% | 71.43% | 80.00% | 100.00% |
| hr | 80.00% | 100.00% | 73.33% | 80.00% | 100.00% |
| finance | 40.00% | 100.00% | 16.67% | 40.00% | 100.00% |
| manufacturing | 76.00% | 92.31% | 80.00% | 60.00% | 100.00% |
| procurement | 88.00% | 100.00% | 86.67% | 100.00% | 100.00% |
| customer_support | 84.00% | 92.86% | 86.67% | 70.00% | 100.00% |
| healthcare | 64.00% | 100.00% | 30.77% | 90.00% | 100.00% |

## Highest-priority errors

These failures should be reviewed before tuning any model or Python rule:

- `backend/senior/R005` **Docker**: expected `matched`, predicted `not_matched`. Gold excerpt: Docker
- `backend/other_stack/R005` **Docker**: expected `matched`, predicted `not_matched`. Gold excerpt: Docker
- `backend/negated/R002` **Django**: expected `matched`, predicted `not_matched`. Gold excerpt: Django
- `backend/negated/R003` **PostgreSQL**: expected `matched`, predicted `not_matched`. Gold excerpt: PostgreSQL
- `backend/negated/R005` **Docker**: expected `uncertain`, predicted `not_matched`. Gold excerpt: Preparing for Docker certification.
- `ai_ml/full/R005` **Google Cloud**: expected `matched`, predicted `not_matched`. Gold excerpt: Google Cloud
- `ai_ml/abbreviations/R003` **Natural Language Processing**: expected `matched`, predicted `not_matched`. Gold excerpt: NLP
- `ai_ml/abbreviations/R005` **Google Cloud**: expected `matched`, predicted `not_matched`. Gold excerpt: GCP
- `ai_ml/unscoped_years/R003` **Natural Language Processing**: expected `matched`, predicted `not_matched`. Gold excerpt: NLP
- `ai_ml/unscoped_years/R004` **2+ years of Python experience**: expected `uncertain`, predicted `matched`. Gold excerpt: 4 years of professional experience.
- `hr/full/R005` **Excel**: expected `matched`, predicted `not_matched`. Gold excerpt: Excel
- `hr/junior/R005` **Excel**: expected `matched`, predicted `not_matched`. Gold excerpt: Excel
- `hr/learning/R001` **Recruitment**: expected `matched`, predicted `not_matched`. Gold excerpt: Recruitment
- `hr/different/R004` **3+ years of HR experience**: expected `not_matched`, predicted `uncertain`. Gold excerpt: 3 years in marketing.
- `hr/different/R005` **Excel**: expected `matched`, predicted `not_matched`. Gold excerpt: Excel
- `finance/full/R001` **Financial reporting**: expected `matched`, predicted `not_matched`. Gold excerpt: Financial reporting
- `finance/full/R002` **Accounts payable**: expected `matched`, predicted `not_matched`. Gold excerpt: Accounts payable
- `finance/full/R003` **Microsoft Excel**: expected `matched`, predicted `not_matched`. Gold excerpt: Microsoft Excel
- `finance/full/R005` **QuickBooks**: expected `matched`, predicted `not_matched`. Gold excerpt: QuickBooks
- `finance/in_progress/R001` **Financial reporting**: expected `matched`, predicted `not_matched`. Gold excerpt: Financial reporting
- `finance/in_progress/R002` **Accounts payable**: expected `matched`, predicted `not_matched`. Gold excerpt: Accounts payable
- `finance/in_progress/R003` **Microsoft Excel**: expected `matched`, predicted `not_matched`. Gold excerpt: Microsoft Excel
- `finance/wrong_degree/R001` **Financial reporting**: expected `matched`, predicted `not_matched`. Gold excerpt: Financial reporting
- `finance/wrong_degree/R002` **Accounts payable**: expected `matched`, predicted `not_matched`. Gold excerpt: Accounts payable
- `finance/wrong_degree/R003` **Microsoft Excel**: expected `matched`, predicted `not_matched`. Gold excerpt: Microsoft Excel
- `finance/negated/R002` **Accounts payable**: expected `matched`, predicted `not_matched`. Gold excerpt: Accounts payable
- `finance/negated/R003` **Microsoft Excel**: expected `matched`, predicted `not_matched`. Gold excerpt: Microsoft Excel
- `finance/learning/R001` **Financial reporting**: expected `matched`, predicted `not_matched`. Gold excerpt: Financial reporting
- `finance/learning/R003` **Microsoft Excel**: expected `matched`, predicted `not_matched`. Gold excerpt: Microsoft Excel
- `finance/learning/R005` **QuickBooks**: expected `matched`, predicted `not_matched`. Gold excerpt: QuickBooks
- `manufacturing/full/R005` **SAP**: expected `matched`, predicted `not_matched`. Gold excerpt: SAP
- `manufacturing/training/R001` **Production planning**: expected `matched`, predicted `not_matched`. Gold excerpt: Production planning
- `manufacturing/training/R002` **Quality control**: expected `uncertain`, predicted `not_matched`. Gold excerpt: Currently training in quality control.
- `manufacturing/different/R004` **4+ years of production experience**: expected `not_matched`, predicted `uncertain`. Gold excerpt: 5 years of retail experience.
- `manufacturing/different/R005` **SAP**: expected `matched`, predicted `not_matched`. Gold excerpt: SAP
- `manufacturing/unscoped/R004` **4+ years of production experience**: expected `uncertain`, predicted `matched`. Gold excerpt: 7 years of professional experience.
- `procurement/full/R005` **SAP**: expected `matched`, predicted `not_matched`. Gold excerpt: SAP
- `procurement/other/R004` **3+ years of procurement experience**: expected `not_matched`, predicted `uncertain`. Gold excerpt: 4 years of sales experience.
- `procurement/other/R005` **SAP**: expected `matched`, predicted `not_matched`. Gold excerpt: SAP
- `customer_support/full/R005` **Zendesk**: expected `matched`, predicted `not_matched`. Gold excerpt: Zendesk
- ...plus 12 additional errors. See the JSON.

## Known limitations

- Every CV and JD is a short text fixture; PDF/DOCX/OCR quality is NOT measured.
- The manually authored labels are not independently reviewed by HR domain experts.
- No protected characteristics or actual applicant data were used; fairness and real-world validity are NOT established.
- Gold ranking derives from the same documented required-coverage policy; it is not a hiring-outcome ground truth.
- Eligibility labels and external credential authenticity are outside this benchmark.
- For live runs, preserve the JSON and note that Python validators and fallback can change Qwen statuses.
