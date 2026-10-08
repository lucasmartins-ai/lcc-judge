import io
import json
import re
import time
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from lcc_engine.observations import ObservationEngine,ObservationRequest
from research import tool_relation_state_capture_v3 as v3

FIELDS={name:{field:i+1 for i,field in enumerate(units)} for name,units in v3.FIELD_UNITS.items()}


def fake(name):
    return lambda rng,index:(dict(FIELDS[name]),dict(api=name,authored=dict(mode=index)))


def captured(clock=lambda:'2026-10-08T12:00:00Z'):
    with patch('research.tool_relation_state_worker.observe_retry',fake('retry')),\
         patch('research.tool_relation_state_worker.observe_udp',fake('udp')),\
         patch('research.tool_relation_state_worker.observe_git',fake('git')):
        return v3.capture_fixture(7,0,clock=clock)


class CaptureMetadataV3Tests(unittest.TestCase):
    def test_wall_clock_is_utc_second_format_from_system_clock(self):
        value=v3.utc_now()
        self.assertRegex(value,r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')
        parsed=datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        self.assertLess(abs(parsed.timestamp()-time.time()),5)

    def test_no_monotonic_counter_reaches_the_timestamp(self):
        with patch('time.perf_counter_ns',side_effect=AssertionError),patch('time.monotonic',side_effect=AssertionError),\
             patch('time.perf_counter',side_effect=AssertionError):
            v3.utc_now()
        source=Path(v3.__file__).read_text()
        self.assertIsNone(re.search(r'perf_counter|monotonic|fromtimestamp|utcfromtimestamp',source))

    def test_capture_emits_one_record_per_collector_field_with_schema_unit_and_capture_time(self):
        result=captured()
        records=result['observations']
        self.assertEqual(len(records),18)
        self.assertEqual({r['field'] for r in records},{f for u in v3.FIELD_UNITS.values() for f in u})
        for r in records:
            self.assertEqual(set(r),{'time','level','entity','field','value','unit','clock','source'})
            self.assertEqual(r['unit'],v3.FIELD_UNITS[r['source']][r['field']])
            self.assertEqual((r['time'],r['clock'],r['level']),('2026-10-08T12:00:00Z','system_wall_utc','INFO'))
            self.assertRegex(r['entity'],r'^tool-[0-9a-f]{12}$')

    def test_collector_schema_drift_fails_capture(self):
        drifted=lambda rng,index:({'retry_attempts':1},{})
        with patch('research.tool_relation_state_worker.observe_retry',drifted),self.assertRaises(ValueError):
            v3.capture_fixture(7,0,clock=lambda:'2026-10-08T12:00:00Z')

    def test_schema_does_not_come_from_caption_registry(self):
        source=Path(v3.__file__).read_text()
        self.assertNotIn('tool_relation_contracts',source)
        self.assertNotIn('tool_relation_state_contracts',source)

    def test_round_trip_into_rank_observations(self):
        records=captured()['observations']
        blocks=v3.to_observation_blocks(records)
        self.assertTrue(all(b['status']=='COMPLETE' for b in blocks))
        entity=records[0]['entity']
        request=ObservationRequest(entity,'udp_sent_datagrams','2026-10-08T00:00:00Z','2026-10-08T23:59:59Z')
        result=ObservationEngine().rank_observations(request,[dict(id=b['id'],text=b['text']) for b in blocks])
        statuses={i['id']:i['status'] for i in result['items']}
        match=[b['id'] for b in blocks if json.loads(b['text'])['field']=='udp_sent_datagrams']
        self.assertEqual([k for k,v in statuses.items() if v=='MATCH'],match)
        self.assertEqual(result['unknowns'],0)
        self.assertEqual(len(result['dropped_ids']),17)
        outside=ObservationRequest(entity,'udp_sent_datagrams','2026-10-09T00:00:00Z','2026-10-09T00:00:01Z')
        self.assertEqual(ObservationEngine().rank_observations(outside,blocks)['kept_ids'],[])

    def test_missing_or_non_wall_clock_metadata_stays_unknown_never_drop(self):
        base=captured()['observations'][0]
        broken=[{k:v for k,v in base.items() if k!=gone} for gone in ['time','level','entity','field','value','unit','clock']]
        broken+=[dict(base,clock='perf_counter_ns',time='2026-10-08T12:00:00Z'),dict(base,time=123456789),
                 dict(base,time='2026-10-08T12:00:00+00:00'),dict(base,unit=None)]
        blocks=v3.to_observation_blocks(broken)
        self.assertTrue(all(b['status']=='UNKNOWN' and b['missing'] for b in blocks))
        request=ObservationRequest(base['entity'],base['field'],'2026-10-08T00:00:00Z','2026-10-08T23:59:59Z')
        result=ObservationEngine().rank_observations(request,blocks)
        self.assertEqual(result['dropped_ids'],[])
        self.assertEqual(result['unknowns'],len(blocks))

    def test_conversion_is_deterministic(self):
        records=captured()['observations']
        self.assertEqual(v3.to_observation_blocks(records),v3.to_observation_blocks(json.loads(json.dumps(records))))

def run_main(**observers):
    out=io.StringIO();error=None
    patches=[patch('research.tool_relation_state_worker.require_worker',lambda:None),
             patch('research.tool_relation_state_worker.git_command',lambda args,cwd:dict(stdout='git version 9.9\n')),
             patch('importlib.metadata.version',lambda name:'1.2.3'),
             patch('sys.stdin',io.StringIO(json.dumps(dict(seed=7,fixtures=2)))),patch('sys.stdout',out)]
    patches+=[patch(f'research.tool_relation_state_worker.observe_{n}',observers.get(n,fake(n))) for n in v3.FIELD_UNITS]
    for p in patches:p.start()
    try:v3.main()
    except Exception as e:error=e
    finally:
        for p in reversed(patches):p.stop()
    return json.loads(out.getvalue()),error


class CaptureMainV3Tests(unittest.TestCase):
    def test_success_receipt_records_provenance_and_fixture_hash(self):
        receipt,error=run_main()
        self.assertIsNone(error)
        self.assertEqual(receipt['versions'],dict(git='git version 9.9',tenacity='1.2.3'))
        self.assertIn('python',receipt)
        self.assertIs(receipt['all_reference_checks_passed'],True)
        for f in receipt['fixtures']:
            content=json.dumps({n:dict(mode=f['index']) for n in v3.FIELD_UNITS},sort_keys=True)
            self.assertEqual(f['fixture_content'],content)
            self.assertEqual(f['fixture_content_sha256'],__import__('hashlib').sha256(content.encode()).hexdigest())

    def test_capture_failure_prints_partial_receipt_then_raises(self):
        calls=[]
        def udp(rng,index):
            calls.append(index)
            if index==1:raise OSError('boom')
            return fake('udp')(rng,index)
        receipt,error=run_main(udp=udp)
        self.assertIsInstance(error,ValueError)
        self.assertIs(receipt['all_reference_checks_passed'],False)
        self.assertEqual(receipt['error_type'],'ValueError')
        self.assertIn('udp: OSError: boom',receipt['error'])
        self.assertEqual(receipt['versions'],dict(git='git version 9.9',tenacity='1.2.3'))
        self.assertEqual(len(receipt['fixtures']),1)
        partial=receipt['partial_fixture']
        self.assertEqual((partial['index'],partial['failed_source'],partial['all_reference_checks_passed']),(1,'udp',False))
        self.assertEqual({r['source'] for r in partial['observations']},{'retry'})
        self.assertEqual(set(partial['raw_observations']),{'retry'})


if __name__=='__main__':
    unittest.main()
