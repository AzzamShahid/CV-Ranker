import numpy as np
import pytest
from dataclasses import dataclass
from cv_ranker.semantic import EvidenceSegment, CapabilityQuery, SQLiteVectorCache, ShadowRetriever, EmbeddingError
from cv_ranker.semantic.core import literal_phrase_present
from cv_ranker.semantic.embedding import normalize, OllamaEmbeddingGemma
from cv_ranker.semantic.adapters import from_resume_segments


class FakeEncoder:
    fingerprint = 'fake:v1:query-doc-test'
    def __init__(self):
        self.document_calls = 0
        self.query_calls = 0
    def embed_documents(self, texts):
        self.document_calls += 1
        return np.array([[1.0, 0.0] if 'endpoint' in x.lower() else [0.0, 1.0] for x in texts],dtype=np.float32)
    def embed_queries(self, texts):
        self.query_calls += 1
        return np.array([[1.0, 0.0] if 'endpoint' in x.lower() else [0.0, 1.0] for x in texts],dtype=np.float32)


def src(segment_id, text, admissible=True, candidate_id='A'):
    return EvidenceSegment(candidate_id=candidate_id, segment_id=segment_id, text=text, admissible=admissible)


def query(text='API endpoint development', req='R001', cap='R001-C01'):
    return CapabilityQuery(requirement_id=req, capability_id=cap, text=text)


def test_boundary_safety():
    bad = [('Java','JavaScript'),('SQL','NoSQL'),('C','Communication'),('Go','Good'),('C','C++'),('C','C#')]
    for needle, haystack in bad:
        assert not literal_phrase_present(needle, haystack), (needle, haystack)
    for needle, text in [('SQL', 'Worked with SQL.'), ('Go', 'I used Go for services'), ('C++', 'Developed C++ systems')]:
        assert literal_phrase_present(needle, text), (needle, text)


def test_no_admission_no_results(tmp_path):
    e=FakeEncoder()
    with SQLiteVectorCache(tmp_path/'x.db') as cache:
        hits=ShadowRetriever(e,cache).retrieve('A',[src('S1','endpoint',False)], [query()])
    assert hits==[]
    assert e.document_calls==0 and e.query_calls==0


def test_foreign_candidate_never_retrieved(tmp_path):
    e=FakeEncoder()
    with SQLiteVectorCache(tmp_path/'x.db') as cache:
        hits=ShadowRetriever(e,cache,top_k=5).retrieve('A',[
            src('S001','Endpoint implementation',candidate_id='B'),
            src('S002','CSV financial reporting',candidate_id='A')], [query()])
    assert [h.source.segment_id for h in hits]==['S002']


def test_exact_phrase_hit_preserved_outside_topk(tmp_path):
    e=FakeEncoder()
    with SQLiteVectorCache(tmp_path/'x.db') as cache:
        hits=ShadowRetriever(e,cache,top_k=1).retrieve('A',[
            src('S001','Built endpoint routes'),src('S002','Proven API endpoint development')],[query()])
    assert {h.source.segment_id for h in hits}=={'S001','S002'}
    assert next(h for h in hits if h.source.segment_id=='S002').lexical_exact


def test_read_only_does_not_evaluate_negation(tmp_path):
    e=FakeEncoder()
    with SQLiteVectorCache(tmp_path/'x.db') as cache:
        hits=ShadowRetriever(e,cache,top_k=3).retrieve('A',[
            src('S001','I never developed API endpoints'),
            src('S002','Currently learning database integration')],
            [query('API endpoints'),query('database integration', cap='R001-C02')])
    assert len(hits)==2
    assert all(not hasattr(h, 'matched') and not hasattr(h, 'status') for h in hits)


def test_deduplicates_source_ids_across_queries(tmp_path):
    e=FakeEncoder()
    with SQLiteVectorCache(tmp_path/'x.db') as cache:
        hits=ShadowRetriever(e,cache).retrieve('A',[src('S001','Built API endpoints and database integration')],
            [query('endpoint development'),query('database integration',cap='R001-C02')])
    assert len(hits)==1
    assert hits[0].capability_ids == ('R001-C01','R001-C02')


