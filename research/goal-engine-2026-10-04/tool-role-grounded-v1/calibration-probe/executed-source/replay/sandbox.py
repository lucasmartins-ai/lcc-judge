"""Bounded Docker worker for generated fixture programs; never runs them on host.

The AST checks define fixture APIs, not a security boundary. Docker is required;
missing/stale runtime returns UNKNOWN. No mounts, credentials or network enter it.
Build explicitly with `python -m replay.sandbox build`; inference never pulls images.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parent
IMAGE = 'lcc-judge-fixtures:local'
PROFILE = 'lcc-fixture-container/0.1'
SOURCE_FILES = ['tasks.py', 'real_fixtures.py', 'outcome_verifier.py', 'sandbox.py', 'sandbox_worker.py']
MAX_INPUT_BYTES = 131072
MAX_OUTPUT_BYTES = 65536
ALLOWED_MODULES = {'contextlib', 'functools', 'json', 'collections', 'decimal',
                   'math', 're', 'threading', 'time', 'unittest'}


def fixture_namespace(source, filename):
    """Limit fixture syntax and capabilities. This is not the OS security boundary."""
    require_worker()
    tree = ast.parse(source)
    forbidden = {'open', 'eval', 'exec', 'compile', 'input', 'globals', 'locals',
                 'vars', 'getattr', 'setattr', 'delattr', 'dir', 'breakpoint',
                 'exit', 'quit', 'os', 'sys', 'builtins', 'subprocess', 'socket',
                 'inspect', 'importlib'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [item.name for item in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module]
            if node.level or any(item.name.startswith('_') for item in node.names):
                raise ValueError('Import outside fixture API')
        else:
            modules = []
        if any(module not in ALLOWED_MODULES for module in modules):
            raise ValueError('Import outside fixture API')
        if isinstance(node, ast.Name) and (node.id.startswith('__') or node.id in forbidden):
            raise ValueError('Name outside fixture API')
        if isinstance(node, ast.Attribute) and (node.attr.startswith('_') or node.attr in forbidden):
            raise ValueError('Attribute outside fixture API')
    safe = {name: value for name, value in vars(builtins).items()
            if name not in forbidden and not name.startswith('_')}

    def limited_import(name, globals=None, locals=None, fromlist=(), level=0):
        if (level or name not in ALLOWED_MODULES
                or any(item.startswith('_') for item in fromlist)):
            raise ValueError('Import outside fixture API')
        return builtins.__import__(name, globals, locals, fromlist, level)

    safe.update(__import__=limited_import, __build_class__=builtins.__build_class__)
    scope = {'__builtins__': safe, '__name__': 'fixture_program'}
    exec(compile(tree, filename, 'exec'), scope)
    return scope


def source_digest():
    files = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in SOURCE_FILES}
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(), files


def require_worker():
    # Prevent accidental direct host execution. OS containment is enforced by run_check.
    if (os.environ.get('LCC_FIXTURE_WORKER') != '1' or not Path('/.dockerenv').is_file()
            or not str(ROOT).startswith('/opt/lcc-fixture/')):
        raise RuntimeError('Generated code requires the confined container worker')


def runtime_identity():
    docker = shutil.which('docker')
    if docker is None:
        return None
    try:
        proc = subprocess.run([docker, 'image', 'inspect', IMAGE], capture_output=True, text=True, timeout=5)
        if proc.returncode:
            return None
        info = json.loads(proc.stdout)[0]
        expected, _ = source_digest()
        if info['Config'].get('Labels', {}).get('lcc.fixture.source-sha256') != expected:
            return None
        if info['Config'].get('Volumes'):
            return None
        return dict(docker=docker, image_id=info['Id'], source_sha256=expected,
                    profile=PROFILE, os=info['Os'], architecture=info['Architecture'])
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError):
        return None


def container_argv(identity, name):
    return [identity['docker'], 'run', '--rm', '--pull=never', '--init', '-i',
            '--name', name, '--label', 'lcc.fixture-run=true', '--network=none',
            '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
            '--pids-limit=64', '--memory=256m', '--memory-swap=256m', '--cpus=1',
            '--ulimit', 'nofile=64:64', '--log-driver=none', '--user=65534:65534',
            '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m', '--workdir=/tmp',
            '--env', 'LCC_FIXTURE_WORKER=1', identity['image_id'],
            'python', '-I', '/opt/lcc-fixture/replay/sandbox_worker.py']


def run_check(task_number, source, *, recipe='candidate', timeout=12):
    request = json.dumps(dict(task_number=task_number, source=source, recipe=recipe)).encode()
    if len(request) > MAX_INPUT_BYTES:
        return dict(passed=None, reason='sandbox_input_limit')
    identity = runtime_identity()
    if identity is None:
        return dict(passed=None, reason='sandbox_unavailable', sandbox_profile=PROFILE)
    name = 'lcc-fixture-' + uuid.uuid4().hex
    proc = None
    buffers = [bytearray(), bytearray()]
    overflow = threading.Event()
    threads = []
    reason = None

    def drain(stream, target):
        try:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                remaining = MAX_OUTPUT_BYTES - len(target)
                target.extend(chunk[:max(0, remaining)])
                if len(chunk) > remaining:
                    overflow.set()
        except (ValueError, OSError):
            pass

    def send(stream):
        try:
            stream.write(request)
            stream.close()
        except (BrokenPipeError, OSError, ValueError):
            pass

    try:
        proc = subprocess.Popen(container_argv(identity, name), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for stream, target in [(proc.stdout, buffers[0]), (proc.stderr, buffers[1])]:
            thread = threading.Thread(target=drain, args=(stream, target), daemon=True)
            threads.append(thread)
            thread.start()
        writer = threading.Thread(target=send, args=(proc.stdin,), daemon=True)
        threads.append(writer)
        writer.start()
        deadline = time.monotonic() + timeout
        while proc.poll() is None:
            if overflow.is_set():
                reason = 'sandbox_output_limit'
                break
            if time.monotonic() >= deadline:
                reason = 'verifier_timeout'
                break
            try:
                proc.wait(timeout=min(.1, max(.001, deadline - time.monotonic())))
            except subprocess.TimeoutExpired:
                pass
    except OSError:
        reason = 'sandbox_unavailable'
    finally:
        # Removing the unique container kills its entire PID namespace, including children.
        try:
            subprocess.run([identity['docker'], 'rm', '--force', name],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            reason = 'sandbox_cleanup_failed'
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                reason = 'sandbox_cleanup_failed'
            for thread in threads:
                thread.join(timeout=1)
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                stream.close()
    if reason:
        return dict(passed=None, reason=reason, sandbox=identity)
    if overflow.is_set():
        return dict(passed=None, reason='sandbox_output_limit', sandbox=identity)
    if proc.returncode != 0:
        return dict(passed=None, reason='verifier_process_error', sandbox=identity)
    try:
        result = json.loads(buffers[0])
        if (not isinstance(result, dict) or 'passed' not in result
                or (result['passed'] is not None and type(result['passed']) is not bool)):
            raise ValueError('Invalid worker result')
    except (ValueError, TypeError):
        return dict(passed=None, reason='verifier_process_error', sandbox=identity)
    result['sandbox'] = identity
    return result


def build_image(base='python:3.13-slim'):
    docker = shutil.which('docker')
    if docker is None:
        raise RuntimeError('Docker is required to build the fixture worker')
    info = json.loads(subprocess.check_output([docker, 'image', 'inspect', base], text=True))[0]
    digests = info.get('RepoDigests', [])
    if not digests:
        raise RuntimeError('Pull the official Python base image once before building; a digest is required')
    base_digest = digests[0]
    digest, files = source_digest()
    with tempfile.TemporaryDirectory(prefix='lcc-fixture-build-') as tmp:
        context = Path(tmp)
        package = context / 'replay'
        package.mkdir()
        (package / '__init__.py').write_text('')
        for name in SOURCE_FILES:
            shutil.copyfile(ROOT / name, package / name)
        (context / 'Dockerfile').write_text(
            f'FROM {base_digest}\n'
            'ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1\n'
            f'LABEL lcc.fixture.source-sha256="{digest}"\n'
            'COPY replay /opt/lcc-fixture/replay\n'
            'USER 65534:65534\n')
        subprocess.run([docker, 'build', '--pull=false', '--network=none', '-t', IMAGE, str(context)], check=True)
    return dict(base_digest=base_digest, sources=files, runtime=runtime_identity())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['build', 'status'])
    parser.add_argument('--base', default='python:3.13-slim')
    args = parser.parse_args()
    print(json.dumps(build_image(args.base) if args.action == 'build' else runtime_identity(), indent=2))
