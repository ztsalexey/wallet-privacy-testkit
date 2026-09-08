"""Freeze a detector on calibration sessions and score independent study sessions."""
import hashlib
import json
from pathlib import Path

from .study_design import make_plan

from .privacy import window_features, labels_for_windows, confusion, fit_threshold


def prepare_session(root, session, window_ns):
    filename = session['trace']
    if not isinstance(filename, str) or Path(filename).name != filename or filename in ('.', '..'):
        raise ValueError('trace must name a file beside the study manifest')
    path = root / filename
    if hashlib.sha256(path.read_bytes()).hexdigest() != session['trace_sha256']:
        raise ValueError('study trace checksum mismatch')
    windows = window_features(path, session['start_ns'], session['end_ns'], window_ns)
    labels = labels_for_windows(windows, session['payments'])
    amount, before, after = (session[k] for k in ('payment_amount', 'recipient_before', 'recipient_after'))
    if not all(type(v) is int and v >= 0 for v in (amount, before, after)) or not amount:
        raise ValueError('invalid study balance observations')
    if after - before != amount * len(session['payments']):
        raise ValueError('study payment receipts do not match intended amounts')
    return windows, labels


def freeze_detector(root, sessions, window_ns):
    if not sessions or any(s['split'] != 'calibration' for s in sessions):
        raise ValueError('only calibration sessions can freeze a detector')
    features, labels = [], []
    for session in sessions:
        windows, truth = prepare_session(Path(root), session, window_ns)
        features.extend(w['largest_client_record'] for w in windows)
        labels.extend(truth)
    return {'schema_version': 1, 'feature': 'largest_client_record', 'window_ns': window_ns,
            'threshold_bytes': fit_threshold(features, labels),
            'calibration_trace_sha256': [s['trace_sha256'] for s in sessions]}


def analyze_study(manifest_path):
    path = Path(manifest_path)
    try:
        manifest = json.loads(path.read_text())
        if type(manifest['schema_version']) is not int or manifest['schema_version'] not in (1, 2):
            raise ValueError('unsupported study schema')
        sessions = manifest['sessions']
        plan_path = path.parent / 'study-plan.json'
        if hashlib.sha256(plan_path.read_bytes()).hexdigest() != manifest['plan_sha256']:
            raise ValueError('study plan checksum mismatch')
        plan = json.loads(plan_path.read_text())
        if not isinstance(plan, dict):
            raise ValueError('study plan must be a JSON object')
        if type(plan.get('schema_version', 1)) is not int or plan.get('schema_version', 1) != manifest['schema_version']:
            raise ValueError('study plan and manifest schema differ')
        if manifest['schema_version'] == 2:
            validate_randomized_study(plan, sessions)
        if plan['window_ns'] != manifest['window_ns']:
            raise ValueError('study window differs from plan')
        duration = plan['duration_ns']
        if type(duration) is not int or duration <= 0 or any(s['end_ns'] - s['start_ns'] != duration for s in sessions):
            raise ValueError('study session duration differs from plan')
        if any(a['end_ns'] > b['start_ns'] for a,b in zip(sessions, sessions[1:])):
            raise ValueError('study sessions must not overlap')
        if [{k: s[k] for k in p} for s,p in zip(sessions, plan['sessions'])] != plan['sessions'] or len(sessions) != len(plan['sessions']):
            raise ValueError('study does not contain every planned session in order')
        if not sessions or len({s['id'] for s in sessions}) != len(sessions):
            raise ValueError('missing or duplicate study sessions')
        if len({s['trace_sha256'] for s in sessions}) != len(sessions):
            raise ValueError('study sessions must not reuse trace content')
        calibration = [s for s in sessions if s['split'] == 'calibration']
        evaluation = [s for s in sessions if s['split'] == 'evaluation']
        if not evaluation or len(calibration) + len(evaluation) != len(sessions):
            raise ValueError('study requires calibration and evaluation sessions')
        expected = freeze_detector(path.parent, calibration, manifest['window_ns'])
        model_path = path.parent / 'frozen-detector.json'
        if hashlib.sha256(model_path.read_bytes()).hexdigest() != manifest['detector_sha256']:
            raise ValueError('frozen detector checksum mismatch')
        model = json.loads(model_path.read_text())
        if model != expected:
            raise ValueError('frozen detector differs from calibration-only fit')
        frozen = manifest['frozen_time_ns']
        if type(frozen) is not int or not max(s['end_ns'] for s in calibration) <= frozen < min(s['start_ns'] for s in evaluation):
            raise ValueError('detector must be frozen before any evaluation session')
        results, grouped = [], {}
        for session in sessions:
            windows, truth = prepare_session(path.parent, session, model['window_ns'])
            predicted = [w['largest_client_record'] >= model['threshold_bytes'] for w in windows]
            results.append({'id': session['id'], 'split': session['split'], 'wallet': session['wallet'],
                            'condition': session['condition'], 'payment_operations': len(session['payments']),
                            'metrics': confusion(predicted, truth),
                            'negative_windows_with_traffic': sum(not y and w['client_bytes'] + w['server_bytes'] > 0 for w, y in zip(windows, truth)),
                            'observations': [dict(w, payment_active=y, predicted_payment=p) for w,y,p in zip(windows,truth,predicted)]})
            key = (session['split'], session['wallet'], session['condition'])
            predictions, labels = grouped.setdefault(key, ([], []))
            predictions.extend(predicted); labels.extend(truth)
        report = {'schema_version': 1, 'threshold_bytes': model['threshold_bytes'], 'window_ns': model['window_ns'],
                'groups': [{'split': k[0], 'wallet': k[1], 'condition': k[2], 'metrics': confusion(*v)} for k,v in grouped.items()],
                'sessions': results,
                'scope': 'descriptive local send-window detection; correlated windows; not wallet ranking or identity linkage'}
        if manifest['schema_version'] == 2:
            report['schema_version'] = 2
            report['design_seed'] = plan['seed']
            for result, session in zip(results, sessions):
                result['repeat'] = session['repeat']
                result['payment_timing'] = [
                    {'scheduled_phase_ns': offset % model['window_ns'],
                     'actual_phase_ns': (payment['start_ns'] - session['start_ns']) % model['window_ns'],
                     'scheduling_delay_ns': payment['start_ns'] - payment['scheduled_start_ns']}
                    for offset, payment in zip(session['payment_offsets_ns'], session['payments'])]
            for group in report['groups']:
                members = [r['metrics'] for r in results if all(r[k] == group[k] for k in ('split', 'wallet', 'condition'))]
                group['session_count'] = len(members)
                group['session_rates'] = {k: {'mean': sum(m[k] for m in members) / len(members),
                    'min': min(m[k] for m in members), 'max': max(m[k] for m in members)}
                    for k in ('recall', 'false_positive_rate', 'balanced_accuracy')}
        return report
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError('incomplete or malformed study') from error


