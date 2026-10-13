import copy
import pytest
from evaluation.repeatability_probe import summarize_runs


def report(size, statuses, *, accuracy=None, model='qwen2.5:3b', hash_value='fixed'):
    labels = [('s', 'R001', 'NLP', 'matched', 'semantic_abbreviation'),
              ('s', 'R002', 'Other Tool', 'not_matched', 'related_different')]
    rows = []
    for (scenario_id, rid, name, expected, category), status in zip(labels, statuses):
        rows.append({'scenario_id': scenario_id, 'requirement_id': rid, 'requirement_name': name,
                     'category': category, 'expected': expected, 'predicted': status,
                     'correct': status == expected})
    observed = sum(r['correct'] for r in rows) / len(rows)
    return {'build_id': 'b', 'assessment_protocol': 'v3', 'benchmark_data_sha256': hash_value,
            'scope': 'assessment', 'model': model, 'assessment_batch_size': size,
            'metrics': {'accuracy': observed if accuracy is None else accuracy},
            'measurement_quality': {'valid_live_llm_measurement': False},
            'raw_model_diagnostics': {'raw_status_accuracy_on_observed': 0.5}, 'rows': rows}


def test_summarizes_flips_and_false_positive_exposure():
    results = [
        (1, 20, report(20, ['not_matched', 'matched'])),
        (1, 3, report(3, ['matched', 'not_matched'])),
        (2, 20, report(20, ['matched', 'not_matched'])),
        (2, 3, report(3, ['matched', 'matched'])),
    ]
    summary = summarize_runs(results)
    assert summary['requirement_count'] == 2
    assert len(summary['paired_trials']) == 2
    assert summary['per_batch']['20']['unstable_requirement_count'] == 2
    assert summary['per_batch']['3']['unstable_requirement_count'] == 1
    assert summary['per_batch']['20']['run_details'][0]['false_positive_matches'] == 1
    assert summary['per_batch']['3']['run_details'][0]['false_positive_matches'] == 0
    assert not summary['per_batch']['3']['clean_llm_path_runs']


def test_rejects_changed_labels_and_data():
    a = report(20, ['matched', 'not_matched'])
    b = report(3, ['matched', 'not_matched'])
    b['rows'][0]['expected'] = 'not_matched'
    with pytest.raises(ValueError, match='Requirement name/label'):
        summarize_runs([(1, 20, a), (1, 3, b)])
    b = report(3, ['matched', 'not_matched'], hash_value='different')
    with pytest.raises(ValueError, match='Different build'):
        summarize_runs([(1, 20, a), (1, 3, b)])


def test_rejects_incomplete_duplicates_inconsistent_and_batch_mismatch():
    a = report(20, ['matched', 'not_matched'])
    with pytest.raises(ValueError, match='Duplicate trial'):
        summarize_runs([(1, 20, a), (1, 20, a)])
    b = copy.deepcopy(a)
    b['rows'][0]['predicted'] = 'missing_requirement'
    with pytest.raises(ValueError, match='Incomplete'):
        summarize_runs([(1, 20, b)])
    b = copy.deepcopy(a)
    b['metrics']['accuracy'] = 0.123
    with pytest.raises(ValueError, match='inconsistent'):
        summarize_runs([(1, 20, b)])
    with pytest.raises(ValueError, match='Batch-size mismatch'):
        summarize_runs([(1, 3, a)])


def test_analyze_only_command_from_saved_results(monkeypatch, tmp_path, capsys):
    import sys
    from evaluation.repeatability_probe import main
    for size in (3, 20):
        (tmp_path / f'trial_01_batch_{size}.json').write_text(
            __import__('json').dumps(report(size, ['matched', 'not_matched'])), encoding='utf-8')
    monkeypatch.setattr(sys, 'argv', ['repeatability_probe.py', '--analyze-only', '--output-dir', str(tmp_path)])
    assert main() == 0
    summary = __import__('json').loads((tmp_path / 'repeatability_summary.json').read_text())
    assert summary['per_batch']['3']['run_count'] == 1
    assert summary['per_batch']['20']['run_count'] == 1
    assert 'REPEATED BATCH-SIZE DIAGNOSTICS' in capsys.readouterr().out
