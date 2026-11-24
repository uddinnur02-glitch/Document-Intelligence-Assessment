"""Offline OCR benchmark. Character/word error and invoice-field accuracy.

No API, background worker, database or LLM. Use only consented, locally stored files.
"""
import argparse
import json
import re
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from .processing import extract_file
from .invoices import FIELDS, rule_extract


def normalize(text):
    return ' '.join(str(text or '').casefold().split())


def edit_distance(a, b):
    # O(min(len(a),len(b))) memory; suitable for short invoice text, not huge PDFs.
    if len(a)<len(b): a,b=b,a
    previous=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        current=[i]
        for j,y in enumerate(b,1):
            current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(x!=y)))
        previous=current
    return previous[-1]


def ocr_text(extracted):
    # Page-based text excludes 'Page N (ocr)' metadata inserted in extracted['text'].
    return '\n'.join(p.get('text','') for p in extracted.get('pages',[]))


def evaluate(manifest, output):
    manifest=Path(manifest).resolve(); output=Path(output).resolve()
    cases=json.loads(manifest.read_text(encoding='utf-8'))['cases']
    if not cases: raise ValueError('No cases provided')
    output.mkdir(parents=True,exist_ok=True)
    records=[]; chars_bad=chars_total=words_bad=words_total=fields_good=fields_total=0
    for ix,c in enumerate(cases):
        relative=Path(c['path'])
        target=(manifest.parent/relative).resolve()
        if relative.is_absolute() or not target.is_relative_to(manifest.parent):
            raise ValueError(f'Unsafe path at case {ix}')
        labels=c.get('expected_fields',{})
        if any(k not in FIELDS for k in labels): raise ValueError(f'Unknown expected field at {ix}')
        error=None; extracted=None; prediction=None; expected_failure=c.get('expect_failure',False)
        started=time.perf_counter()
        try:
            extracted=extract_file(str(target),target.name)
            prediction=rule_extract(extracted)['fields']
        except Exception as e:
            error=f'{type(e).__name__}: {str(e)[:200]}'
        duration=round(time.perf_counter()-started,6)
        ok=error is None
        rec={'id':c.get('id',relative.name),'file':str(relative),'processed':ok,
             'expected_outcome_met':ok!=expected_failure,'elapsed_seconds':duration,
             'error':error,'truncated':extracted.get('truncated') if extracted else None,
             'pages':extracted.get('page_count') if extracted else None,
             'expected_pages':c.get('expected_pages'),'fields':{},'cer':None,'wer':None}
        if ok and 'expected_text' in c:
            actual=normalize(ocr_text(extracted)); truth=normalize(c['expected_text'])
            a,b=edit_distance(actual,truth),len(truth)
            aw,bw=edit_distance(actual.split(),truth.split()),len(truth.split())
            chars_bad+=a; chars_total+=b; words_bad+=aw; words_total+=bw
            rec['cer']=round(a/b,6) if b else None
            rec['wer']=round(aw/bw,6) if bw else None
        if ok:
            for key,truth in labels.items():
                found=prediction.get(key)
                good=normalize(found)==normalize(truth)
                fields_good+=good; fields_total+=1
                rec['fields'][key]={'expected':truth,'predicted':found,'correct':good}
        records.append(rec)
    processed=sum(r['processed'] for r in records)
    metrics={
      'total_cases':len(records),'processed_cases':processed,
      'processing_success_rate':round(processed/len(records),6),
      'expected_outcome_rate':round(sum(r['expected_outcome_met'] for r in records)/len(records),6),
      'ocr_character_error_rate_micro':round(chars_bad/chars_total,6) if chars_total else None,
      'ocr_word_error_rate_micro':round(words_bad/words_total,6) if words_total else None,
      'invoice_field_exact_match_accuracy':round(fields_good/fields_total,6) if fields_total else None,
      'labeled_invoice_fields':fields_total,
      'mean_elapsed_seconds':round(statistics.mean(r['elapsed_seconds'] for r in records),6),
      'truncated_successful_cases':sum(r['truncated'] is True for r in records if r['processed']),
      'page_count_mismatches':sum(r['pages']!=r['expected_pages'] for r in records if r['processed'] and r['expected_pages'] is not None)}
    result={'generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'scope':'offline synthetic/consented OCR + rule-based invoice extraction (no API, Celery, DB or network)',
            'metrics':metrics,'cases':records,
            'limitations':['OCR CER/WER compare normalized text with exact sequence, so line-order differences may increase error.',
                           '2-page sample uses the first invoice as invoice-field ground truth; OCR text scoring covers both pages.',
                           'Synthetic scans do not establish real-world accuracy or generalization.',
                           'Text is bounded by per-page preview caps; truncated files must be reviewed.',
                           'No timing for upload, Celery, PostgreSQL, model load, indexing or frontend.']}
    (output/'ocr_evaluation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    lines=['# Phase 10B — Measured OCR and Invoice Evaluation','',f"Generated (UTC): {result['generated_at_utc']}",'',result['scope'],'',
           '| Metric | Measured value |','|---|---:|']
    for k,v in metrics.items(): lines.append(f'| {k.replace("_"," ")} | {v if v is not None else "not measured"} |')
    lines+=['','## Per-file evidence','','| Case | Processed | Time (s) | CER | WER | Truncated | Error |','|---|---|---:|---:|---:|---|---|']
    for r in records:
        lines.append(f"| {r['id']} | {r['processed']} | {r['elapsed_seconds']} | {r['cer']} | {r['wer']} | {r['truncated']} | {(r['error'] or '—').replace('|','/')} |")
    lines+=['','## Limitations','']+[f'- {v}' for v in result['limitations']]
    (output/'ocr_evaluation.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    report=evaluate(args.manifest,args.output)
    print(json.dumps(report['metrics'],indent=2))
    print(f'Reports written to {args.output}')
if __name__=='__main__': main()
