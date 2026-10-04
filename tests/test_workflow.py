import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from tastex.validation import ValidationError
from tastex.workflow import DEFAULT_DB, ROOT, encoded, read_json, run_case, replay, verify_run, file_sha

class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='tastex-test-')
        cls.root=Path(cls.tmp.name)
        cls.original_hash=file_sha(DEFAULT_DB)
        cls.out=cls.root/'baseline'
        cls.result=run_case(ROOT/'cases/kiwi-jerky/brief.json', cls.out)

    @classmethod
    def tearDownClass(cls):
        assert cls.original_hash==file_sha(DEFAULT_DB), 'Source DB changed'
        cls.tmp.cleanup()

    def copy_run(self, name):
        path=self.root/name; shutil.copytree(self.out,path); return path

    def test_real_pipeline_and_exact_replay(self):
        result=replay(self.out,self.root/'replayed')
        self.assertTrue(result['exact_replay'])
        self.assertEqual(result['run_id'],self.result['run_id'])
        self.assertEqual(result['verified_artifacts'],9)
        a=verify_run(self.out); b=verify_run(self.root/'replayed')
        self.assertEqual(a,b)
        self.assertNotIn(str(ROOT), (self.out/'manifest.json').read_text())

    def test_no_overwrite(self):
        with self.assertRaisesRegex(ValidationError, 'already exists'):
            run_case(ROOT/'cases/kiwi-jerky/brief.json',self.out)

    def test_file_tamper_and_path_escape_rejected(self):
        changed=self.copy_run('tamper'); (changed/'report.md').write_text('replaced')
        with self.assertRaisesRegex(ValidationError,'hash mismatch'): verify_run(changed)
        escaped=self.copy_run('escape'); manifest=read_json(escaped/'manifest.json')
        manifest['artifacts']['../outside']='0'*64
        (escaped/'manifest.json').write_bytes(encoded(manifest))
        with self.assertRaisesRegex(ValidationError,'Unsafe'): verify_run(escaped)

    def test_replay_rejects_changed_database_and_code(self):
        wrong=self.root/'wrong.sqlite'; wrong.write_bytes(b'not the original')
        with self.assertRaisesRegex(ValidationError,'original database'): replay(self.out,self.root/'wrong-replay',db_path=wrong)
        from unittest.mock import patch
        with patch('tastex.workflow.source_fingerprint', return_value='a'*64):
            with self.assertRaisesRegex(ValidationError,'original workflow'): replay(self.out,self.root/'code-replay')

    def test_manifest_case_mismatch_rejected(self):
        changed=self.copy_run('case-mismatch'); manifest=read_json(changed/'manifest.json'); manifest['case_id']='OTHER'
        (changed/'manifest.json').write_bytes(encoded(manifest))
        with self.assertRaisesRegex(ValidationError,'case/revision'): verify_run(changed)

    def test_alias_change_during_retrieval_does_not_publish_a_run(self):
        from unittest.mock import patch
        evidence=read_json(self.out/'evidence.json')
        evidence['provenance']['aliases_sha256']='a'*64
        target=self.root/'changed-alias'
        with patch('tastex.retrieval.collect_evidence',return_value=evidence):
            with self.assertRaisesRegex(ValidationError,'configuration changed'):
                run_case(ROOT/'cases/kiwi-jerky/brief.json',target)
        self.assertFalse(target.exists())

    def test_code_change_during_run_does_not_publish(self):
        from unittest.mock import patch
        target=self.root/'changed-code'
        with patch('tastex.workflow.source_fingerprint',side_effect=['a'*64,'b'*64]):
            with self.assertRaisesRegex(ValidationError,'implementation changed'):
                run_case(ROOT/'cases/kiwi-jerky/brief.json',target)
        self.assertFalse(target.exists())

    def test_observation_template_stays_empty(self):
        template=read_json(self.out/'observation-template.json')
        self.assertEqual(template['run_id'],self.result['run_id'])
        self.assertTrue(all(v is None for v in template['ratings'].values()))
        self.assertTrue(all(v is None for v in template['actual_masses_g'].values()))
        with tempfile.TemporaryDirectory() as tmp:
            from tastex.experience import ExperienceStore
            with ExperienceStore(Path(tmp)/'experience.sqlite') as store:
                with self.assertRaises(ValueError): store.record(template,self.out)
                self.assertEqual(store.verify()['event_count'],0)

    def test_blind_sheet_does_not_reveal_recipe(self):
        text=(self.out/'tasting-sheet.md').read_text()
        for term in ('猕猴桃','牛肉','cell-','kiwi','3 g','5 g'):
            self.assertNotIn(term,text)
        self.assertEqual(text.count('待填写'),28)

    def test_transfer_mechanics_not_recipe_transfer(self):
        result=run_case(ROOT/'benchmarks/transfer-brief.json',self.root/'transfer')
        self.assertNotEqual(result['run_id'],self.result['run_id'])
        self.assertEqual(result['cells'],4)
        d=read_json(self.root/'transfer/design.json')
        self.assertEqual(d['template']['origin'],'synthetic_test')
        self.assertIsNone(d['metrics']['sensory_results'])

    def test_reference_resolution_and_unresolved_are_explicit(self):
        e=read_json(self.out/'evidence.json')
        refs={r['reference']:r for r in e['route_references']}
        self.assertEqual(refs['p044_t01_r04']['status'],'retained_reference')
        self.assertEqual(refs['book_pages:43']['status'],'retained_reference')
        from tastex.workflow import audit_references
        result=audit_references({'routes':[{'id':'x','evidence_refs':['not-real']} ]},e)
        self.assertEqual(result[0]['status'],'unresolved_reference')

    def test_cli_failure_is_json_without_stacktrace(self):
        proc=subprocess.run([sys.executable,'-m','tastex','run','missing.json','--out',str(self.root/'missing')],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(proc.returncode,1); self.assertIn('error',json.loads(proc.stderr)); self.assertEqual(proc.stdout,'')

    def test_duplicate_and_nonfinite_json_rejected(self):
        for index, text in enumerate(('{"x":1,"x":2}','{"x":NaN}')):
            p=self.root/f'invalid-{index}.json'; p.write_text(text)
            with self.assertRaises(ValidationError): read_json(p)

if __name__=='__main__': unittest.main()
