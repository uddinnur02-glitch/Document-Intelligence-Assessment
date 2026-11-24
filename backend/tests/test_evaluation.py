import json
from pathlib import Path
from app.evaluate import run_evaluation


def test_evaluation_reports_actual_metrics(tmp_path):
    sample = tmp_path / 'invoice.csv'
    sample.write_text('Invoice No,TEST-01\nSupplier,Test Seller\nTotal,25.00\n', encoding='utf-8')
    broken = tmp_path / 'broken.pdf'
    broken.write_text('not a pdf', encoding='utf-8')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'cases': [
        {'path': 'invoice.csv', 'expected_fields': {'invoice_number': 'TEST-01', 'total': '25.00', 'tax': None}},
        {'path': 'broken.pdf', 'expect_failure': True}
    ]}), encoding='utf-8')
    result = run_evaluation(manifest, tmp_path / 'results')
    metrics = result['metrics']
    assert metrics['total_cases'] == 2
    assert metrics['processed_cases'] == 1
    assert metrics['expected_outcome_rate'] == 1
    assert metrics['field_exact_match_accuracy'] == 1
    assert metrics['mean_elapsed_seconds'] >= 0
    assert (tmp_path/'results'/'evaluation.md').is_file()
    assert (tmp_path/'results'/'evaluation.json').is_file()


def test_evaluation_counts_incorrect_fields(tmp_path):
    (tmp_path/'x.csv').write_text('Invoice No,YES-01\n', encoding='utf-8')
    manifest = tmp_path/'labels.json'
    manifest.write_text(json.dumps({'cases':[
        {'path':'x.csv','expected_fields':{'invoice_number':'WRONG-99'}}
    ]}), encoding='utf-8')
    assert run_evaluation(manifest, tmp_path/'out')['metrics']['field_exact_match_accuracy']==0


def test_evaluation_rejects_path_traversal(tmp_path):
    import pytest
    manifest=tmp_path/'labels.json'
    manifest.write_text(json.dumps({'cases':[{'path':'../secret.csv'}]}),encoding='utf-8')
    with pytest.raises(ValueError,match='safe relative path'):
        run_evaluation(manifest,tmp_path/'out')


def test_evaluation_rejects_empty_manifest(tmp_path):
    import pytest
    manifest=tmp_path/'labels.json'
    manifest.write_text(json.dumps({'cases':[]}),encoding='utf-8')
    with pytest.raises(ValueError,match='non-empty'):
        run_evaluation(manifest,tmp_path/'out')
