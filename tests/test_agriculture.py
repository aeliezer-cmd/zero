import unittest
import sqlite3
import datetime as dt
import app
import agriculture
import transfer

class AgricultureTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.executescript(app.SCHEMA)
        self.c.execute("INSERT INTO companies(id,name) VALUES(1,'Fincas')")
        self.c.execute("INSERT INTO users(id,username,name,password) VALUES(1,'admin','Admin','!')")
        self.c.execute("INSERT INTO memberships(user_id,company_id,role,role_name) VALUES(1,1,'admin','Admin')")
        self.c.execute("INSERT INTO employees(id,company_id,name,position,basis,rate) VALUES(1,1,'Juan','Agricultor','daily',10000)")
        self.f=self.save('farm',name='Finca Norte')['id']
        friday=app.today()-dt.timedelta(days=(app.today().weekday()-4)%7+7)
        self.day=(friday-dt.timedelta(days=6)).isoformat()
        self.end=friday.isoformat()
    def tearDown(self): self.c.close()
    def save(self,action,**d): return app.mutate(self.c,1,1,action,d)
    def make_contract(self,basis='day'):
        return self.save('farm_contract',farm_id=self.f,employee_id=1,kind='temporary',basis=basis,rate='100',description='Cosecha',start_date=self.day,end_date=self.end)['id']
    def test_sales_and_export(self):
        self.save('farm_sale',farm_id=self.f,product='Cacao',quantity='2.125',unit='kg',price='10.10',received='20',customer='Comprador',seller='Vendedor',sale_date=self.day)
        sale=self.c.execute('SELECT * FROM farm_sales').fetchone()
        self.assertEqual(sale['amount'],2146)
        self.assertEqual(sale['received'],2000)
        archive=transfer.export_company(app,self.c,1,1)
        result=transfer.register(app,self.c,dict(company_name='Copia',username='copia',name='Admin',password='abcd',archive=archive),True)
        copied=self.c.execute('SELECT * FROM farm_sales WHERE company_id=?',(result['company_id'],)).fetchone()
        self.assertEqual(copied['amount'],2146);self.assertNotEqual(copied['farm_id'],self.f)
    def test_payroll_once_and_payment(self):
        co=self.make_contract();job=self.save('farm_job',contract_id=co,quantity='2',work_date=self.day,description='Recogida')['id']
        with self.assertRaises(ValueError): self.save('weekly_payroll',farm_id=self.f,start_date=self.day)
        self.save('approve_job',id=job)
        p=self.save('weekly_payroll',farm_id=self.f,start_date=self.day)['id']
        self.assertEqual(self.c.execute('SELECT amount FROM farm_payrolls WHERE id=?',(p,)).fetchone()[0],20000)
        with self.assertRaises(ValueError): self.save('weekly_payroll',farm_id=self.f,start_date=self.day)
        self.save('pay_payroll',id=p,reference='Transferencia 1')
        with self.assertRaises(ValueError): self.save('pay_payroll',id=p,reference='Otra')
        archive=transfer.export_company(app,self.c,1,1)
        imported=transfer.register(app,self.c,dict(company_name='Nomina copia',username='nomina',name='Admin',password='abcd',archive=archive),True)
        line=self.c.execute('SELECT * FROM farm_payroll_lines WHERE company_id=?',(imported['company_id'],)).fetchone()
        self.assertNotEqual(line['job_id'],job)
        self.assertEqual(line['amount'],20000)
    def test_fixed_and_contract_status(self):
        co=self.make_contract('fixed')
        self.save('farm_job',contract_id=co,quantity='1',work_date=self.day,description='Trabajo completo')
        with self.assertRaises(ValueError): self.save('farm_job',contract_id=co,quantity='1',work_date=self.day,description='Duplicado')
        self.save('contract_status',id=co,status='completed')
        with self.assertRaises(ValueError): self.save('farm_job',contract_id=co,quantity='1',work_date=self.day,description='Cerrado')
    def test_scope_and_permissions(self):
        self.c.execute("INSERT INTO departments(id,company_id,name) VALUES(1,1,'Otra área')")
        self.c.execute("INSERT INTO users(id,username,name,password) VALUES(2,'limitado','Limitado','!')")
        self.c.execute("INSERT INTO memberships(user_id,company_id,role,role_name,departments) VALUES(2,1,'register','Auxiliar','[1]')")
        m=app.membership(self.c,2,1)
        self.assertEqual(agriculture.state(app,self.c,2,1,m)['farms'],[])
        with self.assertRaises(app.Denied): app.mutate(self.c,2,1,'farm',dict(name='Prohibida'))
        co=self.make_contract()
        with self.assertRaises(app.Denied): app.mutate(self.c,2,1,'farm_job',dict(contract_id=co,work_date=self.day,quantity=1,description='Prohibido'))
    def test_expense_paid_floor_and_audit(self):
        e=self.save('expense',description='Factura',amount='100',expense_date=self.day)['id']
        self.save('approve_expense',id=e)
        self.save('expense_payment',expense_id=e,amount='50',paid_date=self.day,reference='Pago',request_key='unique')
        with self.assertRaises(ValueError): self.save('edit_expense',id=e,amount='40',expense_date=self.day,description='Cambio',reason='Corrección')
        self.save('edit_expense',id=e,amount='120',expense_date=self.day,description='Corregido',reason='Faltaba material')
        self.assertEqual(self.c.execute('SELECT amount FROM expenses WHERE id=?',(e,)).fetchone()[0],12000)
        self.assertIn('Faltaba material',self.c.execute("SELECT details FROM audit WHERE action='editar gasto'").fetchone()[0])

    def test_edit_and_delete_operations(self):
        # 1. Edit and delete farm
        f2=self.save('farm',name='Unidad Temporal')['id']
        self.save('edit_farm',id=f2,name='Unidad Renombrada')
        row=self.c.execute('SELECT name FROM farms WHERE id=?',(f2,)).fetchone()
        self.assertEqual(row['name'],'Unidad Renombrada')
        del_f=self.save('delete_farm',id=f2)
        self.assertTrue(del_f.get('ok'))

        # 2. Edit and delete contract
        co2=self.save('farm_contract',farm_id=self.f,employee_id=1,kind='temporary',basis='hour',rate='250.00',description='Mantenimiento',start_date=self.day,end_date=self.end)['id']
        self.save('edit_farm_contract',id=co2,rate='300.00',description='Mantenimiento Especial')
        co_row=self.c.execute('SELECT * FROM farm_contracts WHERE id=?',(co2,)).fetchone()
        self.assertEqual(co_row['rate'],30000)
        self.assertEqual(co_row['description'],'Mantenimiento Especial')

        # 3. Add, edit, status, and delete job
        job=self.save('farm_job',contract_id=co2,quantity='5',work_date=self.day,description='Horas limpieza')['id']
        j_row=self.c.execute('SELECT * FROM farm_jobs WHERE id=?',(job,)).fetchone()
        self.assertEqual(j_row['amount'],150000) # 5 * 30000

        # Change status via job_status
        self.save('job_status',id=job,status='approved')
        self.assertEqual(self.c.execute('SELECT status FROM farm_jobs WHERE id=?',(job,)).fetchone()['status'],'approved')

        # Edit job
        self.save('edit_farm_job',id=job,quantity='8',work_date=self.day,description='Horas ampliadas',status='approved')
        j_row2=self.c.execute('SELECT * FROM farm_jobs WHERE id=?',(job,)).fetchone()
        self.assertEqual(j_row2['quantity'],'8')
        self.assertEqual(j_row2['amount'],240000) # 8 * 30000

        # Delete job
        del_j=self.save('delete_farm_job',id=job)
        self.assertTrue(del_j.get('ok'))
        self.assertIsNone(self.c.execute('SELECT * FROM farm_jobs WHERE id=?',(job,)).fetchone())

        # Delete contract
        del_co=self.save('delete_farm_contract',id=co2)
        self.assertTrue(del_co.get('ok'))
        self.assertIsNone(self.c.execute('SELECT * FROM farm_contracts WHERE id=?',(co2,)).fetchone())

    def test_farm_full_profile_and_attachments(self):
        # Create farm with full profile
        res=self.save('farm',name='Planta Industrial Este',code='PI-01',category='Planta / Almacén',manager_id=1,address='Carretera Mella km 12',phone='809-555-0199',size_capacity='1200 m2',status='active',notes='Acceso para camiones de carga')
        fid=res['id']
        row=self.c.execute('SELECT * FROM farms WHERE id=?',(fid,)).fetchone()
        self.assertEqual(row['name'],'Planta Industrial Este')
        self.assertEqual(row['code'],'PI-01')
        self.assertEqual(row['category'],'Planta / Almacén')
        self.assertEqual(row['manager_id'],1)
        self.assertEqual(row['address'],'Carretera Mella km 12')
        self.assertEqual(row['phone'],'809-555-0199')
        self.assertEqual(row['size_capacity'],'1200 m2')
        self.assertEqual(row['status'],'active')
        self.assertEqual(row['notes'],'Acceso para camiones de carga')

        # Edit farm profile
        self.save('edit_farm',id=fid,name='Planta Industrial Central',status='maintenance',notes='En remodelación de techo')
        row2=self.c.execute('SELECT * FROM farms WHERE id=?',(fid,)).fetchone()
        self.assertEqual(row2['name'],'Planta Industrial Central')
        self.assertEqual(row2['status'],'maintenance')
        self.assertEqual(row2['notes'],'En remodelación de techo')
        self.assertEqual(row2['code'],'PI-01')

        # Test attachments for farms
        import attachments
        import base64
        fake_png=base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'\x00'*50).decode()
        attachments.upload(app,self.c,1,dict(company_id=1,entity='farms',entity_id=fid,filename='plano_catastral.png',content_base64=fake_png))
        att=self.c.execute("SELECT * FROM attachments WHERE entity='farms' AND entity_id=?",(fid,)).fetchone()
        self.assertIsNotNone(att)
        self.assertEqual(att['filename'],'plano_catastral.png')

    def test_employment_type_and_bulk_approvals(self):
        # 1. Create fixed and temporary employees
        e_fixed = self.save('employee', name='Ana Fija', position='Contadora', basis='monthly', rate='45000', employment_type='fixed')['id']
        e_temp = self.save('employee', name='Pedro Temporal', position='Jornalero', basis='daily', rate='1200', employment_type='temporary')['id']
        
        emp1 = self.c.execute('SELECT * FROM employees WHERE id=?', (e_fixed,)).fetchone()
        emp2 = self.c.execute('SELECT * FROM employees WHERE id=?', (e_temp,)).fetchone()
        self.assertEqual(emp1['employment_type'], 'fixed')
        self.assertEqual(emp2['employment_type'], 'temporary')

        # Edit employee type
        self.save('edit_employee', id=e_temp, name='Pedro Temporal', position='Jornalero Senior', basis='daily', rate='1400', employment_type='temporary')
        emp2_upd = self.c.execute('SELECT * FROM employees WHERE id=?', (e_temp,)).fetchone()
        self.assertEqual(emp2_upd['position'], 'Jornalero Senior')
        self.assertEqual(emp2_upd['employment_type'], 'temporary')

        # 2. Bulk approve worklogs
        self.save('worklog', employee_id=e_fixed, work_date=self.day, minutes=480, activity='Auditoría', method='Presencial')
        self.save('worklog', employee_id=e_fixed, work_date=self.day, minutes=240, activity='Balances', method='Revisión de comprobantes')
        proposed_logs = self.c.execute("SELECT COUNT(*) FROM worklogs WHERE status='proposed'").fetchone()[0]
        self.assertEqual(proposed_logs, 2)
        
        res_wl = self.save('approve_all_worklogs', work_date=self.day)
        self.assertEqual(res_wl['approved_count'], 2)
        remaining_wl = self.c.execute("SELECT COUNT(*) FROM worklogs WHERE status='proposed'").fetchone()[0]
        self.assertEqual(remaining_wl, 0)

        # 3. Bulk approve farm jobs
        co = self.save('farm_contract', farm_id=self.f, employee_id=e_temp, kind='temporary', basis='day', rate='1400', description='Siembra', start_date=self.day, end_date=self.end)['id']
        self.save('farm_job', contract_id=co, quantity='1', work_date=self.day, description='Siembra Lote A')
        self.save('farm_job', contract_id=co, quantity='1', work_date=self.day, description='Siembra Lote B')
        proposed_jobs = self.c.execute("SELECT COUNT(*) FROM farm_jobs WHERE status='proposed'").fetchone()[0]
        self.assertEqual(proposed_jobs, 2)

        res_fj = self.save('approve_all_farm_jobs', work_date=self.day)
        self.assertEqual(res_fj['approved_count'], 2)
        remaining_fj = self.c.execute("SELECT COUNT(*) FROM farm_jobs WHERE status='proposed'").fetchone()[0]
        self.assertEqual(remaining_fj, 0)

        # 4. Auto-provision default cash account
        self.save('create_default_cash_account')
        cash_acc = self.c.execute("SELECT * FROM cash_accounts WHERE company_id=1").fetchone()
        self.assertIsNotNone(cash_acc)
        self.assertEqual(cash_acc['name'], 'Caja General (DOP)')
        self.assertEqual(cash_acc['currency'], 'DOP')

    def test_queue_job_assign_report_and_approve(self):
        emp_id = self.save('employee', name='Ramón Operario', position='Podador', basis='daily', rate='1500', employment_type='temporary')['id']
        
        # 1. Assign queue job
        res_assign = self.save('assign_queue_job', employee_id=emp_id, farm_id=self.f, description='Poda intensiva de lote 1', basis='fixed', amount='5000', work_date=self.day, notes='Usar equipo de protección')
        job_id = res_assign['id']
        job = self.c.execute('SELECT * FROM farm_jobs WHERE id=?', (job_id,)).fetchone()
        self.assertEqual(job['employee_id'], emp_id)
        self.assertEqual(job['status'], 'proposed')
        self.assertEqual(job['progress'], 0)
        self.assertEqual(job['earned_amount'], 0)
        self.assertEqual(job['completion_status'], 'assigned')

        # 2. Report progress (60%)
        res_rep = self.save('report_queue_job', id=job_id, completion_status='in_progress', progress=60, report_notes='Completado 60% de árboles')
        self.assertEqual(res_rep['progress'], 60)
        self.assertEqual(res_rep['earned_amount'], 300000) # 60% of 5000 = 3000 RD$
        self.assertEqual(res_rep['completion_status'], 'in_progress')
        job_upd = self.c.execute('SELECT * FROM farm_jobs WHERE id=?', (job_id,)).fetchone()
        self.assertEqual(job_upd['progress'], 60)
        self.assertEqual(job_upd['earned_amount'], 300000)

        # 3. Approve job
        res_app = self.save('approve_queue_job', id=job_id)
        self.assertTrue(res_app.get('ok'))
        job_app = self.c.execute('SELECT * FROM farm_jobs WHERE id=?', (job_id,)).fetchone()
        self.assertEqual(job_app['status'], 'approved')
        self.assertEqual(job_app['amount'], 300000)

        # 4. Verify employee account entry created
        entry = self.c.execute("SELECT * FROM employee_account_entries WHERE employee_id=? AND reference=?", (emp_id, f"farm_job:{job_id}")).fetchone()
        self.assertIsNotNone(entry)
        self.assertEqual(entry['credit'], 300000)
        self.assertEqual(entry['kind'], 'accrual_job')

        # 5. Cannot approve a job with 0% progress and 'not_done'
        job2_id = self.save('assign_queue_job', employee_id=emp_id, farm_id=self.f, description='Poda suspendida', basis='fixed', amount='2000', work_date=self.day)['id']
        self.save('report_queue_job', id=job2_id, completion_status='not_done', progress=0, report_notes='Lluvia')
        with self.assertRaises(ValueError):
            self.save('approve_queue_job', id=job2_id)

if __name__=='__main__': unittest.main()



