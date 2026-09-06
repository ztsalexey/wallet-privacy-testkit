"""Continuous capture around a persistent wallet with background sync and mining."""

import hashlib
import json
import os
import pty
import re
import select
import subprocess
import threading
import time
from pathlib import Path

from lab import STATE, emit, rpc, synchronize, wallet_args
from wallet_privacy_testkit.capture import TLSForwarder, TraceRecorder
from wallet_privacy_testkit.privacy import analyze_privacy


class InteractiveWallet:
    def __init__(self, endpoint, log_path):
        self.master, slave = pty.openpty()
        self.log = log_path.open('wb')
        args = [a for a in wallet_args('alice', 'balance', server=endpoint)[:-1] if a != '--nosync']
        self.process = subprocess.Popen(args, stdin=slave, stdout=slave, stderr=slave,
                                        env=dict(os.environ, TERM='dumb'))
        os.close(slave)
        try:
            self.read_prompt()
        except BaseException:
            self.close()
            raise

    def read_prompt(self):
        data = bytearray()
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            if select.select([self.master], [], [], 0.2)[0]:
                try:
                    chunk = os.read(self.master, 65536)
                except OSError as error:
                    raise RuntimeError('interactive wallet closed before prompt') from error
                self.log.write(chunk)
                self.log.flush()
                data.extend(chunk)
                if b'>> ' in data:
                    return data.decode(errors='replace')
            if self.process.poll() is not None:
                raise RuntimeError('interactive wallet exited unexpectedly')
        raise RuntimeError('interactive wallet prompt timeout')

    def wait_until(self, timestamp):
        while time.monotonic_ns() < timestamp:
            if select.select([self.master], [], [], min(0.2, max(0, (timestamp - time.monotonic_ns()) / 1e9)))[0]:
                self.log.write(os.read(self.master, 65536))
                self.log.flush()
            if self.process.poll() is not None:
                raise RuntimeError('wallet exited during continuous capture')

    def send(self, recipient, amount):
        command = 'quicksend ' + json.dumps(recipient) + ' ' + str(amount) + '\n'
        started = time.monotonic_ns()
        os.write(self.master, command.encode())
        output = self.read_prompt()
        ended = time.monotonic_ns()
        match = re.search(r'"txids"\s*:\s*\[\s*"([0-9a-f]{64})"\s*\]', output)
        if not match:
            raise RuntimeError('interactive payment did not return one transaction ID')
        return {'start_ns': started, 'end_ns': ended, 'txid': match[1]}

    def sync(self):
        # Completed tasks keep their handle until polled; clear it before
        # requesting another sync, as the interactive CLI does at prompts.
        os.write(self.master, b'sync poll\n')
        output = self.read_prompt()
        if 'Error:' in output:
            raise RuntimeError('periodic wallet sync failed')
        if 'Sync task is not complete.' in output:
            return
        os.write(self.master, b'sync run\n')
        output = self.read_prompt()
        if 'Error:' in output:
            raise RuntimeError('periodic wallet sync failed')

    def close(self):
        if self.process.poll() is None:
            try:
                os.write(self.master, b'quit\n')
                self.process.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait()
        os.close(self.master)
        self.log.close()


def run_privacy(recipient):
    output = Path('/output')
    manifest = {'schema_version': 1, 'window_ns': 4_000_000_000,
                'design': '72-second continuous sessions; persistent CLI; sync commands every 6 seconds; blocks every 3 seconds',
                'sessions': []}
    for split, payment_seconds in [('calibration', [14, 34, 54]), ('evaluation', [10, 38, 58])]:
        emit(f'continuous privacy {split}')
        before = synchronize()['bob']
        trace = output / f'{split}.trace.jsonl'
        recorder = TraceRecorder(trace)
        forwarder = TLSForwarder(('localhost', 9067), recorder)
        client = None
        stop = threading.Event()
        errors = []
        miner = None
        try:
            client = InteractiveWallet(f'https://127.0.0.1:{forwarder.server_address[1]}', STATE / f'{split}-interactive.log')
            def mine():
                while not stop.wait(3):
                    try:
                        rpc('generate', [1])
                    except BaseException as error:
                        errors.append(type(error).__name__)
                        return
            miner = threading.Thread(target=mine, daemon=True)
            miner.start()
            # Startup stays in the trace, but is outside the fixed evaluation interval.
            client.wait_until(time.monotonic_ns() + 6_000_000_000)
            start = time.monotonic_ns()
            end = start + 72_000_000_000
            payments = []
            sync_commands = []
            schedule = sorted([(s, 'sync') for s in range(0, 72, 6)] +
                              [(s, 'send') for s in payment_seconds])
            for second, action in schedule:
                client.wait_until(start + second * 1_000_000_000)
                if action == 'sync':
                    sync_commands.append(time.monotonic_ns())
                    client.sync()
                else:
                    payments.append(client.send(recipient, 50_000))
            client.wait_until(end)
        finally:
            stop.set()
            if miner is not None:
                miner.join(timeout=125)
                if miner.is_alive():
                    errors.append('miner did not stop')
            if client is not None:
                client.close()
            forwarder.close()
            recorder.close()
        if errors:
            raise RuntimeError(f'background mining failed: {errors}')
        rpc('generate', [3])
        after = synchronize()['bob']
        for payment in payments:
            payment['confirmations'] = rpc('getrawtransaction', [payment['txid'], 1]).get('confirmations', 0)
        manifest['sessions'].append({'split': split, 'trace': trace.name,
            'trace_sha256': hashlib.sha256(trace.read_bytes()).hexdigest(),
            'start_ns': start, 'end_ns': end, 'payments': payments,
            'sync_command_times_ns': sync_commands,
            'payment_amount': 50_000, 'recipient_before': before, 'recipient_after': after})
        (output / 'privacy-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    result = analyze_privacy(output / 'privacy-manifest.json')
    (output / 'privacy-report.json').write_text(json.dumps(result, indent=2) + '\n')
