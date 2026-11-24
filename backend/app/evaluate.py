"""Repeatable, offline evaluation on a labeled dataset. No LLM/Redis/DB required.

Usage: python -m app.evaluate --manifest evaluation/manifest.json --output evaluation/results
Relative document paths are interpreted relative to the manifest's directory.
"""
import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from .processing import extract_file
from .invoices import rule_extract, FIELDS


def _safe_mean(values):
    return round(statistics.mean(values), 6) if values else None


def run_evaluation(manifest_path, output_dir):
    manifest_path = Path(manifest_path).resolve()
    output_dir = Path(output_dir).resolve()
    config = json.loads(manifest_path.read_text(encoding='utf-8'))
    cases = config.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('Manifest must have a non-empty cases array')
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    labeled = 0
    correct = 0
    predicted = 0
    precision_correct = 0
    all_times = []
    for index, case in enumerate(cases):
        rel = Path(case['path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError(f'Case {index}: use a safe relative path')
        file_path = (manifest_path.parent / rel).resolve()
        if not file_path.is_relative_to(manifest_path.parent):
            raise ValueError(f'Case {index}: file escapes manifest directory')
        expected_failure = bool(case.get('expect_failure', False))
        gold = case.get('expected_fields', {})
        if not isinstance(gold, dict) or any(k not in FIELDS for k in gold):
            raise ValueError(f'Case {index}: unknown or invalid expected_fields')
        started = time.perf_counter()
        extracted = None
        invoice = None
        error = None
        try:
            extracted = extract_file(str(file_path), file_path.name)
            invoice = rule_extract(extracted)
        except Exception as exc:
            error = f'{type(exc).__name__}: {str(exc)[:250]}'
        elapsed = time.perf_counter() - started
        all_times.append(elapsed)
        successful = error is None
        field_checks = {}
        for key, truth in gold.items():
            # A null label means the field should be absent. It is NOT excluded from scoring.
            found = invoice['fields'].get(key) if invoice else None
            matches = str(found or '').casefold().strip() == str(truth or '').casefold().strip()
            field_checks[key] = {'expected': truth, 'predicted': found, 'correct': matches}
            labeled += 1
            correct += int(matches)
            if found is not None:
                predicted += 1
                precision_correct += int(matches and truth is not None)
        # Failures are expected only for explicitly bad documents.
        rows.append({
            'case': case.get('id', rel.name), 'file': str(rel), 'type': rel.suffix.lower(),
            'expected_failure': expected_failure, 'processed': successful,
            'expectation_met': successful != expected_failure,
            'elapsed_seconds': round(elapsed, 6),
            'page_count': extracted.get('page_count') if extracted else None,
            'sheet_count': extracted.get('sheet_count') if extracted else None,
            'extracted_chars': extracted.get('extracted_chars') if extracted else None,
            'truncated': extracted.get('truncated') if extracted else None,
            'line_item_count': len(invoice['line_items']) if invoice else None,
            'fields': field_checks, 'error': error
        })
    total = len(rows)
    processed = sum(int(r['processed']) for r in rows)
    met = sum(int(r['expectation_met']) for r in rows)
    metrics = {
        'total_cases': total,
        'processed_cases': processed,
        'processing_success_rate': round(processed / total, 6),
        'processing_failure_rate': round(1 - processed / total, 6),
        'expected_outcome_rate': round(met / total, 6),
        'labeled_fields': labeled,
        'field_exact_match_accuracy': round(correct / labeled, 6) if labeled else None,
        'field_precision_nonnull': round(precision_correct / predicted, 6) if predicted else None,
        'mean_elapsed_seconds': _safe_mean(all_times),
        'median_elapsed_seconds': round(statistics.median(all_times), 6),
        'max_elapsed_seconds': round(max(all_times), 6),
        'documents_per_second': round(total / sum(all_times), 6) if sum(all_times) else None,
        'truncated_successful_cases': sum(int(r['truncated']) for r in rows if r['processed']),
    }
    report = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'offline synchronous extraction + local rule-based invoice parsing (no Celery, DB, network, or semantic indexing)',
              'metrics': metrics, 'cases': rows,
              'cautions': [
                  'These measurements are only valid for the labeled manifest on the machine that ran the evaluation.',
                  'Field exact-match scores are computed over explicitly labeled fields, including labeled nulls.',
                  'Timing excludes upload, queue delay, database persistence, and embedding generation.',
                  'Synthetic examples cannot establish real-world invoice accuracy.',
                  'A completed job may still contain truncated text; inspect truncated_successful_cases.',
              ]}
    (output_dir/'evaluation.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    def fmt(value):
        return 'not measured' if value is None else str(value)
    md = [
        '# Document Intelligence — Measured Evaluation', '',
        f"Generated (UTC): {report['generated_at_utc']}", '',
        f"Scope: {report['scope']}", '',
        '| Metric | Measured value |', '|---|---:|',
    ]
    for name, value in metrics.items():
        md.append(f'| {name.replace("_", " ")} | {fmt(value)} |')
    md += ['', '## Per-file results', '', '| Case | Processed | Expected outcome met | Seconds | Truncated | Error |', '|---|---|---|---:|---|---|']
    for row in rows:
        md.append(f"| {row['case']} | {row['processed']} | {row['expectation_met']} | {row['elapsed_seconds']} | {row['truncated']} | {(row['error'] or '—').replace('|','/')} |")
    md += ['', '## Limitations', ''] + [f'- {c}' for c in report['cautions']]
    (output_dir/'evaluation.md').write_text('\n'.join(md)+'\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description='Evaluate local processing on labeled documents')
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = run_evaluation(args.manifest, args.output)
    print(json.dumps(report['metrics'], indent=2))
    print(f"Reports saved to {Path(args.output).resolve()}")


if __name__ == '__main__':
    main()
