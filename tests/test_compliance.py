import unittest
import os
import tempfile
import sqlite3

import app
import dmca
import mailer
import transfer


class DummyCore:
    def text(self, val, label="Campo", maxlen=200):
        if not val or not str(val).strip():
            raise ValueError(f"{label} es requerido.")
        val = str(val).strip()
        if len(val) > maxlen:
            raise ValueError(f"{label} excede {maxlen} caracteres.")
        return val

    def one(self, c, query, params=()):
        cur = c.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None

    def rows(self, c, query, params=()):
        cur = c.execute(query, params)
        return [dict(r) for r in cur.fetchall()]

    def now(self):
        return "2026-10-01T09:30:00"

    def today(self):
        import datetime as dt
        return dt.date(2026, 10, 1)

    def password_hash(self, pwd):
        return "hash:" + pwd

    def audit(self, c, uid, cid, action, entity, entity_id, details=None):
        pass


class TestCompliance(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_compliance.sqlite3")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(app.SCHEMA)
        self.conn.commit()
        self.core = DummyCore()

    def tearDown(self):
        self.conn.close()
        try:
            os.remove(self.db_path)
            os.rmdir(self.tmp_dir)
        except OSError:
            pass

    # 1. COPPA / GDPR Age Gating
    def test_age_gating_underage_us_blocked(self):
        underage_birth = "2018-05-15"
        payload = {
            "company_name": "Empresa Test US",
            "name": "Administrador Test",
            "username": "younguser",
            "password": "password123",
            "birth_date": underage_birth,
            "jurisdiction": "US"
        }
        with self.assertRaises(ValueError) as ctx:
            transfer.register(self.core, self.conn, payload, importing=False)
        self.assertIn("13 años", str(ctx.exception))
        # Ensure no PII was stored
        row = self.conn.execute("SELECT * FROM users WHERE username = 'younguser'").fetchone()
        self.assertIsNone(row)

    def test_age_gating_underage_eu_blocked(self):
        underage_eu_birth = "2012-01-01"  # 14 years old in 2026 (under 16)
        payload = {
            "company_name": "Empresa Test EU",
            "name": "Administrador EU",
            "username": "euteen",
            "password": "password123",
            "birth_date": underage_eu_birth,
            "jurisdiction": "EU"
        }
        with self.assertRaises(ValueError) as ctx:
            transfer.register(self.core, self.conn, payload, importing=False)
        self.assertIn("16 años", str(ctx.exception))
        row = self.conn.execute("SELECT * FROM users WHERE username = 'euteen'").fetchone()
        self.assertIsNone(row)

    def test_age_gating_valid_registration(self):
        valid_birth = "2000-01-01"
        payload = {
            "company_name": "Empresa Valida",
            "name": "Administrador Valido",
            "username": "adultuser",
            "password": "password123",
            "birth_date": valid_birth,
            "jurisdiction": "US"
        }
        res = transfer.register(self.core, self.conn, payload, importing=False)
        self.assertIsNotNone(res["user_id"])
        row = self.conn.execute("SELECT * FROM users WHERE id = ?", (res["user_id"],)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["username"], "adultuser")

    # 2. DMCA Safe Harbor Intake & Counter Notice
    def test_dmca_workflow(self):
        cid = self.conn.execute("INSERT INTO companies(name, demo) VALUES('Test Corp', 0)").lastrowid
        uid = self.conn.execute("INSERT INTO users(username, name, password) VALUES('admin', 'Admin', 'pwd')").lastrowid

        notice_res = dmca.submit_notice(
            self.core,
            self.conn,
            uid,
            cid,
            {
                "claimant_name": "Jane Doe",
                "claimant_email": "jane@example.com",
                "copyrighted_work": "Original catalog photos",
                "infringing_content": "Attachment id or product description",
                "good_faith": 1,
                "accuracy": 1,
                "signature": "Jane Doe"
            }
        )
        self.assertTrue(notice_res["ok"])
        notice_id = notice_res["id"]
        self.assertGreater(notice_id, 0)

        notice_row = self.conn.execute("SELECT * FROM dmca_notices WHERE id = ?", (notice_id,)).fetchone()
        self.assertIsNotNone(notice_row)
        self.assertEqual(notice_row["status"], "received")

        # Submit counter notice
        counter_res = dmca.submit_counter_notice(
            self.core,
            self.conn,
            uid,
            cid,
            {
                "notice_id": notice_id,
                "user_name": "John Smith",
                "user_address": "456 Main St, Santo Domingo",
                "user_phone": "809-555-1234",
                "statement_penalty": 1,
                "jurisdiction_consent": 1,
                "signature": "John Smith"
            }
        )
        self.assertTrue(counter_res["ok"])
        counter_id = counter_res["id"]
        counter_row = self.conn.execute("SELECT * FROM dmca_counter_notices WHERE id = ?", (counter_id,)).fetchone()
        self.assertIsNotNone(counter_row)
        self.assertEqual(counter_row["status"], "received")

    # 3. Mailer CAN-SPAM & RFC 8058 One-Click Unsubscribe
    def test_mailer_rfc8058_headers_and_token(self):
        email_to = "subscriber@example.com"
        cid = 1
        token = mailer.generate_unsubscribe_token(cid, email_to)
        payload = mailer.verify_unsubscribe_token(token)
        self.assertEqual(payload["email"], email_to)
        self.assertEqual(payload["cid"], cid)

        with self.assertRaises(ValueError):
            mailer.verify_unsubscribe_token(token + "tampered")

        msg = mailer.build_compliant_email(
            to_email=email_to,
            subject="Monthly Statement",
            body_html="<p>Check out your statement updates!</p>",
            company_id=cid,
            company_name="Acme Agro Corp",
            base_url="https://app.example.com"
        )

        self.assertIn("List-Unsubscribe", msg)
        self.assertIn("List-Unsubscribe-Post", msg)
        self.assertEqual(msg["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")
        self.assertIn("<https://app.example.com/api/email/unsubscribe?token=", msg["List-Unsubscribe"])


if __name__ == "__main__":
    unittest.main()
