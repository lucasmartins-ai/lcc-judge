"""Extend the frozen probe audit without changing its executed sources."""
import json

from research import goal_interpreter_probe as probe


def validate_summary(summary, protocol, neural_validation):
    assert summary['protocol_sha256'] == protocol['sha256']
    assert summary['validation'] == neural_validation['aggregate']
    assert summary['router_gate_pass'] is neural_validation['router_gate_pass']
    expected = ('fresh_confirmation_required' if neural_validation['router_gate_pass']
                else 'STOP_before_fresh_confirmation_and_LCC')
    assert summary['next_action'] == expected
    for flag in ('training', 'P2_admission', 'default_changed', 'independent_human_review'):
        assert summary[flag] is False, flag
    assert type(summary['API_calls']) is int and summary['API_calls'] == 0


def audit():
    protocol = probe.checked_protocol(live=True)
    summary = probe.load(probe.OUT / 'summary.json')
    validation = probe.load(probe.OUT / 'validation-metrics.json')['neural']
    validate_summary(summary, protocol, validation)
    probe.audit()
    result = dict(status='PASS', protocol_sha256=protocol['sha256'],
                  scope='Frozen core audit plus complete validation summary, stop action and nonpromotion flags',
                  core_audit_sha256=probe.sha(probe.OUT / 'audit.json'),
                  summary_sha256=probe.sha(probe.OUT / 'summary.json'),
                  validation_metrics_sha256=probe.sha(probe.OUT / 'validation-metrics.json'),
                  sources={name: probe.sha(probe.ROOT / name) for name in (
                      'research/audit_goal_interpreter_probe.py',
                      'tests/test_goal_probe_summary_audit.py')},
                  router_gate_pass=summary['router_gate_pass'], additional_model_forwards=0,
                  independent_human_review=False)
    path = probe.OUT / 'audit-summary-supplement.json'
    if path.exists():
        assert result == probe.load(path)
    else:
        probe.save(path, result)
    print(json.dumps(result))


if __name__ == '__main__':
    audit()
