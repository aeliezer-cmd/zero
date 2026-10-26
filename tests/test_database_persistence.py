import unittest
import json
import base64
import tempfile
import sqlite3
import shutil
from pathlib import Path
import app

class TestDatabasePersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.sqlite3', delete=False)
        self.tmp.close()
        self.db_path = Path(self.tmp.name)
        self.orig_db = app.DB
        app.DB = self.db_path
        app.initialize(seed=True)

    def tearDown(self):
        app.DB = self.orig_db
        if self.db_path.exists():
            self.db_path.unlink()

    def test_user_sessions_table_and_persistence(self):
        with app.connect() as c:
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            self.assertIn('user_sessions', tables)
            c.execute("INSERT OR REPLACE INTO user_sessions(token, user_id, csrf, expires) VALUES(?,?,?,?)",
                      ('test_token_123', 2, 'csrf_abc', 9999999999.0))
            row = app.one(c, "SELECT * FROM user_sessions WHERE token=?", ('test_token_123',))
            self.assertIsNotNone(row)
            self.assertEqual(row['user_id'], 2)

    def test_auto_seed_monarca_exists(self):
        with app.connect() as c:
            monarca = app.one(c, "SELECT id, name FROM companies WHERE name LIKE '%Monarca%'")
            self.assertIsNotNone(monarca)
            employees = app.rows(c, "SELECT * FROM employees WHERE company_id=?", (monarca['id'],))
            self.assertEqual(len(employees), 0)

    def test_database_backup_and_restore(self):
        with tempfile.NamedTemporaryFile(suffix='.sqlite3', delete=False) as backup_tmp:
            backup_path = Path(backup_tmp.name)
        try:
            with app.connect() as src, sqlite3.connect(backup_path) as dst:
                src.backup(dst)
            raw_bytes = backup_path.read_bytes()
            self.assertTrue(raw_bytes.startswith(b'SQLite format 3\x00'))
        finally:
            if backup_path.exists():
                backup_path.unlink()

    def test_auto_backup_mechanism(self):
        app.auto_backup()
        backup_dir = app.DB.parent / 'backups'
        today_backup = backup_dir / f"auto_backup_{app.today().isoformat()}.sqlite3"
        self.assertTrue(today_backup.exists())
        self.assertGreater(today_backup.stat().st_size, 0)

    def test_fresh_zero_sqlite3_copies_template(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            fresh_db = temp_dir / 'zero.sqlite3'
            self.assertFalse(fresh_db.exists())
            old_db = app.DB
            app.DB = fresh_db
            try:
                app.initialize(seed=False)
                self.assertTrue(fresh_db.exists())
                with app.connect() as c:
                    monarca = app.one(c, "SELECT id, name FROM companies WHERE name LIKE '%Monarca%'")
                    self.assertIsNotNone(monarca)
                    farms = app.rows(c, "SELECT * FROM farms WHERE company_id=?", (monarca['id'],))
                    self.assertGreaterEqual(len(farms), 7)
            finally:
                app.DB = old_db
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == '__main__':
    unittest.main()
