"""Fresh-wallet regtest experiments, executed only inside the Compose lab."""

import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import time
import urllib.request
from pathlib import Path

import grpc

from wallet_privacy_testkit.fault_relay import SendTransactionRelay
from wallet_privacy_testkit.recovery import check_scenario, verify_recovery_report

STATE = Path('/lab')
ENDPOINT = 'https://localhost:9067'
SOURCES = {
    'zingolib': '9e897f8b2fc5f12a99604f2533164af62af7d3ac',
    'lightwalletd': 'd79cd1100575ff909d70e00d5514a4092df94934',
    'zebra': '6.2.3',
}


def emit(phase):
    print(json.dumps({'phase': phase}), flush=True)


def rpc(method, params=None):
    request = urllib.request.Request(
        'http://zebra:18232',
        json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or []}).encode(),
        {'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        value = json.load(response)
    if value.get('error'):
        raise RuntimeError(f'node {method}: {value["error"]}')
    return value['result']


def wait_node():
    last_error = None
    for _ in range(90):
        try:
            return rpc('getblockchaininfo')
        except (OSError, RuntimeError) as error:
            last_error = error
            time.sleep(1)
    raise RuntimeError(f'regtest RPC did not become ready: {last_error}')


def wallet_args(name, command, args=(), sync=False, server=ENDPOINT):
    if name not in ('alice', 'bob'):
        raise ValueError('unknown disposable wallet')
    folder = STATE / name
    folder.mkdir(exist_ok=True)
    return ['zingo-cli', '--chain', 'regtest', '--server', server,
            '--data-dir', str(folder), '--waitsync' if sync else '--nosync', command, *args]


def wallet(name, command, args=(), sync=False, server=ENDPOINT):
    result = subprocess.run(wallet_args(name, command, args, sync, server),
                            capture_output=True, text=True, timeout=300)
    # Raw wallet output is kept only in the disposable volume, never the report.
    (STATE / f'{name}-{command}.log').write_text(result.stdout + result.stderr)
    if result.returncode or re.search(r'"error"\s*:', result.stdout):
        raise RuntimeError(f'{name} {command} failed; exit={result.returncode}')
    return result.stdout


def parsed(output):
    decoder = json.JSONDecoder()
    for match in re.finditer(r'[\[{]', output):
        try:
            return decoder.raw_decode(output[match.start():])[0]
        except json.JSONDecodeError:
            pass
    raise ValueError('expected structured wallet output')


def orchard_balance(output):
    match = re.search(r'\bconfirmed_orchard_balance:\s*([\d_]+)', output)
    if not match:
        raise ValueError('missing confirmed Orchard balance')
    return int(match[1].replace('_', ''))


def transaction_status(output, txid):
    for entry in re.split(r'\btxid:\s*', output)[1:]:
        if entry.startswith(txid):
            match = re.search(r'\bstatus:\s*([^\n]+)', entry)
            return match[1].strip() if match else 'unknown'
    return 'absent'


class Indexer:
    def __init__(self, port=9067):
        self.port = port
        self.process = None
        self.log = None
        self.state_dir = STATE / f'indexer-{port}'

    @property
    def endpoint(self):
        return f'https://localhost:{self.port}'

    def start(self):
        if self.process is not None:
            raise RuntimeError('indexer already started')
        wait_node()
        self.log = (STATE / f'indexer-{self.port}-stderr.log').open('a')
        args = ['lightwalletd', '--grpc-bind-addr', f'127.0.0.1:{self.port}',
                '--http-bind-addr', f'127.0.0.1:{self.port + 1}',
                '--tls-cert', str(STATE / 'cert.pem'), '--tls-key', str(STATE / 'key.pem'),
                '--data-dir', str(self.state_dir), '--log-file', str(STATE / f'indexer-{self.port}.log'),
                '--rpcuser', 'regtest', '--rpcpassword', 'regtest', '--rpchost', 'zebra', '--rpcport', '18232']
        self.process = subprocess.Popen(args, stdout=self.log, stderr=self.log)
        try:
            with grpc.secure_channel(f'localhost:{self.port}', grpc.ssl_channel_credentials(
                    root_certificates=(STATE / 'cert.pem').read_bytes())) as channel:
                grpc.channel_ready_future(channel).result(timeout=90)
        except BaseException:
            self.stop()
            raise
        return self.process.pid

    def stop(self):
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None
            self.log.close()
            self.log = None


@contextlib.contextmanager
def indexer():
    instance = Indexer()
    instance.start()
    try:
        yield instance
    finally:
        instance.stop()


def initialize():
    if (STATE / 'zebra.toml').exists():
        raise RuntimeError('lab volume must be new')
    STATE.mkdir(exist_ok=True)
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                    '-keyout', str(STATE / 'key.pem'), '-out', str(STATE / 'cert.pem'),
                    '-days', '2', '-subj', '/CN=localhost',
                    '-addext', 'basicConstraints=critical,CA:FALSE',
                    '-addext', 'extendedKeyUsage=serverAuth',
                    '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1'],
                   check=True, capture_output=True)
    os.chmod(STATE / 'key.pem', 0o600)
    # A random, unspendable bootstrap P2PKH destination enables the regtest
    # miner before any wallet exists. Only the bootstrap block pays this address.
    payload = bytes([0x1d, 0x25]) + os.urandom(20)
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    number = int.from_bytes(payload + checksum, 'big')
    alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    bootstrap_address = ''
    while number:
        number, digit = divmod(number, 58)
        bootstrap_address = alphabet[digit] + bootstrap_address
    (STATE / 'zebra.toml').write_text('''[network]
network = "Regtest"
listen_addr = "127.0.0.1:18233"
initial_mainnet_peers = []
initial_testnet_peers = []
cache_dir = false
[network.testnet_parameters.activation_heights]
BeforeOverwinter = 1
Overwinter = 1
Sapling = 1
Blossom = 1
Heartwood = 1
Canopy = 1
NU5 = 1
NU6 = 1
"NU6.1" = 1
"NU6.2" = 1
[rpc]
listen_addr = "0.0.0.0:18232"
enable_cookie_auth = false
[state]
cache_dir = "/lab/chain"
[tracing]
filter = "warn"
''')
    with (STATE / 'zebra.toml').open('a') as config:
        config.write(f'\n[mining]\nminer_address = "{bootstrap_address}"\n')


