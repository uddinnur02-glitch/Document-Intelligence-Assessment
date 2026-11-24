from app.benchmark_e2e import summarize, render_report


def test_summarize_counts_complete_failed_and_timeouts():
    cases = [
        {'status':'completed','result_available':True,'total_seconds':2.0},
        {'status':'completed','result_available':False,'total_seconds':3.0},
        {'status':'failed','total_seconds':4.0},
        {'status':'timed_out','total_seconds':5.0},
    ]
    summary = summarize(cases)
    assert summary['completed_with_result'] == 1
    assert summary['failed'] == 1
    assert summary['timed_out'] == 1
    assert summary['successful_completion_rate'] == 0.25
    assert summary['mean_total_seconds'] == 3.5


def test_empty_summarize_does_not_divide_by_zero():
    data = summarize([])
    assert data['total_cases'] == 0
    assert data['successful_completion_rate'] is None


def test_report_discloses_limits():
    case = {'case':1,'document_id':'test-id','status':'completed','upload_seconds':0.1,
            'enqueue_seconds':0.2,'queue_to_terminal_seconds':0.3,'total_seconds':0.6,
            'result_available':True,'history_events':['queued','processing','completed'],'error':None}
    doc = {'generated_utc':'2026-11-24T00:00:00Z','summary':summarize([case]),'cases':[case]}
    report = render_report(doc)
    assert 'not a concurrency or capacity test' in report
    assert 'test-id' in report
    assert 'queued, processing, completed' in report
