"""P1 role supervision bound to measured receipts, with explicit authored framing.

Counterfactual claims test relevance independently of numeric correctness. Only
objective/text enter the scorer; role ids, truth and receipt bindings are metadata.
Semantic UNKNOWN labels are NOT recognized by the existing syntax projection.
"""
from __future__ import annotations

import hashlib
import json
import random

from research.measurement_projection import project_measurement
from research.tool_role_contracts import FINAL_FAMILIES, ROLES, TRAIN_FAMILIES, UNKNOWN_GOALS, measured_value

SEEDS = {'train': 442421, 'validation': 442422, 'final': 442423}
COUNTS = {'train': 32, 'validation': 12, 'final': 24}
TEMPLATES = {
    'train': {
        'en': ('Report the {}.', 'Which observation gives the {}?', 'Keep evidence for the {}.', 'Identify the {}.'),
        'pt': ('Informe {}.', 'Qual observação mostra {}?', 'Mantenha evidências sobre {}.', 'Identifique {}.'),
    },
    'validation': {
        'en': ('I need the measured {}.', 'Select the report that states the {}.'),
        'pt': ('Preciso da medição de {}.', 'Selecione o relato que informa {}.'),
    },
    'final': {
        'en': ('Find evidence of the {}.', 'Give me the recorded {}.'),
        'pt': ('Encontre evidências sobre {}.', 'Mostre o valor registrado de {}.'),
    },
}
UNKNOWN_QUERIES = {
    'train': UNKNOWN_GOALS,
    'validation': {
        'en': ('Count the displayed text rows, even when the final row has no newline.',
               'What caused the operation to fail?',
               'Which observations are indispensable to repair the entire system?'),
        'pt': ('Conte as linhas exibidas do texto, mesmo se a última não terminar com nova linha.',
               'O que causou a falha da operação?',
               'Quais observações são indispensáveis para reparar o sistema inteiro?'),
    },
    'final': {
        'en': ('Determine the number of visible lines, including wrapping and an unterminated last line.',
               'Diagnose why this operation failed.',
               'Choose only the evidence required to resolve the overall system problem.'),
        'pt': ('Determine o número de linhas visíveis, incluindo quebras de exibição e uma última linha incompleta.',
               'Diagnostique por que essa operação falhou.',
               'Escolha somente as evidências necessárias para resolver o problema geral do sistema.'),
    },
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def validate_receipt(raw):
    """Reject incomplete/tampered captures before deriving any label."""
    try:
        if (raw['status'] != 'MEASURED' or raw['error'] is not None or raw['returncode'] != 0
                or raw['host_measurement_executed'] is not False):
            raise ValueError('Receipt did not complete in the trusted worker')
        measurements = raw['measurements']
        if json.loads(raw['stdout']) != measurements or measurements['request'] != raw['request']:
            raise ValueError('Parsed data differ from the original worker stdout')
        if measurements['all_reference_checks_passed'] is not True:
            raise ValueError('Worker reference checks did not complete')
        fixtures = measurements['fixtures']
        if len(fixtures) != raw['request']['fixtures']:
            raise ValueError('Incomplete fixture capture')
        for index, fixture in enumerate(fixtures):
            content = fixture['fixture_content']
            if (fixture['index'] != index
                    or hashlib.sha256(content.encode()).hexdigest() != fixture['fixture_content_sha256']
                    or len(fixture['fields']) != 31
                    or not all(type(v) is int for v in fixture['fields'].values())
                    or not fixture['checks'] or not all(c['passed'] is True for c in fixture['checks'])):
                raise ValueError('Malformed or failed fixture')
            expected = {'wc_bytes': len(content.encode()), 'wc_characters': len(content),
                        'wc_newlines': content.count('\n'), 'wc_words': len(content.split())}
            if any(fixture['fields'][k] != v for k, v in expected.items()):
                raise ValueError('Content-derived counters do not match')
        return fixtures
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid measurement receipt') from exc


def _report(entity, caption, value, index):
    level = ('INFO', 'WARN', 'ERROR')[index % 3]
    body = dict(entity=entity, level=level, measurement=caption, value=value)
    if index % 2 == 0:
        return json.dumps(body, sort_keys=True)
    return f'Tool report {entity} [{level}]: {caption}: {value}.'


def _question(split, language, role, index):
    alias_index = index % 2 if split == 'train' else (2 if split == 'validation' else index % 3)
    aliases = ROLES[role][3 if language == 'en' else 4]
    templates = TEMPLATES[split][language]
    # Avoid coupling the same alias to only one training template.
    return templates[(index // 2) % len(templates)].format(aliases[alias_index])


def build_rows(split, raw):
    if split not in SEEDS:
        raise ValueError('Unknown prospective split')
    fixtures = validate_receipt(raw)
    families = FINAL_FAMILIES if split == 'final' else TRAIN_FAMILIES
    rows = []
    for fixture in fixtures:
        index = fixture['index']
        fields = fixture['fields']
        for family, roles in families.items():
            for language in ['en', 'pt']:
                group = digest([split, raw['request']['seed'], family, index, language])
                entity = 'tool-' + group[:12]
                for requested in roles:
                    question = _question(split, language, requested, index)
                    objective = question + f' Report evidence for {entity}; ordinary and unusual values both count.'
                    for observed in roles:
                        other = roles[1] if observed == roles[0] else roles[0]
                        caption_index = index % 2 if split == 'train' else (2 if split == 'validation' else index % 3)
                        caption = ROLES[observed][5][caption_index]
                        actual_value = measured_value(fields, observed)
                        for variant, value_role in [('measured', observed), ('value_swap', other)]:
                            reported_value = measured_value(fields, value_role)
                            text = _report(entity, caption, reported_value, index)
                            binding = dict(source=ROLES[observed][1], field=ROLES[observed][0], unit=ROLES[observed][2],
                                           value_source_field=ROLES[value_role][0], value_source_role=value_role,
                                           actual_value=actual_value, fixture_index=index,
                                           fixture_content_sha256=fixture['fixture_content_sha256'])
                            row = dict(id=digest([group, requested, observed, variant]), group=group,
                                       report_id=digest([group, observed, variant]), split=split, family=family,
                                       goal_language=language, report_language='en', requested_role=requested,
                                       observed_role=observed, objective=objective, text=text, entity=entity,
                                       label=int(requested == observed), unknown_kind=None, report_variant=variant,
                                       fact_truth=reported_value == actual_value, reported_value=reported_value,
                                       binding=binding, framing='authored P1 claim, bound to captured tool fields',
                                       evidence_span=[0, len(text)])
                            rows.append(row)
        # UNKNOWN is a separate decision class, not a negative ranker example.
        for language in ['en', 'pt']:
            group = digest([split, raw['request']['seed'], 'unknown', index, language])
            entity = 'tool-' + group[:12]
            text = _report(entity, ROLES['newline'][5][index % 3], fields['wc_newlines'], index)
            cases = [(question, text, 'unsupported_goal') for question in UNKNOWN_QUERIES[split][language]]
            # Correct request but no unambiguous observation binding.
            cases.append((_question(split, language, 'newline', index),
                          json.dumps(dict(entity=entity, measurement='Unqualified rows', value=fields['wc_newlines'])),
                          'unbound_record'))
            for case, (question, report, kind) in enumerate(cases):
                objective = question + f' Report evidence for {entity}; ordinary and unusual values both count.'
                rows.append(dict(id=digest([group, case]), group=group, report_id=digest([group, case]),
                                 split=split, family='unknown', goal_language=language, report_language='en',
                                 requested_role=None, observed_role='newline', objective=objective, text=report, entity=entity,
                                 label=None, unknown_kind=kind, report_variant='measured', fact_truth=True,
                                 reported_value=fields['wc_newlines'],
                                 binding=dict(source='wc', field='wc_newlines', unit='newlines',
                                              value_source_field='wc_newlines', value_source_role='newline',
                                              actual_value=fields['wc_newlines'], fixture_index=index,
                                              fixture_content_sha256=fixture['fixture_content_sha256']),
                                 framing='authored unsupported-goal or unbound-record P1 case', evidence_span=[0, len(report)]))
    for row in rows:
        row['model_pair'] = dict(objective=row['objective'], text=row['text'])
        row['content_hash'] = digest([row['objective'], row['text']])
        view = project_measurement(**row['model_pair'])
        row['projection_status'] = view['status']
        row['projected_input_hash'] = view.get('projected_input_sha256')
    random.Random(SEEDS[split]).shuffle(rows)
    return rows