def bootstrap():
    wait_node()
    rpc('generate', [1])
    with indexer():
        emit('creating fresh wallets')
        addresses = {name: parsed(wallet(name, 'addresses'))[0]['encoded_address']
                     for name in ('alice', 'bob')}
        miner = parsed(wallet('alice', 't_addresses'))[0]['encoded_address']
        (STATE / 'addresses.json').write_text(json.dumps(addresses))
        config = STATE / 'zebra.toml'
        config.write_text(re.sub(r'miner_address = "[^"]+"', f'miner_address = "{miner}"', config.read_text()))


def synchronize(server=ENDPOINT):
    return {name: orchard_balance(wallet(name, 'balance', sync=True, server=server))
            for name in ('alice', 'bob')}


def exercise(name, recipient, amount, primary):
    mode = 'after-hold' if name == 'after-hold' else 'after-once'
    balances = synchronize()
    mempool_before = rpc('getrawmempool')
    if mempool_before:
        raise RuntimeError('scenario must start with an empty mempool')
    relay = SendTransactionRelay('localhost:9067', mode,
                                 upstream_ca=STATE / 'cert.pem',
                                 certificate=STATE / 'cert.pem', private_key=STATE / 'key.pem')
    process = None
    intervention = {}
    try:
        with (STATE / f'{name}-send.log').open('w') as log:
            process = subprocess.Popen(wallet_args('alice', 'quicksend',
                [json.dumps([{'address': recipient, 'amount': amount}])], server=relay.endpoint),
                stdout=log, stderr=log)
            if mode == 'after-hold':
                deadline = time.monotonic() + 240
                while time.monotonic() < deadline:
                    accepted = [e for e in list(relay.events) if e.get('response_held')
                                and e.get('upstream_response', {}).get('error_code') == 0]
                    if accepted:
                        if process.poll() is not None:
                            raise RuntimeError('wallet exited before the crash boundary')
                        intervention['accepted_time_ns'] = accepted[0]['upstream_response_time_ns']
                        intervention['kill_time_ns'] = time.monotonic_ns()
                        process.kill()
                        break
                    if process.poll() is not None:
                        raise RuntimeError('wallet exited before an accepted submission was held')
                    time.sleep(0.02)
                if 'kill_time_ns' not in intervention:
                    raise RuntimeError('accepted submission was not observed before timeout')
            intervention['wallet_exit_code'] = process.wait(timeout=240)
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        relay.close()
    attempts = []
    for event in relay.events:
        response = event.get('upstream_response', {})
        txid = response.get('message') if response.get('error_code') == 0 else None
        if txid is not None and txid.startswith('"'):
            txid = json.loads(txid)
        attempts.append({'attempt': event['attempt'], 'transaction_sha256': event['transaction_sha256'],
                         'transaction_bytes': event['transaction_bytes'], 'forwarded': event['forwarded'],
                         'upstream_code': response.get('error_code'), 'accepted_txid': txid,
                         'response_lost': event.get('response_lost', False),
                         'response_held': event.get('response_held', False)})
    accepted = [a['accepted_txid'] for a in attempts if a['accepted_txid'] is not None]
    if len(accepted) != 1 or not re.fullmatch('[0-9a-f]{64}', accepted[0]):
        raise RuntimeError('expected exactly one node-accepted transaction')
    txid = accepted[0]
    mempool_after = rpc('getrawmempool')
    raw_hash = hashlib.sha256(bytes.fromhex(rpc('getrawtransaction', [txid, 0]))).hexdigest()
    recovery_endpoint = ENDPOINT
    secondary = None
    try:
        if name in ('indexer-restart', 'outage', 'alternate-indexer'):
            intervention['old_pid'] = primary.process.pid
            primary.stop()
            intervention['indexer_stopped'] = True
            if name == 'outage':
                started = time.monotonic_ns()
                with grpc.secure_channel('localhost:9067', grpc.ssl_channel_credentials(
                        root_certificates=(STATE / 'cert.pem').read_bytes())) as channel:
                    try:
                        grpc.channel_ready_future(channel).result(timeout=1)
                        intervention['endpoint_unavailable'] = False
                    except grpc.FutureTimeoutError:
                        intervention['endpoint_unavailable'] = True
                time.sleep(12)
                intervention['outage_elapsed_ns'] = time.monotonic_ns() - started
            if name == 'alternate-indexer':
                secondary = Indexer(9077)
                intervention.update(original_indexer_stopped=True, original_port=9067,
                                    recovery_port=9077, fresh_indexer_state=not secondary.state_dir.exists())
                secondary.start()
                recovery_endpoint = secondary.endpoint
            else:
                intervention['new_pid'] = primary.start()
        before_mining = transaction_status(wallet('alice', 'transactions', server=recovery_endpoint), txid)
        if name != 'no-mining':
            rpc('generate', [3])
        after = synchronize(recovery_endpoint)
        history = wallet('alice', 'transactions', server=recovery_endpoint)
        node_tx = rpc('getrawtransaction', [txid, 1])
        return {'name': name, 'intent': {'amount': amount}, 'attempts': attempts,
                'recipient': {'before': balances['bob'], 'after': after['bob']},
                'wallet': {'after_reopen': before_mining, 'after_sync': transaction_status(history, txid)},
                'node': {'mempool_before': mempool_before, 'mempool_after_submit': mempool_after,
                         'mempool_final': rpc('getrawmempool'),
                         'transaction': {'txid': txid, 'sha256': raw_hash,
                                         'confirmations': node_tx.get('confirmations', 0)}},
                'intervention': intervention}
    finally:
        if secondary is not None:
            secondary.stop()
        if primary.process is None:
            primary.start()


