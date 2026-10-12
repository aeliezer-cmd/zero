import sqlite3
import unittest
import app, commerce, fiscal, payroll, treasury, agriculture

class CrudExitsTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(':memory:')
        self.c.row_factory = sqlite3.Row
        self.c.executescript(app.SCHEMA)
        self.c.execute("INSERT INTO companies(id,name) VALUES(1,'Empresa Test')")
        self.c.execute("INSERT INTO users(id,username,name,password) VALUES(1,'admin','Admin','!')")
        self.c.execute("INSERT INTO memberships(user_id,company_id,role,role_name) VALUES(1,1,'admin','Admin')")
        self.c.execute("INSERT INTO departments(id,company_id,name) VALUES(1,1,'Operaciones')")
        self.c.execute("INSERT INTO projects(id,company_id,name) VALUES(1,1,'General')")
        self.c.execute("INSERT INTO customers(id,company_id,name,contact) VALUES(1,1,'Cliente 1','809-555-0101')")
        self.c.execute("INSERT INTO products(id,company_id,name,amount,description) VALUES(1,1,'Servicio 1',500000,'Mensual')")
        self.c.execute("INSERT INTO employees(id,company_id,name,position,basis,rate,department_id,project_id) VALUES(1,1,'Juan Perez','Operador','monthly',2500000,1,1)")
        self.c.commit()

    def tearDown(self):
        self.c.close()

    def save(self, action, **data):
        with self.c:
            self.c.execute('BEGIN IMMEDIATE')
            return app.mutate(self.c, 1, 1, action, data)

    def test_delete_expense_and_payments(self):
        # Create an expense
        acc = self.save('cash_account', name='Caja DOP', kind='cash')['id']
        self.save('cash_deposit', account_id=acc, amount='1000', movement_date=app.today().isoformat(), reference='Aporte', request_key='dep1')
        exp = self.save('expense', description='Papelería', amount='200', expense_date=app.today().isoformat(), receipt='FAC-1', department_id=1, project_id=1)['id']
        self.save('approve_expense', id=exp)
        
        # Pay the expense partially
        pay = self.save('expense_payment', expense_id=exp, amount='100', paid_date=app.today().isoformat(), reference='Pago 1', request_key='pay1', account_id=acc)['id']
        
        # Cannot delete expense with active payments
        with self.assertRaises(ValueError):
            self.save('delete_expense', id=exp)
            
        # Delete payment
        self.save('delete_expense_payment', id=pay)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM expense_payments WHERE id=?', (pay,)).fetchone()[0], 0)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM cash_movements WHERE source="expense_payments" AND source_id=?', (pay,)).fetchone()[0], 0)
        
        # Now delete expense should succeed
        res = self.save('delete_expense', id=exp)
        self.assertTrue(res['ok'])
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM expenses WHERE id=?', (exp,)).fetchone()[0], 0)

    def test_edit_and_delete_worklog(self):
        wl = self.save('worklog', employee_id=1, minutes=120, work_date=app.today().isoformat(), activity='Mantenimiento', method='Manual', notes='OK')['id']
        self.assertEqual(self.c.execute('SELECT minutes FROM worklogs WHERE id=?', (wl,)).fetchone()[0], 120)
        
        # Edit worklog
        self.save('edit_worklog', id=wl, minutes=180, activity='Mantenimiento General', method='Herramientas', notes='Modificado')
        row = self.c.execute('SELECT minutes, activity FROM worklogs WHERE id=?', (wl,)).fetchone()
        self.assertEqual(row['minutes'], 180)
        self.assertEqual(row['activity'], 'Mantenimiento General')
        
        # Delete worklog
        self.save('delete_worklog', id=wl)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM worklogs WHERE id=?', (wl,)).fetchone()[0], 0)

    def test_discard_pending_payroll(self):
        # Create worklog and approve it
        self.save('employee_pay', employee_id=1, basis='monthly', rate=3000000, cadence='monthly')
        # Add an adjustment
        adj = self.save('payroll_adjustment', employee_id=1, kind='extra', work_date=app.today().isoformat(), quantity='2', rate=50000, description='Horas extra', request_key='adj1')['id']
        
        p = self.save('payroll', cadence='monthly', end_date='2026-10-30', allow_early_close=True, percentage='100', request_key='payr1')['id']
        
        # Verify adjustment was linked
        self.assertEqual(self.c.execute('SELECT payroll_id FROM payroll_adjustments WHERE id=?', (adj,)).fetchone()[0], p)
        # Verify employee account entry was created
        acc_entries = self.c.execute('SELECT COUNT(*) FROM employee_account_entries WHERE reference LIKE ?', (f'payroll:{p}:%',)).fetchone()[0]
        self.assertGreaterEqual(acc_entries, 1)
        
        # Discard the pending payroll
        res = self.save('discard_payroll', id=p)
        self.assertTrue(res['ok'])
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM payrolls WHERE id=?', (p,)).fetchone()[0], 0)
        self.assertIsNone(self.c.execute('SELECT payroll_id FROM payroll_adjustments WHERE id=?', (adj,)).fetchone()[0])
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM employee_account_entries WHERE reference LIKE ?', (f'payroll:{p}:%',)).fetchone()[0], 0)

    def test_edit_and_delete_farm_sale(self):
        f = self.save('farm', name='Finca 1')['id']
        acc = self.save('cash_account', name='Caja Agro DOP', kind='cash')['id']
        self.save('cash_deposit', account_id=acc, amount='500', movement_date=app.today().isoformat(), reference='Dep', request_key='d_agro')
        
        sale = self.save('farm_sale', farm_id=f, product='Plátanos', quantity='100', unit='racimos', price='50', customer='Comprador 1', seller='Vendedor 1', sale_date=app.today().isoformat(), received='20', account_id=acc)['id']
        
        # Check cash movement created
        cm = self.c.execute('SELECT amount FROM cash_movements WHERE source="farm_sale" AND source_id=?', (sale,)).fetchone()
        self.assertEqual(cm['amount'], 2000)
        
        # Edit sale
        self.save('edit_farm_sale', id=sale, farm_id=f, product='Plátanos Extra', quantity='150', unit='racimos', price='50', customer='Comprador 1', seller='Vendedor 1', sale_date=app.today().isoformat(), received='30', account_id=acc)
        row = self.c.execute('SELECT product, amount, received FROM farm_sales WHERE id=?', (sale,)).fetchone()
        self.assertEqual(row['product'], 'Plátanos Extra')
        self.assertEqual(row['amount'], 750000)
        self.assertEqual(row['received'], 3000)
        
        cm2 = self.c.execute('SELECT amount FROM cash_movements WHERE source="farm_sale" AND source_id=?', (sale,)).fetchone()
        self.assertEqual(cm2['amount'], 3000)
        
        # Delete sale
        self.save('delete_farm_sale', id=sale)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM farm_sales WHERE id=?', (sale,)).fetchone()[0], 0)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM cash_movements WHERE source="farm_sale" AND source_id=?', (sale,)).fetchone()[0], 0)

    def test_edit_and_delete_ncf_sequence(self):
        seq = self.save('ncf_sequence', tipo_ncf='B01', numero_inicial='1', numero_final='50', fecha_vencimiento='2028-12-31')['id']
        
        # Edit sequence
        self.save('edit_ncf_sequence', id=seq, numero_final='100', fecha_vencimiento='2029-12-31')
        row = self.c.execute('SELECT numero_final, fecha_vencimiento FROM secuencias_ncf WHERE id=?', (seq,)).fetchone()
        self.assertEqual(row['numero_final'], 100)
        self.assertEqual(row['fecha_vencimiento'], '2029-12-31')
        
        # Delete sequence (unused)
        res = self.save('delete_ncf_sequence', id=seq)
        self.assertTrue(res['ok'])
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM secuencias_ncf WHERE id=?', (seq,)).fetchone()[0], 0)

    def test_archive_and_delete_cash_account(self):
        acc = self.save('cash_account', name='Cuenta Temporal', kind='cash')['id']
        
        # Archive account
        self.save('archive_cash_account', id=acc)
        self.assertEqual(self.c.execute('SELECT archived FROM cash_accounts WHERE id=?', (acc,)).fetchone()[0], 1)
        
        # Unarchive
        self.save('archive_cash_account', id=acc)
        self.assertEqual(self.c.execute('SELECT archived FROM cash_accounts WHERE id=?', (acc,)).fetchone()[0], 0)
        
        # Delete (no movements)
        self.save('delete_cash_account', id=acc)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM cash_accounts WHERE id=?', (acc,)).fetchone()[0], 0)

    def test_edit_and_delete_subscription(self):
        sub = self.save('subscription', customer_id=1, product_id=1, amount='500', frequency='months', interval=1, start_date=app.today().isoformat(), due_days=15)['id']
        
        # Edit subscription
        self.save('edit_subscription', id=sub, amount='600', frequency='months', interval=2, start_date=app.today().isoformat(), due_days=10)
        row = self.c.execute('SELECT amount, interval, due_days FROM subscriptions WHERE id=?', (sub,)).fetchone()
        self.assertEqual(row['amount'], 60000)
        self.assertEqual(row['interval'], 2)
        self.assertEqual(row['due_days'], 10)
        
        # Delete subscription
        self.save('delete_subscription', id=sub)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM subscriptions WHERE id=?', (sub,)).fetchone()[0], 0)

    def test_cancel_and_delete_invoice(self):
        inv = self.save('invoice', customer_id=1, invoice_date=app.today().isoformat(), due_date=app.today().isoformat(), items=[{'product_id': 1, 'quantity': '1'}], request_key='inv1')['id']
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM sales_invoices WHERE id=?', (inv,)).fetchone()[0], 1)
        
        # Delete invoice
        res = self.save('delete_invoice', id=inv)
        self.assertTrue(res['ok'])
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM sales_invoices WHERE id=?', (inv,)).fetchone()[0], 0)
