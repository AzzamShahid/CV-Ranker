# Applied AI / ML Engineer — CV Ranker benchmark pack

All resumes, employers, identities, and performance figures are **fictional synthetic test data**. Do not present them as genuine applicants.

## Scope
- Updated role JD: original skill lists plus an explicit 3+ years relevant professional-experience condition.
- 12 resumes in DOCX, PDF, and original-text TXT form.
- The top three profiles are dense two-page resumes, verified for page fill.
- Scenarios: exact direct matches, transferable framework/orchestration functions, partial model experience, domain-mismatched years, below-3-year tenure, learning-only language, negative claims and copied JD text.
- Each PDF and DOCX is a distinct layout/parsing challenge; TXT is a control input for easier debugging.

## Suggested testing order
1. Run the JD TXT and the 12 TXT resumes (or a 5-6 candidate subset to control LLM costs).
2. Run the matching PDF and DOCX files to detect extraction-induced changes.
3. Compare `candidate_scenarios.csv` and original quoted text, not only the model-generated scores.
4. Test the 3-year threshold: unrelated work, academic work and simultaneous jobs must not substitute for relevant professional tenure.
5. Test the TensorFlow OR PyTorch logic: one of them is sufficient; both should not be required.
6. Test functional transferability: Haystack/DSPy or custom orchestration may demonstrate chain-like work, but not direct LangChain usage.
7. Negation, learning-only text, and copied JD criteria should not earn demonstrated-experience credit.

## Interpreting result labels
- 'direct' means the source claims the requested capability, not that an external verifier independently authenticated the person's skill.
- 'transferable' is a model-proposed functional relationship and should stay separate from the original score until reviewed.
- 'not evidenced' should not be interpreted as definitive inability; it means no supporting statements were located/accepted in the source.
- All synthetic evaluation outcomes require human review; no fixed expected score is supplied.

## Privacy
The `example.com` email addresses are placeholders; these are not real resumes. Sending any real CV to OpenRouter should follow your organization's privacy policies.
