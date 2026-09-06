import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from test_privacy import fixture
from wallet_privacy_testkit.study import freeze_detector, analyze_study


def study_fixture(root):
    old = json.loads(fixture(root).read_text())
    sessions = old['sessions']
    for i,s in enumerate(sessions):
        s.update(id=f'session-{i}', wallet='wallet', condition='baseline')
        if i:
            trace = root / s['trace']
            events = [json.loads(line) for line in trace.read_text().splitlines()]
            for e in events: e['t_ns'] += 100
            trace.write_text(''.join(json.dumps(e)+'\n' for e in events))
            s['trace_sha256'] = hashlib.sha256(trace.read_bytes()).hexdigest()
            s['start_ns'] += 100; s['end_ns'] += 100
            for p in s['payments']: p['start_ns'] += 100; p['end_ns'] += 100
    plan = {'window_ns': 10, 'duration_ns': 40, 'sessions': [{k:s[k] for k in ('id','split','wallet','condition')} for s in sessions]}
    plan_path = root / 'study-plan.json'; plan_path.write_text(json.dumps(plan))
    model_path = root / 'frozen-detector.json'
    model_path.write_text(json.dumps(freeze_detector(root, sessions[:1], 10)))
    manifest = dict(old, frozen_time_ns=50, plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                    detector_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest())
    path = root / 'study-manifest.json'; path.write_text(json.dumps(manifest))
    return path


class StudyTests(unittest.TestCase):
    def test_frozen_model_reports_false_positives_and_misses(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze_study(study_fixture(Path(tmp)))
            self.assertEqual(result['threshold_bytes'], 100)
            self.assertEqual(result['groups'][1]['metrics']['false_positive_rate'], 0.5)
            self.assertEqual(result['groups'][1]['metrics']['fn'], 1)

    def test_evaluation_truth_does_not_change_predictions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = study_fixture(Path(tmp)); original = analyze_study(path)
            data = json.loads(path.read_text())
            data['sessions'][1]['payments'][0].update(start_ns=101,end_ns=105)
            path.write_text(json.dumps(data)); changed = analyze_study(path)
            self.assertEqual(original['threshold_bytes'], changed['threshold_bytes'])
            self.assertEqual([w['predicted_payment'] for w in original['sessions'][1]['observations']],
                             [w['predicted_payment'] for w in changed['sessions'][1]['observations']])

    def test_late_freeze_partial_plan_and_model_changes_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for mutation in ('late', 'partial', 'duration', 'overlap', 'model'):
                with self.subTest(mutation=mutation):
                    path=study_fixture(Path(tmp)); data=json.loads(path.read_text())
                    if mutation=='late': data['frozen_time_ns']=101
                    elif mutation=='partial': data['sessions'].pop()
                    elif mutation=='duration': data['sessions'][1]['start_ns'] += 10
                    elif mutation=='overlap': data['sessions'][1].update(start_ns=30,end_ns=70)
                    else:
                        model_path=Path(tmp)/'frozen-detector.json'
                        model=json.loads(model_path.read_text()); model['threshold_bytes']=1
                        model_path.write_text(json.dumps(model))
                        data['detector_sha256']=hashlib.sha256(model_path.read_bytes()).hexdigest()
                    path.write_text(json.dumps(data))
                    with self.assertRaises(ValueError): analyze_study(path)
