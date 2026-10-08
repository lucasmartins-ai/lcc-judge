"""Trusted worker entrypoint; image contains only fixtures, never the host workspace."""
import contextlib
import io
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from replay.sandbox import require_worker

require_worker()

request = json.load(sys.stdin)
captured = io.StringIO()
try:
    with contextlib.redirect_stdout(captured):
        if request['recipe'] == 'legacy':
            from replay.real_fixtures import check_code
            checks = check_code(request['task_number'], request['source'])
        elif request['recipe'] == 'candidate':
            from replay.outcome_verifier import check_program
            checks = check_program(request['task_number'], request['source'])
        else:
            raise ValueError('Unsupported fixture recipe')
    result = dict(passed=True, reason='confined_executable_fixture_checks', checks=checks)
except Exception as exc:
    result = dict(passed=False, reason='generated_program_failed_fixture',
                  error=f'{type(exc).__name__}: {exc}'[:2000])
result['program_stdout'] = captured.getvalue()[-2000:]
print(json.dumps(result))
