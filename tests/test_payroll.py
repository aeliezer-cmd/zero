import copy
import datetime as dt
import json
import sqlite3
import unittest
import tempfile
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import app, payroll, treasury, transfer

class PayrollTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.execute('PRAGMA foreign_keys=ON');self.c.executescript(app.SCHEMA)
        self.c.execute("INSERT INTO companies(id,name) VALUES(1,'Empresa')")
        self.c.execute("INSERT INTO users(id,username,name,password) VALUES(1,'admin','Admin','!')")
        self.c.execute("INSERT INTO memberships(user_id,company_id,role,role_name) VALUES(1,1,'admin','Admin')")
        self.c.execute("INSERT INTO employees(id,company_id,name,position,basis,rate) VALUES(1,1,'Ana','Operaria','hourly',10000)")
        self.c.commit();self.day='2026-09-25'
        self.clock=patch.object(app,'today',return_value=dt.date(2026,9,30));self.clock.start()
    def tearDown(self): self.clock.stop();self.c.close()
    def save(self,action,**d):
        try:
            with self.c:
                return app.mutate(self.c,1,1,action,d)
        except Exception:
            try: self.c.rollback()
            except Exception: pass
            raise
    def setup_rate(self,basis='weekly',rate='700',cadence='weekly'):
        return self.save('employee_pay',employee_id=1,basis=basis,rate=rate,cadence=cadence)
    def generate(self,**overrides):
        d=dict(cadence='weekly',end_date=self.day,percentage='100',request_key='payroll-1');d.update(overrides)
        return self.save('payroll',**d)
    def account(self,amount='5000'):
        a=self.save('cash_account',name='Caja chica',kind='cash')['id']
        self.save('cash_deposit',account_id=a,amount=amount,movement_date=self.day,reference='Capital inicial',request_key='capital1',origin='capital')
        return a
    def test_calendar_boundaries(self):
        self.assertEqual(payroll.period(dt.date(2026,9,25),'weekly'),(dt.date(2026,9,19),7))
        self.assertEqual(payroll.period(dt.date(2026,9,15),'biweekly'),(dt.date(2026,8,31),15))
        self.assertEqual(payroll.period(dt.date(2026,9,30),'biweekly'),(dt.date(2026,9,16),15))
        self.assertEqual(payroll.period(dt.date(2026,9,30),'monthly'),(dt.date(2026,8,31),30))
        self.assertEqual(payroll.period(dt.date(2028,2,29),'monthly'),(dt.date(2028,1,31),30))
        for day,cadence in [(dt.date(2026,9,24),'weekly'),(dt.date(2026,8,31),'monthly'),(dt.date(2026,9,16),'biweekly')]:
            with self.assertRaises(ValueError): payroll.period(day,cadence)
    def test_base_fraction_and_duplicate_overlap(self):
        self.setup_rate('monthly','30000','biweekly')
        p=self.generate(cadence='biweekly',end_date='2026-09-15',percentage='50')
        row=app.one(self.c,'SELECT * FROM payrolls WHERE id=?',(p['id'],));self.assertEqual(row['amount'],750000)
        self.assertEqual(self.generate(cadence='biweekly',end_date='2026-09-15',percentage='50'),p)
        with self.assertRaises(ValueError): self.generate(cadence='biweekly',end_date='2026-09-15',percentage='50',request_key='duplicate')
        self.setup_rate('monthly','30000','monthly')
        with self.assertRaises(ValueError): self.generate(cadence='monthly',end_date='2026-09-30',request_key='overlap')
    def test_hours_days_rounding_approved_only(self):
        self.setup_rate('hourly','10.01')
        for minutes,status in [(30,'approved'),(60,'proposed')]:
            self.save('worklog',employee_id=1,work_date=self.day,minutes=minutes,activity='Trabajo',method='Manual')
            if status=='approved': self.save('approve_worklog',id=app.one(self.c,'SELECT MAX(id) id FROM worklogs')['id'])
        p=self.generate();self.assertEqual(app.one(self.c,'SELECT * FROM payrolls')['amount'],501)
        self.assertEqual(json.loads(app.one(self.c,'SELECT * FROM payroll_lines')['detail'])['units'],'0.5')
    def test_contract_revisions_only_release_difference(self):
        self.setup_rate('hourly','10')
        co=self.save('work_contract',employee_id=1,description='Pintar',total='1000')['id']
        self.save('contract_release',id=co,description='Primera etapa',total='1000',progress='25',work_date=self.day,request_key='release1')
        self.save('contract_release',id=co,description='Ampliar función',total='1200',progress='50',work_date=self.day,request_key='release2')
        adjustments=app.rows(self.c,'SELECT * FROM payroll_adjustments ORDER BY id')
        self.assertEqual([a['amount'] for a in adjustments],[25000,35000])
        with self.assertRaises(ValueError): self.save('contract_release',id=co,description='Retroceso',total='100',progress='50',work_date=self.day,request_key='release3')
        p=self.generate();self.assertEqual(app.one(self.c,'SELECT * FROM payrolls')['amount'],60000)
        self.assertEqual(self.c.execute('SELECT count(*) FROM payroll_adjustments WHERE payroll_id=?',(p['id'],)).fetchone()[0],2)
    def test_extra_hours_preview_stale(self):
        self.setup_rate();d=dict(cadence='weekly',end_date=self.day,percentage='100')
        preview=self.save('payroll_preview',**d)
        self.save('payroll_adjustment',employee_id=1,kind='agreed',quantity='2.5',rate='200',description='Horas acordadas',work_date=self.day,request_key='hours1')
        with self.assertRaises(ValueError): self.generate(preview_token=preview['preview_token'])
        self.assertEqual(self.c.execute('SELECT count(*) FROM payrolls').fetchone()[0],0)
        self.generate();self.assertEqual(app.one(self.c,'SELECT * FROM payrolls')['amount'],120000)
    def test_payments_partial_cash_insufficient_atomic_retry(self):
        self.setup_rate();p=self.generate()['id'];a=self.account('500')
        d=dict(id=p,account_id=a,amount='300',paid_date=self.day,reference='Abono',request_key='payment1')
        r=self.save('payroll_payment',**d);self.assertEqual(self.save('payroll_payment',**d),r)
        s=app.state(self.c,1,1);self.assertEqual(s['payrolls'][0]['payment_status'],'partial');self.assertEqual(s['cash_accounts'][0]['balance'],20000)
        with self.assertRaises(ValueError): self.save('payroll_payment',**dict(d,amount='400',request_key='payment2'))
        self.assertEqual(self.c.execute('SELECT count(*) FROM payroll_payments').fetchone()[0],1)
        self.save('cash_deposit',account_id=a,amount='200',movement_date=self.day,reference='Capital',request_key='capital2')
        self.save('payroll_payment',**dict(d,amount='400',request_key='payment2'))
        self.assertEqual(app.state(self.c,1,1)['payrolls'][0]['payment_status'],'paid')
        self.assertEqual(treasury.balance(self.c,a),0)
    def test_company_scope_and_hidden_payroll_totals(self):
        self.setup_rate();p=self.generate()['id']
        with self.c:
            self.c.execute("INSERT INTO departments(id,company_id,name) VALUES(1,1,'Otro')")
            self.c.execute("INSERT INTO users(id,username,name,password) VALUES(2,'review','Revisor','!')")
            self.c.execute("INSERT INTO memberships(user_id,company_id,role,role_name,departments,collections) VALUES(2,1,'review','Revisor','[1]',1)")
        self.assertEqual(app.state(self.c,2,1)['payrolls'],[])
        with self.assertRaises(app.Denied):
            with self.c: app.mutate(self.c,2,1,'employee_pay',dict(employee_id=1,basis='weekly',rate='1',cadence='weekly'))
        with self.assertRaises(app.Denied): payroll.allowed_payroll(app,self.c,1,app.membership(self.c,2,1),p)
    def test_transfer_and_roundtrip_archive_legacy(self):
        self.setup_rate();p=self.generate()['id'];a=self.account()
        b=self.save('cash_account',name='Banco',kind='bank',bank_name='Banco de prueba',account_number='001234',holder_name='Empresa',account_type='checking')['id']
        d=dict(account_id=a,target_id=b,amount='1000',movement_date=self.day,reference='Depósito',request_key='transfer1')
        self.save('cash_transfer',**d);self.save('cash_transfer',**d)
        self.assertEqual(treasury.balance(self.c,b),100000)
        self.save('payroll_payment',id=p,account_id=b,amount='700',paid_date=self.day,reference='Pago',request_key='payment1')
        bundle=transfer.export_company(app,self.c,1,1)
        with self.c: r=transfer.register(app,self.c,dict(company_name='Copia',username='copy',name='Admin',password='abcd',archive=copy.deepcopy(bundle)),True)
        s=app.state(self.c,r['user_id'],r['company_id']);self.assertEqual(sum(a['balance'] for a in s['cash_accounts']),430000)
        self.assertEqual(s['payrolls'][0]['payment_status'],'paid')
        legacy=copy.deepcopy(bundle);legacy['version']=5
        for table in treasury.TABLES+('employee_pay_settings','work_contracts','payroll_adjustments','payroll_payments'): legacy['data'].pop(table)
        for row in legacy['data']['payrolls']:
            for col in ('cadence','request_key','request_json'): row.pop(col)
        for row in legacy['data']['payroll_lines']: row.pop('detail')
        transfer.validate(app,self.c,legacy)
    def test_payroll_concurrent_no_duplicate_and_no_overdraft(self):
        self.setup_rate();a=self.account('700')
        with tempfile.TemporaryDirectory() as folder:
            path=folder+'/test.sqlite3'
            with sqlite3.connect(path) as target: self.c.backup(target)
            def run(action,d):
                try:
                    with sqlite3.connect(path,timeout=10) as c:
                        c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');c.execute('BEGIN IMMEDIATE')
                        return app.mutate(c,1,1,action,d)
                except ValueError: return None
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda key:run('payroll',dict(cadence='weekly',end_date=self.day,percentage='100',request_key=key)),['one','two']))
            self.assertEqual(sum(r is not None for r in results),1)
            p=next(r['id'] for r in results if r)
            with ThreadPoolExecutor(max_workers=2) as pool:
                payments=list(pool.map(lambda key:run('payroll_payment',dict(id=p,account_id=a,amount='500',paid_date=self.day,reference='Pago',request_key=key)),['pay1','pay2']))
            self.assertEqual(sum(r is not None for r in payments),1)
            with sqlite3.connect(path) as c: self.assertEqual(treasury.balance(c,a),20000)
    def test_expense_payment_posts_cash_atomically(self):
        a=self.account('100');e=self.save('expense',description='Material',amount='80',expense_date=self.day)['id']
        self.save('approve_expense',id=e)
        d=dict(expense_id=e,account_id=a,amount='80',paid_date=self.day,reference='Efectivo',request_key='expense1')
        self.save('expense_payment',**d);self.save('expense_payment',**d)
        self.assertEqual(treasury.balance(self.c,a),2000)
        self.assertEqual(app.state(self.c,1,1)['expenses'][0]['balance'],0)
    def test_live_projection_and_flexible_preview(self):
        self.setup_rate('monthly','60000','monthly')
        s=app.state(self.c,1,1)
        proj=s.get('payroll_projection')
        self.assertIsNotNone(proj)
        self.assertIn('monthly',proj['cadences'])
        self.assertEqual(len(proj['employees']),1)
        self.assertEqual(proj['employees'][0]['rate'],6000000)
        # Verify payroll_preview allows previewing future closing date without throwing
        prev=self.save('payroll_preview',cadence='monthly',end_date='2026-10-30',percentage='100')
        self.assertEqual(prev['amount'],6000000)

    def test_pay_past_payroll_flexible_date(self):
        self.setup_rate('weekly','700')
        p=self.generate(cadence='weekly',end_date='2026-09-25')['id']
        a=self.account('1000')
        # Paying a past payroll on current day or period start
        res=self.save('payroll_payment',id=p,account_id=a,amount='700',paid_date='2026-09-28',reference='Pago nómina pasada',request_key='pay_past_1')
        self.assertIn('id',res)
        s=app.state(self.c,1,1)
        self.assertEqual(s['payrolls'][0]['payment_status'],'paid')
    def test_early_close_and_employee_filtering(self):
        self.setup_rate('monthly','50000','monthly')
        # Allow early close on active/future close date
        p=self.save('payroll',cadence='monthly',end_date='2026-10-30',allow_early_close=True,percentage='100',request_key='early_close_1')
        self.assertIn('id',p)
        row=app.one(self.c,'SELECT * FROM payrolls WHERE id=?',(p['id'],))
        self.assertEqual(row['amount'],5000000)

        # Adding 2nd employee and processing single employee vs batch
        self.c.execute("INSERT INTO employees(id,company_id,name,position,basis,rate) VALUES(2,1,'Pedro','Diseñador','monthly',40000)")
        self.c.commit()
        self.save('employee_pay',employee_id=2,basis='monthly',rate='40000',cadence='monthly')
        
        # Batch generation skips already closed Ana (id 1) and calculates Pedro (id 2)
        p2=self.save('payroll',cadence='monthly',end_date='2026-10-30',allow_early_close=True,percentage='100',request_key='batch_2')
        self.assertIn('id',p2)
    def test_deduction_adjustment_and_discount_days(self):
        # Monthly base 30,000 (1,000 per day on 30-day basis)
        self.setup_rate('monthly','30000','monthly')
        
        # 1. Deduction adjustment (e.g. 2 days absence = 2000 RD$)
        self.save('payroll_adjustment',employee_id=1,kind='deduction',rate='1000',quantity='2',description='Descuento por 2 días de ausencia',work_date='2026-09-20',request_key='deduct_1')
        
        # Check projection state
        s=app.state(self.c,1,1)
        proj=s.get('payroll_projection')
        emp_proj=proj['employees'][0]
        self.assertEqual(emp_proj['deductions_total'],200000)
        self.assertEqual(emp_proj['projected_total'],2800000)
        
        # 2. Preview with deduction applied
        prev=self.save('payroll_preview',cadence='monthly',end_date='2026-09-30',percentage='100')
        self.assertEqual(prev['amount'],2800000)
        self.assertEqual(prev['lines'][0]['deductions'],200000)
        
        # 3. Process payroll with discount_days directly in payroll calculation (e.g. 3 additional days discounted = 25 days paid instead of 30)
        # Base 30,000 * 27/30 = 27,000. Minus 2,000 deduction adjustment = 25,000 net.
        p=self.save('payroll',cadence='monthly',end_date='2026-09-30',discount_days='3',percentage='100',request_key='payroll_deduct_p1')
        row=app.one(self.c,'SELECT * FROM payrolls WHERE id=?',(p['id'],))
        self.assertEqual(row['amount'],2500000)

    def test_custom_days_for_daily_and_fixed_workers(self):
        # Daily worker: 800 RD$ per day (basis='daily')
        self.c.execute("INSERT INTO employees(id,company_id,name,position,basis,rate) VALUES(3,1,'Carlos','Jornalero','daily',80000)")
        self.c.commit()
        self.save('employee_pay',employee_id=3,basis='daily',rate='800',cadence='weekly')
        
        # Assign custom 4.5 days worked for Carlos
        p=self.save('payroll',cadence='weekly',end_date='2026-09-25',employee_id=3,custom_days='4.5',percentage='100',request_key='custom_days_p3')
        row=app.one(self.c,'SELECT * FROM payrolls WHERE id=?',(p['id'],))
        # 4.5 days * 800 RD$ = 3,600 RD$ (360000 cents)
        self.assertEqual(row['amount'],360000)

    def test_employee_account_tss_viaticos_and_payout(self):
        # 1. Setup cash account with opening balance
        acc_id = self.save('cash_account', name='Caja General DOP', currency='DOP', kind='cash')['id']
        self.save('cash_deposit', account_id=acc_id, amount='50000', movement_date='2026-09-01', reference='Aporte inicial', request_key='dep-001')

        # 2. Add bonus credit to employee 1
        self.save('employee_account_entry', employee_id=1, direction='credit', amount='10000', entry_date='2026-09-10', concept='Bono por resultados', reference='Bono-01')

        # 3. Apply TSS deduction (Ley 87-01) on 30,000 RD$ base salary
        res_tss = self.save('apply_employee_tss', employee_id=1, base_salary='30000', period_start='2026-09-01', period_end='2026-09-30')
        self.assertEqual(res_tss['sfs'], 91200)       # 3.04% of 30,000 = 912 RD$
        self.assertEqual(res_tss['afp'], 86100)       # 2.87% of 30,000 = 861 RD$
        self.assertEqual(res_tss['total_tss'], 177300) # 5.91% of 30,000 = 1,773 RD$
        self.assertEqual(res_tss['total_patronal'], 461700) # 15.39% patronal = 4,617 RD$

        # 4. Record viático with company cash (disbursed directly from treasury)
        res_vc = self.save('record_employee_viatico', employee_id=1, mode='company_cash', cash_account_id=acc_id, amount='2500', viatico_date='2026-09-15', concept='Viático transporte Santo Domingo', reference='Comprobante-101')
        self.assertTrue(res_vc.get('ok'))

        # 5. Record viático payable (assumed by employee, reimbursable)
        res_vp = self.save('record_employee_viatico', employee_id=1, mode='employee_payable', amount='1200', viatico_date='2026-09-18', concept='Cena y dieta con cliente', reference='Factura-502')
        self.assertTrue(res_vp.get('ok'))

        # 6. Check summary via employee_account action
        summary = self.save('employee_account', employee_id=1)
        self.assertTrue(summary.get('ok'))
        self.assertEqual(summary['total_credit'], 1120000) # 10,000 bonus + 1,200 viático reimbursable
        self.assertEqual(summary['total_debit'], 427300)   # 1,773 TSS + 2,500 viático company cash
        expected_balance = 1120000 - 427300              # 6,927 RD$ (692700 cents)
        self.assertEqual(summary['balance'], expected_balance)
        self.assertEqual(summary['total_tss'], 177300)
        self.assertEqual(summary['total_viaticos_payable'], 120000)
        self.assertEqual(summary['total_viaticos_company'], 250000)

        # 7. Pay partial balance from treasury
        res_pay = self.save('pay_employee_balance', employee_id=1, account_id=acc_id, amount='4000', paid_date='2026-09-20', reference='Transf-9988', notes='Abono de saldo')
        self.assertTrue(res_pay.get('ok'))

        # Verify new balance
        summary2 = self.save('employee_account', employee_id=1)
        self.assertEqual(summary2['balance'], expected_balance - 400000)
        self.assertEqual(summary2['total_paid'], 400000)

    def test_tasks_with_hours_days_weeks_months_influence_payroll(self):
        # Setup employee 1 with hourly rate of 200 RD$ (20,000 cents)
        self.setup_rate('hourly', '200', 'weekly')

        # Create tasks with duration in hours and days
        t1 = self.save('task', title='Instalación eléctrica', responsible_id=1, due_date='2026-09-22', duration=4, duration_unit='hours')
        t2 = self.save('task', title='Pintura de fachada', responsible_id=1, due_date='2026-09-23', duration=1, duration_unit='days')
        
        # Mark tasks as done
        self.save('edit_task', id=t1['id'], title='Instalación eléctrica', responsible_id=1, due_date='2026-09-22', duration=4, duration_unit='hours', status='done')
        self.save('edit_task', id=t2['id'], title='Pintura de fachada', responsible_id=1, due_date='2026-09-23', duration=1, duration_unit='days', status='done')

        # 4 hours + 1 day (8 hours) = 12 hours * 200 RD$ = 2,400 RD$ (240,000 cents)
        with patch.object(app, 'today', return_value=dt.date(2026, 9, 25)):
            proj = self.save('payroll_projection', cadence='weekly')
            emp_p = [x for x in proj['employees'] if x['employee_id'] == 1][0]
            self.assertEqual(emp_p['task_units_accrued'], 12.0)
            self.assertEqual(emp_p['accrued_base'], 240000)

        # Generate payroll
        p = self.generate(request_key='payroll-tasks-1')
        p_row = app.one(self.c, 'SELECT * FROM payrolls WHERE id=?', (p['id'],))
        self.assertEqual(p_row['amount'], 240000)

        line = app.one(self.c, 'SELECT * FROM payroll_lines WHERE payroll_id=?', (p['id'],))
        detail = json.loads(line['detail'])
        self.assertEqual(len(detail['tasks']), 2)
        self.assertEqual(detail['amount'], 240000)

    def test_unit_labores_and_daily_tasks_influence_payroll(self):
        # Setup employee 1 with daily rate of 1,000 RD$ (100,000 cents)
        self.setup_rate('daily', '1000', 'weekly')

        # Task in days: 2 days
        t = self.save('task', title='Nivelación de terreno', responsible_id=1, due_date='2026-09-21', duration=2, duration_unit='days')
        self.save('edit_task', id=t['id'], title='Nivelación de terreno', responsible_id=1, due_date='2026-09-21', duration=2, duration_unit='days', status='done')

        # Create farm and labor
        f = self.save('farm', name='Finca Central')['id']
        job = self.save('add_farm_labor', farm_id=f, employee_id=1, description='Cosecha lote sur', duration=3, duration_unit='days', rate='1500', work_date='2026-09-22')
        self.save('approve_queue_job', id=job['id'])

        # Tasks = 2 days @ 1000 = 2,000 RD$
        # Unit labor = 3 days @ 1500 = 4,500 RD$
        # Total = 6,500 RD$ (650,000 cents)
        p = self.generate(request_key='payroll-tasks-labores-1')
        p_row = app.one(self.c, 'SELECT * FROM payrolls WHERE id=?', (p['id'],))
        self.assertEqual(p_row['amount'], 650000)

        line = app.one(self.c, 'SELECT * FROM payroll_lines WHERE payroll_id=?', (p['id'],))
        detail = json.loads(line['detail'])
        self.assertEqual(len(detail['tasks']), 1)
        self.assertEqual(len(detail['unit_labores']), 1)
        self.assertEqual(detail['amount'], 650000)

if __name__=='__main__': unittest.main()

