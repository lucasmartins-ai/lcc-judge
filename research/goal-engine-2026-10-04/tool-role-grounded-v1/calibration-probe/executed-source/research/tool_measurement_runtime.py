"""Bounded trusted-tool worker, separate from generated-fixture execution API."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

from replay.sandbox import container_argv
from research.tool_measurement_worker import validate_request

ROOT=Path(__file__).resolve().parents[1]
IMAGE='lcc-tool-measurements:local'
BASE='python@sha256:3dd7cc108ec1493442514f5c2a871af6af0ec31d768ff6e378a93340c3b3db5f'
PROFILE='trusted-tool-observations/0.1'
SOURCES=['research/tool_measurement_worker.py','research/tool_measurement_runtime.py','replay/sandbox.py']
OUTPUT_LIMIT=4*1024*1024


def source_identity():
    files={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES}
    digest=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()
    return digest,files


def runtime_identity():
    docker=shutil.which('docker')
    if docker is None:
        return None
    try:
        proc=subprocess.run([docker,'image','inspect',IMAGE],capture_output=True,text=True,timeout=5)
        if proc.returncode:
            return None
        info=json.loads(proc.stdout)[0]
        digest,unused=source_identity()
        if info['Config'].get('Labels',{}).get('lcc.tool-measurement.source-sha256')!=digest or info['Config'].get('Volumes'):
            return None
        return dict(docker=docker,image_id=info['Id'],source_sha256=digest,profile=PROFILE,os=info['Os'],architecture=info['Architecture'])
    except (OSError,ValueError,KeyError,subprocess.TimeoutExpired):
        return None


def measurement_argv(identity,name):
    # Reuse the existing tested OS confinement recipe without broadening the
    # generated-fixture import/AST API. This image executes only its trusted file.
    argv=container_argv(identity,name)
    argv[argv.index('lcc.fixture-run=true')]='lcc.tool-measurement-run=true'
    argv[argv.index('LCC_FIXTURE_WORKER=1')]='LCC_TOOL_MEASUREMENT_WORKER=1'
    argv[-1]='/opt/lcc-measure/worker.py'
    return argv


def measure_batch(request,timeout=45):
    validate_request(request)
    if type(timeout) not in (int,float) or not 0<timeout<=60:
        raise ValueError('Bounded worker timeout required')
    identity=runtime_identity()
    if identity is None:
        return dict(status='UNKNOWN',error='trusted_worker_unavailable',profile=PROFILE)
    began=time.perf_counter()
    name='lcc-tool-measure-'+uuid.uuid4().hex
    argv=measurement_argv(identity,name)
    payload=json.dumps(request,allow_nan=False).encode()
    proc=None
    buffers=[bytearray(),bytearray()]
    overflow=threading.Event()
    threads=[]
    error=None
    def drain(stream,buffer):
        try:
            while True:
                chunk=stream.read(4096)
                if not chunk:
                    break
                remaining=OUTPUT_LIMIT-len(buffer)
                buffer.extend(chunk[:max(0,remaining)])
                if len(chunk)>remaining:
                    overflow.set()
        except (OSError,ValueError):
            pass
    def send(stream):
        try:
            stream.write(payload)
            stream.close()
        except (OSError,ValueError):
            pass
    try:
        proc=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        for stream,buffer in [(proc.stdout,buffers[0]),(proc.stderr,buffers[1])]:
            t=threading.Thread(target=drain,args=(stream,buffer),daemon=True)
            threads.append(t);t.start()
        t=threading.Thread(target=send,args=(proc.stdin,),daemon=True)
        threads.append(t);t.start()
        deadline=time.monotonic()+timeout
        while proc.poll() is None:
            if overflow.is_set():
                error='trusted_worker_output_limit';break
            if time.monotonic()>=deadline:
                error='trusted_worker_timeout';break
            try:
                proc.wait(timeout=min(.1,max(.001,deadline-time.monotonic())))
            except subprocess.TimeoutExpired:
                pass
    except OSError:
        error='trusted_worker_unavailable'
    finally:
        try:
            subprocess.run([identity['docker'],'rm','--force',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
        except (OSError,subprocess.TimeoutExpired):
            error='trusted_worker_cleanup_unverified'
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                error='trusted_worker_cleanup_unverified'
            for t in threads:
                t.join(timeout=1)
            for stream in (proc.stdin,proc.stdout,proc.stderr):
                stream.close()
    if overflow.is_set():
        error='trusted_worker_output_limit'
    stdout=buffers[0].decode('utf-8',errors='replace')
    stderr=buffers[1].decode('utf-8',errors='replace')
    raw=dict(request=request,request_sha256=hashlib.sha256(payload).hexdigest(),
             runtime={k:v for k,v in identity.items() if k!='docker'},container_argv=[v for v in argv[1:]],
             stdout=stdout,stderr=stderr,returncode=proc.returncode if proc is not None else None,
             elapsed_s=time.perf_counter()-began,host_measurement_executed=False,profile=PROFILE)
    if error:
        return dict(**raw,status='UNKNOWN',error=error)
    if proc is None or proc.returncode!=0:
        return dict(**raw,status='UNKNOWN',error='trusted_worker_process_error')
    try:
        parsed=json.loads(stdout)
        if (parsed['request']!=request or len(parsed['fixtures'])!=request['fixtures']
                or parsed['all_reference_checks_passed'] is not True):
            raise ValueError('Incomplete worker measurements')
    except (ValueError,KeyError,TypeError):
        return dict(**raw,status='UNKNOWN',error='trusted_worker_invalid_response')
    return dict(**raw,status='MEASURED',error=None,measurements=parsed)


def build(out):
    docker=shutil.which('docker')
    if docker is None:
        raise RuntimeError('Docker required; no host tool fallback')
    subprocess.run([docker,'image','inspect',BASE],stdout=subprocess.DEVNULL,check=True)
    digest,files=source_identity()
    out.mkdir(parents=True,exist_ok=True)
    worker=(ROOT/'research/tool_measurement_worker.py').read_bytes()
    dockerfile=(f'FROM {BASE}\nENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1\n'
                f'LABEL lcc.tool-measurement.source-sha256="{digest}"\n'
                'COPY worker.py /opt/lcc-measure/worker.py\nUSER 65534:65534\n')
    (out/'worker.py').write_bytes(worker)
    (out/'Dockerfile').write_text(dockerfile)
    subprocess.run([docker,'build','--pull=false','--network=none','-t',IMAGE,str(out)],check=True)
    result=dict(base=BASE,source_sha256=digest,sources=files,runtime=runtime_identity())
    (out/'build.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['build','status'])
    parser.add_argument('--out',type=Path,default=ROOT/'research/goal-engine-2026-10-04/tool-role-grounded-v1/build-recipe')
    args=parser.parse_args()
    print(json.dumps(build(args.out) if args.action=='build' else runtime_identity(),indent=2))
