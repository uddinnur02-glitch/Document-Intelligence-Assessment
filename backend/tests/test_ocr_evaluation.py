from app.evaluate_ocr import normalize,edit_distance,ocr_text,evaluate
import json

def test_distance():
    assert edit_distance('cat','cut')==1
    assert edit_distance('','test')==4
    assert edit_distance('a b'.split(),'a c'.split())==1

def test_normalize():
    assert normalize(' A\n B ')=='a b'

def test_ocr_page_extraction():
    assert ocr_text({'pages':[{'text':'one'},{'text':'two'}]})=='one\ntwo'

def test_evaluation_safe_path(tmp_path):
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'cases':[{'path':'../escape.png'}]}))
    try: evaluate(manifest,tmp_path/'out')
    except ValueError as err: assert 'Unsafe path' in str(err)
    else: raise AssertionError('Unsafe path accepted')

def test_corrupt_file_expected_failure(tmp_path):
    (tmp_path/'broken.png').write_bytes(b'broken')
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'cases':[{'path':'broken.png','expect_failure':True}]}))
    report=evaluate(manifest,tmp_path/'output')
    assert report['metrics']['expected_outcome_rate']==1
    assert report['metrics']['processed_cases']==0
    assert (tmp_path/'output/ocr_evaluation.md').is_file()
