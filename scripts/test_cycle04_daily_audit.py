"""発走前待機・期限超過・公式結果待機・回顧未完了を独立検査する。"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

import cycle04_daily_audit as audit

DATE='2026-10-18'
RACE='20261018-TOK-01'
POST=DATE+'T10:00:00+09:00'

class DailyAuditTest(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
        self.day={'race_date_jst':DATE,'initial_scope':[RACE], 'selected_scope':[RACE],
                  'final_scope':[], 'reviewed_scope':[],
                  'races':{RACE:{'scheduled_post_time_jst':POST,'prediction_history':[],
                                 'recommendation_state':'PENDING'}}}
    def run_at(self, time, day=None):
        with patch.object(audit,'_recommendation_check',return_value=[]):
            return audit.audit_days(self.root,[day or self.day],now=datetime.fromisoformat(DATE+'T'+time+'+09:00'))
    def test_initial_and_selected_final_wait_before_but_fail_at_deadline(self):
        before=self.run_at('09:59:59')
        self.assertEqual(before['overdue_count'],0)
        self.assertEqual([x['state'] for x in before['rows']],['WAITING','WAITING','WAITING_RESULT'])
        for time in ('10:00:00','10:00:01'):
            with self.subTest(time=time):
                report=self.run_at(time)
                self.assertEqual(report['overdue_count'],2)
    def test_unselected_race_does_not_require_final(self):
        self.day['selected_scope']=[]
        self.assertNotIn('FINAL',[x['stage'] for x in self.run_at('11:00:00')['rows']])
    def test_future_unrequested_dates_do_not_create_missing_rows(self):
        report=audit.audit_days(self.root,[],now=datetime.fromisoformat(DATE+'T09:00:00+09:00'))
        self.assertEqual(report['rows'],[])
        self.assertEqual(report['state'],'NOT_REQUESTED')
        self.assertEqual(report['target_count'],0)
    def test_result_unknown_waits_but_official_result_makes_missing_review_overdue(self):
        result={'status':'OFFICIAL','race_date_jst':DATE,'race_id':RACE,
                'source_url':'https://www.jra.go.jp/result','retrieved_at_jst':DATE+'T10:05:00+09:00',
                'finish_groups':[[1],[2],[3]]}
        path='docs/validation/test-result.json';full=self.root/path;full.parent.mkdir(parents=True)
        raw=json.dumps(result).encode();full.write_bytes(raw)
        self.day['races'][RACE]['result_ready_ref']={'artifact_path':path,'sha256':audit.fingerprint(raw)}
        with patch.object(audit,'validate_formal_result'), patch('cycle04_result_binding.validate_formal_result'):
            report=self.run_at('10:06:00')
        review=[x for x in report['rows'] if x['stage']=='REVIEW'][0]
        self.assertEqual(review['state'],'OVERDUE')
        full.write_bytes(raw+b' ')
        with self.assertRaisesRegex(ValueError,'hash'):
            self.run_at('10:06:00')
    def test_declared_scope_without_day_is_failure_even_before_post(self):
        path=self.root/'docs/validation/persistence-intents'/DATE/'first.json'
        path.parent.mkdir(parents=True);path.write_text(json.dumps({
            'schema_version':'prediction-persistence-intent-v1','required_race_ids':['2026-10-18-TOKYO-01']}))
        report=audit.audit_days(self.root,[],now=datetime.fromisoformat(DATE+'T09:00:00+09:00'))
        self.assertEqual(report['overdue_count'],1)
        self.assertEqual(report['rows'][0]['race_id'],RACE)

    def test_normal_checker_returns_nonzero_for_overdue_not_for_waiting(self):
        import io
        import check_cycle04
        from contextlib import redirect_stdout,redirect_stderr
        folder=self.root/'docs/validation/records/cycle_04'
        folder.mkdir(parents=True);(folder/(DATE+'.json')).write_text('{}')
        for clock,expected in (('09:59:59',0),('10:00:00',1)):
            instant=datetime.fromisoformat(DATE+'T'+clock+'+09:00')
            class Clock(datetime):
                @classmethod
                def now(cls,tz=None):return instant
            completion={'normal_cycle_complete':False,'issues':[],
                        'state':'未完了','summary_git_readback_verified':False}
            with patch('check_cycle04.check_preparation',return_value={'status':'ACTIVE'}), \
                 patch('check_cycle04.validate_day',return_value=self.day), \
                 patch('cycle04_completion.evaluate_days',return_value=completion), \
                 patch.object(audit,'datetime',Clock), \
                 patch.object(audit,'_recommendation_check',return_value=[]), \
                 redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                self.assertEqual(check_cycle04.main(['--root',str(self.root)]),expected)

if __name__=='__main__':unittest.main()