def validate_randomized_study(plan, sessions):
    """Reject departures from the seeded design, including reused sender evidence."""
    if plan != make_plan(plan['seed']):
        raise ValueError('study plan differs from seeded design')
    addresses, funding_ids, payment_ids = set(), set(), set()
    previous_end = 0
    for session in sessions:
        address = session['sender_address_sha256']
        if not isinstance(address, str) or len(address) != 64 or any(c not in '0123456789abcdef' for c in address) or address in addresses:
            raise ValueError('study requires distinct sender address hashes')
        addresses.add(address)
        created = session['sender_created_ns']
        if session['sender_directory_was_absent'] is not True or type(created) is not int or not previous_end <= created < session['start_ns']:
            raise ValueError('study requires fresh sender state before every session')
        previous_end = session['end_ns']
        if type(session['sender_initial_balance']) is not int or session['sender_initial_balance'] != 0:
            raise ValueError('study sender must start empty')
        if type(session['sender_funded_balance']) is not int or session['sender_funded_balance'] != plan['funding_outputs'] * plan['funding_amount_per_output']:
            raise ValueError('study sender funding differs from plan')
        if type(session['funding_confirmations']) is not int or session['funding_confirmations'] < 10:
            raise ValueError('study funding did not settle before capture')
        if type(session['payment_amount']) is not int or session['payment_amount'] != plan['payment_amount']:
            raise ValueError('study payment amount differs from plan')
        funding = session['funding_txid']
        if not isinstance(funding, str) or len(funding) != 64 or any(c not in '0123456789abcdef' for c in funding) or funding in funding_ids:
            raise ValueError('study requires distinct funding transactions')
        funding_ids.add(funding)
        if len(session['payments']) != len(session['payment_offsets_ns']):
            raise ValueError('study payment count differs from plan')
        for offset, payment in zip(session['payment_offsets_ns'], session['payments']):
            scheduled = payment['scheduled_start_ns']
            if type(scheduled) is not int or scheduled != session['start_ns'] + offset or payment['start_ns'] < scheduled:
                raise ValueError('study payment schedule differs from plan')
            txid = payment['txid']
            if not isinstance(txid, str) or len(txid) != 64 or any(c not in '0123456789abcdef' for c in txid) or txid in payment_ids:
                raise ValueError('study requires distinct payment transactions')
            payment_ids.add(txid)
