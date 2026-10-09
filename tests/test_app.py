import concurrent.futures
import datetime as dt
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
import app

class PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_db,cls.old_root=app.DB,app.ROOT
        cls.tmp=tempfile.TemporaryDirectory()
        app.ROOT=Path(cls.tmp.name);app.DB=app.ROOT/'data'/'test.sqlite3'
        app.initialize(seed=False)
        cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        cls.port=cls.server.server_address[1]
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        with app.connect() as c:
            c.execute('UPDATE users SET password=?',(app.password_hash('TestingPassword123!'),))
            c.execute('INSERT INTO users(id,username,name,password) VALUES(4,?,?,?)',('limited','Limitado',app.password_hash('TestingPassword123!')))
            c.execute('INSERT INTO users(id,username,name,password) VALUES(5,?,?,?)',('reviewer','Revisor',app.password_hash('TestingPassword123!')))
            dep=c.execute('SELECT id FROM departments WHERE company_id=3 LIMIT 1').fetchone()[0]
            cls.dep=dep
            c.execute('INSERT INTO memberships VALUES(4,3,?,?,?,?,?)',('register','Auxiliar',0,json.dumps([dep]),'[]'))
            c.execute('INSERT INTO memberships VALUES(5,3,?,?,?,?,?)',('review','Supervisor',1,'[]','[]'))
        cls.cookie,cls.csrf=cls.login('admin')
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();app.DB,app.ROOT=cls.old_db,cls.old_root;cls.tmp.cleanup()
    @classmethod
    def request(cls,path,body=None,cookie='',csrf='',origin=None):
        con=http.client.HTTPConnection('127.0.0.1',cls.port)
        headers={'Cookie':cookie,'X-CSRF-Token':csrf}
        if origin: headers['Origin']=origin
        if body is not None: headers['Content-Type']='application/json'
        con.request('POST' if body is not None else 'GET','/api/'+path,body=json.dumps(body) if body is not None else None,headers=headers)
        r=con.getresponse();status=r.status;resheaders=dict(r.getheaders());data=json.loads(r.read());con.close();return status,data,resheaders
    @classmethod
    def login(cls,username):
        status,data,h=cls.request('login',{'username':username,'password':'TestingPassword123!'})
        assert status==200,(status,data)
        cookie=h['Set-Cookie'].split(';')[0]
        status,data,h=cls.request('me',cookie=cookie)
        return cookie,data['csrf']
    def action(self,action,**data):
        status,result,_=self.request('action',{'company_id':3,'action':action,**data},self.cookie,self.csrf)
        self.assertEqual(status,200,result)
        return result
    def contract(self,**overrides):
        cu=self.action('customer',name='Cliente prueba')['id']
        pr=self.action('product',name='Servicio prueba',amount='100.00')['id']
        return self.action('subscription',customer_id=cu,product_id=pr,amount='100.00',frequency='once',interval=1,start_date=(app.today()-dt.timedelta(days=10)).isoformat(),due_days=5,**overrides)['id']
    def charges(self,sid):
        with app.connect() as c: return [x for x in app.charge_list(c,3) if x['subscription_id']==sid]
    def test_01_auth_isolation_and_csrf(self):
        self.assertEqual(self.request('state?company_id=3')[0],403)
        self.assertEqual(self.request('state?company_id=1',cookie=self.cookie)[0],403)
        self.assertEqual(self.request('action',{'company_id':3,'action':'customer','name':'x'},self.cookie)[0],403)
        self.assertEqual(self.request('action',{'company_id':3,'action':'customer','name':'x'},self.cookie,self.csrf,'https://evil.example')[0],403)
        status,data,_=self.request('me',cookie=self.cookie)
        self.assertEqual([x['id'] for x in data['companies']],[3])
        status,data,_=self.request('dashboard',cookie=self.cookie)
        self.assertEqual([x['id'] for x in data['companies']],[3])
    def test_02_month_anchors(self):
        sub={'start_date':'2024-01-31','frequency':'months','interval':1}
        self.assertEqual([app.occurrence(sub,i).isoformat() for i in range(4)],['2024-01-31','2024-02-29','2024-03-31','2024-04-30'])
        sub['start_date']='2025-01-31'
        self.assertEqual(app.occurrence(sub,1).isoformat(),'2025-02-28')
        sub['interval']=2
        self.assertEqual(app.occurrence(sub,1).isoformat(),'2025-03-31')
    def test_03_generation_idempotence_and_end(self):
        with app.connect() as c:
            cu=c.execute('INSERT INTO customers(company_id,name) VALUES(3,?)',('Recurrencia',)).lastrowid
            pr=c.execute('INSERT INTO products(company_id,name,amount) VALUES(3,?,10000)',('Plan',)).lastrowid
            sid=c.execute("INSERT INTO subscriptions(company_id,customer_id,product_id,amount,frequency,interval,start_date,end_date,due_days,created_at) VALUES(3,?,?,10000,'months',1,'2024-01-31','2024-03-31',5,?)",(cu,pr,app.now())).lastrowid
            app.generate(c,2,3,dt.date(2024,5,1))
            entries=app.rows(c,'SELECT * FROM charges WHERE subscription_id=?',(sid,))
            self.assertEqual(len(entries),3)
            self.assertEqual(entries[1]['due_date'],'2024-03-05')
            app.generate(c,2,3,dt.date(2024,5,1))
            self.assertEqual(c.execute('SELECT COUNT(*) FROM charges WHERE subscription_id=?',(sid,)).fetchone()[0],3)
            c.execute("UPDATE subscriptions SET canceled_at=? WHERE id=?",(app.now(),sid))
            self.assertEqual(app.generate(c,2,3,dt.date(2027,1,1)),0)
    def test_04_partial_payments_retry_and_overpayment(self):
        sid=self.contract();ch=self.charges(sid)[0]
        key='test-payment-'+str(sid)
        data=dict(charge_id=ch['id'],amount='30.25',paid_date=app.today().isoformat(),reference='Recibo 1',request_key=key)
        first=self.action('payment',**data);retry=self.action('payment',**data)
        self.assertEqual(first['id'],retry['id']);self.assertTrue(retry['duplicate'])
        self.assertEqual(self.charges(sid)[0]['balance'],6975)
        status,_,_=self.request('action',{'company_id':3,'action':'payment',**data,'amount':'80','request_key':key+'other'},self.cookie,self.csrf)
        self.assertEqual(status,400)
        self.action('payment',**{**data,'amount':'69.75','request_key':key+'last'})
        self.assertEqual(self.charges(sid)[0]['status'],'paid')
        self.assertEqual(self.charges(sid)[0]['alert'],'')
    def test_05_concurrent_payments_do_not_overdraw(self):
        sid=self.contract();ch=self.charges(sid)[0]
        def pay(i): return self.request('action',{'company_id':3,'action':'payment','charge_id':ch['id'],'amount':'70','paid_date':app.today().isoformat(),'reference':'Concurrente','request_key':f'concurrent-{sid}-{i}'},self.cookie,self.csrf)[0]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor: result=list(executor.map(pay,[1,2]))
        self.assertEqual(sorted(result),[200,400]);self.assertEqual(self.charges(sid)[0]['balance'],3000)
    def test_06_scope_and_cumulative_roles(self):
        eid=self.action('expense',description='Aprobar dentro del alcance',amount='150',expense_date=app.today().isoformat(),department_id=self.dep)['id']
        outside=self.action('expense',description='Fuera de alcance',amount='120',expense_date=app.today().isoformat())['id']
        cookie,csrf=self.login('limited')
        status,data,_=self.request('state?company_id=3',cookie=cookie)
        self.assertNotIn('customers',data);self.assertIn(eid,[x['id'] for x in data['expenses']]);self.assertNotIn(outside,[x['id'] for x in data['expenses']])
        self.assertEqual(self.request('action',{'company_id':3,'action':'approve_expense','id':eid},cookie,csrf)[0],403)
        self.assertEqual(self.request('action',{'company_id':3,'action':'expense','description':'Escapar','amount':'1','expense_date':app.today().isoformat()},cookie,csrf)[0],403)
        reviewer,token=self.login('reviewer')
        self.assertEqual(self.request('action',{'company_id':3,'action':'approve_expense','id':eid},reviewer,token)[0],200)
        self.assertEqual(self.request('action',{'company_id':3,'action':'department','name':'No permitido'},reviewer,token)[0],403)
    def test_07_cross_company_foreign_keys_blocked(self):
        with app.connect() as c:
            cu=c.execute('INSERT INTO customers(company_id,name) VALUES(1,?)',('Privado',)).lastrowid
            pr=c.execute('INSERT INTO products(company_id,name,amount) VALUES(3,?,10000)',('Local',)).lastrowid
        status,_,_=self.request('action',{'company_id':3,'action':'subscription','customer_id':cu,'product_id':pr,'amount':'100','frequency':'once','interval':1,'start_date':app.today().isoformat(),'due_days':0},self.cookie,self.csrf)
        self.assertEqual(status,404)
    def test_08_alert_windows_shared(self):
        fixed=dt.date(2026,9,22)
        with app.connect() as c:
            for delta,expected in [(6,''),(5,'Vence en 5 días o menos'),(1,'Vence en 24 horas'),(0,'Vence hoy'),(-1,'Vencido')]:
                cu=c.execute('INSERT INTO customers(company_id,name) VALUES(3,?)',('Alertas',)).lastrowid
                pr=c.execute('INSERT INTO products(company_id,name,amount) VALUES(3,?,100)',('Alerta',)).lastrowid
                sid=c.execute("INSERT INTO subscriptions(company_id,customer_id,product_id,amount,frequency,interval,start_date,due_days,created_at) VALUES(3,?,?,100,'once',1,'2026-09-01',0,?)",(cu,pr,app.now())).lastrowid
                ident=c.execute("INSERT INTO charges(company_id,subscription_id,period_date,due_date,amount,created_at) VALUES(3,?,'2026-09-01',?,100,?)",(sid,(fixed+dt.timedelta(days=delta)).isoformat(),app.now())).lastrowid
                with patch('app.today',return_value=fixed):
                    admin=next(x for x in app.state(c,2,3)['charges'] if x['id']==ident)
                    reviewer=next(x for x in app.state(c,5,3)['charges'] if x['id']==ident)
                    self.assertEqual(admin['alert'],expected);self.assertEqual(reviewer['alert'],expected)
    def test_09_persistence_backup_and_audit(self):
        customer=self.action('customer',name='Persistencia')['id']
        with app.connect() as c:
            self.assertEqual(c.execute('SELECT name FROM customers WHERE id=?',(customer,)).fetchone()[0],'Persistencia')
            self.assertTrue(c.execute("SELECT id FROM audit WHERE entity='customers' AND entity_id=?",(customer,)).fetchone())
        backup=Path(self.tmp.name)/'backup.sqlite3';app.backup(backup)
        with sqlite3.connect(backup) as c:
            self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(c.execute('SELECT name FROM customers WHERE id=?',(customer,)).fetchone()[0],'Persistencia')
    def test_10_cancel_preserves_balance(self):
        sid=self.contract();before=self.charges(sid)
        self.action('cancel_subscription',id=sid)
        self.assertEqual(self.charges(sid),before)
        with app.connect() as c:
            self.assertTrue(app.one(c,'SELECT * FROM subscriptions WHERE id=?',(sid,))['canceled_at'])
            app.generate(c,2,3,app.today()+dt.timedelta(days=400))
            self.assertEqual(len(app.rows(c,'SELECT * FROM charges WHERE subscription_id=?',(sid,))),1)
    def test_11_dashboard_cash_not_billings(self):
        with app.connect() as c: before=app.dashboard(c,2,app.today(),app.today())['companies'][0]['collected']
        sid=self.contract()
        with app.connect() as c: after=app.dashboard(c,2,app.today(),app.today())['companies'][0]['collected']
        self.assertEqual(before,after)
        ch=self.charges(sid)[0]
        self.action('payment',charge_id=ch['id'],amount='12.50',paid_date=app.today().isoformat(),reference='Prueba caja',request_key='cash-'+str(sid))
        with app.connect() as c: result=app.dashboard(c,2,app.today(),app.today())['companies'][0]['collected']
        self.assertEqual(result-before,1250)
    def test_12_expense_requires_approval(self):
        eid=self.action('expense',description='Material',amount='50',expense_date=app.today().isoformat())['id']
        data={'company_id':3,'action':'expense_payment','expense_id':eid,'amount':'20','paid_date':app.today().isoformat(),'reference':'E-1','request_key':'expense-'+str(eid)}
        self.assertEqual(self.request('action',data,self.cookie,self.csrf)[0],400)
        self.action('approve_expense',id=eid)
        self.assertEqual(self.request('action',data,self.cookie,self.csrf)[0],200)
        self.assertEqual(self.request('action',data,self.cookie,self.csrf)[0],200)
        with app.connect() as c: self.assertEqual(c.execute('SELECT SUM(amount) FROM expense_payments WHERE expense_id=?',(eid,)).fetchone()[0],2000)
    def test_13_timezone_and_money(self):
        self.assertEqual(app.dt.datetime(2026,9,23,2,tzinfo=dt.timezone.utc).astimezone(app.TZ).date(),dt.date(2026,9,22))
        self.assertEqual(app.amount('0.29'),29)
        for value in ('0','-1','nan','infinity','1.001'):
            with self.assertRaises(ValueError): app.amount(value)
    def test_14_historical_balance_uses_payment_date(self):
        sid=self.contract();ch=self.charges(sid)[0]
        cutoff=app.today()-dt.timedelta(days=1)
        with app.connect() as c: before=app.dashboard(c,2,cutoff,cutoff)['companies'][0]
        self.action('payment',charge_id=ch['id'],amount='10.00',paid_date=app.today().isoformat(),reference='Después del cierre',request_key='historical-'+str(sid))
        with app.connect() as c: after=app.dashboard(c,2,cutoff,cutoff)['companies'][0]
        self.assertEqual(before['receivable'],after['receivable'])
        self.assertEqual(before['collected'],after['collected'])
    def test_15_failure_rolls_back(self):
        with app.connect() as c: before=c.execute('SELECT COUNT(*) FROM payments').fetchone()[0]
        status,_,_=self.request('action',{'company_id':3,'action':'payment','charge_id':999999,'amount':'1','paid_date':app.today().isoformat(),'reference':'Inválido','request_key':'bad-reference'},self.cookie,self.csrf)
        self.assertEqual(status,404)
        with app.connect() as c: after=c.execute('SELECT COUNT(*) FROM payments').fetchone()[0]
        self.assertEqual(before,after)
    def test_17_registration_creates_isolated_company(self):
        payload={'company_name':'Empresa nueva QA','name':'Dueño QA','username':'nuevo_qa','password':'1234'}
        status,result,_=self.request('register',payload)
        self.assertEqual(status,201,result)
        status,_,headers=self.request('login',{'username':'nuevo_qa','password':'1234'})
        self.assertEqual(status,200)
        cookie=headers['Set-Cookie'].split(';')[0]
        status,me,_=self.request('me',cookie=cookie)
        self.assertEqual(len(me['companies']),1);self.assertEqual(me['companies'][0]['name'],'Empresa nueva QA')
        self.assertEqual(self.request('state?company_id=3',cookie=cookie)[0],403)
        self.assertEqual(self.request('register',payload)[0],400)
    def test_18_export_import_roundtrip_and_duplicate(self):
        status,archive,_=self.request('export?company_id=3',cookie=self.cookie)
        self.assertEqual(status,200)
        self.assertNotIn('users',archive['data']);self.assertNotIn('memberships',archive['data'])
        self.assertTrue(all(set(a)=={'id','name'} for a in archive['actors']))
        payload={'company_name':'Copia QA','name':'Responsable copia','username':'copia_qa','password':'1234','archive':archive}
        status,result,_=self.request('register-import',payload)
        self.assertEqual(status,201,result)
        newcid=result['company_id'];newuid=result['user_id']
        with app.connect() as c:
            recovered=app.state(c,newuid,newcid);original=app.state(c,2,3)
            for table in ('customers','products','subscriptions','charges','payments','employees','worklogs','tasks','expenses'):
                self.assertEqual(len(recovered[table]),len(original[table]),table)
            self.assertEqual(sum(x['balance'] for x in recovered['charges']),sum(x['balance'] for x in original['charges']))
            self.assertEqual(sum(x['paid'] for x in recovered['expenses']),sum(x['paid'] for x in original['expenses']))
            self.assertEqual(len(recovered['members']),1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM memberships WHERE user_id=?',(newuid,)).fetchone()[0],1)
            self.assertTrue(all(x['company_id']==newcid for x in recovered['charges']))
            self.assertTrue(c.execute('SELECT name FROM users WHERE active=0').fetchone())
        status,_,_=self.request('register-import',{**payload,'username':'duplicate_qa','company_name':'Copia duplicada QA'})
        self.assertEqual(status,400)
        with app.connect() as c: self.assertIsNone(app.one(c,"SELECT id FROM users WHERE username='duplicate_qa'"))
    def test_19_export_authorization(self):
        cookie,_=self.login('reviewer')
        self.assertEqual(self.request('export?company_id=3',cookie=cookie)[0],403)
        self.assertEqual(self.request('export?company_id=1',cookie=self.cookie)[0],403)
        self.assertEqual(self.request('export?company_id=3')[0],403)
    def test_20_import_rejects_foreign_refs_atomically(self):
        _,archive,_=self.request('export?company_id=3',cookie=self.cookie)
        archive['data']['subscriptions'][0]['customer_id']=999999
        payload={'company_name':'Inválida QA','name':'Inválido','username':'invalid_qa','password':'1234','archive':archive}
        self.assertEqual(self.request('register-import',payload)[0],400)
        with app.connect() as c:
            self.assertIsNone(app.one(c,"SELECT id FROM companies WHERE name='Inválida QA'"))
            self.assertIsNone(app.one(c,"SELECT id FROM users WHERE username='invalid_qa'"))
    def test_21_import_rejects_overpayment(self):
        _,archive,_=self.request('export?company_id=3',cookie=self.cookie)
        archive['data']['payments'][0]['amount']=99999999
        payload={'company_name':'Saldo inválido','name':'Inválido','username':'invalid_balance','password':'1234','archive':archive}
        self.assertEqual(self.request('register-import',payload)[0],400)
    def test_22_registration_does_not_claim_existing_account(self):
        payload={'company_name':'Reclamar QA','name':'Otro','username':'admin','password':'1234'}
        self.assertEqual(self.request('register',payload)[0],400)
        self.assertEqual(self.request('register',{**payload,'username':'new_origin'},origin='https://evil.example')[0],403)
        with app.connect() as c: self.assertEqual(c.execute('SELECT COUNT(*) FROM memberships WHERE user_id=2').fetchone()[0],1)
    def test_23_csv_respects_scope_and_permissions(self):
        import report_export
        filters={'type':'expenses','start':'2020-01-01','end':'2030-01-01','department':str(self.dep)}
        with app.connect() as c:
            csv=report_export.build(app,c,4,3,filters).decode('utf-8-sig')
            self.assertIn('Aprobar dentro del alcance',csv)
            self.assertNotIn('Fuera de alcance',csv)
            with self.assertRaises(app.Denied): report_export.build(app,c,4,3,{**filters,'type':'charges'})
            with self.assertRaises(app.Denied): report_export.build(app,c,2,1,filters)
            empty=report_export.build(app,c,2,3,{**filters,'department':'999999'}).decode('utf-8-sig')
            self.assertEqual(len(empty.splitlines()),1)
    def test_24_attachments_persist_validate_and_enforce_scope(self):
        import base64
        payload=base64.b64encode(b'%PDF-1.4\n% comprobante de prueba\n%%EOF').decode()
        eid=self.action('expense',description='Gasto con factura',amount='10',expense_date=app.today().isoformat(),department_id=self.dep)['id']
        data={'company_id':3,'entity':'expenses','entity_id':eid,'filename':'factura.pdf','content_base64':payload}
        status,result,_=self.request('attachments',data,self.cookie,self.csrf)
        self.assertEqual(status,200,result);aid=result['id']
        self.assertTrue(self.request('attachments',data,self.cookie,self.csrf)[1]['duplicate'])
        status,files,_=self.request('attachments?company_id=3&entity=expenses&entity_id='+str(eid),cookie=self.cookie)
        self.assertEqual(len(files['files']),1);self.assertNotIn('content_base64',files['files'][0])
        bad={**data,'filename':'virus.html'}
        self.assertEqual(self.request('attachments',bad,self.cookie,self.csrf)[0],400)
        self.assertEqual(self.request('attachments',{**data,'filename':'../factura.pdf'},self.cookie,self.csrf)[0],400)
        demo,token=self.login('demo')
        self.assertEqual(self.request('attachments',data,demo,token)[0],403)
        self.assertEqual(self.request('attachment?id='+str(aid),cookie=demo)[0],403)
        self.assertEqual(self.request('attachment?id='+str(aid))[0],403)
        limited,ltoken=self.login('limited')
        outside=self.action('expense',description='Factura fuera de alcance',amount='10',expense_date=app.today().isoformat())['id']
        self.assertEqual(self.request('attachments',{**data,'entity_id':outside},limited,ltoken)[0],403)
        con=http.client.HTTPConnection('127.0.0.1',self.port);con.request('GET','/api/attachment?id='+str(aid),headers={'Cookie':self.cookie});r=con.getresponse()
        self.assertEqual(r.status,200);self.assertEqual(r.read(),base64.b64decode(payload));self.assertIn('attachment',r.getheader('Content-Disposition'));con.close()
    def test_25_attachment_archive_roundtrip(self):
        _,archive,_=self.request('export?company_id=3',cookie=self.cookie)
        self.assertEqual(archive['version'],7);self.assertTrue(archive['data']['attachments'])
        payload={'company_name':'Copia con archivos QA','name':'Autor QA','username':'archivos_qa','password':'1234','archive':archive}
        status,result,_=self.request('register-import',payload)
        self.assertEqual(status,201,result)
        with app.connect() as c:
            files=app.rows(c,'SELECT * FROM attachments WHERE company_id=?',(result['company_id'],))
            self.assertEqual(files[0]['content_base64'],archive['data']['attachments'][0]['content_base64'])
            expense=app.ref(c,'expenses',files[0]['entity_id'],result['company_id'])
            self.assertEqual(expense['description'],'Gasto con factura')
    def test_26_legacy_archive_without_attachments(self):
        _,archive,_=self.request('export?company_id=3',cookie=self.cookie)
        archive['version']=1;archive['data'].pop('attachments')
        payload={'company_name':'Copia antigua QA','name':'Autor QA','username':'legacy_qa','password':'1234','archive':archive}
        status,result,_=self.request('register-import',payload)
        self.assertEqual(status,201,result)
    def test_27_payroll_attachments(self):
        import base64
        payload=base64.b64encode(b'%PDF-1.4\n% cheque nomina\n%%EOF').decode()
        farm_id=self.action('farm',name='Finca Test Adjunto')['id']
        emp_id=self.action('employee',name='Trabajador QA',position='Campo',basis='daily',rate=100000,department_id=self.dep)['id']
        co_id=self.action('farm_contract',farm_id=farm_id,employee_id=emp_id,kind='temporary',basis='day',rate=100000,description='Poda',start_date='2026-09-19',end_date='2026-09-25')['id']
        job_id=self.action('farm_job',contract_id=co_id,work_date='2026-09-25',quantity='1',description='Poda día 1')['id']
        self.action('approve_job',id=job_id)
        p_id=self.action('weekly_payroll',farm_id=farm_id,end_date='2026-09-25')['id']
        data={'company_id':3,'entity':'farm_payrolls','entity_id':p_id,'filename':'cheque_pago.pdf','content_base64':payload}
        status,result,_=self.request('attachments',data,self.cookie,self.csrf)
        self.assertEqual(status,200,result)
        status,files,_=self.request('attachments?company_id=3&entity=farm_payrolls&entity_id='+str(p_id),cookie=self.cookie)
        self.assertEqual(len(files['files']),1)
        self.assertEqual(files['files'][0]['filename'],'cheque_pago.pdf')
    def test_28_employee_edit_and_attachments(self):
        import base64
        emp_id=self.action('employee',name='Juan Perez',position='Operario',basis='daily',rate='1200.00',department_id=self.dep)['id']
        # Edit employee
        self.action('edit_employee',id=emp_id,name='Juan Perez Modificado',position='Encargado',basis='monthly',rate='35000.00',department_id=self.dep,conditions='Horario de 8am a 5pm')
        with app.connect() as c:
            emp=app.ref(c,'employees',emp_id,3)
            self.assertEqual(emp['name'],'Juan Perez Modificado')
            self.assertEqual(emp['position'],'Encargado')
            self.assertEqual(emp['basis'],'monthly')
            self.assertEqual(emp['rate'],3500000)
            self.assertEqual(emp['conditions'],'Horario de 8am a 5pm')
        # Attach identification (cedula)
        payload=base64.b64encode(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82').decode()
        data={'company_id':3,'entity':'employees','entity_id':emp_id,'filename':'cedula_juan_perez.png','content_base64':payload}
        status,result,_=self.request('attachments',data,self.cookie,self.csrf)
        self.assertEqual(status,200,result)
        status,files,_=self.request('attachments?company_id=3&entity=employees&entity_id='+str(emp_id),cookie=self.cookie)
        self.assertEqual(len(files['files']),1)
        self.assertEqual(files['files'][0]['filename'],'cedula_juan_perez.png')

    def test_29_operability_and_admin_delete(self):
        # 1. Department edit and delete
        dep_id=self.action('department',name='Dept Temporal')['id']
        self.action('edit_department',id=dep_id,name='Dept Renombrado')
        with app.connect() as c:
            self.assertEqual(app.ref(c,'departments',dep_id,3)['name'],'Dept Renombrado')
        # Delete unused department
        res=self.action('delete_department',id=dep_id)
        self.assertTrue(res.get('ok'))
        # Department in use cannot be deleted
        dep_used=self.action('department',name='Dept En Uso')['id']
        emp_id=self.action('employee',name='Ana',position='Operario',basis='daily',rate='1000',department_id=dep_used)['id']
        with self.assertRaises(Exception):
            self.action('delete_department',id=dep_used)

        # 2. Project edit and delete
        proj_id=self.action('project',name='Proyecto Temporal')['id']
        self.action('edit_project',id=proj_id,name='Proyecto Renombrado')
        with app.connect() as c:
            self.assertEqual(app.ref(c,'projects',proj_id,3)['name'],'Proyecto Renombrado')
        # Delete unused project
        res_p=self.action('delete_project',id=proj_id)
        self.assertTrue(res_p.get('ok'))

        # 3. Task edit and delete
        task_id=self.action('task',title='Tarea Inicial',due_date='2026-09-30',responsible_id=emp_id,department_id=dep_used)['id']
        self.action('edit_task',id=task_id,title='Tarea Modificada',status='progress',due_date='2026-10-05',support='Apoyo compras')
        with app.connect() as c:
            t=app.ref(c,'tasks',task_id,3)
            self.assertEqual(t['title'],'Tarea Modificada')
            self.assertEqual(t['status'],'progress')
            self.assertEqual(t['due_date'],'2026-10-05')
            self.assertEqual(t['support'],'Apoyo compras')
        res_t=self.action('delete_task',id=task_id)
        self.assertTrue(res_t.get('ok'))
        with app.connect() as c:
            self.assertIsNone(c.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone())

        # 4. Member edit, delete and safeguards
        user_id=self.action('member',username='colab_nuevo',name='Colaborador Nuevo',password='Colaborador123456!',role='register',role_name='Auxiliar')['id']
        # Edit member
        self.action('member',username='colab_nuevo',name='Colaborador Editado',role='review',role_name='Supervisor',hierarchy_rank=2)
        with app.connect() as c:
            mem=c.execute('SELECT * FROM memberships WHERE user_id=? AND company_id=3',(user_id,)).fetchone()
            self.assertEqual(mem['role'],'review')
            self.assertEqual(mem['role_name'],'Supervisor')
            u=c.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
            self.assertEqual(u['name'],'Colaborador Editado')
        # Delete member
        res_m=self.action('delete_member',id=user_id)
        self.assertTrue(res_m.get('ok'))
        with app.connect() as c:
            self.assertIsNone(c.execute('SELECT * FROM memberships WHERE user_id=? AND company_id=3',(user_id,)).fetchone())

        # Self-delete by admin is blocked
        with self.assertRaises(Exception):
            self.action('delete_member',id=self.uid)

    def test_30_attachment_edit_and_delete(self):
        import base64
        # Upload an attachment to an expense
        payload=base64.b64encode(b'%PDF-1.4 test invoice content').decode()
        exp_id=self.action('expense',description='Factura Gasoil',amount='4500.00',department_id=self.dep,expense_date='2026-09-25')['id']
        data={'company_id':3,'entity':'expenses','entity_id':exp_id,'filename':'factura_gasoil_v1.pdf','content_base64':payload}
        status,result,_=self.request('attachments',data,self.cookie,self.csrf)
        self.assertEqual(status,200,result)
        aid=result['id']

        # Edit/rename attachment
        edit_res=self.action('edit_attachment',id=aid,filename='factura_gasoil_corregida.pdf')
        self.assertTrue(edit_res.get('ok'))
        self.assertEqual(edit_res.get('filename'),'factura_gasoil_corregida.pdf')
        with app.connect() as c:
            row=c.execute('SELECT * FROM attachments WHERE id=?',(aid,)).fetchone()
            self.assertEqual(row['filename'],'factura_gasoil_corregida.pdf')

        # Delete attachment
        del_res=self.action('delete_attachment',id=aid)
        self.assertTrue(del_res.get('ok'))
        with app.connect() as c:
            self.assertIsNone(c.execute('SELECT * FROM attachments WHERE id=?',(aid,)).fetchone())

    def test_32_employee_weekly_basis_creation_and_edit(self):
        # Create an employee with weekly basis
        emp_id = self.action('employee', name='Carlos Semanal', position='Operario Semanal', basis='weekly', rate='5000.00', department_id=self.dep, employment_type='fixed')['id']
        with app.connect() as c:
            emp = app.ref(c, 'employees', emp_id, 3)
            self.assertEqual(emp['name'], 'Carlos Semanal')
            self.assertEqual(emp['basis'], 'weekly')
            self.assertEqual(emp['rate'], 500000)
            self.assertEqual(emp['employment_type'], 'fixed')

        # Edit employee to update rate and keep weekly basis
        self.action('edit_employee', id=emp_id, name='Carlos Semanal Actualizado', position='Supervisor Semanal', basis='weekly', rate='6500.00', department_id=self.dep, employment_type='fixed', conditions='Horario de lunes a sábado')
        with app.connect() as c:
            emp = app.ref(c, 'employees', emp_id, 3)
            self.assertEqual(emp['name'], 'Carlos Semanal Actualizado')
            self.assertEqual(emp['position'], 'Supervisor Semanal')
            self.assertEqual(emp['basis'], 'weekly')
            self.assertEqual(emp['rate'], 650000)
            self.assertEqual(emp['conditions'], 'Horario de lunes a sábado')

    def test_33_employee_termination_reactivation_and_lifecycle(self):
        # Create a regular employee and a seasonal/temporary worker
        fixed_id = self.action('employee', name='Juan Despido', position='Auxiliar Almacén', basis='monthly', rate='25000.00', department_id=self.dep, employment_type='fixed')['id']
        temp_id = self.action('employee', name='Pedro Temporero Despido', position='Cosechador', basis='daily', rate='1200.00', department_id=self.dep, employment_type='temporary')['id']

        # Check default status is active
        with app.connect() as c:
            e1 = app.ref(c, 'employees', fixed_id, 3)
            e2 = app.ref(c, 'employees', temp_id, 3)
            self.assertEqual(e1['status'], 'active')
            self.assertEqual(e2['status'], 'active')
            self.assertIsNone(e1['termination_date'])

        # Terminate seasonal worker
        res_t1 = self.action('terminate_employee', id=temp_id, termination_date='2026-10-01', termination_reason='contract_end', termination_notes='Fin de temporada de recolección')
        self.assertTrue(res_t1.get('ok'))
        with app.connect() as c:
            e2_term = app.ref(c, 'employees', temp_id, 3)
            self.assertEqual(e2_term['status'], 'terminated')
            self.assertEqual(e2_term['termination_date'], '2026-10-01')
            self.assertEqual(e2_term['termination_reason'], 'contract_end')
            self.assertEqual(e2_term['termination_notes'], 'Fin de temporada de recolección')

        # Terminate regular employee with desahucio
        res_t2 = self.action('terminate_employee', id=fixed_id, termination_date='2026-10-05', termination_reason='desahucio_employer', termination_notes='Desahucio con preaviso y cesantía pagados')
        self.assertTrue(res_t2.get('ok'))
        with app.connect() as c:
            e1_term = app.ref(c, 'employees', fixed_id, 3)
            self.assertEqual(e1_term['status'], 'terminated')
            self.assertEqual(e1_term['termination_date'], '2026-10-05')
            self.assertEqual(e1_term['termination_reason'], 'desahucio_employer')

        # Reactivate employee
        res_react = self.action('reactivate_employee', id=fixed_id)
        self.assertTrue(res_react.get('ok'))
        with app.connect() as c:
            e1_react = app.ref(c, 'employees', fixed_id, 3)
            self.assertEqual(e1_react['status'], 'active')
            self.assertIsNone(e1_react['termination_date'])
            self.assertIsNone(e1_react['termination_reason'])

        # Add a worklog to fixed employee to give them history
        self.action('worklog', employee_id=fixed_id, work_date='2026-10-06', minutes=480, activity='Inventario', method='Conteo físico')
        # Attempting hard delete on employee with history must be rejected
        status, del_err, _ = self.request('action', {'company_id': 3, 'action': 'delete_employee', 'id': fixed_id}, self.cookie, self.csrf)
        self.assertEqual(status, 400)
        self.assertIn('historial', del_err.get('error', ''))

        # Create an employee with no history and hard delete
        unused_id = self.action('employee', name='Ficha Errónea', position='Prueba', basis='daily', rate='500.00', department_id=self.dep, employment_type='temporary')['id']
        del_ok = self.action('delete_employee', id=unused_id)
        self.assertTrue(del_ok.get('ok'))
        with app.connect() as c:
            self.assertIsNone(c.execute('SELECT * FROM employees WHERE id=?', (unused_id,)).fetchone())

if __name__=='__main__': unittest.main(verbosity=2)
