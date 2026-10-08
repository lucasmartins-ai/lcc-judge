"""Experimental PDB budget arithmetic; textual review is a separate decision.

Scope: a supported controller and all desired replicas healthy. This checks
voluntary disruption budgets, not selectors, full manifests or involuntary loss.
"""
import math
import re


def scaled_value(value,replicas):
    if type(value) is int:
        return value if 0<=value<=2147483647 else None
    if isinstance(value,str) and re.fullmatch(r'[0-9]+%',value):
        percent=int(value[:-1])
        if percent<=100:return (percent*replicas+99)//100
    return None


def numeric_verdict(parameters,replicas,quorum,drain=1,controller_supported=True,healthy=None,numeric_claims=None):
    if any(type(v) is not int for v in [replicas,quorum,drain]) or replicas<1 or not 1<=quorum<=replicas or drain<1:
        return {'passed':None,'reason':'invalid_reference_contract'}
    if controller_supported is not True or (healthy is not None and healthy!=replicas):
        return {'passed':None,'reason':'outside_supported_healthy_workload_scope'}
    if not isinstance(parameters,dict):return {'passed':False,'reason':'invalid_budget_parameters'}
    fields={k:v for k,v in parameters.items() if v is not None}
    if set(fields) not in [{'min_available'},{'max_unavailable'}]:return {'passed':False,'reason':'one_budget_field_required'}
    key,value=next(iter(fields.items()));scaled=scaled_value(value,replicas)
    if scaled is None:return {'passed':False,'reason':'invalid_int32_or_percent'}
    remaining=scaled if key=='min_available' else replicas-scaled
    permitted=replicas-remaining
    if remaining<quorum or permitted<drain:return {'passed':False,'reason':'quorum_or_maintenance_violation','min_remaining':remaining,'max_disruptions':permitted}
    facts={'min_remaining':remaining,'max_disruptions':permitted,'quorum':quorum,'requested_maintenance':drain,
        'quorum_preserved':True,'requested_maintenance_permitted':True,
        'supported_controller':True,'all_desired_replicas_healthy':True,
        'applies_to_voluntary_evictions':True,'prevents_involuntary_node_failures':False,
        'maximal_disruption_required':False}
    if numeric_claims is not None:
        if not isinstance(numeric_claims,dict) or not set(numeric_claims)<={'min_remaining','max_disruptions'}:
            return {'passed':False,'reason':'invalid_numeric_claim_schema'}
        if any(type(v) is not int or v!=facts[k] for k,v in numeric_claims.items()):
            return {'passed':False,'reason':'contradictory_numeric_claim'}
    return {'passed':True,'reason':'exact_pdb_budget_checks','facts':facts}


def check_budget(parameters,replicas=5,quorum=3,drain=1):
    return numeric_verdict(parameters,replicas,quorum,drain)['passed'] is True


def prepare_text_review(artifact,contract):
    if not isinstance(artifact,dict) or artifact.get('status')!='ANSWER' or artifact.get('mechanism')!='configure_pdb':
        return None
    text=artifact.get('answer')
    if not isinstance(text,str) or not text.strip():return None
    result=numeric_verdict(artifact.get('parameters'),numeric_claims=artifact.get('numeric_claims'),**contract)
    if result['passed'] is not True:return None
    return {'verified_facts':result['facts'],'explanation':text}


def combine(numeric,text_probability,threshold):
    if numeric['passed'] is not True:return dict(numeric)
    if type(text_probability) not in [int,float] or not math.isfinite(text_probability) or not 0<=text_probability<=1:
        return {'passed':None,'reason':'text_review_unavailable'}
    return {'passed':text_probability>=threshold,'reason':'math_then_text_review','text_probability':text_probability,'threshold':threshold}
