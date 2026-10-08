"""Separate varied-state worker image using immutable checked parent dependencies.

Reuses the shared bounded transport, never host measurements. The previous image
and source receipts stay unchanged. A future machine must explicitly rebuild the
parent from its immutable Python/dependency recipe before building this layer.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import uuid

from replay.sandbox import container_argv
from research.tool_measurement_runtime import _run_trusted_request
from research.tool_measurement_worker import validate_request
from research.tool_relation_runtime import runtime_identity as parent_identity,dependency_manifest as parent_dependencies

ROOT=Path(__file__).resolve().parents[1]
IMAGE='lcc-tool-relation-states:local'
PROFILE='trusted-tool-relation-states/0.2'
SOURCES=['research/tool_relation_state_worker.py','research/tool_relation_state_runtime.py',
         'research/tool_relation_worker.py','research/tool_relation_runtime.py',
         'research/tool_measurement_worker.py','research/tool_measurement_runtime.py','replay/sandbox.py']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def parent_build_reference(parent):
    result=subprocess.run([parent['docker'],'image','inspect',parent['image_id']],capture_output=True,text=True,timeout=5,check=True)
    info=json.loads(result.stdout)[0]
    if info['Id']!=parent['image_id']:raise RuntimeError('Parent inspect identity changed')
    for reference in info.get('RepoDigests',[]):
        if not re.fullmatch(r'lcc-tool-relations@sha256:[0-9a-f]{64}',reference):continue
        verified=subprocess.run([parent['docker'],'image','inspect',reference],capture_output=True,text=True,timeout=5,check=True)
        if json.loads(verified.stdout)[0]['Id']==parent['image_id']:return reference
    raise RuntimeError('A verified local parent repository digest is required; bare image ID is not a Dockerfile FROM reference')


def dependency_manifest():
    parent=parent_identity()
    if parent is None:raise RuntimeError('Explicit verified previous Git/Tenacity image setup required')
    return dict(parent_runtime={k:v for k,v in parent.items() if k!='docker'},
                parent_build_reference=parent_build_reference(parent),original_dependencies=parent_dependencies())


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


def build(out):
    if out.exists():raise FileExistsError('New immutable build recipe destination required')
    parent=parent_identity()
    if parent is None:raise RuntimeError('Build the verified parent explicitly; no host fallback')
    dependencies=dependency_manifest();source_sha,files,dep_sha=source_identity()
    out.mkdir(parents=True)
    for name in SOURCES:
        target=out/'sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
        if sha(target)!=files[name]:raise ValueError('Source changed during build snapshot')
    (out/'tool_relation_state_worker.py').write_bytes((ROOT/'research/tool_relation_state_worker.py').read_bytes())
    recipe=(f"FROM {dependencies['parent_build_reference']}\n"
            'ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1\n'
            'COPY tool_relation_state_worker.py /usr/local/lib/python3.13/site-packages/research/\n'
            f'LABEL lcc.tool-relation-states.source-sha256="{source_sha}" lcc.tool-relation-states.dependency-sha256="{dep_sha}"\n'
            'USER 65534:65534\n')
    (out/'Dockerfile').write_text(recipe)
    (out/'dependency-manifest.json').write_text(json.dumps(dependencies,indent=2)+'\n')
    subprocess.run([parent['docker'],'build','--pull=false','--network=none','-t',IMAGE,str(out)],check=True)
    identity=runtime_identity()
    if identity is None:raise RuntimeError('Separate built image identity not verified')
    result=dict(parent_image_id=parent['image_id'],parent_build_reference=dependencies['parent_build_reference'],sources=files,source_sha256=source_sha,
        dependencies=dependencies,dependency_sha256=dep_sha,runtime=identity,build_network_disabled=True)
    (out/'build.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['build','status'])
    parser.add_argument('--out',type=Path,default=ROOT/'research/goal-engine-2026-10-04/tool-relation-states-v2/build-recipe')
    args=parser.parse_args();print(json.dumps(build(args.out) if args.action=='build' else runtime_identity(),indent=2))
