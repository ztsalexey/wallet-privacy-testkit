import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from wallet_privacy_testkit.privacy import analyze_privacy, confusion, fit_threshold, window_features


def fixture(folder):
    sessions = []
    for split, sizes, positive in [('calibration', [10, 100, 20, 120], [1, 3]),
                                    ('evaluation', [110, 10, 120, 20], [2, 3])]:
        events = [{'event': 'connect', 'connection': 1, 't_ns': 0}]
        for i, size in enumerate(sizes):
            events += [{'event': 'chunk', 'connection': 1, 'direction': 'c2s', 'bytes': size, 't_ns': i * 10 + 1},
                       {'event': 'tls_record', 'connection': 1, 'direction': 'c2s', 'record_bytes': size,
                        'content_type': 23, 't_ns': i * 10 + 2}]
        events.append({'event': 'close', 'connection': 1, 't_ns': 40})
        path = folder / f'{split}.jsonl'
        path.write_text(''.join(json.dumps(e) + '\n' for e in events))
        sessions.append({'split': split, 'trace': path.name,
                         'trace_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'start_ns': 0, 'end_ns': 40, 'payment_amount': 100,
                         'recipient_before': 0, 'recipient_after': 200,
                         'payments': [{'start_ns': i * 10 + 1, 'end_ns': i * 10 + 5, 'confirmations': 3}
                                      for i in positive]})
    manifest = folder / 'manifest.json'
    manifest.write_text(json.dumps({'schema_version': 1, 'window_ns': 10, 'sessions': sessions}))
    return manifest


class PrivacyTests(unittest.TestCase):
    def test_held_out_false_positives_and_misses_are_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze_privacy(fixture(Path(tmp)))
        self.assertEqual(result['threshold_bytes'], 100)
        metrics = result['sessions'][1]['metrics']
        self.assertEqual([metrics[x] for x in ('tp', 'fp', 'fn', 'tn')], [1, 1, 1, 1])
        self.assertEqual(metrics['false_positive_rate'], 0.5)

    def test_evaluation_labels_do_not_change_calibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = fixture(Path(tmp))
            original = analyze_privacy(path)
            data = json.loads(path.read_text())
            data['sessions'][1]['payments'][0].update(start_ns=1, end_ns=5)
            path.write_text(json.dumps(data))
            changed = analyze_privacy(path)
            self.assertEqual(original['threshold_bytes'], changed['threshold_bytes'])
            self.assertEqual([w['predicted_payment'] for w in original['sessions'][1]['observations']],
                             [w['predicted_payment'] for w in changed['sessions'][1]['observations']])

    def test_trace_corruption_and_duplicate_sessions_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = fixture(Path(tmp))
            trace = Path(tmp) / 'evaluation.jsonl'
            trace.write_text(trace.read_text() + '\n')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                analyze_privacy(path)
            path = fixture(Path(tmp))
            data = json.loads(path.read_text())
            data['sessions'][1]['trace'] = data['sessions'][0]['trace']
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                analyze_privacy(path)
            path = fixture(Path(tmp))
            data = json.loads(path.read_text())
            data['sessions'][1]['trace_sha256'] = data['sessions'][0]['trace_sha256']
            (Path(tmp) / 'evaluation.jsonl').write_bytes((Path(tmp) / 'calibration.jsonl').read_bytes())
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'same trace content'):
                analyze_privacy(path)

    def test_full_window_and_negative_class_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture(Path(tmp))
            with self.assertRaises(ValueError):
                window_features(Path(tmp) / 'calibration.jsonl', 0, 50, 10)
        with self.assertRaises(ValueError):
            confusion([True, True], [True, True])
        self.assertEqual(fit_threshold([10, 10], [True, False]), 11)
