"""Next-action evidence labels on synthetic transcripts (never reads a real store)."""
import json
import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from research import next_action_labels as nal
from research import real_context_bench as rcb

IAR = SimpleNamespace(_claude_text=rcb.claude_text, _CLAUDE_AUTO=('You are Claude Code', 'This session is being continued',
                                                                  '[Request interrupted', 'Caveat:'))
READ_OUT = ('     1→import os\n     2→\n     3→def parse_config_value(raw_text, default=None):\n'
            '     4→    return raw_text.strip() if raw_text else default\n')
WEATHER = 'The weather report says it will be sunny all weekend in the mountains near the lake.'


def blank_split(text):
    """Stand-in for lcc split_blocks: blank-line paragraphs with offsets and content ids."""
    out = []
    for i, m in enumerate(re.finditer(r'(?:[^\n]+\n?)+', text)):
        out.append((f'blk_{i:04d}_{abs(hash(m.group(0))) % 10**12:012d}', m.group(0), m.start(), m.end()))
    return out


def count(s):
    return max(1, len(s) // 4)


def rec(uuid, parent, typ, content, **kw):
    return dict(uuid=uuid, parentUuid=parent, type=typ, sessionId='s1', message=dict(role=typ, content=content), **kw)


def claude_session(edit_after_reread=False):
    window = [rec('a3', 'p2', 'assistant', [dict(type='text', text='Fixing `parse_config_value` now.')])]
    if edit_after_reread:
        window += [rec('a4', 'a3', 'assistant', [dict(type='tool_use', id='t2', name='Read',
                                                      input=dict(file_path='/repo/src/app_core.py'))]),
                   rec('u4', 'a4', 'user', [dict(type='tool_result', tool_use_id='t2', content=READ_OUT)])]
    window += [
        rec('a5', 'u4' if edit_after_reread else 'a3', 'assistant', [dict(type='tool_use', id='t3', name='Edit', input=dict(
            file_path='/repo/src/app_core.py', old_string='    return raw_text.strip() if raw_text else default',
            new_string='    return raw_text.strip() or default'))]),
        rec('u5', 'a5', 'user', [dict(type='tool_result', tool_use_id='t3', content='ok')]),
        rec('p3', 'u5', 'user', 'thanks, now commit'),
        rec('a6', 'p3', 'assistant', [dict(type='text', text='Committed.')]),
    ]
    return [
        rec('p1', None, 'user', 'look at the config loader please'),
        rec('a1', 'p1', 'assistant', [dict(type='text', text=WEATHER),
                                      dict(type='tool_use', id='t1', name='Read', input=dict(file_path='/repo/src/app_core.py'))]),
        rec('u1', 'a1', 'user', [dict(type='tool_result', tool_use_id='t1', content=READ_OUT)]),
        rec('a2', 'u1', 'assistant', [dict(type='text', text='The loader returns default on empty input.')]),
        rec('p2', 'a2', 'user', 'empty strings should fall back too, fix it'),
    ] + window


def label_claude(records, pos):
    recs = {r['uuid']: r for r in records}
    blocks = rcb.render_blocks(nal.claude_context(recs, records[pos]['uuid']))
    ev, ended = nal.claude_window(records, pos, IAR)
    rows, st = nal.label_item(nal.claude_human(records[pos], IAR), blocks, ev, blank_split, count, {})
    return rows, st, ended


def row_with(rows, records, needle):
    blocks = rcb.render_blocks(nal.claude_context({r['uuid']: r for r in records}, 'p2'))
    text = rcb.render(blocks)
    for r, (_, t, _, _) in zip(rows, blank_split(text)):
        if needle in t:
            return r
    raise AssertionError(needle)


class Features(unittest.TestCase):
    def test_kinds_and_thresholds(self):
        f = nal.features('see /repo/src/app_core.py and research/x.py, ratio 0.973 at 20261012, sha 8b29747; '
                         'and/or pt/en; parse_config_value fooBar plain words here')
        self.assertIn(('path', '/repo/src/app_core.py'), f)
        self.assertIn(('path', 'src/app_core.py'), f)  # suffix key >= 12 chars
        self.assertIn(('path', 'app_core.py'), f) if len('app_core.py') >= nal.MIN_KEY else None
        self.assertNotIn(('path', 'and/or'), f)
        self.assertNotIn(('path', 'pt/en'), f)
        self.assertIn(('num', '0.973'), f)
        self.assertIn(('num', '20261012'), f)
        self.assertIn(('hex', '8b29747'), f)
        self.assertIn(('ident', 'parse_config_value'), f)
        self.assertNotIn(('ident', 'getX'), nal.features('call getX now'))  # camel but < 6 chars
        self.assertFalse({x for x in f if x[0] == 'ident' and x[1] in ('plain', 'words', 'ratio')})

    def test_uuid_is_one_feature(self):
        f = nal.features('session 2b4c3560-1216-4abd-8ad2-6860cc055046 done')
        self.assertEqual({x for x in f if x[0] == 'hex'}, {('hex', '2b4c3560-1216-4abd-8ad2-6860cc055046')})

    def test_line_number_prefix_stripped(self):
        f = nal.features(READ_OUT)
        self.assertIn(('line', 'return raw_text.strip() if raw_text else default'), f)
        self.assertNotIn(('line', 'import os'), f)  # under 24 chars

    def test_json_escaped_tool_use_matches_unescaped(self):
        f, _ = nal.block_view(json.dumps(dict(old_string='def parse_config_value(raw_text, default=None):\n    pass')))
        self.assertIn(('line', 'def parse_config_value(raw_text, default=None):'), f)

    def test_render_headers_ignored(self):
        f, _ = nal.block_view('[m0003 user tool_result Bash]\nshort')
        self.assertFalse(f)


class Claude(unittest.TestCase):
    def test_edit_anchor_marks_read_result_used(self):
        records = claude_session()
        rows, st, ended = label_claude(records, 4)
        self.assertEqual(ended, 'next_prompt')
        read = row_with(rows, records, 'raw_text.strip()')
        self.assertTrue(read['used'])
        self.assertIn('edit_anchor', {r for x in read['reasons'] for r in x['rules']})
        self.assertFalse(row_with(rows, records, 'weather report')['used'])

    def test_refetch_is_loose_only(self):
        records = claude_session(edit_after_reread=True)
        rows, _, _ = label_claude(records, 4)
        read = row_with(rows, records, 'raw_text.strip()')
        self.assertTrue(read['used_loose'])
        self.assertTrue(all(x['refetched'] for x in read['reasons'] if x['kind'] == 'line'))

    def test_goal_terms_are_not_evidence(self):
        records = claude_session()
        records[4]['message']['content'] = 'fix parse_config_value for empty strings'
        rows, st, _ = label_claude(records, 4)
        self.assertGreaterEqual(st.get('goal_dropped', 0), 1)
        self.assertFalse(any(x['value'] == 'parse_config_value' for r in rows for x in r['reasons']))

    def test_interrupt_and_compaction_end_window(self):
        records = claude_session()
        records[5:5] = [rec('i1', 'p2', 'user', [dict(type='text', text='[Request interrupted by user]')])]
        self.assertEqual(nal.claude_window(records, 4, IAR), ([], 'interrupt'))
        records = claude_session()
        records[5:5] = [dict(uuid='c1', parentUuid='p2', type='system', subtype='compact_boundary')]
        self.assertEqual(nal.claude_window(records, 4, IAR)[1], 'compaction')

    def test_sidechain_and_meta_skipped(self):
        records = claude_session()
        records[5:5] = [dict(rec('x1', 'p2', 'assistant', [dict(type='text', text='subagent')]), isSidechain=True),
                        dict(rec('x2', 'p2', 'user', 'Base directory for this skill: /x'), isMeta=True)]
        ev, ended = nal.claude_window(records, 4, IAR)
        self.assertEqual(ended, 'next_prompt')
        self.assertNotIn(('text', 'subagent'), ev)
        self.assertIn('user', {e[0] for e in ev})

    def test_context_matches_bench_walk(self):
        records = claude_session()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 's.jsonl'
            p.write_text(''.join(json.dumps(r) + '\n' for r in records))
            _, want = rcb.context_records(p, 'p2')
        self.assertEqual(nal.claude_context({r['uuid']: r for r in records}, 'p2'), want)


class CommonCap(unittest.TestCase):
    def test_feature_in_most_blocks_dropped(self):
        blocks = [dict(m=i, role='assistant', kind='text', tool_name=None, tool_use_id=None, is_error=False,
                       content=f'paragraph {i} mentions shared_helper_name and more words here') for i in range(8)]
        ev = [('call', 'Bash', dict(command='grep -rn shared_helper_name src'))]
        rows, st, = nal.label_item('fix it', blocks, ev, blank_split, count, {})
        self.assertEqual(st['common_dropped'], 1)
        self.assertFalse(any(r['used'] for r in rows))


class Filters(unittest.TestCase):
    def test_ancestor_dir_dropped(self):
        blocks = [dict(m=i, role='assistant', kind='text', tool_name=None, tool_use_id=None, is_error=False,
                       content=c) for i, c in enumerate([
                           'working inside /Users/me/projects/webapp for this whole session today',
                           'the component lives at /Users/me/projects/webapp/src/Hero.tsx right now'] + [WEATHER] * 6)]
        ev = [('call', 'Read', dict(file_path='/Users/me/projects/webapp/src/Hero.tsx')),
              ('call', 'Bash', dict(command='cd /Users/me/projects/webapp && npm test'))]
        rows, st = nal.label_item('fix it', blocks, ev, blank_split, count, {})
        self.assertEqual(st.get('ancestor_dir_dropped'), 1)  # project root (no suffix key for directories)
        self.assertEqual([r['used'] for r in rows][:2], [False, True])

    def test_root_dirs(self):
        self.assertTrue(nal.root_dir('/Users/Master/DOG'))
        self.assertTrue(nal.root_dir('~/Downloads/LOOKAORCHESTRATOR'))
        self.assertTrue(nal.root_dir('/dev/null'))
        self.assertTrue(nal.root_dir('/private/tmp/claude-501/x/tasks/b1.output'))
        self.assertFalse(nal.root_dir('/Users/Master/proj/src/app.py'))
        self.assertFalse(nal.root_dir('data/video/inbox'))
        self.assertTrue(nal.root_dir('/Users/Master/Downloads/someproject'))  # project root, 4 components
        self.assertFalse(nal.root_dir('/Users/Master/Downloads/someproject/src/lib'))

    def test_review_trivial_classes(self):  # label review 2026-10-12, medium finding
        f = nal.features('see index.tsx and main.js, data.ts')
        self.assertFalse({x for x in f if x[1] in ('index.tsx', 'main.js', 'data.ts')})
        self.assertIn(('path', 'connection_pool.ts'), nal.features('see connection_pool.ts'))  # >= 12 chars kept
        self.assertIn(('ident', 'config.load_all'), nal.features('call config.load_all now'))
        self.assertNotIn(('ident', 'u00e3o'), nal.features('{"t": "configura\\u00e3o"}'))
        self.assertNotIn(('path', 'Master/PIQUETPARTNERS'), nal.features('cd /Users/Master/PIQUETPARTNERS'))
        self.assertFalse({x for x in nal.features('cd /Users/Master/Downloads/someproject && ls') if x[0] == 'line'})
        self.assertIn(('line', 'npm run build -- --filter web'),
                      nal.features('cd /Users/me/proj && npm run build -- --filter web'))
        n = nal.features('score 100.0 and 25000 and 0.973 and 12345 and 3.1416')
        self.assertEqual({x[1] for x in n if x[0] == 'num'}, {'0.973', '12345', '3.1416'})
        q = nal.text_evidence('use `description` and `the retry wrapper` here')
        self.assertEqual({x[1] for _, x in q if x[0] == 'quoted'}, {'the retry wrapper'})

    def test_content_links_join_forked_items(self):
        def it(iid, group, ids):
            return dict(item_id=iid, group=group, blocks=[dict(id=b, chars=300, protected=False) for b in ids])
        a = it('a', 'g1', [f'x{i}' for i in range(10)])
        b = it('b', 'g2', [f'x{i}' for i in range(3)] + [f'y{i}' for i in range(20)])  # 3/10 of a: linked
        c = it('c', 'g3', ['x0'] + [f'z{i}' for i in range(20)])  # 1/10 of a, 1/21 of c: not linked
        d = it('d', 'g1', [f'x{i}' for i in range(10)])  # same group: not a cross-group link
        self.assertEqual(nal.content_links([a, b, c, d]), {('a', 'b'), ('b', 'd')})

    def test_generic(self):
        sets = {f'g{i}': {('ident', 'console.log'), ('ident', f'only_in_{i}')} for i in range(6)}
        gen = nal.generic_features(sets, 6)
        self.assertEqual(gen, {('ident', 'console.log')})
        item = dict(evidence_sets=[dict(kind='ident', value='console.log')], blocks=[dict(protected=False, reasons=[
            dict(kind='ident', value='console.log', refetched=False, rules=['call_value'])])])
        nal.apply_generic(item, gen)
        self.assertFalse(item['blocks'][0]['used'])
        self.assertEqual(item['used_candidates'], 0)


class Codex(unittest.TestCase):
    def records(self):
        def ri(**p):
            return dict(type='response_item', payload=p)
        patch = ('*** Begin Patch\n*** Update File: src/app_core.py\n@@\n'
                 '-    return raw_text.strip() if raw_text else default\n+    return raw_text.strip() or default\n*** End Patch')
        return [
            dict(type='session_meta', payload=dict(id='c1', source='cli')),
            dict(type='event_msg', payload=dict(type='user_message', message='fix the loader')),
            ri(type='message', role='user', content=[dict(type='input_text', text='fix the loader')]),
            ri(type='message', role='user', content=[dict(type='input_text', text='<environment_context>x</environment_context>')]),
            ri(type='message', role='assistant', content=[dict(type='output_text', text='Patching.')]),
            ri(type='custom_tool_call', name='apply_patch', call_id='k1', input=patch),
            ri(type='custom_tool_call_output', call_id='k1', output='Exit code: 0'),
            dict(type='event_msg', payload=dict(type='user_message', message='now run tests')),
            ri(type='message', role='user', content=[dict(type='input_text', text='now run tests')]),
        ]

    def test_window(self):
        ev, ended = nal.codex_window(self.records(), 1, 'fix the loader')
        self.assertEqual(ended, 'next_prompt')
        self.assertEqual([e[0] for e in ev], ['user', 'text', 'call', 'result'])
        w = nal.window_evidence(ev)
        self.assertIn('edit_anchor', w[('line', 'return raw_text.strip() if raw_text else default')]['rules'])
        self.assertIn(('path', 'src/app_core.py'), w)

    def test_compaction_and_abort(self):
        r = self.records()
        r[4:4] = [dict(type='compacted', payload=dict(message='summary'))]
        self.assertEqual(nal.codex_window(r, 1, 'fix the loader')[1], 'compaction')
        r = self.records()
        r[4:4] = [dict(type='event_msg', payload=dict(type='turn_aborted'))]
        self.assertEqual(nal.codex_window(r, 1, 'fix the loader')[1], 'interrupt')


class Hermes(unittest.TestCase):
    def test_window(self):
        def row(i, role, content='', calls=None, summary=0):
            return dict(id=i, role=role, content=content, tool_calls=json.dumps(calls) if calls else None,
                        tool_call_id=None, tool_name=None, timestamp=float(i), _compressed_summary=summary)
        call = dict(id='h1', function=dict(name='patch', arguments=json.dumps(dict(
            path='/repo/src/app_core.py', old_string='def parse_config_value(raw_text, default=None):', new_string='x'))))
        rows = [row(1, 'user', 'fix it'), row(2, 'user', '[System note]'), row(3, 'assistant', 'ok', [call]),
                row(4, 'tool', '{"success": true}'), row(5, 'user', 'next one'), row(6, 'assistant', 'later')]
        human = lambda r: r['role'] == 'user' and not r['content'].startswith('[')  # noqa: E731
        ev, ended = nal.hermes_window(rows, 0, human)
        self.assertEqual(ended, 'next_prompt')
        self.assertEqual([e[0] for e in ev], ['user', 'text', 'call', 'result'])
        self.assertIn(('path', '/repo/src/app_core.py'), nal.window_evidence(ev))
        rows[3]['_compressed_summary'] = 1
        self.assertEqual(nal.hermes_window(rows, 0, human)[1], 'compaction')


class Wrapped(unittest.TestCase):
    def test_json_wrapped(self):
        w = '\x00json:' + json.dumps([dict(type='text', text='Resume prior conversation. x'), dict(type='image')])
        self.assertEqual(nal.json_wrapped(w), 'Resume prior conversation. x')
        self.assertEqual(nal.json_wrapped('plain'), 'plain')
        self.assertEqual(nal.json_wrapped('\x00json:not json'), '\x00json:not json')


class Provenance(unittest.TestCase):
    def test_block_spanning_dossier_blocks(self):
        blocks = [dict(m=0, role='assistant', kind='text', tool_name=None, tool_use_id=None, is_error=False,
                       content='```\nunclosed fence starts here with enough characters'),
                  dict(m=1, role='user', kind='tool_result', tool_name='Bash', tool_use_id='t', is_error=True,
                       content='Traceback: boom error in the module loader path')]
        text = rcb.render(blocks)
        whole = [('blk_0000_x', text, 0, len(text))]
        rows, _ = nal.label_item('g', blocks, [], lambda t: whole, count, {})
        self.assertEqual(rows[0]['src'], [0, 1])
        self.assertTrue(rows[0]['is_error'])
        self.assertEqual(nal.offsets(blocks)[1], text.index('[m0001'))

    @unittest.skipUnless(__import__('importlib').util.find_spec('lcc.relevance.blocks'), 'needs pinned lcc')
    def test_fast_split_equals_lcc(self):
        from lcc.relevance.blocks import split_blocks
        texts = [rcb.render(rcb.render_blocks(claude_session())), '```py\nx = 1\n\n\ny = 2\n', 'a' * 13000 + '\nb\n',
                 '\n\n' + '\n'.join(f'line {i} ' * 40 for i in range(300)) + '\n\n~~~\nunclosed\n\npara\n', '']
        for t in texts:
            want = [(b.id, b.text, b.character_start, b.character_end)
                    for b in split_blocks(t, min_block_chars=nal.MIN_BLOCK, max_block_chars=nal.MAX_BLOCK)]
            self.assertEqual(nal.lcc_split(t), want)

    @unittest.skipUnless(__import__('importlib').util.find_spec('lcc.relevance.blocks'), 'needs pinned lcc')
    def test_lcc_split_offsets(self):
        from lcc.relevance.blocks import split_blocks
        records = claude_session()
        blocks = rcb.render_blocks(nal.claude_context({r['uuid']: r for r in records}, 'p2'))
        split = lambda t: [(b.id, b.text, b.character_start, b.character_end)  # noqa: E731
                           for b in split_blocks(t, min_block_chars=nal.MIN_BLOCK, max_block_chars=nal.MAX_BLOCK)]
        ev, _ = nal.claude_window(records, 4, IAR)
        rows, _ = nal.label_item('fix it', blocks, ev, split, count, {})
        self.assertTrue(any(r['used'] and r['kind'] == 'tool_result' for r in rows))


class Splits(unittest.TestCase):
    def test_deterministic_disjoint_per_source(self):
        groups = {'claude': [f'c{i}' for i in range(100)], 'codex': [f'x{i}' for i in range(20)]}
        a, b = nal.assign_splits(groups), nal.assign_splits(groups)
        self.assertEqual(a, b)
        c = Counter(a[g] for g in groups['claude'])
        self.assertEqual((c['train'], c['dev'], c['test']), (70, 15, 15))
        self.assertEqual(Counter(a[g] for g in groups['codex'])['test'], 3)

    def test_union(self):
        u = nal.Union()
        u.join('a', 'b')
        u.join('c', 'b')
        self.assertEqual(len({u.find(x) for x in 'abc'}), 1)


if __name__ == '__main__':
    unittest.main()
