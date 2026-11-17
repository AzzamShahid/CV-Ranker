"""Negative differential tests: matching raw subprocess exits is not proof."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from scripts import verify_differential_v4966 as verifier

ROOT = Path(__file__).resolve().parents[1]
ORACLE = json.loads((ROOT/'verification/differential_expectations_v4967.json').read_text())


def test_same_tree_and_symlink_alias_rejected_before_running_any_probe(tmp_path):
    real=ROOT.resolve()
    with pytest.raises(verifier.DifferentialFailure,match='Same source tree'):
        verifier.verify_pair(real,real,pair='v52_to_v53',
                             candidate_manifest_sha256=verifier.digest(real/'cv_ranker/build_manifest.json'),
                             probe=real/'verification/differential_probe_v4966.py',oracle=ORACLE)
    alias=tmp_path/'link';alias.symlink_to(real,target_is_directory=True)
    with pytest.raises(verifier.DifferentialFailure,match='Same source tree'):
        verifier.verify_pair(real,alias,pair='v52_to_v53',
                             candidate_manifest_sha256=verifier.digest(real/'cv_ranker/build_manifest.json'),
                             probe=real/'verification/differential_probe_v4966.py',oracle=ORACLE)


def test_copied_identical_build_cannot_pass_for_different_release(tmp_path):
    # Different path alone does not prove different source content.
    a=tmp_path/'one';b=tmp_path/'two'
    a.mkdir();b.mkdir()
    (a/'cv_ranker').mkdir();(b/'cv_ranker').mkdir()
    original=(ROOT/'cv_ranker/build_manifest.json').read_bytes()
    (a/'cv_ranker/build_manifest.json').write_bytes(original)
    (b/'cv_ranker/build_manifest.json').write_bytes(original)
    with pytest.raises(verifier.DifferentialFailure):
        verifier.verify_pair(a,b,pair='v52_to_v53',
            candidate_manifest_sha256=hashlib.sha256(original).hexdigest(),
            probe=ROOT/'verification/differential_probe_v4966.py',oracle=ORACLE)


def test_reversed_pair_and_wrong_baseline_identity_rejected(tmp_path):
    # Any successor checkout cannot impersonate the trusted v52 baseline,
    # the baseline, regardless of where the baseline would be extracted.
    other=tmp_path/'other'
    other.mkdir()
    with pytest.raises(verifier.DifferentialFailure,match='Manifest identity'):
        verifier.verify_pair(ROOT,other,pair='v52_to_v53',
            candidate_manifest_sha256=verifier.V52_MANIFEST,
            probe=ROOT/'verification/differential_probe_v4966.py',oracle=ORACLE)


def _valid_data(expected, root, manifest, build, version):
    return {'exit':0,'data':{
        'build':build,'protocol':version,
        'loaded_module':str(root/'cv_ranker/weighted_scoring.py'),
        'module_sha256':manifest['files']['cv_ranker/weighted_scoring.py'],
        'probes':copy.deepcopy(expected)}}


def test_missing_probe_and_mutated_score_fail_independent_oracle():
    m=verifier.load_manifest(ROOT,verifier.digest(ROOT/'cv_ranker/build_manifest.json'))
    expected=ORACLE['v52_to_v53']['candidate']
    valid=_valid_data(expected,ROOT,m,m['build'],m['protocol'])
    verifier.validate_probe(ROOT,m,valid,m['build'],m['protocol'],expected)
    missing=copy.deepcopy(valid);missing['data']['probes'].pop('RECENT-003')
    with pytest.raises(verifier.DifferentialFailure,match='Missing'):
        verifier.validate_probe(ROOT,m,missing,m['build'],m['protocol'],expected)
    changed=copy.deepcopy(valid)
    changed['data']['probes']['RECENT-001']['main_floor']=50.0
    with pytest.raises(verifier.DifferentialFailure,match='oracle disagrees'):
        verifier.validate_probe(ROOT,m,changed,m['build'],m['protocol'],expected)


def test_wrong_import_root_and_wrong_child_identity_fail():
    m=verifier.load_manifest(ROOT,verifier.digest(ROOT/'cv_ranker/build_manifest.json'))
    oracle=ORACLE['v52_to_v53']['candidate']
    valid=_valid_data(oracle,ROOT,m,m['build'],m['protocol'])
    valid['data']['loaded_module']='/tmp/evil/cv_ranker/weighted_scoring.py'
    with pytest.raises(verifier.DifferentialFailure,match='different source'):
        verifier.validate_probe(ROOT,m,valid,m['build'],m['protocol'],oracle)
    valid['data']['loaded_module']=str(ROOT/'cv_ranker/weighted_scoring.py')
    valid['data']['build']='invented-release'
    with pytest.raises(verifier.DifferentialFailure,match='identity'):
        verifier.validate_probe(ROOT,m,valid,m['build'],m['protocol'],oracle)


def test_child_invalid_json_crash_and_timeout_are_not_success(tmp_path):
    bad=tmp_path/'bad.py';bad.write_text("print('not json')")
    failed=verifier.run_tree(ROOT,bad)
    assert failed['exit']==0 and failed['error']=='invalid_json_output'
    bad.write_text('raise RuntimeError("intentional test fault")')
    crashed=verifier.run_tree(ROOT,bad)
    assert crashed['exit']!=0 and crashed['error']=='child_nonzero_exit'
    bad.write_text('import time;time.sleep(4)')
    expired=verifier.run_tree(ROOT,bad,timeout_seconds=1)
    assert expired['exit'] is None and expired['error']=='probe_timeout'
    m=verifier.load_manifest(ROOT,verifier.digest(ROOT/'cv_ranker/build_manifest.json'))
    for result in (failed,crashed,expired):
        with pytest.raises(verifier.DifferentialFailure):
            verifier.validate_probe(ROOT,m,result,m['build'],m['protocol'],
                                    ORACLE['v52_to_v53']['candidate'])


def test_strict_manifest_rejects_unhashed_python_and_wrong_digest(tmp_path):
    # Mutating a copied source without updating signed input identity fails.
    with pytest.raises(verifier.DifferentialFailure,match='Manifest identity'):
        verifier.load_manifest(ROOT,'0'*64)
    sandbox=tmp_path/'candidate';(sandbox/'cv_ranker').mkdir(parents=True)
    p=sandbox/'cv_ranker/build_manifest.json'
    p.write_bytes((ROOT/'cv_ranker/build_manifest.json').read_bytes())
    with pytest.raises(verifier.DifferentialFailure):
        verifier.load_manifest(sandbox,None)
