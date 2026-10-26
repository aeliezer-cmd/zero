import datetime as dt
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
import app
import transfer

class SupplierDirectoryAndSingleCompanyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_db, cls.old_root = app.DB, app.ROOT
        cls.tmp = tempfile.TemporaryDirectory()
        app.ROOT = Path(cls.tmp.name)
        app.DB = app.ROOT / 'data' / 'test.sqlite3'
        app.initialize(seed=False)
        cls.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

        with app.connect() as c:
            c.execute('UPDATE users SET password=?', (app.password_hash('TestingPassword123!'),))
        cls.cookie, cls.csrf = cls.login('admin')

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        app.DB, app.ROOT = cls.old_db, cls.old_root
        cls.tmp.cleanup()

    @classmethod
    def request(cls, path, body=None, cookie='', csrf=''):
        con = http.client.HTTPConnection('127.0.0.1', cls.port)
        headers = {'Cookie': cookie, 'X-CSRF-Token': csrf}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        con.request('POST' if body is not None else 'GET', '/api/' + path,
                    body=json.dumps(body) if body is not None else None, headers=headers)
        r = con.getresponse()
        status = r.status
        resheaders = dict(r.getheaders())
        data = json.loads(r.read())
        con.close()
        return status, data, resheaders

    @classmethod
    def login(cls, username):
        status, data, h = cls.request('login', {'username': username, 'password': 'TestingPassword123!'})
        assert status == 200, (status, data)
        cookie = h['Set-Cookie'].split(';')[0]
        status, data, h = cls.request('me', cookie=cookie)
        return cookie, data['csrf']

    def test_01_supplier_crud_and_expense_linking(self):
        # 1. Create a supplier
        status, res, _ = self.request('action', {
            'company_id': 3,
            'action': 'supplier',
            'name': 'Agroquímica Dominicana SRL',
            'rnc': '1-30-12345-6',
            'contact': 'Ing. Juan Valdez',
            'phone': '809-555-8899',
            'email': 'ventas@agroquimica.do',
            'address': 'Km 4 Carretera Duarte, La Vega',
            'category': 'Insumos Agrícolas',
            'notes': 'Crédito a 30 días.'
        }, self.cookie, self.csrf)
        self.assertEqual(status, 200, res)
        sup_id = res['id']
        self.assertTrue(sup_id > 0)

        # 2. Verify supplier appears in state()
        with app.connect() as c:
            st = app.state(c, 2, 3)
            sup = next((s for s in st['suppliers'] if s['id'] == sup_id), None)
            self.assertIsNotNone(sup)
            self.assertEqual(sup['name'], 'Agroquímica Dominicana SRL')
            self.assertEqual(sup['rnc'], '1-30-12345-6')
            self.assertEqual(sup['category'], 'Insumos Agrícolas')
            self.assertEqual(sup['expenses_count'], 0)
            self.assertEqual(sup['total_amount'], 0)

        # 3. Edit supplier
        status, edit_res, _ = self.request('action', {
            'company_id': 3,
            'action': 'edit_supplier',
            'id': sup_id,
            'name': 'Agroquímica Dominicana GM SRL',
            'rnc': '1-30-12345-6',
            'contact': 'Ing. Juan Valdez (Gerente)',
            'phone': '809-555-9900',
            'email': 'contacto@agroquimica.do',
            'address': 'Km 4 Carretera Duarte, La Vega',
            'category': 'Fertilizantes y Abonos',
            'notes': 'Descuento 5% por pronto pago.'
        }, self.cookie, self.csrf)
        self.assertEqual(status, 200, edit_res)

        # 4. Create an expense linked to this supplier
        with app.connect() as c:
            dept = c.execute("SELECT id FROM departments WHERE company_id=3 LIMIT 1").fetchone()[0]
        status, exp_res, _ = self.request('action', {
            'company_id': 3,
            'action': 'expense',
            'description': 'Compra de fertilizante triple 15 para fincas',
            'amount': '15500.00',
            'expense_date': app.today().isoformat(),
            'department_id': dept,
            'supplier_id': sup_id,
            'receipt': 'Factura B01-000452'
        }, self.cookie, self.csrf)
        self.assertEqual(status, 200, exp_res)
        exp_id = exp_res['id']

        # 5. Check state() now computes supplier statistics
        with app.connect() as c:
            st = app.state(c, 2, 3)
            sup = next((s for s in st['suppliers'] if s['id'] == sup_id), None)
            self.assertEqual(sup['expenses_count'], 1)
            self.assertEqual(sup['total_amount'], 1550000)
            exp = next((e for e in st['expenses'] if e['id'] == exp_id), None)
            self.assertEqual(exp['supplier_id'], sup_id)

        # 6. Attempt to delete supplier with linked expense -> Must fail with descriptive error
        status, del_err, _ = self.request('action', {
            'company_id': 3,
            'action': 'delete_supplier',
            'id': sup_id
        }, self.cookie, self.csrf)
        self.assertEqual(status, 400)
        self.assertIn('gasto(s) vinculado(s)', del_err['error'])

        # 7. Unlink or delete expense, then delete supplier
        status, del_exp, _ = self.request('action', {
            'company_id': 3,
            'action': 'delete_expense',
            'id': exp_id
        }, self.cookie, self.csrf)
        self.assertEqual(status, 200, del_exp)

        # Now supplier deletion succeeds
        status, del_ok, _ = self.request('action', {
            'company_id': 3,
            'action': 'delete_supplier',
            'id': sup_id
        }, self.cookie, self.csrf)
        self.assertEqual(status, 200, del_ok)

        with app.connect() as c:
            st = app.state(c, 2, 3)
            self.assertFalse(any(s['id'] == sup_id for s in st['suppliers']))

    def test_02_single_company_per_account(self):
        # 1. User 'admin' has exactly 1 company in /api/me
        status, me_admin, _ = self.request('me', cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual(len(me_admin['companies']), 1)
        self.assertEqual(me_admin['companies'][0]['id'], 3)
        self.assertEqual(me_admin['companies'][0]['name'], 'Calidad de Vida')

        # 2. User 'monarca' has exactly 1 company in /api/me (Grupo Monarca GM SRL)
        cookie_monarca, csrf_monarca = self.login('monarca')
        status, me_monarca, _ = self.request('me', cookie=cookie_monarca)
        self.assertEqual(status, 200)
        self.assertEqual(len(me_monarca['companies']), 1)
        self.assertEqual(me_monarca['companies'][0]['id'], 4)
        self.assertEqual(me_monarca['companies'][0]['name'], 'Grupo Monarca GM SRL')

        # 3. User 'demo' has exactly 1 company in /api/me (Calidad de Vida · DEMO)
        cookie_demo, _ = self.login('demo')
        status, me_demo, _ = self.request('me', cookie=cookie_demo)
        self.assertEqual(status, 200)
        self.assertEqual(len(me_demo['companies']), 1)
        self.assertEqual(me_demo['companies'][0]['id'], 1)

        # 4. User cannot create a second company
        status, err_co, _ = self.request('company', {
            'company_id': 3,
            'name': 'Segunda Empresa Prohibida SRL'
        }, self.cookie, self.csrf)
        self.assertEqual(status, 403)
        self.assertIn('sola empresa', err_co['error'])

    def test_03_monarca_data_intact(self):
        # Grupo Monarca GM SRL company id 4 must have all its farms and departments intact
        cookie_monarca, csrf_monarca = self.login('monarca')
        with app.connect() as c:
            st = app.state(c, 3, 4)
            self.assertGreaterEqual(len(st['farms']), 7)
            farm_names = {f['name'] for f in st['farms']}
            for expected in ('Patricia', 'La Mesa', 'Güiza', 'Las Pajas', 'Las Caobas', 'Esquea', 'Las Mujeres'):
                self.assertIn(expected, farm_names)
            # Ensure departments exist
            self.assertGreaterEqual(len(st['departments']), 7)

if __name__ == '__main__':
    unittest.main()
