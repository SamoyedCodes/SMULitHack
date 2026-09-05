"""Backward compatibility and side-effect-free saved scorecards; no providers involved."""

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.config import Config
from backend.evaluation_report import EvaluationScorecard, METRICS, build_scorecard, render_report
from backend.models import ReviewIssue, Verdict
from backend.store import Store


def card_fixture():
    report = {'review_status':'provisional_pending_independent_review', 'model':'fake',
        'budget':{'ceiling_usd':'14', 'charged_usd':'0', 'unreconciled_reserved_usd':'0.082739200', 'requests':1, 'unreconciled_requests':1},
        'stopped':'Response has no trustworthy usage cost; reservation retained and campaign stopped.',
        'groups':{}, 'failures':[{'sample':f's{i:02}', 'status':'text_ready', 'error':None} for i in range(1,11)]}
    for name, count in [('development',7), ('holdout',3), ('all',10)]:
        report['groups'][name] = {**{k:{'correct':0, 'total':0, 'rate':None} for k in METRICS if k != 'high_confidence_error_rate'},
            'documents':count, 'fields_unreviewed':count*8, 'predictions_unreviewed':0, 'pairs_unassessed':0,
            'correctness_by_confidence':{band:{'correct':0, 'total':0, 'rate':None, 'unreviewed':0} for band in ('high','medium','low')}}
    entries = [{'sample_id': f's{i:02}', 'document_id':f'd{i}', 'split':'development' if i < 8 else 'holdout'} for i in range(1,11)]
    docs = [{'id':f'd{i}', 'status':'failed', 'findings':[]} for i in range(1,11)]
    run = {'documents': docs, 'model':report['model'], 'budget':report['budget'], 'stopped':report['stopped']}
    judgments = {'findings': {e['sample_id']:{} for e in entries}}
    key = {'documents':{e['sample_id']:{'facts':[]} for e in entries}}
    return report, {'documents':entries, 'answer_key_sha256':'a'*64}, run, {'2026-09-05':{}}, judgments, key


def make_card():
    return build_scorecard(*card_fixture(), 'b'*64)


def test_typed_reasons_preserve_old_records_and_reject_invented_categories(tmp_path):
    old = dict(id='old', document_ids=['d'], title='Unknown', lawyer_question='What is missing?')
    issue = ReviewIssue(**old)
    assert issue.reason_codes == []
    assert Verdict(item_id='v', status='uncertain', reason='Unknown').reason_codes == []
    with pytest.raises(ValueError):
        ReviewIssue(**old, reason_codes=['breach'])
    store = Store(tmp_path)
    store.set_setting('legacy-review', old)
    assert ReviewIssue(**Store(tmp_path).setting('legacy-review')).id == 'old'
    assert store.setting('legacy-review') == old


def test_scorecard_partial_judgments_and_error_examples_are_separate():
    args = list(card_fixture())
    report, manifest, run, portfolios, judgments, key = args
    run['documents'][0]['status'] = 'complete'
    run['documents'][0]['findings'] = [dict(id='f', field='payments', value='<script>wrong</script>', confidence='high')]
    judgments['findings']['s01']['f'] = {'correct':False, 'reason':'Wrong party and currency.'}
    key['documents']['s01']['facts'] = [{'field':'payments', 'expected':'Buyer pays SGD 50.'}]
    for group in ('development','all'):
        report['groups'][group]['correctness_by_confidence']['high'] = {'correct':1,'total':2,'rate':.5,'unreviewed':3}
    card = build_scorecard(*args, 'b'*64)
    assert card.groups['all'].metrics['high_confidence_error_rate'].rate == .5
    assert card.groups['all'].metrics['high_confidence_error_rate'].unreviewed == 3
    assert card.groups['holdout'].metrics['high_confidence_error_rate'].rate is None
    assert card.groups['development'].completed_documents == 1
    assert card.examples[0].expected == 'Buyer pays SGD 50.'
    assert card.examples[0].explanation == 'Wrong party and currency.'
    report_html = render_report(card)
    assert '<script>wrong' not in report_html and '&lt;script&gt;' in report_html
    assert 'Not measurable' in report_html and 'unknown' in report_html
    altered = card.model_dump(mode='json')
    altered['groups']['all']['metrics']['field_accuracy']['rate'] = 1
    with pytest.raises(ValueError):
        EvaluationScorecard.model_validate(altered)


def test_evaluation_routes_read_only_missing_invalid_and_snapshot_bound(tmp_path, monkeypatch):
    cfg = Config(tmp_path / 'workspace')
    cfg.evaluation_dir = tmp_path / 'campaign'
    app = create_app(cfg, start_worker=False)
    with TestClient(app) as client:
        # Filesystem/provider mutations during a GET would fail this check.
        assert client.get('/api/evaluation/scorecard').status_code == 404
        assert not cfg.evaluation_dir.exists()
        cfg.evaluation_dir.mkdir()
        path = cfg.evaluation_dir / 'scorecard.json'
        path.write_text(make_card().model_dump_json())
        before = path.read_bytes(), path.stat().st_mtime_ns
        monkeypatch.setattr(Store, 'enqueue', lambda *a, **k: pytest.fail('GET queued work'))
        monkeypatch.setattr(Store, '__init__', lambda *a, **k: pytest.fail('GET initialized storage'))
        response = client.get('/api/evaluation/scorecard')
        assert response.status_code == 200
        card = response.json()
        assert card['groups']['all']['completed_documents'] == 0
        assert card['budget']['unreconciled_reserved_usd'] == '0.082739200'
        report = client.get('/api/evaluation/report', params={'run_sha256':card['run_sha256'], 'generated_at':card['generated_at']})
        assert report.status_code == 200 and 'attachment' in report.headers['content-disposition']
        assert 'No reviewed semantic mistakes' in report.text
        assert client.get('/api/evaluation/report?run_sha256=changed').status_code == 409
        assert client.get('/api/evaluation/report?generated_at=changed').status_code == 409
        assert (path.read_bytes(), path.stat().st_mtime_ns) == before
        path.write_text('{private-corrupt-content')
        bad = client.get('/api/evaluation/scorecard')
        assert bad.status_code == 500 and 'private-corrupt' not in bad.text
        path.unlink()
        outside = tmp_path / 'elsewhere.json'; outside.write_text(make_card().model_dump_json())
        path.symlink_to(outside)
        assert client.get('/api/evaluation/scorecard').status_code == 500


def test_extraction_reasons_follow_evidence_and_support_without_changing_gates():
    from backend.evidence import apply_extraction
    from backend.models import Extraction, SupportReview
    from test_extraction import _parties_draft, document, sample_pages
    draft = _parties_draft()
    uncertain = Verdict(item_id=draft.id, status='uncertain', reason='Two readings remain.',
                        reason_codes=['ambiguous_terms'], missing_context=['Schedule 2.'])
    doc = apply_extraction(document(), Extraction(title='Test', findings=[draft]), SupportReview(verdicts=[uncertain]), sample_pages())
    assert doc.findings[0].value is None and doc.findings[0].provenance == 'unresolved'
    assert doc.issues[0].reason_codes == ['missing_context', 'ambiguous_terms']
    draft.citations[0].quote = 'Invented text'
    rejected = apply_extraction(document(), Extraction(title='Test', findings=[draft]), SupportReview(verdicts=[uncertain]), sample_pages())
    assert 'unsupported_evidence' in rejected.issues[0].reason_codes
    assert not rejected.findings[0].evidence and rejected.findings[0].value is None
    assert any(i.reason_codes == ['not_established'] for i in rejected.issues)
