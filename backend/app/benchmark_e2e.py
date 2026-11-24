"""Measure full HTTP upload -> Celery queue -> DB result retrieval.

Run inside backend container: python -m app.benchmark_e2e --input /examples/sample_invoice.csv
Generated documents remain in the database; do not run against production data.
"""
import argparse
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

FINAL_STATUSES = {'completed', 'failed'}


def summarize(cases):
    """Summarize measured cases without presenting uncompleted runs as successes."""
    finished = [c for c in cases if c['status'] in FINAL_STATUSES]
    successful = [c for c in cases if c['status'] == 'completed' and c.get('result_available')]
    elapsed = [c['total_seconds'] for c in cases if c.get('total_seconds') is not None]
    return {
        'total_cases': len(cases),
        'completed_with_result': len(successful),
        'failed': sum(c['status'] == 'failed' for c in cases),
        'timed_out': sum(c['status'] == 'timed_out' for c in cases),
        'request_errors': sum(c['status'] == 'request_error' for c in cases),
        'successful_completion_rate': round(len(successful) / len(cases), 4) if cases else None,
        'mean_total_seconds': round(statistics.mean(elapsed), 4) if elapsed else None,
        'median_total_seconds': round(statistics.median(elapsed), 4) if elapsed else None,
        'max_total_seconds': round(max(elapsed), 4) if elapsed else None,
        'terminal_cases': len(finished),
    }


def run_case(client, file_path, api_url, poll_interval, max_seconds, number):
    record = {'case': number, 'filename': file_path.name, 'document_id': None,
              'status': 'request_error', 'upload_seconds': None, 'enqueue_seconds': None,
              'queue_to_terminal_seconds': None, 'total_seconds': None,
              'result_available': False, 'history_events': [], 'error': None}
    t0 = time.perf_counter()
    try:
        with file_path.open('rb') as handle:
            response = client.post(f'{api_url}/api/documents', files={'file': (file_path.name, handle)})
        response.raise_for_status()
        doc = response.json()
        record['document_id'] = doc['id']
        record['upload_seconds'] = round(time.perf_counter() - t0, 4)

        t1 = time.perf_counter()
        queued = client.post(f"{api_url}/api/documents/{doc['id']}/process")
        queued.raise_for_status()
        record['enqueue_seconds'] = round(time.perf_counter() - t1, 4)
        polling_start = time.perf_counter()
        deadline = polling_start + max_seconds
        status = None
        while time.perf_counter() < deadline:
            status_response = client.get(f"{api_url}/api/documents/{doc['id']}")
            status_response.raise_for_status()
            state = status_response.json()
            status = state.get('status')
            if status in FINAL_STATUSES:
                break
            time.sleep(poll_interval)
        record['queue_to_terminal_seconds'] = round(time.perf_counter() - polling_start, 4)
        record['status'] = status if status in FINAL_STATUSES else 'timed_out'
        if record['status'] == 'timed_out':
            record['error'] = f'No terminal state within {max_seconds} seconds after enqueue'
        elif record['status'] == 'failed':
            record['error'] = state.get('error_message') or 'Worker reported failure'
        else:
            result_response = client.get(f"{api_url}/api/documents/{doc['id']}/result")
            result_response.raise_for_status()
            result = result_response.json()
            record['result_available'] = result.get('status') == 'completed' and isinstance(result.get('result'), dict)
            if not record['result_available']:
                record['error'] = 'Completed status but structured document result was not retrievable'
        try:
            history = client.get(f"{api_url}/api/documents/{doc['id']}/history")
            history.raise_for_status()
            record['history_events'] = [e.get('event') for e in history.json()]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            record['history_error'] = f'{type(exc).__name__}: {str(exc)[:160]}'
    except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as exc:
        record['status'] = 'request_error'
        # Do not disclose request headers, authentication keys, or document contents.
        record['error'] = f'{type(exc).__name__}: {str(exc)[:200]}'
    finally:
        record['total_seconds'] = round(time.perf_counter() - t0, 4)
    return record


