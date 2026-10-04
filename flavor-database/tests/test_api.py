#!/usr/bin/env python3
"""Repeatable API boundary tests; never modify the source database."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flavor_db import FlavorDB, FlavorDBError


class APITests(unittest.TestCase):
    def setUp(self):
        self.db = FlavorDB()

    def tearDown(self):
        self.db.close()

    def test_sql_blocks_mutations_transactions_and_external_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            external = Path(tmp) / 'unauthorized.sqlite'
            statements = [
                'DELETE FROM ingredients',
                "WITH c AS (SELECT 1) DELETE FROM ingredients WHERE id='unknown'",
                "WITH c AS (SELECT 1) UPDATE ingredients SET display_name='bad' WHERE id='unknown'",
                "WITH c AS (SELECT 1) INSERT INTO metadata(key,value_json) VALUES('bad','null')",
                'PRAGMA query_only=OFF', 'VACUUM', 'BEGIN',
                f"ATTACH DATABASE '{external}' AS external", 'SELECT load_extension(?)',
                'SELECT readfile(?)', 'SELECT writefile(?,?)',
                'SELECT 1; DELETE FROM ingredients',
            ]
            for query in statements:
                params = ['missing'] * query.count('?')
                with self.subTest(query=query), self.assertRaises((FlavorDBError, sqlite3.Error)):
                    self.db.sql(query, params=params)
            self.assertFalse(external.exists())
            self.assertEqual(self.db.connection.execute('PRAGMA query_only').fetchone()[0], 1)
            self.assertEqual(self.db.sql('SELECT count(*) AS n FROM ingredients')['items'][0]['n'], 1474)

    def test_sql_timeout_and_authorizer_restore(self):
        with FlavorDB(sql_timeout=0.01) as db:
            start = time.monotonic()
            with self.assertRaisesRegex(sqlite3.OperationalError, 'interrupted'):
                db.sql('WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n) SELECT count(*) FROM n')
            self.assertLess(time.monotonic() - start, 2)
            self.assertEqual(db.sql('SELECT 7 AS answer')['items'], [{'answer': 7}])
            self.assertEqual(db.stats()['counts']['ingredients'], 1474)

    def test_sql_bound_parameters_and_output_cap(self):
        result = self.db.sql('SELECT id FROM ingredients ORDER BY id', limit=3)
        self.assertEqual(result['returned'], 3)
        self.assertTrue(result['truncated'])
        self.assertTrue(result['has_more'])
        self.assertIsNone(result['total'])
        self.assertEqual(self.db.sql('SELECT id FROM ingredients WHERE display_name=?', params=["草莓' OR 1=1 --"])['returned'], 0)
        self.assertEqual(self.db.sql('SELECT :text AS result', params={'text': "' OR 1=1 --"})['items'], [{'result': "' OR 1=1 --"}])
        self.assertEqual(self.db.sql('SELECT 1 AS same, 2 AS same')['items'], [[1, 2]])
        self.assertEqual(self.db.sql("SELECT x'6162' AS value")['items'][0]['value'], {'encoding': 'base64', 'byte_size': 2, 'data': 'YWI='})
        for bad in (0, -1, 10001, True, '3'):
            with self.subTest(limit=bad), self.assertRaises(FlavorDBError):
                self.db.sql('SELECT 1', limit=bad)

    def test_search_literals_and_pagination(self):
        for query in ('%', '_', '\\', "' OR 1=1 --"):
            actual = self.db.search(query, limit=1)
            expected = self.db.connection.execute('SELECT count(*) FROM search_documents WHERE instr(text,?)>0', (query,)).fetchone()[0]
            self.assertEqual(actual['total'], expected)
        first = self.db.search('', kind='ingredient', limit=2)
        second = self.db.search('', kind='ingredient', limit=2, offset=2)
        self.assertEqual(first['total'], 1474)
        self.assertTrue(first['has_more'])
        self.assertTrue(second['truncated'])
        self.assertFalse(set(x['id'] for x in first['items']) & set(x['id'] for x in second['items']))
        last = self.db.search('', kind='ingredient', limit=2, offset=1473)
        self.assertEqual(last['returned'], 1)
        self.assertFalse(last['has_more'])
        self.assertEqual(self.db.search('', kind='page', limit=3)['items'][0]['id'], '1')
        for limit, offset in ((0, 0), (1001, 0), (1, -1), (True, 0)):
            with self.subTest(limit=limit, offset=offset), self.assertRaises(FlavorDBError):
                self.db.search('', limit=limit, offset=offset)

    def test_asset_metadata_and_explicit_export(self):
        asset_id = self.db.connection.execute('SELECT id FROM assets ORDER BY id LIMIT 1').fetchone()[0]
        metadata = self.db.asset(asset_id)
        self.assertNotIn('content', metadata)
        self.assertNotIn('output_path', metadata)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'ingredient.svg'
            exported = self.db.asset(asset_id, out=target)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), metadata['sha256'])
            self.assertEqual(exported['written_bytes'], metadata['byte_size'])
            target.write_bytes(b'existing-data')
            with self.assertRaises(FlavorDBError):
                self.db.asset(asset_id, out=target)
            self.assertEqual(target.read_bytes(), b'existing-data')
            self.db.asset(asset_id, out=target, force=True)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), metadata['sha256'])
            with self.assertRaises(FlavorDBError):
                self.db.asset(asset_id, out=self.db.path, force=True)

    def test_cli_json_stdout_and_json_errors(self):
        command = [sys.executable, str(ROOT / 'flavor_db.py')]
        ok = subprocess.run(command + ['search', '草莓', '--kind', 'ingredient', '--limit', '1'], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(json.loads(ok.stdout)['returned'], 1)
        self.assertEqual(ok.stderr, '')
        for args in (['ingredient', 'missing'], ['search', 'x', '--limit', '0'], ['sql', '--query', 'DELETE FROM ingredients'], ['unknown-command']):
            with self.subTest(args=args):
                bad = subprocess.run(command + list(args), capture_output=True, text=True)
                self.assertNotEqual(bad.returncode, 0)
                self.assertEqual(bad.stdout, '')
                self.assertIn('message', json.loads(bad.stderr)['error'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(APITests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        report = {'suite': 'api_boundary_tests', 'tests_run': result.testsRun, 'success': result.wasSuccessful(),
                  'failures': [{'test': str(t), 'traceback': reason} for t, reason in result.failures],
                  'errors': [{'test': str(t), 'traceback': reason} for t, reason in result.errors]}
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
