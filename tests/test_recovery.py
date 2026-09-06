import unittest

from wallet_privacy_testkit.recovery import SCENARIOS, check_scenario, verify_recovery_report


def observation(name='after-once'):
    txid, digest = 'a' * 64, 'b' * 64
    return {'name': name, 'intent': {'amount': 100}, 'recipient': {'before': 20, 'after': 120},
            'attempts': [{'attempt': 1, 'transaction_sha256': digest, 'transaction_bytes': 1000,
                          'forwarded': True, 'upstream_code': 0, 'accepted_txid': txid,
                          'response_held': name == 'after-hold', 'response_lost': True}],
            'wallet': {'after_reopen': 'calculated', 'after_sync': 'confirmed'},
            'node': {'mempool_before': [], 'mempool_after_submit': [txid], 'mempool_final': [],
                     'transaction': {'txid': txid, 'sha256': digest, 'confirmations': 3}},
            'intervention': {'wallet_exit_code': -9, 'accepted_time_ns': 10, 'kill_time_ns': 11,
                             'indexer_stopped': True, 'old_pid': 11, 'new_pid': 12,
                             'endpoint_unavailable': True, 'outage_elapsed_ns': 12_000_000_000,
                             'original_indexer_stopped': True, 'original_port': 9067,
                             'recovery_port': 9077, 'fresh_indexer_state': True}}


def report():
    negative = observation('no-mining')
    negative['node']['transaction']['confirmations'] = 0
    negative['node']['mempool_final'] = negative['node']['mempool_after_submit'][:]
    negative['wallet']['after_sync'] = 'pending'
    negative['recipient']['after'] = negative['recipient']['before']
    return {'schema_version': 2, 'scenarios': [observation(n) for n in sorted(SCENARIOS)],
            'negative_controls': [negative], 'status': 'not trusted'}


class RecoveryTests(unittest.TestCase):
    def test_verdict_is_recomputed_from_observations(self):
        result = verify_recovery_report(report())
        self.assertEqual(result['status'], 'pass')
        self.assertIn('node_confirmation', result['negative_control_detected'])
        self.assertEqual(result['scenarios'][0]['recipient_balance_delta'], 100)

    def test_inconsistent_observations_override_claimed_success(self):
        mutations = [
            lambda r: r['recipient'].update(after=121),
            lambda r: r['node']['transaction'].update(confirmations=0),
            lambda r: r['wallet'].update(after_sync='pending'),
            lambda r: r['attempts'][0].update(transaction_sha256='c' * 64),
            lambda r: r['node']['mempool_after_submit'].append('d' * 64),
            lambda r: r['attempts'][0].update(accepted_txid='d' * 64),
            lambda r: r['attempts'][0].update(response_lost=False, response_held=False),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                evidence = report()
                evidence['status'] = 'pass'
                mutate(evidence['scenarios'][0])
                with self.assertRaises(ValueError):
                    verify_recovery_report(evidence)

    def test_intervention_boundaries_are_checked(self):
        for name, field, value in [('after-hold', 'kill_time_ns', 9),
                                   ('indexer-restart', 'indexer_stopped', False),
                                   ('outage', 'outage_elapsed_ns', 1),
                                   ('alternate-indexer', 'fresh_indexer_state', False)]:
            with self.subTest(name=name):
                row = observation(name)
                row['intervention'][field] = value
                self.assertTrue(check_scenario(row))

    def test_negative_control_cannot_silently_become_positive(self):
        evidence = report()
        evidence['negative_controls'] = [observation('no-mining')]
        with self.assertRaisesRegex(ValueError, 'negative control'):
            verify_recovery_report(evidence)

    def test_missing_and_malformed_observations_fail_closed(self):
        for mutate in [lambda r: r['scenarios'].pop(),
                       lambda r: r.update(schema_version=1),
                       lambda r: r['scenarios'][0]['recipient'].update(before=True),
                       lambda r: r['scenarios'][0]['attempts'].clear(),
                       lambda r: r['scenarios'][0]['attempts'][0].update(attempt=4)]:
            evidence = report()
            mutate(evidence)
            with self.assertRaises(ValueError):
                verify_recovery_report(evidence)