def render_report(report):
    summary = report['summary']
    lines = [
        '# Phase 10C — Measured End-to-End API Benchmark', '',
        f"Generated UTC: {report['generated_utc']}", '',
        'Scope: HTTP upload → FastAPI → Redis/Celery → PostgreSQL → HTTP status/result/history.',
        'Documents are created in the connected database and are **not** automatically deleted.',
        'This is a sequential benchmark, not a concurrency or capacity test.', '',
        '| Metric | Value |', '|---|---:|',
    ]
    for key, value in summary.items():
        lines.append(f'| {key.replace("_", " ")} | {value} |')
    lines += ['', '## Per-document evidence', '',
              '| Case | Document ID | Status | Upload s | Enqueue s | Queue-to-terminal s | Total s | Result retrieved |',
              '|---|---|---|---:|---:|---:|---:|---|']
    for c in report['cases']:
        lines.append('| ' + ' | '.join(str(v) for v in [c['case'],c['document_id'],c['status'],c['upload_seconds'],c['enqueue_seconds'],c['queue_to_terminal_seconds'],c['total_seconds'],c['result_available']]) + ' |')
    lines += ['', '## Failures and audit trails', '']
    for c in report['cases']:
        lines.append(f"- Case {c['case']}: status={c['status']}; events={', '.join(c['history_events']) or 'unavailable'}; error={c['error'] or 'none'}")
    lines += ['', '## Limitations', '',
              '- Timings include local HTTP overhead, polling interval, and any Celery/embedding initialization.',
              '- Queue-to-terminal timing includes polling delay; it is not precise task-execution timing.',
              '- Success means a completed document had a retrievable structured result, not that extracted invoice fields were accurate.',
              '- No OCR CER/WER or invoice-field ground truth is measured here; use Phase 10B separately.',
              '- Single-client sequential runs do not establish throughput under concurrent users.',
              '- Runs may create duplicate synthetic records; do not run with sensitive or production documents.',
              '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('/examples/sample_invoice.csv'))
    parser.add_argument('--output', type=Path, default=Path('/app/evaluation/e2e_results'))
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--poll-seconds', type=float, default=0.5)
    parser.add_argument('--timeout-seconds', type=float, default=180)
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error(f'File not found: {args.input}. Confirm the examples mount exists.')
    if not 1 <= args.runs <= 30:
        parser.error('--runs must be between 1 and 30')
    if not 0.1 <= args.poll_seconds <= 10 or not 5 <= args.timeout_seconds <= 1800:
        parser.error('Poll interval must be 0.1–10 seconds, timeout must be 5–1800 seconds')
    api_url = args.base_url.rstrip('/')
    headers = {'X-API-Key': os.environ['CARE_GUIDE_API_KEY']} if os.getenv('CARE_GUIDE_API_KEY') else {}
    with httpx.Client(headers=headers, timeout=60) as client:
        try:
            check = client.get(f'{api_url}/api/health')
            check.raise_for_status()
        except httpx.HTTPError as exc:
            parser.error(f'Backend health check failed: {exc}')
        cases = []
        for i in range(1, args.runs + 1):
            print(f'Running end-to-end test {i}/{args.runs}...', flush=True)
            case = run_case(client, args.input, api_url, args.poll_seconds, args.timeout_seconds, i)
            cases.append(case)
            print(f"  {case['status']}; {case['total_seconds']} s; result={case['result_available']}", flush=True)
    report = {
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'HTTP API + Celery + database (sequential)',
        'input_filename': args.input.name,
        'summary': summarize(cases),
        'cases': cases,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'e2e_evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (args.output / 'e2e_evaluation.md').write_text(render_report(report), encoding='utf-8')
    print('Report:', args.output / 'e2e_evaluation.md', flush=True)
    if report['summary']['completed_with_result'] != len(cases):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
