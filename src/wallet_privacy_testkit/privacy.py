"""Fixed-window, held-out send-activity detection from continuous TLS metadata."""

import hashlib
import json
from pathlib import Path

from .capture import read_trace, summarize_trace


def window_features(trace, start_ns, end_ns, window_ns):
    for value in (start_ns, end_ns, window_ns):
        if type(value) is not int or value < 0:
            raise ValueError('window boundaries must be nonnegative integer nanoseconds')
    if not window_ns or end_ns <= start_ns or (end_ns - start_ns) % window_ns:
        raise ValueError('measurement interval must contain whole fixed windows')
    summarize_trace(trace)
    rows = [{'index': i, 'start_ns': start_ns + i * window_ns,
             'end_ns': start_ns + (i + 1) * window_ns,
             'client_bytes': 0, 'server_bytes': 0, 'largest_client_record': 0}
            for i in range((end_ns - start_ns) // window_ns)]
    events = read_trace(trace)
    if any(type(e.get('t_ns')) is not int or e['t_ns'] < 0 for e in events):
        raise ValueError('invalid trace timestamp')
    if min(e['t_ns'] for e in events) > start_ns or max(e['t_ns'] for e in events) < end_ns:
        raise ValueError('trace does not span the full declared observation interval')
    for event in events:
        timestamp = event.get('t_ns')
        if type(timestamp) is not int:
            raise ValueError('invalid trace timestamp')
        if not start_ns <= timestamp < end_ns:
            continue
        row = rows[(timestamp - start_ns) // window_ns]
        if event['event'] == 'chunk':
            size = event.get('bytes')
            if type(size) is not int or size < 0 or event.get('direction') not in ('c2s', 's2c'):
                raise ValueError('invalid chunk observation')
            row['client_bytes' if event['direction'] == 'c2s' else 'server_bytes'] += size
        if event['event'] == 'tls_record' and event.get('direction') == 'c2s' and event.get('content_type') == 23:
            size = event['record_bytes']
            if type(size) is not int or size < 5:
                raise ValueError('invalid record size')
            row['largest_client_record'] = max(row['largest_client_record'], size)
    return rows


def labels_for_windows(windows, payments):
    if not isinstance(payments, list) or not payments:
        raise ValueError('missing ground-truth payments')
    previous_end = windows[0]['start_ns']
    for payment in payments:
        start, end = payment['start_ns'], payment['end_ns']
        if type(start) is not int or type(end) is not int or not previous_end <= start < end <= windows[-1]['end_ns']:
            raise ValueError('overlapping or out-of-range payment intervals')
        if type(payment['confirmations']) is not int or payment['confirmations'] < 3:
            raise ValueError('ground-truth payment did not confirm')
        previous_end = end
    return [any(p['start_ns'] < w['end_ns'] and w['start_ns'] < p['end_ns'] for p in payments)
            for w in windows]


def confusion(predictions, labels):
    if len(predictions) != len(labels) or not labels or not all(type(x) is bool for x in predictions + labels):
        raise ValueError('invalid predictions or labels')
    tp = sum(p and y for p, y in zip(predictions, labels))
    fp = sum(p and not y for p, y in zip(predictions, labels))
    fn = sum(not p and y for p, y in zip(predictions, labels))
    tn = sum(not p and not y for p, y in zip(predictions, labels))
    if not tp + fn or not tn + fp:
        raise ValueError('both payment and non-payment windows are required')
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
            'recall': tp / (tp + fn), 'false_positive_rate': fp / (fp + tn),
            'precision': tp / (tp + fp) if tp + fp else None,
            'balanced_accuracy': (tp / (tp + fn) + tn / (tn + fp)) / 2}


def fit_threshold(features, labels):
    """Choose one cutoff on calibration data; ties prefer fewer detections."""
    candidates = sorted(set([0, *features, max(features) + 1]))
    return max(candidates, key=lambda cutoff: (
        confusion([x >= cutoff for x in features], labels)['balanced_accuracy'], cutoff))


def analyze_privacy(manifest_path):
    path = Path(manifest_path)
    try:
        manifest = json.loads(path.read_text())
        if manifest['schema_version'] != 1 or type(manifest['schema_version']) is not int:
            raise ValueError('unsupported privacy experiment schema')
        sessions = manifest['sessions']
        if [s['split'] for s in sessions] != ['calibration', 'evaluation']:
            raise ValueError('exactly one calibration and one evaluation session are required')
        if len({s['trace'] for s in sessions}) != 2:
            raise ValueError('calibration and evaluation traces must be different')
        if len({s['trace_sha256'] for s in sessions}) != 2:
            raise ValueError('calibration and evaluation cannot reuse the same trace content')
        prepared = []
        for session in sessions:
            filename = session['trace']
            if not isinstance(filename, str) or Path(filename).name != filename or filename in ('.', '..'):
                raise ValueError('trace must name a file beside the manifest')
            trace = path.parent / filename
            if hashlib.sha256(trace.read_bytes()).hexdigest() != session['trace_sha256']:
                raise ValueError('trace checksum mismatch')
            windows = window_features(trace, session['start_ns'], session['end_ns'], manifest['window_ns'])
            labels = labels_for_windows(windows, session['payments'])
            amount = session['payment_amount']
            before, after = session['recipient_before'], session['recipient_after']
            if not all(type(x) is int and x >= 0 for x in (amount, before, after)) or amount == 0:
                raise ValueError('invalid privacy payment balance observations')
            if after - before != amount * len(session['payments']):
                raise ValueError('privacy payment receipts do not match the requested amounts')
            prepared.append((windows, labels))
        calibration, calibration_labels = prepared[0]
        cutoff = fit_threshold([w['largest_client_record'] for w in calibration], calibration_labels)
        results = []
        for session, (windows, labels) in zip(sessions, prepared):
            predictions = [w['largest_client_record'] >= cutoff for w in windows]
            results.append({'split': session['split'], 'windows': len(windows),
                            'payment_operations': len(session['payments']),
                            'negative_windows_with_traffic': sum(not y and w['client_bytes'] + w['server_bytes'] > 0
                                                                for w, y in zip(windows, labels)),
                            'metrics': confusion(predictions, labels),
                            'observations': [dict(w, payment_active=y, predicted_payment=p)
                                             for w, y, p in zip(windows, labels, predictions)]})
        return {'feature': 'largest client TLS application record completed in each fixed window',
                'threshold_bytes': cutoff, 'window_ns': manifest['window_ns'], 'sessions': results,
                'scope': 'local send-activity detection; not transaction matching or user identification'}
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError('incomplete or malformed privacy experiment') from error
