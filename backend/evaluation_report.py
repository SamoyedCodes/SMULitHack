"""Saved evaluation scorecards. Loading and rendering never initialize a campaign."""
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .models import Record

METRICS = {
    'field_accuracy': 'Field accuracy', 'answerable_coverage': 'Answerable coverage',
    'prediction_correctness': 'Prediction correctness', 'citation_validity': 'Citation validity',
    'deadline_accuracy': 'Deadline accuracy', 'deadline_recall': 'Deadline recall',
    'candidate_recall': 'Candidate recall', 'retained_for_review_recall': 'Retained for review recall',
    'conflict_precision': 'Conflict precision', 'conflict_recall': 'Conflict recall',
    'high_confidence_error_rate': 'High-confidence error rate',
}


class EvaluationRatio(Record):
    correct: int = Field(ge=0)
    total: int = Field(ge=0)
    rate: float | None = Field(ge=0, le=1)
    unreviewed: int = Field(default=0, ge=0)

    @model_validator(mode='after')
    def consistent(self):
        expected = self.correct / self.total if self.total else None
        if self.correct > self.total or (expected is None) != (self.rate is None):
            raise ValueError('Inconsistent metric counts.')
        if expected is not None and abs(expected - self.rate) > 1e-9:
            raise ValueError('Inconsistent metric rate.')
        return self


class EvaluationGroup(Record):
    documents: int = Field(ge=0)
    completed_documents: int = Field(ge=0)
    fields_unreviewed: int = Field(ge=0)
    predictions_unreviewed: int = Field(ge=0)
    pairs_unassessed: int = Field(ge=0)
    metrics: dict[str, EvaluationRatio]
    confidence: dict[Literal['high', 'medium', 'low'], EvaluationRatio]

    @model_validator(mode='after')
    def complete(self):
        if set(self.metrics) != set(METRICS) or set(self.confidence) != {'high', 'medium', 'low'} or self.completed_documents > self.documents:
            raise ValueError('Incomplete scorecard group.')
        return self


class EvaluationFailure(Record):
    sample: str
    split: Literal['development', 'holdout']
    status: str
    message: str


class EvaluationExample(Record):
    sample: str
    split: Literal['development', 'holdout']
    finding_id: str
    confidence: Literal['high', 'medium', 'low']
    expected: str
    observed: str
    explanation: str


class EvaluationBudgetSummary(Record):
    ceiling_usd: str = Field(pattern=r'^\d+(\.\d+)?$')
    charged_usd: str = Field(pattern=r'^\d+(\.\d+)?$')
    unreconciled_reserved_usd: str = Field(pattern=r'^\d+(\.\d+)?$')
    requests: int = Field(ge=0)
    unreconciled_requests: int = Field(ge=0)


class EvaluationScorecard(Record):
    schema_version: Literal[1] = 1
    campaign_id: str
    run_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    answer_key_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    generated_at: datetime
    as_of_dates: list[str]
    model: str
    review_status: str
    stopped: str | None
    budget: EvaluationBudgetSummary
    groups: dict[Literal['development', 'holdout', 'all'], EvaluationGroup]
    failures: list[EvaluationFailure]
    examples: list[EvaluationExample]
    limitations: list[str]

    @model_validator(mode='after')
    def complete(self):
        if set(self.groups) != {'development', 'holdout', 'all'}:
            raise ValueError('Missing evaluation split.')
        return self


def build_scorecard(report, manifest, run, portfolios, judgments, key, run_sha256):
    entries = {e['sample_id']: e for e in manifest['documents']}
    docs = {d['id']: d for d in run['documents']}
    groups = {}
    for name, group in report['groups'].items():
        high = group['correctness_by_confidence']['high']
        metrics = {k: group[k] for k in METRICS if k != 'high_confidence_error_rate'}
        errors = high['total'] - high['correct']
        metrics['high_confidence_error_rate'] = {'correct': errors, 'total': high['total'],
            'rate': errors / high['total'] if high['total'] else None, 'unreviewed': high['unreviewed']}
        groups[name] = EvaluationGroup(documents=group['documents'], completed_documents=sum(
            docs[e['document_id']]['status'] in {'complete', 'needs_review'} for e in entries.values()
            if name == 'all' or e['split'] == name), fields_unreviewed=group['fields_unreviewed'],
            predictions_unreviewed=group['predictions_unreviewed'], pairs_unassessed=group['pairs_unassessed'],
            metrics=metrics, confidence=group['correctness_by_confidence'])
    examples = []
    for sid, entry in entries.items():
        for finding in docs[entry['document_id']]['findings']:
            judgment = judgments['findings'][sid].get(finding['id'])
            if not judgment or judgment['correct'] is not False:
                continue
            expected = [f for f in key['documents'][sid]['facts'] if f['field'] == finding['field']]
            examples.append(EvaluationExample(sample=sid, split=entry['split'], finding_id=finding['id'],
                confidence=finding['confidence'], expected='; '.join(f['expected'] for f in expected) or 'No keyed expectation in this field; assess the additional claim against its source.',
                observed=finding['value'], explanation=judgment['reason']))
    examples.sort(key=lambda e: ({'high': 0, 'medium': 1, 'low': 2}[e.confidence], e.sample, e.finding_id))
    return EvaluationScorecard(campaign_id=hashlib.sha256((manifest['answer_key_sha256'] + run_sha256).encode()).hexdigest()[:16],
        run_sha256=run_sha256, answer_key_sha256=manifest['answer_key_sha256'], generated_at=datetime.now(timezone.utc),
        as_of_dates=sorted(portfolios), model=run['model'], review_status=report['review_status'],
        stopped=report['stopped'], budget=report['budget'], groups=groups,
        failures=[EvaluationFailure(sample=f['sample'], split=entries[f['sample']]['split'], status=f['status'],
            message=f['error'] or 'Analysis has not completed.') for f in report['failures']], examples=examples,
        limitations=['Saved benchmark campaign; these results do not describe the current live portfolio.',
            'Pending independent answer-key review. Ten documents are not a calibration study.',
            'Citation validity establishes source presence and coordinates, not semantic correctness.',
            'Coverage includes incorrect answers. Unreviewed judgments never count as correct.',
            'Recall includes missing outputs from incomplete work; it is not accuracy on completed answers.',
            'Deadline and conflict metrics concern only the frozen keyed set. The 80-file ingestion check is separate.'])


