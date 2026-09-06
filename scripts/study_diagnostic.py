#!/usr/bin/env python3
"""Post-hoc interpretation of window scores; not a predeclared study endpoint."""
import argparse
import hashlib
import json
from pathlib import Path

from wallet_privacy_testkit.study import analyze_study


def diagnose(path):
    path = Path(path)
    report = analyze_study(path)
    manifest = json.loads(path.read_text())
    wallets = {}
    for session, result in zip(manifest['sessions'], report['sessions']):
        if session['split'] != 'evaluation':
            continue
        row = wallets.setdefault(session['wallet'], {
            'payments': 0, 'payments_overlapping_a_flagged_window': 0,
            'largest_client_record_per_session': []})
        row['largest_client_record_per_session'].append(
            max(w['largest_client_record'] for w in result['observations']))
        for payment in session['payments']:
            row['payments'] += 1
            row['payments_overlapping_a_flagged_window'] += any(
                w['predicted_payment'] and payment['start_ns'] < w['end_ns']
                and w['start_ns'] < payment['end_ns'] for w in result['observations'])
    return {
        'analysis_role': 'post-hoc descriptive diagnostic; not a predeclared primary endpoint',
        'manifest_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'threshold_bytes': report['threshold_bytes'],
        'wallets': wallets,
        'scope': 'Temporal overlap only; does not penalize false alarms outside commands. '
                 'Read alongside the full window confusion matrices; not transaction linkage.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    print(json.dumps(diagnose(parser.parse_args().manifest), indent=2))
