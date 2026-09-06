"""Repeated, predeclared privacy sessions with a calibration-only frozen detector."""
import hashlib
import json
import platform
import re
import subprocess
import threading
import time
from pathlib import Path

from lab import STATE, emit, parsed, rpc, synchronize, wallet, orchard_balance
from privacy_run import InteractiveWallet
from network import StreamConditioner
from wallet_privacy_testkit.capture import TLSForwarder, TraceRecorder
from wallet_privacy_testkit.study import freeze_detector, analyze_study

from wallet_privacy_testkit.study_design import make_plan, CONDITIONS


def devtool(command, arguments=(), endpoint='127.0.0.1:9067', *, name='devtool'):
    args = ['zcash-devtool', 'wallet', '-w', str(STATE / name), command, *arguments]
    if command in ('init', 'sync', 'pay'):
        args += ['-s', endpoint, '--connection', 'direct']
    result = subprocess.run(args, input='\n', capture_output=True, text=True, timeout=180)
    with (STATE / 'devtool-commands.log').open('a') as log:
        log.write(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f'devtool {command} failed; exit={result.returncode}')
    return result.stdout


class DevelopmentWallet:
    def __init__(self, endpoint, name):
        self.name = name
        self.endpoint = endpoint
        self.sync()

    def sync(self):
        devtool('sync', endpoint=self.endpoint, name=self.name)

    def wait_until(self, timestamp):
        time.sleep(max(0, (timestamp - time.monotonic_ns()) / 1e9))

    def send(self, recipient, amount):
        started = time.monotonic_ns()
        output = devtool('pay', ['--identity', str(STATE / (self.name + '-age.txt')),
            '--payment-uri', f'zcash:{recipient}?amount={amount / 100_000_000:.8f}',
            '--disable-confirmation'], self.endpoint, name=self.name)
        txids = re.findall(r'^([0-9a-f]{64})$', output, re.MULTILINE)
        if len(txids) != 1:
            raise RuntimeError('devtool payment did not return one transaction ID')
        return {'start_ns': started, 'end_ns': time.monotonic_ns(), 'txid': txids[0]}

    def close(self):
        pass


def initialize_devtool(name):
    (STATE / name).mkdir()
    upgrades = ['overwinter', 'sapling', 'blossom', 'heartwood', 'canopy', 'nu5', 'nu6', 'nu6_1', 'nu6_2']
    (STATE / 'devtool-heights.toml').write_text(''.join(f'{u} = 1\n' for u in upgrades) + 'nu6_3 = "never"\n')
    devtool('init', ['--name', 'disposable-study', '--identity', str(STATE / (name + '-age.txt')),
                    '-n', 'regtest', '--activation-heights', str(STATE / 'devtool-heights.toml')], name=name)
    output = devtool('list-addresses', ['--receiver', 'orchard'], name=name)
    addresses = re.findall(r'uregtest1[0-9a-z]+', output)
    if len(addresses) != 1:
        raise RuntimeError('missing development wallet Orchard address')
    return addresses[0]


