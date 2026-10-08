"""Authored P1 tool-measurement relations, with goal-dependent paired labels.

The annotation oracle compares declared measurement slots. Models only see the
natural-language objective and rendered report. This is a synthetic semantic
diagnostic, not human-reviewed or outcome-backed necessity ground truth.
"""
from __future__ import annotations

import hashlib
import json
import random

# Each side: three query paraphrases and three separately worded report meanings.
FAMILIES = {
    'command_result': (
        (('What return code did the command produce?', 'Keep the numeric termination status of the shell invocation.', 'Which value says whether the invoked process exited successfully?'),
         ('The invoked process finished with exit status', 'Shell termination code observed', 'Return status of the completed command')),
        (('How many output lines did the command print?', 'Keep the amount of text lines emitted by the invocation.', 'Which measurement counts rows written to standard output?'),
         ('Number of stdout lines emitted by the process', 'Printed line count from the command', 'Rows in captured standard output'))),
    'download': (
        (('How large was the downloaded payload?', 'Keep the byte volume received in the transfer.', 'Which measurement describes the size of the fetched object?'),
         ('Bytes in the received response body', 'Fetched object payload size', 'Downloaded content length in bytes')),
        (('How long did the download take?', 'Keep the elapsed duration of the transfer.', 'Which measurement describes time spent fetching the object?'),
         ('Milliseconds elapsed during the fetch', 'Duration of the completed download', 'Transfer completion time in milliseconds'))),
    'build': (
        (('How large is the produced build artifact?', 'Keep the packaged output size.', 'Which measurement counts bytes in the generated bundle?'),
         ('Generated artifact byte length', 'Size of the packaged build result', 'Bundle bytes after compilation')),
        (('How long did producing the build take?', 'Keep the compilation duration.', 'Which measurement records elapsed time for generating the bundle?'),
         ('Build completion duration in milliseconds', 'Elapsed compilation time', 'Time spent producing the artifact'))),
    'queue': (
        (('How many jobs are waiting for a worker?', 'Keep the size of the pending work backlog.', 'Which measurement counts jobs not yet being processed?'),
         ('Pending jobs awaiting assignment', 'Work queue backlog item count', 'Jobs still waiting in the queue')),
        (('How many workers are currently processing jobs?', 'Keep the number of busy executors.', 'Which measurement counts active workers rather than waiting jobs?'),
         ('Workers occupied by running tasks', 'Number of currently busy executors', 'Active worker process count'))),
    'dependency': (
        (('What version is actually installed for the dependency?', 'Keep the observed package release number.', 'Which measurement identifies the dependency present in the environment?'),
         ('Installed package release number', 'Actual dependency version found on disk', 'Observed version of the available package')),
        (('What version is required by the dependency constraint?', 'Keep the requested package release number.', 'Which measurement identifies the package version specified by the project?'),
         ('Version required by the project manifest', 'Dependency version constraint specified', 'Requested package release in the requirement'))),
    'disk': (
        (('How much storage space is free?', 'Keep the bytes still available on the volume.', 'Which measurement describes remaining disk capacity?'),
         ('Unoccupied bytes available on the filesystem', 'Free storage space in bytes', 'Remaining unused volume capacity')),
        (('What is the total capacity of the disk?', 'Keep the full size of the storage volume.', 'Which measurement describes the capacity before subtracting used space?'),
         ('Total filesystem capacity in bytes', 'Full volume storage size', 'Combined occupied and unoccupied disk bytes'))),
    'memory': (
        (('How much memory is resident in RAM?', 'Keep the process physical memory usage.', 'Which measurement describes pages currently resident for the process?'),
         ('Resident set size in bytes', 'Physical memory occupied by process pages', 'Bytes of process memory currently in RAM')),
        (('How much virtual address space is allocated?', 'Keep the process virtual memory allocation.', 'Which measurement describes reserved address space rather than physical pages?'),
         ('Allocated virtual address space in bytes', 'Virtual memory size reserved for the process', 'Process address space allocation'))),
    'http': (
        (('How often was the HTTP request retried?', 'Keep the number of repeated request attempts.', 'Which measurement counts retries of the outbound call?'),
         ('Retry attempts for the HTTP operation', 'Number of repeated outbound requests', 'Count of request retry operations')),
        (('What HTTP status did the response return?', 'Keep the numeric response status code.', 'Which measurement identifies the returned web response code?'),
         ('HTTP response status code observed', 'Numeric status of the received response', 'Returned web protocol response code'))),
    'database': (
        (('How far behind is the database replica?', 'Keep the measured replication delay.', 'Which measurement says how late the replicated data is?'),
         ('Replica lag duration in milliseconds', 'Delay before replicated data becomes current', 'Measured replication lag')),
        (('How long did executing the database query take?', 'Keep the statement execution duration.', 'Which measurement describes time spent running the query?'),
         ('Database statement execution time', 'Duration of the completed query', 'Milliseconds spent executing the SQL statement'))),
    'cache': (
        (('How many cache lookups succeeded?', 'Keep the number of requests served from cached entries.', 'Which measurement counts hits in the cache?'),
         ('Successful cache hit count', 'Lookups served by an existing cached entry', 'Requests with a cache hit')),
        (('How many cache lookups missed?', 'Keep the number of requests without a cached entry.', 'Which measurement counts misses in the cache?'),
         ('Cache miss count', 'Lookups for which no cached entry existed', 'Requests with a cache miss'))),
    'environment': (
        (('How many environment variables are defined?', 'Keep the count of names present in the environment.', 'Which measurement counts all declared environment keys?'),
         ('Defined environment variable name count', 'Total variable keys present in the environment', 'Number of declared environment entries')),
        (('How many environment variables have empty values?', 'Keep the count of defined keys with blank contents.', 'Which measurement counts empty assignments rather than all variable names?'),
         ('Environment entries whose value is an empty string', 'Defined variables with blank assigned contents', 'Count of empty environment values'))),
    'file_mode': (
        (('What permission mode does the file have?', 'Keep the numeric filesystem access bits.', 'Which measurement describes file access permissions?'),
         ('File permission mode bits', 'Numeric access rights on the filesystem entry', 'Observed file permission value')),
        (('How many bytes does the file contain?', 'Keep the file content length.', 'Which measurement describes the size of the file data?'),
         ('File content byte count', 'Length of the stored file in bytes', 'Size of the file data'))),
    # Reserved pair families; general vocabulary such as count/time remains shared.
    'test_coverage': (
        (('What fraction of control-flow branches was exercised?', 'Keep the coverage of decision alternatives.', 'Which measurement reports coverage of branches rather than statements?'),
         ('Percentage of branch alternatives covered by tests', 'Branch coverage percentage from the test tool', 'Covered control-flow branch proportion')),
        (('What fraction of statements was executed?', 'Keep coverage of executable source lines.', 'Which measurement reports line coverage rather than decision alternatives?'),
         ('Percentage of executable lines reached by tests', 'Statement coverage percentage', 'Covered source statement proportion'))),
    'test_result': (
        (('How many test cases were skipped?', 'Keep the count of checks deliberately not executed.', 'Which measurement counts tests that did not run?'),
         ('Skipped test case count', 'Checks bypassed without being executed', 'Number of omitted test executions')),
        (('How many executed test cases failed?', 'Keep the count of unsuccessful test results.', 'Which measurement counts tests that ran and did not pass?'),
         ('Failed test case count', 'Executed checks with unsuccessful results', 'Number of failing test executions'))),
    'process_time': (
        (('How much CPU time did the process consume?', 'Keep time actually spent executing on processors.', 'Which measurement counts processor time rather than wall-clock waiting?'),
         ('Combined user and system CPU duration', 'Processor execution time consumed by the task', 'Process CPU time in milliseconds')),
        (('How much wall-clock time elapsed for the process?', 'Keep total start-to-finish duration including waiting.', 'Which measurement counts elapsed time rather than CPU consumption?'),
         ('Wall-clock duration from start until completion', 'Elapsed process time including waits', 'Total real time for the process'))),
    'symlink_size': (
        (('How large is the file reached by resolving the symbolic link?', 'Keep the content size of the link target.', 'Which measurement reports bytes in the referenced file?'),
         ('Byte size of the resolved symlink target file', 'Content length of the file referenced by the symbolic link', 'Data bytes at the resolved link destination')),
        (('How long is the path stored inside the symbolic link?', 'Keep the byte length of the link entry itself.', 'Which measurement reports stored link text rather than target file data?'),
         ('Byte length of the pathname stored in the symlink', 'Size of the symbolic link entry text', 'Length of the stored link path'))),
    'connections': (
        (('How many connection attempts were made?', 'Keep the count of tried network connections.', 'Which measurement counts all attempts to connect?'),
         ('Attempted network connection count', 'Number of connection attempts initiated', 'Total attempts to establish a network connection')),
        (('How many connections were actually established?', 'Keep the count of successfully connected sockets.', 'Which measurement counts active established connections rather than attempts?'),
         ('Successfully established socket count', 'Network connections that reached an established state', 'Number of connected sockets'))),
    'manifest': (
        (('How many entries are declared in the manifest?', 'Keep the count of files explicitly listed by the manifest.', 'Which measurement counts declared entries rather than discovered files?'),
         ('File entries listed in the manifest', 'Declared manifest entry count', 'Number of explicitly enumerated manifest files')),
        (('How many files were found by scanning the directory?', 'Keep the count of discovered filesystem files.', 'Which measurement counts found files rather than declared manifest entries?'),
         ('Files discovered by a directory traversal', 'Scanned filesystem file count', 'Number of file entries found on disk'))),
}
TRAIN_FAMILIES = tuple(list(FAMILIES)[:12])
FINAL_FAMILIES = tuple(list(FAMILIES)[12:])
SEEDS = dict(train=442406, validation=442407, final=442408)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def verify_label(row):
    return int(row['requested_slot'] == row['semantic_slot'])


