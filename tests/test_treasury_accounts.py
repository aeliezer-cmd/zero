import copy
import sqlite3
import unittest
import app, treasury, transfer

class BankAccountTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row;self.c.executescript(app.SCHEMA)
        self.c.execute("INSERT INTO companies(id,name) VALUES(1,'Empresa')")
        self.c.execute("INSERT INTO users(id,username,name,password) VALUES(1,'admin','Admin','!')")
        self.c.execute("INSERT INTO memberships(user_id,company_id,role,role_name) VALUES(1,1,'admin','Admin')")
        self.c.commit()
        self.data=dict(name='Cuenta principal',kind='bank',bank_name='Banco de prueba',account_number='000123456',holder_name='Empresa',holder_document='123456789',account_type='checking',currency='USD',country='República Dominicana',branch='Central',swift='TESTDOXX',notes='Ingresos')
    def tearDown(self): self.c.close()
    def save(self,action,**data):
        with self.c:
            self.c.execute('BEGIN IMMEDIATE');return app.mutate(self.c,1,1,action,data)
    def deposit(self,account,key='deposit1'):
        return self.save('cash_deposit',account_id=account,amount='100',movement_date=app.today().isoformat(),reference='Capital',request_key=key)
    def test_metadata_edit_archive_and_leading_zeros(self):
        a=self.save('cash_account',**self.data)['id']
        self.save('edit_cash_account',**dict(self.data,id=a,branch='Sucursal Norte'))
        row=app.one(self.c,'SELECT * FROM cash_accounts WHERE id=?',(a,))
        self.assertEqual(row['account_number'],'000123456');self.assertEqual(row['branch'],'Sucursal Norte')
        self.deposit(a)
        bundle=transfer.export_company(app,self.c,1,1)
        with self.c: imported=transfer.register(app,self.c,dict(company_name='Copia',username='copy',name='Admin',password='abcd',archive=copy.deepcopy(bundle)),True)
        result=app.state(self.c,imported['user_id'],imported['company_id'])['cash_accounts'][0]
        self.assertEqual((result['currency'],result['balance'],result['account_number']),('USD',10000,'000123456'))
    def test_currency_changes_and_currency_mismatch_rollback(self):
        a=self.save('cash_account',**self.data)['id'];self.deposit(a)
        with self.assertRaises(ValueError): self.save('edit_cash_account',**dict(self.data,id=a,currency='DOP'))
        b=self.save('cash_account',name='Caja',kind='cash')['id']
        before=self.c.execute('SELECT COUNT(*) FROM cash_movements').fetchone()[0]
        with self.assertRaises(ValueError): self.save('cash_transfer',account_id=a,target_id=b,amount='20',movement_date=app.today().isoformat(),reference='Cambio',request_key='transfer1')
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM cash_movements').fetchone()[0],before)
        with self.assertRaises(ValueError): treasury.post(app,self.c,1,1,a,-100,app.today().isoformat(),'Pago DOP','payroll_payment',999)
        usd=self.save('cash_account',name='Caja USD',kind='cash',currency='USD')['id']
        self.save('cash_transfer',account_id=a,target_id=usd,amount='20',movement_date=app.today().isoformat(),reference='Traslado USD',request_key='transfer2')
        self.assertEqual(treasury.balance(self.c,a),8000);self.assertEqual(treasury.balance(self.c,usd),2000)
    def test_required_fields_permissions_and_currency(self):
        for data in [dict(self.data,bank_name=''),dict(self.data,account_number=''),dict(self.data,account_type='invalid'),dict(self.data,currency='XYZ'),dict(self.data,swift='invalid')]:
            with self.assertRaises(ValueError): self.save('cash_account',**data)
        a=self.save('cash_account',**self.data)['id']
        with self.assertRaises(app.Denied): app.mutate(self.c,2,1,'edit_cash_account',dict(self.data,id=a))
        with self.assertRaises(app.Denied): app.mutate(self.c,1,2,'edit_cash_account',dict(self.data,id=a))
    def test_legacy_migration_and_archive_defaults(self):
        self.save('cash_account',name='Caja',kind='cash')
        bundle=transfer.export_company(app,self.c,1,1);bundle['version']=6
        for row in bundle['data']['cash_accounts']:
            for key in treasury.ACCOUNT_FIELDS: row.pop(key)
        transfer.validate(app,self.c,bundle)
        self.assertEqual(bundle['data']['cash_accounts'][0]['currency'],'DOP')
        with sqlite3.connect(':memory:') as c:
            c.execute('CREATE TABLE cash_accounts(id INTEGER PRIMARY KEY,company_id INTEGER,name TEXT,kind TEXT)')
            c.execute("INSERT INTO cash_accounts VALUES(1,1,'Banco anterior','bank')")
            treasury.migrate(c);treasury.migrate(c)
            self.assertEqual(c.execute('SELECT name,currency,account_number FROM cash_accounts').fetchone(),('Banco anterior','DOP',''))

if __name__=='__main__': unittest.main()