def run_tests():
    report = {'schema_version': 2, 'status': 'running', 'sources': SOURCES,
              'architecture': platform.machine(),
              'testkit_version': importlib.metadata.version('wallet-privacy-testkit'),
              'binaries': {name: hashlib.sha256(Path('/usr/local/bin', name).read_bytes()).hexdigest()
                           for name in ('zingo-cli', 'lightwalletd')},
              'scenarios': [], 'negative_controls': []}
    output = Path('/output/report.json')
    try:
        with indexer() as primary:
            emit('mining disposable coinbase funds')
            rpc('generate', [102])
            synchronize()
            emit('shielding matured funds')
            wallet('alice', 'quickshield')
            rpc('generate', [3])
            if synchronize()['alice'] <= 2_000_000:
                raise RuntimeError('wallet funding failed')
            recipient = json.loads((STATE / 'addresses.json').read_text())['bob']
            for name in ('after-once', 'after-hold', 'indexer-restart', 'outage', 'alternate-indexer', 'no-mining'):
                emit(name)
                row = exercise(name, recipient, 100_000, primary)
                key = 'negative_controls' if name == 'no-mining' else 'scenarios'
                report[key].append(row)
                output.write_text(json.dumps(report, indent=2) + '\n')
                if key == 'scenarios' and check_scenario(row):
                    raise RuntimeError(f'{name}: {check_scenario(row)}')
            report['verification'] = verify_recovery_report(report)
            rpc('generate', [3])  # Settle the intentionally unconfirmed negative control.
            synchronize()
            if os.environ.get('WPT_STUDY') == '1':
                from study_run import run_study
                run_study(recipient)
            else:
                from privacy_run import run_privacy
                run_privacy(recipient)
        report['status'] = 'pass'
    except BaseException as error:
        report['status'] = 'fail'
        report['error_type'] = type(error).__name__
        raise
    finally:
        output.write_text(json.dumps(report, indent=2) + '\n')
    emit('pass')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'bootstrap', 'test'])
    action = parser.parse_args().action
    {'init': initialize, 'bootstrap': bootstrap, 'test': run_tests}[action]()
