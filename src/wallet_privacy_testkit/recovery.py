"""Recompute recovery assertions from sanitized observations, without trusting verdicts."""

import re

SCENARIOS = frozenset(('after-once', 'after-hold', 'indexer-restart', 'outage', 'alternate-indexer'))


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')
    return value


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('invalid transaction identifier or hash')
    return value


def check_scenario(row):
    """Return failed assertions; malformed evidence raises ValueError."""
    try:
        name = row['name']
        if name not in SCENARIOS | {'no-mining'}:
            raise ValueError('unknown scenario')
        amount = _integer(row['intent']['amount'], 'intended amount', 1)
        before = _integer(row['recipient']['before'], 'recipient before')
        after = _integer(row['recipient']['after'], 'recipient after')
        node = row['node']
        txid = _hash(node['transaction']['txid'])
        digest = _hash(node['transaction']['sha256'])
        confirmations = _integer(node['transaction']['confirmations'], 'confirmations')
        for field in ('mempool_before', 'mempool_after_submit', 'mempool_final'):
            if not isinstance(node[field], list):
                raise ValueError('mempool observations must be lists')
            for value in node[field]:
                _hash(value)
        attempts = row['attempts']
        if not isinstance(attempts, list) or not attempts:
            raise ValueError('missing submission observations')
        for index, attempt in enumerate(attempts, 1):
            if _integer(attempt['attempt'], 'attempt', 1) != index:
                raise ValueError('non-contiguous attempt sequence')
            _hash(attempt['transaction_sha256'])
            _integer(attempt['transaction_bytes'], 'transaction bytes', 1)
            if type(attempt['forwarded']) is not bool:
                raise ValueError('forwarded must be boolean')
            if attempt.get('accepted_txid') is not None:
                _hash(attempt['accepted_txid'])
        failures = []
        def require(condition, reason):
            if not condition:
                failures.append(reason)
        accepted = [a for a in attempts if a.get('upstream_code') == 0 and type(a.get('upstream_code')) is int]
        require(len(accepted) == 1 and accepted[0].get('accepted_txid') == txid,
                'node_acceptance')
        require(any(a.get('response_held' if name == 'after-hold' else 'response_lost') is True
                    for a in accepted), 'acknowledgement_fault')
        require(all(a['forwarded'] and a['transaction_sha256'] == digest for a in attempts)
                and len({a['transaction_bytes'] for a in attempts}) == 1, 'submission_identity')
        require(node['mempool_before'] == [] and node['mempool_after_submit'] == [txid], 'mempool_uniqueness')
        require(confirmations >= 3, 'node_confirmation')
        require(row['wallet']['after_sync'] == 'confirmed', 'wallet_confirmation')
        require(after - before == amount, 'recipient_balance_delta')
        require(node['mempool_final'] == [], 'final_mempool')
        intervention = row['intervention']
        if name == 'after-hold':
            require(intervention['wallet_exit_code'] == -9
                    and any(a.get('response_held') is True for a in accepted)
                    and _integer(intervention['kill_time_ns'], 'kill time') >=
                    _integer(intervention['accepted_time_ns'], 'acceptance time'), 'crash_boundary')
        elif name == 'indexer-restart':
            require(intervention['indexer_stopped'] is True
                    and _integer(intervention['old_pid'], 'old PID', 1) !=
                    _integer(intervention['new_pid'], 'new PID', 1), 'indexer_restart')
        elif name == 'outage':
            require(intervention['endpoint_unavailable'] is True
                    and _integer(intervention['outage_elapsed_ns'], 'outage duration') >= 10_000_000_000,
                    'outage_boundary')
        elif name == 'alternate-indexer':
            require(intervention['original_indexer_stopped'] is True
                    and intervention['original_port'] != intervention['recovery_port']
                    and intervention['fresh_indexer_state'] is True, 'indexer_switch')
        return failures
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError('incomplete or malformed recovery evidence') from error


def verify_recovery_report(report):
    try:
        if report['schema_version'] != 2 or type(report['schema_version']) is not int:
            raise ValueError('unsupported recovery schema; older summaries cannot be independently verified')
        rows = report['scenarios']
        if not isinstance(rows, list) or len(rows) != len(SCENARIOS) or {r['name'] for r in rows} != SCENARIOS:
            raise ValueError('incomplete or duplicate recovery scenario set')
        summaries = []
        for row in rows:
            failures = check_scenario(row)
            if failures:
                raise ValueError(f'{row["name"]}: {", ".join(failures)}')
            summaries.append({'name': row['name'], 'recipient_balance_delta':
                              row['recipient']['after'] - row['recipient']['before'], 'status': 'pass'})
        controls = report['negative_controls']
        if not isinstance(controls, list) or len(controls) != 1 or controls[0]['name'] != 'no-mining':
            raise ValueError('missing live no-mining negative control')
        failures = check_scenario(controls[0])
        if 'node_confirmation' not in failures or 'recipient_balance_delta' not in failures:
            raise ValueError('negative control did not detect unconfirmed and unpaid state')
        control = controls[0]
        if (set(failures) != {'node_confirmation', 'wallet_confirmation', 'recipient_balance_delta', 'final_mempool'}
                or control['node']['transaction']['confirmations'] != 0
                or control['recipient']['after'] != control['recipient']['before']
                or control['node']['mempool_final'] != [control['node']['transaction']['txid']]):
            raise ValueError('negative control has inconsistent observations')
        return {'status': 'pass', 'scenarios': summaries,
                'negative_control_detected': failures,
                'scope': 'consistency of supplied observations; not proof of their authenticity'}
    except (KeyError, TypeError) as error:
        raise ValueError('incomplete or malformed recovery report') from error
