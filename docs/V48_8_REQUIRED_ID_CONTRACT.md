# Phase 7G V4.8.8 — Required-ID structured decisions

## Triggering observation

The V4.8.7 five-resume run reported **2/5 CVs fully assessed**. The three
remaining CVs had no published score. One showed **R018: assessment row was
missing or duplicated** twice, including after the bounded grouped correction.
The model's JSON parsed correctly, but the schema permitted an arbitrary list
of assessment rows. A syntactically valid list did **not** guarantee one
decision per frozen requirement. The same weak shape was used in the retry.

We do not have the original API response bodies, so cannot prove whether the
provider omitted or duplicated R018, or which prompting/model limitation
triggered that behavior. Either way, the output contract allowed it. This is
a general response-interface defect, not evidence about that CV's suitability.

## Contract change

Prior shape (valid JSON despite absent/multiple IDs):

```json
{"assessments":[{"requirement_id":"R001","decision":"found","reason":"..."}]}
```

New shape (the following keys are examples; **the actual required keys are
generated at runtime from the current frozen JD**):

```json
{
  "R001": {"decision":"found","evidence_ids":["S001"],"matched_term":null,"reason":"Completed work supports this requirement."},
  "R002": {"decision":"not_found","evidence_ids":[],"matched_term":null,"reason":"No candidate assertion supports this requirement."}
}
```

`create_model` builds a strict schema whose top-level **required properties**
are exactly the requirements in the current batch. Extra properties fail
validation. Each property holds only a status, citations, optional exact
source term, and explanation. The model does not get to copy or invent an ID
inside the row. The schema enforces completeness before `_map_response`
performs existing evidence, tone, and citation checks. OpenRouter's content
parser also rejects duplicate JSON properties before Pydantic validation.

The same contract applies to the first grouped call and the single permitted
grouped correction; it does **not** add a separate per-criterion verifier.
Earlier mocked adapters returning the legacy list are accepted by the test
compatibility path only; actual OpenRouter/Ollama adapters receive the new
dynamic schema and must satisfy it.

## API cost and reliability

- Normal successful requests: **unchanged** from V4.8.7. The 18 frozen
  requirements still form at most seven-item groups under the default 2,048
  completion-token limit, typically **3 grouped assessment calls per CV**.
- Source/citation errors: at most one grouped correction per affected batch.
- Model/schema/transport failures can still consume existing bounded retries
  (default `llm_retries=2`, so at most three attempts per logical request).
- Actual cloud attempts and reported tokens are shown under **04 Technical
  details → V4.8 request budget**. They are not identical to logical calls.
- No hardcoded score, fixed candidate, domain-specific dictionary, or extra
  retrieval/embedding pass was introduced.

## Verification and limitations

Offline tests assert missing/extra IDs fail schema validation, duplicate JSON
keys fail safely, and the real OpenRouter response parser accepts the correct
shape. A five-candidate, 18-criterion synthetic batch test verifies all 90
decisions survive grouping, all five candidates receive ranks, and there are
15 logical assessment calls with no corrections. Another test forces an
invalid **last** criterion and confirms one single-ID grouped correction
recovers it without losing other rows.

These tests validate the structural contract, **not Gemini's evidence
reasoning**. The user's next real Cloud demo rerun is required before we can
claim that live 5/5 completion or candidate ordering has improved. Scores
must still be checked for genuine Found, Transferable, Not Found accuracy.

### Windows verification

```powershell
.\run_runtime_check.cmd
.\run_tests.cmd
.\.venv\Scripts\python.exe doctor.py --live --provider openrouter
.\run_ui.cmd
```

After the runtime check confirms V4.8.8 / protocol version 6, rerun the five
fictional CVs; previous Streamlit session results will not recompute on their
own. Record **CVs fully assessed**, candidates' ranks, unresolved IDs, logical
calls, and actual API attempts; do not redistribute private CV texts or API
keys.
