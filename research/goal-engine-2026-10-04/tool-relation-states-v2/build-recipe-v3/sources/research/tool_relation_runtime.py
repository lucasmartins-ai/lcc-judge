"""Separate bounded relation worker, pinned dependencies and shared transport."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import uuid

from replay.sandbox import container_argv
from research.tool_measurement_runtime import BASE, _run_trusted_request
from research.tool_measurement_worker import validate_request

ROOT=Path(__file__).resolve().parents[1]
IMAGE='lcc-tool-relations:local'
PROFILE='trusted-tool-relations/0.1'
LOCKS=ROOT/'research/goal-engine-2026-10-04/semantic-next/tool-dependency-preparation'
ARTIFACTS=ROOT/'release-staging/tool-worker-deps-v1'
SOURCES=['research/tool_relation_worker.py','research/tool_relation_runtime.py',
         'research/tool_measurement_runtime.py','research/tool_measurement_worker.py','replay/sandbox.py']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dependency_manifest():
    packages=json.loads((LOCKS/'debian-packages.json').read_text())
    wheel=json.loads((LOCKS/'tenacity.json').read_text())
    files={item['filename']:item['sha256'] for item in packages['packages']}
    files[wheel['filename']]=wheel['sha256']
    return dict(base=BASE,files=files,package_versions={p['package']:p['version'] for p in packages['packages']},
                tenacity_version=wheel['version'],discovery_image=packages['download_image_id'])


def source_identity():
    files={name:sha(ROOT/name) for name in SOURCES}
    dependencies=dependency_manifest()
    dependency_sha=hashlib.sha256(json.dumps(dependencies,sort_keys=True).encode()).hexdigest()
    state=dict(sources=files,dependencies=dependencies)
    return hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest(),files,dependency_sha


def runtime_identity():
    docker=shutil.which('docker')
    if docker is None:return None
    try:
        proc=subprocess.run([docker,'image','inspect',IMAGE],capture_output=True,text=True,timeout=5)
        if proc.returncode:return None
        info=json.loads(proc.stdout)[0];source_sha,unused,dep_sha=source_identity()
        labels=info['Config'].get('Labels',{})
        if (labels.get('lcc.tool-relations.source-sha256')!=source_sha or
                labels.get('lcc.tool-relations.dependency-sha256')!=dep_sha or info['Config'].get('Volumes')):
            return None
        return dict(docker=docker,image_id=info['Id'],source_sha256=source_sha,
                    dependency_sha256=dep_sha,profile=PROFILE,os=info['Os'],architecture=info['Architecture'])
    except (OSError,ValueError,KeyError,subprocess.TimeoutExpired):
        return None


def measurement_argv(identity,name):
    argv=container_argv(identity,name)
    argv[argv.index('lcc.fixture-run=true')]='lcc.tool-relation-run=true'
    argv[argv.index('LCC_FIXTURE_WORKER=1')]='LCC_TOOL_RELATION_WORKER=1'
    argv[-3:]=['python','-I','-m','research.tool_relation_worker']
    return argv


def measure_batch(request,timeout=45):
    validate_request(request)
    if type(timeout) not in (int,float) or not 0<timeout<=60:
        raise ValueError('Bounded worker timeout required')
    identity=runtime_identity()
    if identity is None:return dict(status='UNKNOWN',error='trusted_relation_worker_unavailable',profile=PROFILE)
    name='lcc-tool-relations-'+uuid.uuid4().hex
    return _run_trusted_request(request,identity,measurement_argv(identity,name),name,timeout,PROFILE)


def build(out):
    if out.exists():raise FileExistsError('Use a new build recipe directory; retain prior attempts')
    docker=shutil.which('docker')
    if docker is None:raise RuntimeError('Docker required, no host dependency/tool fallback')
    subprocess.run([docker,'image','inspect',BASE],stdout=subprocess.DEVNULL,check=True)
    dependencies=dependency_manifest()
    # Verify private artifact identities before any install/build step.
    for name,expected in dependencies['files'].items():
        if Path(name).name!=name or sha(ARTIFACTS/name)!=expected:
            raise ValueError('Dependency artifact identity mismatch')
    source_sha,sources,dep_sha=source_identity()
    out.mkdir(parents=True);(out/'deps').mkdir()
    for name in dependencies['files']:
        (out/'deps'/name).write_bytes((ARTIFACTS/name).read_bytes())
    for name in ['research/tool_relation_worker.py','research/tool_measurement_worker.py']:
        (out/Path(name).name).write_bytes((ROOT/name).read_bytes())
    expected=json.dumps(dependencies['files'],sort_keys=True)
    installer=("import hashlib,json,pathlib,subprocess\n"
               f"expected=json.loads({expected!r})\n"
               "base=pathlib.Path('/opt/lcc-tool-deps')\n"
               "assert set(p.name for p in base.iterdir())==set(expected)\n"
               "for name,digest in expected.items():\n"
               "    assert hashlib.sha256((base/name).read_bytes()).hexdigest()==digest\n"
               "packages=[str(base/name) for name in sorted(expected) if name.endswith('.deb')]\n"
               "wheels=[str(base/name) for name in expected if name.endswith('.whl')]\n"
               "assert len(wheels)==1\n"
               "subprocess.run(['dpkg','--install',*packages],check=True)\n"
               "subprocess.run(['python','-m','pip','install','--no-index','--no-deps','--no-compile',*wheels],check=True)\n")
    (out/'install-deps.py').write_text(installer)
    dockerfile=(f'FROM {BASE}\nENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1\n'
        'COPY deps/ /opt/lcc-tool-deps/\nCOPY install-deps.py /opt/install-deps.py\n'
        'RUN ["python", "/opt/install-deps.py"]\n'
        'COPY tool_relation_worker.py tool_measurement_worker.py /usr/local/lib/python3.13/site-packages/research/\n'
        f'LABEL lcc.tool-relations.source-sha256="{source_sha}" lcc.tool-relations.dependency-sha256="{dep_sha}"\n'
        'USER 65534:65534\n')
    (out/'Dockerfile').write_text(dockerfile)
    # All historical source files are captured; only the two modules needed by
    # this worker are installed. The transport runs on host but never measures.
    for name in SOURCES:
        destination=out/'sources'/name;destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes((ROOT/name).read_bytes())
    (out/'dependency-manifest.json').write_text(json.dumps(dependencies,indent=2)+'\n')
    subprocess.run([docker,'build','--pull=false','--network=none','-t',IMAGE,str(out)],check=True)
    identity=runtime_identity()
    if identity is None:raise RuntimeError('Built image source/dependency identity not verified')
    result=dict(base=BASE,source_sha256=source_sha,sources=sources,dependency_sha256=dep_sha,
                dependencies=dependencies,runtime=identity,build_network_disabled=True)
    (out/'build.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['build','status'])
    parser.add_argument('--out',type=Path,default=ROOT/'research/goal-engine-2026-10-04/tool-relations-grounded-v1/build-recipe')
    args=parser.parse_args()
    print(json.dumps(build(args.out) if args.action=='build' else runtime_identity(),indent=2))
