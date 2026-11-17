#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export CVR_STRICT_SOURCE_HASHES=1
python -m cv_ranker.runtime_check
python -m pytest -q \
  tests/test_v4970_supervisor_three_verdict_e2e.py \
  tests/test_three_verdict_transition.py \
  tests/test_v4967_operation_subset.py \
  tests/test_v4968_prompt_first_contracts.py \
  tests/test_v4966_current_defects.py \
  tests/test_v4917_frozen_skill_scope.py \
  tests/test_v4965_independent_compound_review.py \
  tests/test_phase7g_v47_supervisor_clarity.py
