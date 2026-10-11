import json

import pytest

from research import recoverable_v08 as v08


def _row(rid, replaced, keep=None):
    return dict(id=rid, in_tokens=100, out_tokens=100 - 10 * len(replaced), degraded=False, runtime_fail_safe=[],
                verify_recoverable=[], independent=[], replaced=replaced, keep_reason=keep or {}, counts={})


@pytest.fixture
def bench(tmp_path, monkeypatch):
    dossiers = tmp_path / 'd'
    dossiers.mkdir()
    monkeypatch.setattr(v08, 'PRIVATE', tmp_path / 'p')
    monkeypatch.setattr(v08, 'SETS', {'s': dossiers})

    def put(pin, row):
        (dossiers / f"{row['id']}.json").write_text('{}')
        d = tmp_path / 'p' / pin / 's'
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{row['id']}.json").write_text(json.dumps(row))
    return put


def test_subset_holds_and_removed_reasons_are_counted(bench):
    bench('old', _row('i1', {'a': 'file_whole', 'b': 'command', 'c': 'file_range'}))
    bench('new', _row('i1', {'a': 'file_whole'}, keep={'b': 'command_pointers_disabled'}))  # 'c' became dedupe
    r = v08._compare('s', 'new')
    assert r['subset_violations'] == 0
    assert r['removed_by_reason'] == {'command_pointers_disabled': 1, 'dedupe_lossless': 1}
    assert r['removed_by_kind'] == {'file_whole': 0, 'file_range': 1, 'command': 1}


def test_a_new_pointer_is_a_subset_violation(bench):
    bench('old', _row('i1', {'a': 'file_whole'}))
    bench('new', _row('i1', {'a': 'file_whole', 'z': 'file_whole'}))
    assert v08._compare('s', 'new')['subset_violations'] == 1


def test_missing_item_refuses(bench):
    bench('old', _row('i1', {}))
    bench('old', _row('i2', {}))
    bench('new', _row('i1', {}))
    with pytest.raises(SystemExit):
        v08._compare('s', 'new')
