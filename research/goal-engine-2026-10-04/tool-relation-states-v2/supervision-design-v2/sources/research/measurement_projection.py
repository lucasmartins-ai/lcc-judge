"""Scoped input view for measurement-ranking diagnostics, never a DROP policy.

Only the caller's explicit entity is checked here. The natural question and the
measurement prose/value are preserved for the model. Unknown forms keep the
original record and are not assigned a ranking score by this view.
"""
from __future__ import annotations

import hashlib
import json
import re

SUFFIX = re.compile(r'(?P<question>[^\r\n]+) Report evidence for (?P<entity>tool-[a-f0-9]{12}); ordinary and unusual values both count\.', re.ASCII)
SENTENCE = re.compile(r'Tool report (?P<entity>tool-[a-f0-9]{12}) \[(?P<level>INFO|WARN|ERROR)\]: (?P<measurement>[^\r\n]+): (?P<value>-?\d+)\.', re.ASCII)


def _record(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate record key')
        result[key] = value
    return result


def project_measurement(objective, text):
    if not isinstance(objective, str) or not isinstance(text, str):
        raise ValueError('Question and report must be strings')
    result = dict(status='UNKNOWN', objective=None, text=None, original_text=text,
                  original_input_sha256=hashlib.sha256(json.dumps([objective,text], sort_keys=True).encode()).hexdigest(),
                  error='unsupported_or_ambiguous_scope', drop_authorized=False)
    if len(objective) > 4096 or len(text) > 16384:
        return result
    goal = SUFFIX.fullmatch(objective)
    if goal is None:
        return result
    try:
        if text.startswith('{'):
            body = json.loads(text, object_pairs_hook=_record)
        else:
            match = SENTENCE.fullmatch(text)
            if match is None:
                return result
            body = match.groupdict()
            body['value'] = int(body['value'])
        if (not isinstance(body, dict) or set(body) != {'entity','level','measurement','value'}
                or body['entity'] != goal['entity'] or body['level'] not in ['INFO','WARN','ERROR']
                or not isinstance(body['measurement'], str) or not body['measurement'].strip()
                or any(ord(ch) < 32 for ch in body['measurement']) or type(body['value']) is not int):
            return result
        question = goal['question']
        if not question.strip():
            return result
        projected = f"{body['measurement']}: {body['value']}."
        result.update(status='PROJECTED', objective=question, text=projected, error=None,
                      projected_input_sha256=hashlib.sha256(json.dumps([question,projected], sort_keys=True).encode()).hexdigest())
        return result
    except (ValueError, TypeError, OverflowError):
        return result