def test_vector_cache_reuse(tmp_path):
    encoder=FakeEncoder()
    with SQLiteVectorCache(tmp_path/'cache.db') as cache:
        r=ShadowRetriever(encoder,cache)
        for i in range(3):
            r.retrieve('A',[src('S001','Built API endpoints')],[query('endpoint development')])
    assert encoder.document_calls==1
    assert encoder.query_calls==1


def test_cache_invalidation_on_model_fingerprint(tmp_path):
    e=FakeEncoder()
    with SQLiteVectorCache(tmp_path/'cache.db') as cache:
        r=ShadowRetriever(e,cache)
        r.retrieve('A',[src('S001','Built API endpoints')],[query('endpoint development')])
        e.fingerprint='fake:v2:different-model'
        r.retrieve('A',[src('S001','Built API endpoints')],[query('endpoint development')])
    assert e.document_calls==2 and e.query_calls==2


def test_cache_storage_is_not_original_cv_text(tmp_path):
    with SQLiteVectorCache(tmp_path/'cache.db') as cache:
        key=cache.key('m','document','PRIVATE CV CONTENT')
        cache.put(key,np.array([3,4],dtype=np.float32))
        assert np.allclose(cache.get(key), [0.6,0.8])
    assert b'PRIVATE CV CONTENT' not in (tmp_path/'cache.db').read_bytes()


def test_nan_zero_and_shape_guard():
    for arr in [[[0,0]], [[np.nan,1]], [[np.inf,0]], [[1,0],[0,1]]]:
        with pytest.raises(EmbeddingError):
            normalize(arr,1)


def test_dimension_mismatch(tmp_path):
    class BadEncoder(FakeEncoder):
        def embed_queries(self,texts):
            return np.array([[1,0,0] for _ in texts], dtype=np.float32)
    e=BadEncoder()
    with SQLiteVectorCache(tmp_path/'x.db') as cache:
        with pytest.raises(EmbeddingError,match='dimension mismatch'):
            ShadowRetriever(e,cache).retrieve('A',[src('S1','endpoint')],[query()])


def test_duplicate_source_ids_rejected(tmp_path):
    with SQLiteVectorCache(tmp_path/'x.db') as cache:
        with pytest.raises(ValueError,match='Duplicate source'):
            ShadowRetriever(FakeEncoder(),cache).retrieve('A', [src('S1','endpoint'),src('S1','endpoint')], [query()])


def test_duplicate_capability_ids_rejected(tmp_path):
    with SQLiteVectorCache(tmp_path/'x.db') as cache:
        with pytest.raises(ValueError,match='Duplicate capability'):
            ShadowRetriever(FakeEncoder(),cache).retrieve('A', [src('S1','endpoint')], [query(),query('database integration')])


def test_prefix_and_ollama_contract():
    seen=[]
    class FakeOllama(OllamaEmbeddingGemma):
        def _request(self, route, body):
            seen.append((route,body))
            return {'embeddings': [[3.0,4.0] for _ in body['input']]}
    client=FakeOllama(model_digest='fake:sha')
    a=client.embed_queries(['API work'])
    b=client.embed_documents(['Built routes'])
    assert seen[0][1]['input']==['task: search result | query: API work']
    assert seen[1][1]['input']==['title: none | text: Built routes']
    assert a.shape==b.shape==(1,2)
    assert np.allclose(a[0], [0.6,0.8])
    assert 'truncate' in seen[0][1] and seen[0][1]['truncate'] is False


def test_explicit_admissible_ids_adapter():
    @dataclass
    class S:
        segment_id:str
        text:str
        section:str='experience'
    segments=[S('S001','Built endpoints'),S('S002','Copied JD description')]
    adapted=from_resume_segments('A',segments,{'S001'})
    assert adapted[0].admissible is True
    assert adapted[1].admissible is False
    with pytest.raises(TypeError):
        from_resume_segments('A',segments,None)


def test_only_valid_cache_roles(tmp_path):
    with pytest.raises(ValueError):
        SQLiteVectorCache.key('digest','invalid','text')


def test_cannot_create_candidate_without_identity():
    with pytest.raises(ValueError):
        src('','good')
    with pytest.raises(ValueError):
        CapabilityQuery('R001','','hello')