def load_scorecard(root: Path):
    path = root / 'scorecard.json'
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Scorecard outside configured directory.')
    return EvaluationScorecard.model_validate_json(path.read_text())


def render_report(card: EvaluationScorecard):
    """Escape every saved value; never serve arbitrary HTML from a campaign directory."""
    esc = lambda v: html.escape(str(v))
    ratio = lambda m: f'{m.correct}/{m.total} ({m.rate:.1%})' if m.rate is not None else 'Not measurable (0 denominator)'
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>AITHENA evaluation</title><style>body{font:16px/1.6 system-ui;max-width:1000px;margin:32px auto;padding:20px;color:#172b4d}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd5df;padding:8px;text-align:left;overflow-wrap:anywhere}article{break-inside:avoid}p,li{overflow-wrap:anywhere}@media print{@page{margin:16mm}body{margin:0;padding:0}}</style>',
        '<h1>AITHENA saved evaluation</h1>', f'<p>Campaign {esc(card.campaign_id)} · {esc(card.model)} · {esc(card.generated_at.isoformat())}</p>',
        f'<p>Review: {esc(card.review_status)}. Evaluated dates: {esc(", ".join(card.as_of_dates))}.</p>',
        f'<p>Run: {esc(card.run_sha256)}<br>Frozen key: {esc(card.answer_key_sha256)}</p>',
        f'<p>Campaign stop: {esc(card.stopped or "No stop recorded")}</p>',
        f'<p>Confirmed charges: US${esc(card.budget.charged_usd)}; unreconciled reservation: US${esc(card.budget.unreconciled_reserved_usd)}; ceiling: US${esc(card.budget.ceiling_usd)}; requests: {card.budget.requests}. Actual total spend is unknown while reservations remain unreconciled.</p>',
        '<ul>' + ''.join(f'<li>{esc(x)}</li>' for x in card.limitations) + '</ul>']
    for name in ('holdout', 'development', 'all'):
        group = card.groups[name]
        parts += [f'<h2>{name.title()}</h2><p>{group.completed_documents}/{group.documents} documents completed analysis; {group.fields_unreviewed} unreviewed fields; {group.predictions_unreviewed} unreviewed predictions; {group.pairs_unassessed} unassessed pairs.</p>',
            '<table><thead><tr><th>Metric</th><th>Result</th></tr></thead><tbody>']
        parts += [f'<tr><td>{label}</td><td>{ratio(group.metrics[k])}' + (f'; {group.metrics[k].unreviewed} unreviewed' if k == 'high_confidence_error_rate' else '') + '</td></tr>' for k, label in METRICS.items()]
        parts += ['</tbody></table><h3>Confidence bands</h3><ul>']
        parts += [f'<li>{band}: {ratio(m)} reviewed correct; {m.unreviewed} unreviewed.</li>' for band, m in group.confidence.items()]
        parts += ['</ul><h3>Reviewed semantic mistakes (up to five)</h3>']
        examples = [e for e in card.examples if name == 'all' or e.split == name][:5]
        parts += [f'<article><h4>{esc(e.sample)} · {esc(e.confidence)}</h4><p>Expected: {esc(e.expected)}</p><p>Observed: {esc(e.observed)}</p><p>Reviewer: {esc(e.explanation)}</p></article>' for e in examples]
        if not examples:
            parts += ['<p>No reviewed semantic mistakes available. This is not proof of accuracy.</p>']
    parts += ['<h2>Operational failures and incomplete work</h2><ul>']
    parts += [f'<li>{esc(f.sample)} ({esc(f.split)}): {esc(f.status)} — {esc(f.message)}</li>' for f in card.failures]
    return ''.join(parts + ['</ul></html>'])
