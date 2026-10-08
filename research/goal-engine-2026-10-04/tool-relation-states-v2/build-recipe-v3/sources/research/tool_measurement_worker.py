"""Trusted measured fixtures only. No generated source, paths or commands accepted.

Copied into a pinned, nonnetworked container; these measurements never run on host.
Values are actual command/API observations on authored fixture files, not invented
production telemetry. Stateful inode/free-space/clock fields are saved observations.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import locale
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time


def require_worker():
    if (os.environ.get('LCC_TOOL_MEASUREMENT_WORKER')!='1' or not Path('/.dockerenv').is_file()
            or not str(Path(__file__).resolve()).startswith('/opt/lcc-measure/')):
        raise RuntimeError('Tool measurements require the confined trusted worker')


def validate_request(request):
    if (not isinstance(request,dict) or set(request)!={'seed','fixtures'}
            or type(request['seed']) is not int or not 0<=request['seed']<2**31
            or type(request['fixtures']) is not int or not 1<=request['fixtures']<=64):
        raise ValueError('Only a bounded seed and fixture count are accepted')
    return request


def expected_wc(text):
    # Fixture whitespace is ASCII space/tab/newline. No claim that Python's
    # Unicode whitespace table matches every GNU wc locale/extension.
    return dict(newlines=text.count('\n'),words=len(text.split()),
                characters=len(text),bytes=len(text.encode('utf-8')))


def parse_integer_columns(text,count):
    columns=text.split()
    if len(columns)!=count:
        raise ValueError('Incomplete or extra measurement columns')
    return list(map(int,columns))


def make_content(rng,index):
    vocabulary=['cache','build','status','ação','café','東京','fila','Δ','sample','worker']
    rows=[' '.join(rng.choice(vocabulary) for _ in range(rng.randint(1,9))) for _ in range(rng.randint(2,14))]
    return '\n'.join(rows)+('\n' if index%2==0 else '')


def command(argv,cwd):
    env=dict(PATH='/usr/local/bin:/usr/bin:/bin',LANG='C.UTF-8',LC_ALL='C.UTF-8')
    proc=subprocess.run(argv,cwd=cwd,env=env,capture_output=True,text=True,timeout=3,check=False)
    if len(proc.stdout.encode())+len(proc.stderr.encode())>16384:
        raise ValueError('Tool output limit')
    return dict(argv=argv,returncode=proc.returncode,stdout=proc.stdout,stderr=proc.stderr)


def measured_fixture(seed,index):
    require_worker()
    rng=random.Random(f'{seed}:{index}')
    content=make_content(rng,index)
    records=[]
    fields={}
    checks=[]
    with tempfile.TemporaryDirectory(prefix='tool-measure-',dir='/tmp') as directory:
        base=Path(directory)
        path=base/'data.txt'
        path.write_text(content,encoding='utf-8')
        mode=rng.choice([0o600,0o640,0o644,0o700,0o755])
        path.chmod(mode)
        for link in range(index%4):
            os.link(path,base/f'hard-{link}')
        (base/'symbolic').symlink_to('data.txt')
        hole=base/'sparse.dat'
        with hole.open('wb') as stream:
            stream.seek(rng.randrange(16384,524288))
            stream.write(b'x')
        # Vary actual tmpfs consumption for free-space observations.
        (base/'allocation.bin').write_bytes(b'a'*(4096*rng.randint(1,96)))
        expected=expected_wc(content)
        for flag,key in [('--lines','newlines'),('--words','words'),('--chars','characters'),('--bytes','bytes')]:
            raw=command(['/usr/bin/wc',flag,'data.txt'],directory)
            if raw['returncode']!=0:
                raise ValueError('wc failed')
            value=int(raw['stdout'].split()[0])
            fields['wc_'+key]=value
            checks.append(dict(field='wc_'+key,expected=expected[key],actual=value,passed=value==expected[key],basis='independent fixture content counting'))
            records.append(raw)
        raw=command(['/usr/bin/stat','--printf=%s\t%b\t%B\t%h\t%i\t%a\t%o\n','data.txt'],directory)
        if raw['returncode']!=0:
            raise ValueError('stat failed')
        values=parse_integer_columns(raw['stdout'],7)
        names=['stat_size_bytes','stat_allocated_blocks','stat_block_bytes','stat_hard_links','stat_inode','stat_octal_mode','stat_io_hint_bytes']
        observed=path.stat()
        expected_stat=[len(content.encode()),observed.st_blocks,512,observed.st_nlink,observed.st_ino,int(format(mode,'o')),observed.st_blksize]
        for name,value,wanted in zip(names,values,expected_stat):
            fields[name]=value
            checks.append(dict(field=name,expected=wanted,actual=value,passed=value==wanted,basis='Python os.stat plus authored content/mode'))
        records.append(raw)
        raw=command(['/usr/bin/stat','--printf=%s\t%b\t%B\n','sparse.dat'],directory)
        if raw['returncode']!=0:
            raise ValueError('sparse stat failed')
        logical,blocks,block_bytes=parse_integer_columns(raw['stdout'],3)
        fields.update(sparse_logical_bytes=logical,sparse_allocated_bytes=blocks*block_bytes)
        records.append(raw)
        for key,flags,expected_link in [('link_entry_bytes',[],len('data.txt'.encode())),('link_target_bytes',['--dereference'],len(content.encode()))]:
            raw=command(['/usr/bin/stat',*flags,'--format=%s','symbolic'],directory)
            if raw['returncode']!=0:
                raise ValueError('symlink stat failed')
            value=int(raw['stdout'].strip())
            fields[key]=value
            checks.append(dict(field=key,actual=value,expected=expected_link,passed=value==expected_link,basis='declared link path or target content'))
            records.append(raw)
        for key,options,wanted in [('du_apparent_bytes',['--apparent-size'],logical),('du_allocated_bytes',[],blocks*block_bytes)]:
            raw=command(['/usr/bin/du','--block-size=1',*options,'sparse.dat'],directory)
            if raw['returncode']!=0:
                raise ValueError('du failed')
            value=int(raw['stdout'].split()[0])
            fields[key]=value
            checks.append(dict(field=key,actual=value,expected=wanted,passed=value==wanted,basis='independent stat logical/allocation fields'))
            records.append(raw)
        # df/statvfs snapshot is taken with no intervening fixture writes.
        raw=command(['/usr/bin/df','--block-size=1','--output=size,used,avail','data.txt'],directory)
        if raw['returncode']!=0:
            raise ValueError('df failed')
        total,used,available=parse_integer_columns(raw['stdout'].splitlines()[-1],3)
        fs=os.statvfs(path)
        fields.update(df_total_bytes=total,df_used_bytes=used,df_available_bytes=available)
        for key,value,wanted in [('df_total_bytes',total,fs.f_blocks*fs.f_frsize),
                                 ('df_used_bytes',used,(fs.f_blocks-fs.f_bfree)*fs.f_frsize),
                                 ('df_available_bytes',available,fs.f_bavail*fs.f_frsize)]:
            checks.append(dict(field=key,actual=value,expected=wanted,passed=value==wanted,basis='same filesystem os.statvfs, no intervening writes'))
        records.append(raw)
        # --output and --inodes are mutually exclusive. Explicit inode fields
        # select the inode columns without also passing the format switch.
        raw=command(['/usr/bin/df','--output=itotal,iused,iavail','data.txt'],directory)
        if raw['returncode']!=0:
            raise ValueError('df inode failed')
        itotal,iused,iavailable=parse_integer_columns(raw['stdout'].splitlines()[-1],3)
        fs=os.statvfs(path)
        fields.update(df_inode_total=itotal,df_inode_used=iused,df_inode_available=iavailable)
        for key,value,wanted in [('df_inode_total',itotal,fs.f_files),('df_inode_used',iused,fs.f_files-fs.f_ffree),('df_inode_available',iavailable,fs.f_favail)]:
            checks.append(dict(field=key,actual=value,expected=wanted,passed=value==wanted,basis='same filesystem os.statvfs inode fields'))
        records.append(raw)
        with gzip.open(base/'data.txt.gz','wb') as stream:
            stream.write(content.encode())
        raw=command(['/usr/bin/gzip','--list','data.txt.gz'],directory)
        if raw['returncode']!=0:
            raise ValueError('gzip list failed')
        compressed,uncompressed=map(int,raw['stdout'].splitlines()[-1].split()[:2])
        fields.update(gzip_compressed_bytes=compressed,gzip_uncompressed_bytes=uncompressed)
        for key,value,wanted in [('gzip_compressed_bytes',compressed,(base/'data.txt.gz').stat().st_size),('gzip_uncompressed_bytes',uncompressed,len(content.encode()))]:
            checks.append(dict(field=key,actual=value,expected=wanted,passed=value==wanted,basis='actual gzip file length and original content'))
        records.append(raw)
        printed=rng.randint(1,12)
        exit_code=rng.choice([0,2,7,42])
        # Fixed trusted source; only validated local integer literals vary.
        program=f'import sys; print("observed\\n"*{printed},end=""); sys.exit({exit_code})'
        raw=command([sys.executable,'-I','-c',program],directory)
        fields.update(command_exit_status=raw['returncode'],command_stdout_newlines=raw['stdout'].count('\n'))
        checks.extend([dict(field='command_exit_status',actual=raw['returncode'],expected=exit_code,passed=raw['returncode']==exit_code,basis='trusted requested exit code'),
                       dict(field='command_stdout_newlines',actual=raw['stdout'].count('\n'),expected=printed,passed=raw['stdout'].count('\n')==printed,basis='trusted requested stdout rows')])
        records.append(raw)
        worker_env={f'K{n}':('' if n%3==0 else f'v{n}') for n in range(rng.randint(3,24))}
        env_program='import json,os; print(json.dumps(dict(observed_environment=dict(os.environ),defined=len(os.environ),empty=sum(v=="" for v in os.environ.values()))))'
        result=subprocess.run([sys.executable,'-I','-S','-c',env_program],env=worker_env,capture_output=True,text=True,timeout=3,check=True)
        env_observed=json.loads(result.stdout)
        # CPython may add locale coercion metadata; record actual child state
        # rather than pretending authored keys equal the complete environment.
        fields.update(environment_defined=env_observed['defined'],environment_empty=env_observed['empty'])
        env_state=env_observed['observed_environment']
        checks.extend([dict(field='environment_defined',actual=env_observed['defined'],expected=len(env_state),passed=env_observed['defined']==len(env_state),basis='captured actual isolated environment mapping'),
                       dict(field='environment_empty',actual=env_observed['empty'],expected=sum(v=='' for v in env_state.values()),passed=env_observed['empty']==sum(v=='' for v in env_state.values()),basis='captured actual isolated environment mapping')])
        records.append(dict(argv=[sys.executable,'-I','-S','-c',env_program],returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,
                            authored_env=worker_env,interpretation='actual isolated child environment; CPython locale coercion may add a key'))
        wall_before=time.perf_counter_ns()
        cpu_before=time.process_time_ns()
        requested_sleep_ns=rng.randint(1,4)*1000000
        time.sleep(requested_sleep_ns/1000000000)
        sum(n*n for n in range(rng.randint(1000,8000)))
        cpu_after=time.process_time_ns()
        wall_after=time.perf_counter_ns()
        fields.update(profile_cpu_ns=cpu_after-cpu_before,profile_elapsed_ns=wall_after-wall_before)
        records.append(dict(api='time.process_time_ns/perf_counter_ns',before=dict(cpu_ns=cpu_before,elapsed_ns=wall_before),
                            after=dict(cpu_ns=cpu_after,elapsed_ns=wall_after),requested_sleep_ns=requested_sleep_ns))
        checks.append(dict(field='profile_elapsed_ns',actual=wall_after-wall_before,expected_min=requested_sleep_ns,
                           passed=wall_after-wall_before>=requested_sleep_ns,basis='elapsed includes requested sleep; not exact reproducible timing'))
        if not all(c['passed'] for c in checks):
            raise ValueError('Measured reference check failed')
    return dict(index=index,fixture_content=content,fixture_content_sha256=hashlib.sha256(content.encode()).hexdigest(),
                fields=fields,raw_observations=records,checks=checks,
                scope='authored inputs, actual trusted-tool/API measurements; no model/generated-code/P2/production')


def main():
    require_worker()
    request=validate_request(json.load(sys.stdin))
    locale.setlocale(locale.LC_ALL,'C.UTF-8')
    versions={name:command(['/usr/bin/'+name,'--version'],'/tmp')['stdout'].splitlines()[0] for name in ['wc','stat','du','df','gzip']}
    fixtures=[measured_fixture(request['seed'],i) for i in range(request['fixtures'])]
    print(json.dumps(dict(schema='trusted-tool-measurements/0.1',request=request,versions=versions,
                          python=sys.version,locale=locale.setlocale(locale.LC_ALL),fixtures=fixtures,
                          all_reference_checks_passed=True),ensure_ascii=False,allow_nan=False))


if __name__=='__main__':
    main()