def build_split(split, groups):
    if split not in SEEDS or type(groups) is not int or groups < 1:
        raise ValueError('Valid split and positive group count required')
    rows = []
    domains = FINAL_FAMILIES if split == 'final' else TRAIN_FAMILIES
    for domain in domains:
        for index in range(groups):
            rng = random.Random(f'{SEEDS[split]}:{domain}:{index}')
            entity = f'tool-{rng.getrandbits(48):012x}'
            group = digest([split,domain,index])
            level = rng.choice(['INFO','WARN','ERROR'])
            values = [rng.randrange(0,20),rng.randrange(100,500)]
            for requested in [0,1]:
                queries = FAMILIES[domain][requested][0]
                objective = queries[(index + (1 if split == 'validation' else 0)) % len(queries)]
                objective += f' Report evidence for {entity}; ordinary and unusual values both count.'
                for observed in [0,1]:
                    descriptions = FAMILIES[domain][observed][1]
                    description = descriptions[(index + 1) % len(descriptions)]
                    for status_index,value in enumerate(values):
                        body = dict(entity=entity,level=level,measurement=description,value=value)
                        if index % 2 == 0:
                            text = json.dumps(body,sort_keys=True)
                        else:
                            text = f"Tool report {entity} [{level}]: {description}: {value}."
                        row = dict(id=digest([group,requested,observed,status_index]),group=group,
                                   report_id=digest([group,observed,status_index]),
                                   domain=domain,objective=objective,text=text,
                                   requested_slot=requested,semantic_slot=observed,
                                   label=int(requested==observed),kind='semantic_match' if requested==observed else 'neighbor_measurement',
                                   observation_status='healthy' if status_index==0 else 'anomalous',
                                   status_scope='authored low/high numeric bands; not operational health',
                                   entity=entity,evidence_span=[0,len(text)])
                        row['content_hash']=digest([objective,text])
                        rows.append(row)
    random.Random(SEEDS[split]).shuffle(rows)
    return rows
