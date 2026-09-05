#!/usr/bin/env python3
"""Build and run a fresh isolated Compose lab; remove its disposable state afterward."""

import argparse
import json
import os
import subprocess
import uuid
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new directory for the sanitized report')
    parser.add_argument('--context', help='Docker context; defaults to the active Docker context')
    parser.add_argument('--skip-build', action='store_true', help='reuse the previously built local lab image')
    parser.add_argument('--keep-state-on-failure', action='store_true',
                        help='retain this disposable project for local debugging if a step fails')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    project = 'wpt-' + uuid.uuid4().hex[:12]
    docker = ['docker'] + (['--context', args.context] if args.context else [])
    compose = docker + ['compose', '-p', project, '-f', str(Path(__file__).with_name('compose.yaml'))]
    env = dict(os.environ, WPT_OUTPUT=str(output))
    print(json.dumps({'project': project, 'output': str(output)}), flush=True)

    def call(*arguments, **kwargs):
        return subprocess.run([*compose, *arguments], env=env, check=True, **kwargs)

    passed = False
    try:
        if not args.skip_build:
            with (output / 'build.log').open('w') as log:
                print('Building pinned wallet/indexer images; see build.log for progress.', flush=True)
                call('build', 'lab', stdout=log, stderr=subprocess.STDOUT)
        call('run', '--rm', '--no-deps', 'lab', 'init')
        call('up', '-d', 'zebra')
        call('run', '--rm', '--no-deps', 'lab', 'bootstrap')
        call('restart', 'zebra')
        call('run', '--rm', '--no-deps', 'lab', 'test')
        report = json.loads((output / 'report.json').read_text())
        if report['status'] != 'pass' or len(report['scenarios']) != 2:
            raise RuntimeError('lab did not produce a complete passing report')
        print(json.dumps(report, indent=2))
        passed = True
    finally:
        # The random project name belongs only to this invocation. Never prune
        # the engine or touch other projects, networks, images, or volumes.
        if passed or not args.keep_state_on_failure:
            call('down', '--volumes', '--remove-orphans', timeout=120)
        else:
            print(f'Failed project {project} retained for local debugging; its volume contains disposable wallet secrets.', flush=True)


if __name__ == '__main__':
    main()
