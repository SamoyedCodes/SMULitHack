"""Transparent provisional scoring. Semantic decisions are explicit local judgments, never an LLM judge."""
import json
from collections import Counter

from backend.documents import load_pages
from backend.evidence import resolve_citations
from backend.models import Citation


def ratio(correct, total):
    return {'correct': correct, 'total': total, 'rate': correct / total if total else None}


def score(root, judgment_path=None):
    from scripts.evaluate import verify, write_json, digest
    manifest, cfg, store = verify(root)
    key = json.loads((root / 'answer-key.json').read_text())
    run = json.loads((root / 'run.json').read_text())
    portfolios = json.loads((root / 'portfolios.json').read_text())
    entries = {e['sample_id']: e for e in manifest['documents']}
    sample_for = {e['document_id']: sid for sid, e in entries.items()}
    docs = {d['id']: d for d in run['documents']}
    template = {'answer_key_sha256': manifest['answer_key_sha256'], 'run_sha256': digest(root / 'run.json'),
                'review_status': 'provisional_pending_independent_review', 'facts': {}, 'findings': {}}
    for sid, e in entries.items():
        template['facts'][sid] = {f['id']: {'correct': None, 'matched_findings': [], 'reason': ''}
                                  for f in key['documents'][sid]['facts']}
        template['findings'][sid] = {f['id']: {'correct': None, 'reason': ''}
                                     for f in docs[e['document_id']]['findings'] if f['value'] is not None}
    judgments = json.loads(judgment_path.read_text()) if judgment_path else template
    if any(judgments.get(k) != template[k] for k in ('answer_key_sha256', 'run_sha256', 'review_status')):
        raise ValueError('Judgments do not match this frozen key and run.')
    if set(judgments['facts']) != set(template['facts']) or set(judgments['findings']) != set(template['findings']):
        raise ValueError('Judgments must cover all ten documents, including failed documents.')
    for sid in entries:
        for kind in ('facts', 'findings'):
            if set(judgments[kind][sid]) != set(template[kind][sid]):
                raise ValueError('Judgment identifiers do not match the key or model outputs.')
            for decision in judgments[kind][sid].values():
                if decision['correct'] is not None and (type(decision['correct']) is not bool or not decision.get('reason')):
                    raise ValueError('A semantic judgment requires a boolean decision and an explanation.')
        finding_ids = {f['id'] for f in docs[entries[sid]['document_id']]['findings'] if f['value'] is not None}
        if any(not set(j['matched_findings']) <= finding_ids for j in judgments['facts'][sid].values()):
            raise ValueError('Fact judgment references an unknown or unanswered finding.')
    report = {'review_status': key['review_status'], 'model': run['model'], 'budget': run['budget'],
              'stopped': run['stopped'], 'groups': {}, 'failures': [], 'pair_results': [], 'deadline_results': []}
    for sid, e in entries.items():
        d = docs[e['document_id']]
        if d['status'] not in {'complete', 'needs_review'}:
            report['failures'].append({'sample': sid, 'status': d['status'], 'error': d['error']})
    for group in ('development', 'holdout', 'all'):
        members = {sid for sid, e in entries.items() if group == 'all' or e['split'] == group}
        fact_decisions, field_decisions, predictions = [], [], []
        answerable = covered = reviewed_facts = 0
        band = {b: [] for b in ('high', 'medium', 'low')}
        citations_correct = citations_total = 0
        for sid in members:
            e = entries[sid]
            d = docs[e['document_id']]
            local = judgments['facts'][sid]
            facts = key['documents'][sid]['facts']
            for fact in facts:
                j = local[fact['id']]
                fact_decisions.append(j['correct'])
                reviewed_facts += j['correct'] is not None
                if fact['answerable']:
                    answerable += 1
                    covered += bool(j['matched_findings'])
            for field in {f['field'] for f in facts}:
                decisions = [local[f['id']]['correct'] for f in facts if f['field'] == field]
                extras = [judgments['findings'][sid][f['id']]['correct'] for f in d['findings'] if f['field'] == field and f['value'] is not None]
                field_decisions.append(None if None in decisions + extras else all(decisions + extras))
            for f in d['findings']:
                if f['value'] is not None:
                    j = judgments['findings'][sid][f['id']]['correct']
                    predictions.append(j)
                    band[f['confidence']].append(j)
            pages = load_pages(cfg.directory(e['document_id']) / 'pages.json')
            # Include evidence from findings, issues and derived events, deduplicated by full source reference.
            evidence = [ev for f in d['findings'] + d['issues'] for ev in f.get('evidence', [])]
            evidence += [ev for p in portfolios.values() for event in p['events'] if event['document_id'] == e['document_id'] for ev in event['evidence']]
            for context in run['contexts'].values():
                for a in context['assessments']:
                    evidence += [ev for ev in a['evidence'] if ev['document_id'] == e['document_id']]
            unique = {json.dumps(ev, sort_keys=True): ev for ev in evidence}.values()
            for ev in unique:
                citations_total += 1
                resolved, errors = resolve_citations([Citation(**{k: ev[k] for k in ('document_id', 'span_ids', 'quote')})], pages, {e['document_id']})
                citations_correct += bool(not errors and len(resolved) == 1 and resolved[0].page == ev['page'] and resolved[0].boxes == ev['boxes'])
        summary = {'documents': len(members), 'field_accuracy': ratio(sum(x is True for x in field_decisions), sum(x is not None for x in field_decisions)),
                   'fields_total': len(field_decisions), 'fields_unreviewed': sum(x is None for x in field_decisions),
                   'fact_accuracy': ratio(sum(x is True for x in fact_decisions), reviewed_facts),
                   'facts_total': len(fact_decisions), 'facts_unreviewed': len(fact_decisions) - reviewed_facts,
                   'answerable_coverage': ratio(covered, answerable),
                   'prediction_correctness': ratio(sum(x is True for x in predictions), sum(x is not None for x in predictions)),
                   'predictions_unreviewed': sum(x is None for x in predictions),
                   'citation_validity': ratio(citations_correct, citations_total),
                   'correctness_by_confidence': {b: {**ratio(sum(x is True for x in values), sum(x is not None for x in values)),
                                                    'unreviewed': sum(x is None for x in values)} for b, values in band.items()}}
        pairs = []
        for expected in key.get('pairs', []):
            if not set(expected['samples']) <= members:
                continue
            pair_ids = {entries[s]['document_id'] for s in expected['samples']}
            ctx = run['contexts'].get(expected['sme'], {})
            screens = [s for s in ctx.get('screens', []) if s['current'] and set(s['documents']) == pair_ids]
            assessments = [a for a in ctx.get('assessments', []) if a['current'] and set(a['documents']) == pair_ids]
            observed = assessments[0]['status'] if assessments else None
            pairs.append({'samples': expected['samples'], 'expected': expected['status'], 'observed': observed,
                          'screen': screens[0]['outcome'] if screens else None, 'must_retain': expected['must_retain']})
        positives = [p for p in pairs if p['expected'] == 'potential_conflict']
        predicted = [p for p in pairs if p['observed'] == 'potential_conflict']
        summary.update({'candidate_recall': ratio(sum(p['screen'] == 'candidate' for p in pairs if p['must_retain']), sum(p['must_retain'] for p in pairs)),
                        'retained_for_review_recall': ratio(sum(p['screen'] in {'candidate', 'needs_evidence'} for p in pairs if p['must_retain']), sum(p['must_retain'] for p in pairs)),
                        'conflict_precision': ratio(sum(p['expected'] == 'potential_conflict' for p in predicted), len(predicted)),
                        'conflict_recall': ratio(sum(p['observed'] == 'potential_conflict' for p in positives), len(positives)),
                        'pairs_unassessed': sum(p['observed'] is None for p in pairs)})
        deadlines = []
        for expected in key.get('deadlines', []):
            if expected['sample'] not in members:
                continue
            events = portfolios[expected['as_of']]['events']
            found = any(ev['document_id'] == entries[expected['sample']]['document_id'] and
                        ev['event_date'] == expected['event_date'] and ev['action_date'] == expected['action_date'] and
                        ev['event_type'] == expected['event_type'] for ev in events)
            deadlines.append({**expected, 'found': found})
        # Expected-action recall is distinct from correctness of every emitted date.
        expected_tuples = {(entries[d['sample']]['document_id'], d['as_of'], d['event_date'], d['action_date'], d['event_type']) for d in key.get('deadlines', [])}
        emitted = {(ev['document_id'], day, ev['event_date'], ev['action_date'], ev['event_type']) for day, p in portfolios.items() for ev in p['events'] if sample_for[ev['document_id']] in members}
        summary['deadline_recall'] = ratio(sum(d['found'] for d in deadlines), len(deadlines))
        summary['deadline_accuracy'] = ratio(len(emitted & expected_tuples), len(emitted))
        summary['unexpected_dates'] = [list(t) for t in sorted(emitted - expected_tuples, key=str)]
        report['groups'][group] = summary
        if group == 'all':
            report['pair_results'], report['deadline_results'] = pairs, deadlines
    write_json(root / 'judgments-template.json', template)
    write_json(root / 'metrics.json', report)
    lines = ['# Phase 7 provisional evaluation', '', '**Pending independent answer-key review; ten documents are not a calibration study.**', '',
             f"Model: `{run['model']}`. Charged: US${run['budget']['charged_usd']}; unresolved reservations: US${run['budget']['unreconciled_reserved_usd']}; requests: {run['budget']['requests']}.", '',
             'Semantic judgments are local, explicit assessments against the frozen key; no paid model grades the answers. Unreviewed decisions never count as passes. Answerable coverage counts answered key facts, including incorrect answers; accuracy is reported separately.', '',
             '| Metric | Development | Holdout | All |', '| --- | --- | --- | --- |']
    for metric in ['field_accuracy', 'fact_accuracy', 'answerable_coverage', 'prediction_correctness', 'citation_validity', 'deadline_accuracy', 'deadline_recall', 'candidate_recall', 'retained_for_review_recall', 'conflict_precision', 'conflict_recall']:
        cells = []
        for group in ('development', 'holdout', 'all'):
            m = report['groups'][group][metric]
            cells.append(f"{m['correct']}/{m['total']} ({m['rate']:.1%})" if m['rate'] is not None else 'Not measurable (0 denominator)')
        lines.append('| ' + metric.replace('_', ' ') + ' | ' + ' | '.join(cells) + ' |')
    lines.extend(['', '## Confidence bands (provisional)', ''])
    for band, m in report['groups']['all']['correctness_by_confidence'].items():
        lines.append(f"- {band}: {m['correct']}/{m['total']} reviewed correct; {m['unreviewed']} unreviewed.")
    lines.extend(['', '## Incomplete work and limits', '', f"Campaign stop: {run['stopped'] or 'No budget/provider stop recorded.'}",
                  f"Failed or incomplete documents: {len(report['failures'])}. Unreviewed fields: {report['groups']['all']['fields_unreviewed']}. Unassessed keyed pairs: {report['groups']['all']['pairs_unassessed']}.", '',
                  'Quotation validity establishes source presence and coordinates, not semantic entailment. Candidate/conflict metrics cover the explicitly keyed pairs; all screened pairs and excluded reasons remain in run.json. The 80-file local ingestion test is separate. No claim of 85% accuracy or independent calibration is made.'])
    for f in report['failures']:
        lines.append(f"- {f['sample']}: {f['status']} — {f['error']}")
    (root / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    print(root / 'REPORT.md')
    return report
