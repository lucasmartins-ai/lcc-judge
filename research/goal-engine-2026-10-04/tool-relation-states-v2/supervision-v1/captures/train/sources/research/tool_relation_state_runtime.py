"""Separate varied-state worker image using original immutable pinned dependencies.

Reuses the shared bounded transport, never host measurements. The previous image
and source receipts stay unchanged. Local derived-image digests are not assumed
usable in Dockerfile FROM; build directly from the original fixed Python base and
install the exact checked package/wheel bytes offline inside the new image.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import uuid

from replay.sandbox import container_argv
from research.tool_measurement_runtime import BASE,_run_trusted_request
from research.tool_measurement_worker import validate_request
from research.tool_relation_runtime import dependency_manifest as original_dependencies,ARTIFACTS

ROOT=Path(__file__).resolve().parents[1]
IMAGE='lcc-tool-relation-states:local'
PROFILE='trusted-tool-relation-states/0.2'
SOURCES=['research/tool_relation_state_worker.py','research/tool_relation_state_runtime.py',
         'research/tool_relation_worker.py','research/tool_relation_runtime.py',
         'research/tool_measurement_worker.py','research/tool_measurement_runtime.py','replay/sandbox.py']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def dependency_manifest():
    return original_dependencies()


def source_identity():
    files={name:sha(ROOT/name) for name in SOURCES};dependencies=dependency_manifest()
    dep_sha=hashlib.sha256(json.dumps(dependencies,sort_keys=True).encode()).hexdigest()
    source_sha=hashlib.sha256(json.dumps(dict(sources=files,dependencies=dependencies),sort_keys=True).encode()).hexdigest()
    return source_sha,files,dep_sha


def runtime_identity():
    docker=shutil.which('docker')
    if docker is None:return None
    try:
        result=subprocess.run([docker,'image','inspect',IMAGE],capture_output=True,text=True,timeout=5)
        if result.returncode:return None
        info=json.loads(result.stdout)[0];source_sha,unused,dep_sha=source_identity()
        labels=info['Config'].get('Labels',{})
        if (labels.get('lcc.tool-relation-states.source-sha256')!=source_sha
                or labels.get('lcc.tool-relation-states.dependency-sha256')!=dep_sha or info['Config'].get('Volumes')):
            return None
        return dict(docker=docker,image_id=info['Id'],source_sha256=source_sha,dependency_sha256=dep_sha,
                    profile=PROFILE,os=info['Os'],architecture=info['Architecture'])
    except (OSError,ValueError,KeyError,RuntimeError,subprocess.TimeoutExpired):return None


def measurement_argv(identity,name):
    argv=container_argv(identity,name)
    argv[argv.index('lcc.fixture-run=true')]='lcc.tool-relation-state-run=true'
    argv[argv.index('LCC_FIXTURE_WORKER=1')]='LCC_TOOL_RELATION_STATE_WORKER=1'
    # Existing fixed Git helper checks its own installed immutable module too.
    position=argv.index(identity['image_id']);argv[position:position]=['--env','LCC_TOOL_RELATION_WORKER=1']
    argv[-3:]=['python','-I','-m','research.tool_relation_state_worker']
    return argv


def measure_batch(request,timeout=45):
    validate_request(request)
    if type(timeout) not in (int,float) or not 0<timeout<=60:raise ValueError('Bounded worker timeout required')
    identity=runtime_identity()
    if identity is None:return dict(status='UNKNOWN',error='trusted_relation_state_worker_unavailable',profile=PROFILE)
    name='lcc-tool-relation-states-'+uuid.uuid4().hex
    return _run_trusted_request(request,identity,measurement_argv(identity,name),name,timeout,PROFILE)


def build_recipe(source_sha,dep_sha):
    return (f'FROM {BASE}\nENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1\n'
        'COPY deps/ /opt/lcc-tool-deps/\nCOPY install-deps.py /opt/install-deps.py\n'
        'RUN ["python", "/opt/install-deps.py"]\n'
        'COPY tool_relation_state_worker.py tool_relation_worker.py tool_measurement_worker.py /usr/local/lib/python3.13/site-packages/research/\n'
        f'LABEL lcc.tool-relation-states.source-sha256="{source_sha}" lcc.tool-relation-states.dependency-sha256="{dep_sha}"\n'
        'USER 65534:65534\n')


def build(out):
    if out.exists():raise FileExistsError('New immutable build recipe destination required')
    docker=shutil.which('docker')
    if docker is None:raise RuntimeError('Docker required; no host dependency/tool fallback')
    subprocess.run([docker,'image','inspect',BASE],stdout=subprocess.DEVNULL,check=True)
    dependencies=dependency_manifest();source_sha,files,dep_sha=source_identity()
    for name,wanted in dependencies['files'].items():
        if Path(name).name!=name or sha(ARTIFACTS/name)!=wanted:raise ValueError('Pinned dependency blob identity changed')
    out.mkdir(parents=True);(out/'deps').mkdir()
    for name in dependencies['files']:(out/'deps'/name).write_bytes((ARTIFACTS/name).read_bytes())
    for name in SOURCES:
        target=out/'sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
        if sha(target)!=files[name]:raise ValueError('Source changed during build snapshot')
    for name in ['research/tool_relation_state_worker.py','research/tool_relation_worker.py','research/tool_measurement_worker.py']:
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
    (out/'Dockerfile').write_text(build_recipe(source_sha,dep_sha))
    (out/'dependency-manifest.json').write_text(json.dumps(dependencies,indent=2)+'\n')
    subprocess.run([docker,'build','--pull=false','--network=none','-t',IMAGE,str(out)],check=True)
    identity=runtime_identity()
    if identity is None:raise RuntimeError('Separate built image identity not verified')
    result=dict(base=BASE,sources=files,source_sha256=source_sha,dependencies=dependencies,dependency_sha256=dep_sha,
        runtime=identity,build_RUN_network_disabled=True,
        network_scope='Exact pinned base may require Docker registry metadata resolution; dependency install/RUN has network=none and no live indexes')
    (out/'build.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['build','status'])
    parser.add_argument('--out',type=Path,default=ROOT/'research/goal-engine-2026-10-04/tool-relation-states-v2/build-recipe')
    args=parser.parse_args();print(json.dumps(build(args.out) if args.action=='build' else runtime_identity(),indent=2))
