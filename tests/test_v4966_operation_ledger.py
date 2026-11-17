"""At-most-one local operation dispatch claims (mocked/fixture-only)."""
from __future__ import annotations
import hashlib, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

from cv_ranker.operation_ledger import LocalOperationLedger


def test_claim_one_only_across_concurrent_independent_connections(tmp_path):
    file=tmp_path/'semantics.sqlite'
    key=hashlib.sha256(b'fictional review').hexdigest()
    def worker(_):
        with LocalOperationLedger(file) as ledger:
            return ledger.claim_many([key])
    with ThreadPoolExecutor(max_workers=8) as executor:
        observed=list(executor.map(worker,range(8)))
    assert sum(observed)==1
    with LocalOperationLedger(file) as ledger:
        assert ledger.state(key)=='claimed_unknown_delivery'
        assert not ledger.claim_many([key])
        ledger.finish_many([key],'provider_unknown_delivery')
        assert ledger.state(key)=='provider_unknown_delivery'
        assert not ledger.claim_many([key])


def test_claim_atomic_all_or_none_and_independent_other_signatures(tmp_path):
    path=tmp_path/'claims.sqlite'
    a=hashlib.sha256(b'a').hexdigest();b=hashlib.sha256(b'b').hexdigest();c=hashlib.sha256(b'c').hexdigest()
    with LocalOperationLedger(path) as x:
        assert x.claim_many([a,b])
        assert not x.claim_many([b,c])
        assert x.state(c) is None
        assert x.claim_many([c])
        x.finish_many([a,b],'validated_result')
        assert x.state(a)=='validated_result'
        assert x.state(c)=='claimed_unknown_delivery'


def test_claim_durable_across_os_process_restart(tmp_path):
    import json
    path=tmp_path/'claims.sqlite';key=hashlib.sha256(b'cross process').hexdigest()
    code=('import sys;from cv_ranker.operation_ledger import LocalOperationLedger;'
          'x=LocalOperationLedger(sys.argv[1]);'
          'print("CLAIMED" if x.claim_many([sys.argv[2]]) else "ALREADY");x.close()')
    env={**os.environ,'PYTHONPATH':os.pathsep.join(sys.path)}
    one=subprocess.run([sys.executable,'-c',code,str(path),key],cwd=str(tmp_path),
                       env=env,capture_output=True,text=True,check=True)
    two=subprocess.run([sys.executable,'-c',code,str(path),key],cwd=str(tmp_path),
                       env=env,capture_output=True,text=True,check=True)
    assert one.stdout.strip()=='CLAIMED' and two.stdout.strip()=='ALREADY'
