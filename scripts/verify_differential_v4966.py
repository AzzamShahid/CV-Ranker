"""Authenticated, oracle-checked offline CV Ranker source differential.

Version-aware: --pair v51_to_v52 or v52_to_v53. Unlike the old runner, a
successful subprocess exit alone can NEVER authorize a passing comparison.
The source oracle is independently frozen under verification/, not generated
from the candidate's measured values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


# Trusted fingerprints of original user-provided archives, independently
# verified before modification. The successor manifest is caller supplied.
V51_MANIFEST = '224d9bfb3952972fa5ec3e0829b58345398f8c279bcf924fa35d6656bfb3c068'
V52_MANIFEST = 'a193f16d8dfdc13aa0c776aa867b6ab102704a3baae262e82b90a952b3727297'
BUILD_V51 = 'phase7g-v4-9-65-source-grounded-compound-review-2026-11-13'
BUILD_V52 = 'phase7g-v4-9-66-differential-integrity-repair-2026-11-13'
BUILD_V53 = 'phase7g-v4-9-67-recovery-oracle-repair-2026-11-14'


class DifferentialFailure(ValueError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(root: Path, expected_sha: str | None) -> dict:
    path = root / 'cv_ranker' / 'build_manifest.json'
    if not path.is_file():
        raise DifferentialFailure(f'No build manifest at {root}')
    actual = digest(path)
    if expected_sha is not None and actual != expected_sha:
        raise DifferentialFailure('Manifest identity mismatch with independently supplied digest')
    try:
        manifest = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, UnicodeDecodeError) as exc:
        raise DifferentialFailure('Invalid or unreadable source manifest') from exc
    if not isinstance(manifest.get('files'), dict):
        raise DifferentialFailure('Source manifest has no files dictionary')
    # A valid manifest is not enough if executable Python files were added
    # without rebuilding it. Enforce complete coverage of all runtime and
    # verification Python files in the source checkout (not cached bytecode).
    listed = set(manifest['files'])
    discovered = {str(p.relative_to(root)) for folder in
                  ('cv_ranker','scripts','verification','evaluation','tests')
                  for p in (root/folder).rglob('*.py') if '__pycache__' not in p.parts}
    if discovered - listed:
        raise DifferentialFailure('Unhashed executable Python files exist in the source tree')
    for name, expected in manifest['files'].items():
        local = (root / name).resolve()
        if not local.is_relative_to(root.resolve()) or not local.is_file():
            raise DifferentialFailure('Manifest file outside tree or unavailable')
        if digest(local) != expected:
            raise DifferentialFailure(f'Manifest source hash mismatch: {name}')
    return {'sha256':actual,'files':manifest['files'],'build':manifest.get('build_id'),
            'protocol':manifest.get('assessment_protocol_version')}


def run_tree(root: Path, probe: Path, timeout_seconds: int = 120) -> dict:
    env = {**os.environ,'PYTHONPATH':str(root),'PYTHONDONTWRITEBYTECODE':'1'}
    try:
        completed = subprocess.run([sys.executable,str(probe)],cwd=root,env=env,
             capture_output=True,text=True,timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return {'exit':None,'error':'probe_timeout'}
    except OSError:
        return {'exit':None,'error':'probe_start_error'}
    result = {'exit':completed.returncode}
    if completed.returncode != 0:
        result['error'] = 'child_nonzero_exit'
        return result
    try:
        result['data'] = json.loads(completed.stdout)
    except ValueError:
        result['error'] = 'invalid_json_output'
    return result


def validate_probe(root: Path, manifest: dict, response: dict, expected_build: str,
                   expected_protocol: int, expected: dict) -> None:
    if response.get('exit') != 0 or 'data' not in response:
        raise DifferentialFailure('Probe crashed, timed out, or returned invalid JSON')
    data = response['data']
    if not isinstance(data, dict) or data.get('build') != expected_build \
       or data.get('protocol') != expected_protocol:
        raise DifferentialFailure('Loaded build identity is missing or incorrect')
    if manifest['build'] != expected_build or manifest['protocol'] != expected_protocol:
        raise DifferentialFailure('Package manifest build/protocol identity mismatch')
    loaded = data.get('loaded_module')
    if not isinstance(loaded, str):
        raise DifferentialFailure('Child omitted loaded module path')
    path = Path(loaded).resolve()
    required = (root/'cv_ranker'/'weighted_scoring.py').resolve()
    if path != required or data.get('module_sha256') != manifest['files']['cv_ranker/weighted_scoring.py']:
        raise DifferentialFailure('Child imported code from a different source tree or hash')
    observed = data.get('probes')
    if not isinstance(observed, dict) or set(observed) != set(expected):
        raise DifferentialFailure('Missing, extra, or unexecuted differential probes')
    if observed != expected:
        diffs = [k for k in expected if observed.get(k) != expected[k]]
        raise DifferentialFailure(f'Independent regression oracle disagrees for: {", ".join(diffs)}')


def verify_pair(baseline: Path, candidate: Path, *, pair: str,
                candidate_manifest_sha256: str | None,
                probe: Path, oracle: dict, timeout_seconds: int = 120) -> dict:
    base = baseline.resolve(); newer = candidate.resolve()
    if base == newer:
        raise DifferentialFailure('Same source tree supplied for both roles')
    if not base.is_dir() or not newer.is_dir():
        raise DifferentialFailure('Both source root directories must exist')
    pairs = {'v51_to_v52':(V51_MANIFEST,V52_MANIFEST,BUILD_V51,BUILD_V52,51,52),
             'v52_to_v53':(V52_MANIFEST,candidate_manifest_sha256,BUILD_V52,BUILD_V53,52,53)}
    if pair not in pairs:
        raise DifferentialFailure('Unsupported source-version pair')
    b_sha,c_sha,b_id,c_id,b_ver,c_ver = pairs[pair]
    if pair == 'v52_to_v53' and not c_sha:
        raise DifferentialFailure('Candidate manifest SHA-256 must be supplied independently')
    bmanifest = load_manifest(base,b_sha)
    cmanifest = load_manifest(newer,c_sha)
    if bmanifest['sha256'] == cmanifest['sha256']:
        raise DifferentialFailure('Copied identical build cannot be a repair differential')
    a = run_tree(base,probe,timeout_seconds)
    b = run_tree(newer,probe,timeout_seconds)
    if pair not in oracle:
        raise DifferentialFailure('Versioned independent oracle is missing')
    expected = oracle[pair]
    validate_probe(base,bmanifest,a,b_id,b_ver,expected['baseline'])
    validate_probe(newer,cmanifest,b,c_id,c_ver,expected['candidate'])
    return {'type':'independently_oracle_verified_source_differential',
            'pair':pair,'result':'PASS',
            'baseline_manifest_sha256':bmanifest['sha256'],
            'candidate_manifest_sha256':cmanifest['sha256'],
            'baseline':a,'candidate':b,
            'comparison':{key:{'baseline':a['data']['probes'][key],
                               'candidate':b['data']['probes'][key]}
                          for key in sorted(expected['baseline'])},
            'human_accuracy':'not_measured','provider_cost':'no_external_calls'}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--pair',choices=['v51_to_v52','v52_to_v53'],default='v52_to_v53')
    parser.add_argument('--candidate-manifest-sha256',default=None)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--timeout-seconds',type=int,default=120)
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parent.parent
    probe=root/'verification'/'differential_probe_v4966.py'
    expected=root/'verification'/'differential_expectations_v4967.json'
    try:
        oracle=json.loads(expected.read_text(encoding='utf-8'))
        result=verify_pair(args.baseline,args.candidate,pair=args.pair,
            candidate_manifest_sha256=args.candidate_manifest_sha256,
            probe=probe,oracle=oracle,timeout_seconds=args.timeout_seconds)
        code=0
    except (DifferentialFailure,ValueError,OSError,KeyError) as exc:
        result={'type':'independently_oracle_verified_source_differential',
                'pair':args.pair,'result':'FAIL','failure_type':type(exc).__name__,
                'failure_reason':str(exc)}
        code=1
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f"{result['result']}: {result.get('failure_reason','independent source oracle matched')}")
    return code


if __name__=='__main__':
    raise SystemExit(main())
