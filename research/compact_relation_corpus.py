"""Prospective compact-ranker scope; old exposed families become development data.

Eight newly authored final measurement pairs are reserved before adaptation.
This is a shared-schema, shared-author P1 contract, not external/P2 ground truth.
"""
from __future__ import annotations

import random
import json

from research.semantic_corpus import FAMILIES as EXPOSED_FAMILIES, digest

RESERVED_FAMILIES = {
    'file_text': (
        (('How many text lines are in the file?', 'Keep the count of lines read from the text file.', 'Which measurement counts rows in the file contents?'),
         ('Text file line count', 'Number of newline-delimited rows in the file', 'Lines read from the text contents')),
        (('How many Unicode characters are in the file?', 'Keep the character count of the decoded text.', 'Which measurement counts decoded code points in the contents?'),
         ('Unicode code point count in the decoded file', 'Number of decoded text characters', 'Character length of the file contents'))),
    'network_receive': (
        (('How many payload bytes were received?', 'Keep the byte volume delivered by incoming packets.', 'Which measurement counts received data bytes?'),
         ('Received packet payload byte total', 'Byte volume of incoming data', 'Total bytes delivered in received payloads')),
        (('How many packets were received?', 'Keep the count of incoming packets.', 'Which measurement counts received packets rather than their payload size?'),
         ('Count of received packets', 'Number of incoming packet records', 'Total packets delivered to the receiver'))),
    'scheduler_duration': (
        (('How long did the job wait for scheduling?', 'Keep time spent waiting before execution began.', 'Which measurement describes queue wait duration?'),
         ('Job scheduling wait time in milliseconds', 'Duration queued before the task started', 'Time from submission until execution began')),
        (('How long did the job execute after it started?', 'Keep the duration of active job execution.', 'Which measurement describes running time after scheduling?'),
         ('Job execution duration after starting', 'Time from task start until completion', 'Milliseconds spent running the scheduled job'))),
    'repository_files': (
        (('How many tracked files have local modifications?', 'Keep the count of changed version-controlled files.', 'Which measurement counts modified files already tracked by version control?'),
         ('Locally modified tracked file count', 'Changed files known to version control', 'Number of tracked files with working-copy edits')),
        (('How many files are untracked by version control?', 'Keep the count of files absent from the tracking index.', 'Which measurement counts new untracked files?'),
         ('Untracked working-copy file count', 'Files not present in the version-control index', 'Number of new files unknown to version control'))),
    'search_lines': (
        (('How many lines matched the search pattern?', 'Keep the count of matching lines found by the search.', 'Which measurement counts lines containing the requested pattern?'),
         ('Lines matching the requested search pattern', 'Number of matching text rows', 'Count of lines with a pattern match')),
        (('How many lines were inspected during the search?', 'Keep the total count of lines searched.', 'Which measurement counts examined lines whether or not they matched?'),
         ('Total lines examined by the search', 'Number of text rows inspected for a match', 'Searched line count including nonmatches'))),
    'storage_entries': (
        (('How many inode entries are available?', 'Keep the unused filesystem inode count.', 'Which measurement describes remaining file-entry slots?'),
         ('Free filesystem inode count', 'Unused inode entries available for files', 'Remaining file-entry inode slots')),
        (('How many data blocks are available?', 'Keep the unused filesystem data-block count.', 'Which measurement describes remaining storage blocks?'),
         ('Free filesystem data-block count', 'Unused storage blocks available for data', 'Remaining block allocation units'))),
    'certificate': (
        (('How many days remain before the certificate expires?', 'Keep the remaining certificate lifetime.', 'Which measurement describes time until certificate expiry?'),
         ('Days remaining before certificate expiration', 'Certificate remaining lifetime in days', 'Time until the certificate becomes expired')),
        (('How many certificates are in the presented chain?', 'Keep the count of certificates in the chain.', 'Which measurement describes the number of chain members?'),
         ('Number of certificates in the presented chain', 'Certificate chain member count', 'Total certificate entries in the chain'))),
    'retry_wait': (
        (('How much time was spent sleeping between retries?', 'Keep accumulated backoff sleep duration.', 'Which measurement counts time spent waiting between attempts?'),
         ('Accumulated retry backoff sleep time', 'Total duration waiting between retry attempts', 'Milliseconds spent sleeping before repeated attempts')),
        (('How many retry attempts occurred?', 'Keep the count of repeated attempts.', 'Which measurement counts retries rather than time spent waiting?'),
         ('Number of retry attempts performed', 'Count of repeated attempts', 'Total retry operations that occurred'))),
}

TRAIN_FAMILIES = dict(EXPOSED_FAMILIES)
SEEDS = dict(train=442410, validation=442411, final=442412)


def build_split(split, groups):
    if split not in SEEDS or type(groups) is not int or groups < 1:
        raise ValueError('Known split and positive integer groups required')
    families = RESERVED_FAMILIES if split == 'final' else TRAIN_FAMILIES
    rows = []
    for domain, sides in families.items():
        for index in range(groups):
            rng = random.Random(f'{SEEDS[split]}:{domain}:{index}')
            entity = f'tool-{rng.getrandbits(48):012x}'
            group = digest([split,domain,index])
            level = rng.choice(['INFO','WARN','ERROR'])
            values = [rng.randrange(0,20),rng.randrange(100,500)]
            for requested in [0,1]:
                queries = sides[requested][0]
                objective = queries[(index+(1 if split=='validation' else 0)) % len(queries)]
                objective += f' Report evidence for {entity}; ordinary and unusual values both count.'
                for observed in [0,1]:
                    description = sides[observed][1][(index+1) % 3]
                    for numeric_band, value in enumerate(values):
                        body = dict(entity=entity,level=level,measurement=description,value=value)
                        text = json.dumps(body,sort_keys=True) if index % 2 == 0 else f'Tool report {entity} [{level}]: {description}: {value}.'
                        row = dict(id=digest([group,requested,observed,numeric_band]),group=group,
                            report_id=digest([group,observed,numeric_band]),domain=domain,objective=objective,text=text,
                            requested_slot=requested,semantic_slot=observed,label=int(requested==observed),
                            numeric_band=numeric_band,entity=entity,evidence_span=[0,len(text)])
                        row['content_hash'] = digest([objective,text])
                        rows.append(row)
    random.Random(SEEDS[split]).shuffle(rows)
    return rows
