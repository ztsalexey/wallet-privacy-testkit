import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from wallet_privacy_testkit.study import analyze_study, freeze_detector
from wallet_privacy_testkit.study_design import make_plan, WINDOW_NS, DURATION_NS


def randomized_fixture(root):
    plan = make_plan('1' * 64)
    sessions = []
    for number, spec in enumerate(plan['sessions']):
        start = (number + 1) * 200_000_000_000
        payments = [{'scheduled_start_ns': start + offset, 'start_ns': start + offset,
                     'end_ns': start + offset + 1_000_000_000, 'confirmations': 10,
                     'txid': hashlib.sha256(f'{number}:{i}'.encode()).hexdigest()}
                    for i, offset in enumerate(spec['payment_offsets_ns'])]
        events = [{'event': 'connect', 'connection': 1, 't_ns': start}]
        for i in range(24):
            timestamp = start + i * WINDOW_NS + 1
            size = 100 if i % 7 == 3 else 10
            events.extend([{'event': 'chunk', 'connection': 1, 'direction': 'c2s', 'bytes': size, 't_ns': timestamp},
                           {'event': 'tls_record', 'connection': 1, 'direction': 'c2s', 'record_bytes': size,
                            'content_type': 23, 't_ns': timestamp + 1}])
        events.append({'event': 'close', 'connection': 1, 't_ns': start + DURATION_NS})
        trace = root / (spec['id'] + '.jsonl')
        trace.write_text(''.join(json.dumps(e) + '\n' for e in events))
        sessions.append(dict(spec, trace=trace.name, trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest(),
            start_ns=start, end_ns=start + DURATION_NS, payments=payments, payment_amount=50_000,
            recipient_before=0, recipient_after=150_000, sender_directory_was_absent=True,
            sender_created_ns=start - 1, sender_initial_balance=0, sender_funded_balance=480_000,
            sender_address_sha256=hashlib.sha256(f'sender:{number}'.encode()).hexdigest(),
            funding_txid=hashlib.sha256(f'fund:{number}'.encode()).hexdigest(), funding_confirmations=10))
    plan_path = root / 'study-plan.json'; plan_path.write_text(json.dumps(plan))
    model_path = root / 'frozen-detector.json'
    model_path.write_text(json.dumps(freeze_detector(root, sessions[:3], WINDOW_NS)))
    manifest = {'schema_version': 2, 'sessions': sessions, 'window_ns': WINDOW_NS,
                'plan_sha256': hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                'detector_sha256': hashlib.sha256(model_path.read_bytes()).hexdigest(),
                'frozen_time_ns': sessions[2]['end_ns'] + 1}
    path = root / 'study-manifest.json'; path.write_text(json.dumps(manifest))
    return path


class StudyDesignTests(unittest.TestCase):
    def test_seed_reproduces_balanced_blocks_and_unaligned_timings(self):
        plan = make_plan('1' * 64)
        self.assertEqual(plan, make_plan('1' * 64))
        self.assertNotEqual(plan['sessions'], make_plan('2' * 64)['sessions'])
        sessions = plan['sessions']
        self.assertEqual(len(sessions), 21)
        self.assertEqual(len({s['sender_state_id'] for s in sessions}), 21)
        self.assertTrue(all(s['split'] == 'calibration' for s in sessions[:3]))
        pairs = {(w, c) for w in ('zingolib', 'zcash-devtool') for c in ('baseline', 'latency', 'bandwidth')}
        orders = []
        for offset in (3, 9, 15):
            block = sessions[offset:offset + 6]
            orders.append([(s['wallet'], s['condition']) for s in block])
            self.assertEqual(set(orders[-1]), pairs)
        self.assertEqual(len({tuple(o) for o in orders}), 3)
        for s in sessions:
            for value, low in zip(s['payment_offsets_ns'], (12, 40, 68)):
                self.assertTrue(low * 10**9 <= value < (low + 12) * 10**9)
                self.assertNotEqual(value % WINDOW_NS, 0)
        with self.assertRaises(ValueError): make_plan('seed')

    def test_randomized_report_preserves_session_variation_and_timing(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = analyze_study(randomized_fixture(Path(tmp)))
            self.assertEqual(report['schema_version'], 2)
            self.assertEqual(len(report['groups']), 7)
            for group in report['groups']:
                self.assertEqual(group['session_count'], 3)
                rates = group['session_rates']['recall']
                self.assertLessEqual(rates['min'], rates['mean'])
                self.assertLessEqual(rates['mean'], rates['max'])
            for s in report['sessions']:
                self.assertEqual(len(s['payment_timing']), 3)
                self.assertTrue(all(p['scheduling_delay_ns'] == 0 for p in s['payment_timing']))

    def test_rehashed_plan_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = randomized_fixture(Path(tmp))
            plan_path = Path(tmp) / 'study-plan.json'
            plan = json.loads(plan_path.read_text())
            plan['sessions'][3], plan['sessions'][4] = plan['sessions'][4], plan['sessions'][3]
            plan_path.write_text(json.dumps(plan))
            manifest = json.loads(path.read_text())
            manifest['plan_sha256'] = hashlib.sha256(plan_path.read_bytes()).hexdigest()
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'seeded design'): analyze_study(path)

    def test_reused_state_missing_payments_and_schedule_drift_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = randomized_fixture(Path(tmp)); original = json.loads(path.read_text())
            for mutation in ('address', 'existing', 'created', 'balance', 'funding', 'count', 'schedule', 'txid'):
                with self.subTest(mutation=mutation):
                    data = copy.deepcopy(original); row = data['sessions'][3]
                    if mutation == 'address': row['sender_address_sha256'] = data['sessions'][0]['sender_address_sha256']
                    elif mutation == 'existing': row['sender_directory_was_absent'] = False
                    elif mutation == 'created': row['sender_created_ns'] = 0
                    elif mutation == 'balance': row['sender_initial_balance'] = 1
                    elif mutation == 'funding': row['sender_funded_balance'] = 1
                    elif mutation == 'count': row['payments'].pop()
                    elif mutation == 'schedule': row['payments'][0]['scheduled_start_ns'] += 1
                    else: row['payments'][0]['txid'] = data['sessions'][0]['payments'][0]['txid']
                    path.write_text(json.dumps(data))
                    with self.assertRaises(ValueError): analyze_study(path)

    def test_delayed_evaluation_labels_cannot_refit_the_detector(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = randomized_fixture(Path(tmp)); before = analyze_study(path)
            data = json.loads(path.read_text())
            for payment in data['sessions'][3]['payments']:
                payment['start_ns'] += 2_000_000_000
                payment['end_ns'] += 2_000_000_000
            path.write_text(json.dumps(data)); after = analyze_study(path)
            self.assertEqual(before['threshold_bytes'], after['threshold_bytes'])
            self.assertEqual([w['predicted_payment'] for w in before['sessions'][3]['observations']],
                             [w['predicted_payment'] for w in after['sessions'][3]['observations']])
            self.assertTrue(all(p['scheduling_delay_ns'] == 2_000_000_000 for p in after['sessions'][3]['payment_timing']))
