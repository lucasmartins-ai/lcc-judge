"""Independent recoverability check v4 (no lcc code) = the v0.7 check v3 + the v0.7-review rules.

v3 (research.real_context_bench_v07_test.independent_check_v3) only flags a file pointer when a later call
names the file. It shares the blind spot the v0.7 independent review found: a later script, build, install,
test run or unknown tool can write the file without naming it. v4 adds, for every file pointer:
- H1 opaque later writes: any later call that is not a plain read (shell call off the read-only allowlist, or
  a tool that is neither a known read/task tool nor a write naming its target path) flags the pointer when
  its cwd is unknown/relative, it changes directory, or the pointed file is under its cwd;
- M2 a relative path with no absolute cwd on the call is flagged.
"""
import posixpath
import re

from research import recoverable_dev_measure as rdm
from research.real_context_bench_v07_test import independent_check_v3
from research.recoverable_dev_v2 import _own_cwd

FILE_PTR = re.compile(r'^\[removed: re-read (.+?)(?: \(lines \d+-\d+\))?(?: \(cwd (.+)\))? to recover\]$')
#: Tools that write no workspace file (reads, searches, plans, questions).
PURE = {'Read', 'view', 'read_file', 'NotebookRead', 'Grep', 'Glob', 'LS', 'WebFetch', 'WebSearch', 'web_search',
        'search_files', 'skill_view', 'Skill', 'ToolSearch', 'tool_search', 'TodoWrite', 'TaskCreate', 'TaskUpdate',
        'TaskList', 'TaskGet', 'ExitPlanMode', 'update_plan', 'AskUserQuestion', 'view_image', 'vision_analyze'}
#: Writes whose target is in their input: v3's later-write check already covers them.
TARGETED = {'Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'apply_patch', 'patch', 'write_file'}
CHDIR = re.compile(r'\b(?:cd|pushd)\b|(?:^|\s)-C\b|--(?:prefix|cwd|directory)\b')


def _opaque_dir(use):
    """'' when `use` writes nothing it does not name; else the dir it may write under (None = anywhere)."""
    name = use['tool_name']
    cmd = rdm._cmd(use)
    if cmd is None and (name in PURE or name in TARGETED):
        return ''
    if cmd is not None and rdm._read_only(cmd):
        return ''
    cwd = _own_cwd(use)
    if not cwd or not cwd.startswith('/') or CHDIR.search(use['content']):
        return None
    return posixpath.normpath(cwd)


def _under(path, d):
    path, d = (p.removeprefix('/private') for p in (path, d))
    d = d.rstrip('/')
    return not d or path == d or path.startswith(d + '/')


def independent_check_v4(blocks, decisions, out_text):
    bad = independent_check_v3(blocks, decisions, out_text)
    uses = [b for b in blocks if b['kind'] == 'tool_use']
    pos = {b['tool_use_id']: i for i, b in enumerate(uses)}
    for d in decisions:
        m = FILE_PTR.match(d.get('note') or '') if d.get('decision') == 'replace' else None
        if m is None or d['id'] not in pos:
            continue  # command pointers and missing calls: v3 covers them
        path, cwd = m[1], m[2]
        if path.startswith('/'):
            target = posixpath.normpath(path)
        elif cwd and cwd.startswith('/'):
            target = posixpath.normpath(posixpath.join(cwd, path))
        else:
            bad.append(f"{d['id']}: file pointer with a relative path and no absolute cwd")
            continue
        for u in uses[pos[d['id']] + 1:]:
            where = _opaque_dir(u)
            if where != '' and (where is None or _under(target, where)):
                bad.append(f"{d['id']}: opaque later write ({u['tool_name']}) may have changed {path}")
                break
    return bad