def run_session(output, spec, recipient):
    name = 'study-' + spec['sender_state_id']
    folder = STATE / name
    if folder.exists():
        raise RuntimeError('study sender directory already exists')
    created_ns = time.monotonic_ns()
    if spec['wallet'] == 'zingolib':
        sender = parsed(wallet(name, 'addresses'))[0]['encoded_address']
        initial_balance = orchard_balance(wallet(name, 'balance', sync=True))
    else:
        sender = initialize_devtool(name)
        devtool('sync', name=name)
        initial_balance = json.loads(devtool('balance', ['--json'], name=name))['total']
    if initial_balance != 0:
        raise RuntimeError('fresh study sender must start empty')
    sender_id = hashlib.sha256(sender.encode()).hexdigest()
    # Funding is outside every measurement interval, with the same declared
    # arrangement for both implementations; no real funds or fixed seeds.
    synchronize()
    funding = parsed(wallet('alice', 'quicksend', [json.dumps(
        [{'address': sender, 'amount': 60_000} for _ in range(8)])]))['txids']
    if len(funding) != 1:
        raise RuntimeError('study funding must produce one transaction')
    rpc('generate', [10])
    before = synchronize()['bob']
    if spec['wallet'] == 'zcash-devtool':
        devtool('sync', name=name)
        funded_balance = json.loads(devtool('balance', ['--json'], name=name))['orchard_spendable']
    else:
        funded_balance = orchard_balance(wallet(name, 'balance', sync=True))
    if funded_balance != 480_000:
        raise RuntimeError('fresh sender funding balance differs from plan')
    funding_confirmations = rpc('getrawtransaction', [funding[0], 1]).get('confirmations', 0)
    if funding_confirmations < 10:
        raise RuntimeError('study funding must settle before capture')
    trace = output / (spec['id'] + '.trace.jsonl')
    conditioner = StreamConditioner(('127.0.0.1', 9067), seed=spec['conditioner_seed'], **CONDITIONS[spec['condition']])
    recorder = TraceRecorder(trace)
    forwarder = TLSForwarder(conditioner.server_address, recorder)
    client, miner = None, None
    stop, errors = threading.Event(), []
    try:
        port = forwarder.server_address[1]
        client = (InteractiveWallet(f'https://127.0.0.1:{port}', STATE / (spec['id'] + '.log'), name=name)
                  if spec['wallet'] == 'zingolib' else DevelopmentWallet(f'127.0.0.1:{port}', name))
        def mine():
            while not stop.wait(3):
                try:
                    rpc('generate', [1])
                except Exception as error:
                    errors.append(type(error).__name__)
                    return
        miner = threading.Thread(target=mine, daemon=True); miner.start()
        client.wait_until(time.monotonic_ns() + 6_000_000_000)
        recorder.emit('observation_boundary', 0)
        start = time.monotonic_ns(); end = start + 96_000_000_000
        payments, sync_times = [], []
        schedule = sorted([(s, 'sync') for s in range(spec['sync_offset_ns'], 96_000_000_000, 6_000_000_000)] + [(s, 'send') for s in spec['payment_offsets_ns']])
        for second, action in schedule:
            client.wait_until(start + second)
            if action == 'sync':
                sync_times.append(time.monotonic_ns()); client.sync()
            else:
                payment = client.send(recipient, 50_000)
                payment['scheduled_start_ns'] = start + second
                payments.append(payment)
        client.wait_until(end)
        recorder.emit('observation_boundary', 0)
    finally:
        stop.set()
        if miner:
            miner.join(timeout=125)
            if miner.is_alive(): errors.append('miner did not stop')
        if client: client.close()
        forwarder.close(); conditioner.close(); recorder.close()
    if errors or conditioner.errors:
        raise RuntimeError(f'study background failure: {errors + conditioner.errors}')
    rpc('generate', [10])
    after = synchronize()['bob']
    for payment in payments:
        payment['confirmations'] = rpc('getrawtransaction', [payment['txid'], 1]).get('confirmations', 0)
    return dict(spec, trace=trace.name, trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest(),
                sender_address_sha256=sender_id, sender_created_ns=created_ns,
                sender_directory_was_absent=True, sender_initial_balance=initial_balance,
                sender_funded_balance=funded_balance, start_ns=start, end_ns=end, payments=payments, sync_command_times_ns=sync_times,
                payment_amount=50_000, recipient_before=before, recipient_after=after,
                funding_txid=funding[0], funding_confirmations=funding_confirmations)


def run_study(recipient):
    output = Path('/output')
    design = json.loads((output / 'study-plan.json').read_text())
    if design != make_plan(design['seed']):
        raise RuntimeError('study plan differs from the versioned seeded design')
    planned = design['sessions']
    manifest = {'schema_version': 2, 'window_ns': design['window_ns'], 'plan_sha256': hashlib.sha256((output / 'study-plan.json').read_bytes()).hexdigest(),
                'architecture': platform.machine(), 'sessions': [],
                'binaries': {n: hashlib.sha256(Path('/usr/local/bin', n).read_bytes()).hexdigest() for n in ('zingo-cli', 'zcash-devtool', 'lightwalletd')}}
    path = output / 'study-manifest.json'
    for spec in planned:
        if spec['split'] == 'evaluation' and 'detector_sha256' not in manifest:
            model = freeze_detector(output, manifest['sessions'], design['window_ns'])
            model_path = output / 'frozen-detector.json'
            model_path.write_text(json.dumps(model, indent=2) + '\n')
            manifest['detector_sha256'] = hashlib.sha256(model_path.read_bytes()).hexdigest()
            manifest['frozen_time_ns'] = time.monotonic_ns()
            path.write_text(json.dumps(manifest, indent=2) + '\n')
            emit('detector frozen before evaluation')
        emit(spec['id'])
        row = run_session(output, spec, recipient)
        manifest['sessions'].append(row)
        path.write_text(json.dumps(manifest, indent=2) + '\n')
    result = analyze_study(path)
    (output / 'study-report.json').write_text(json.dumps(result, indent=2) + '\n')
