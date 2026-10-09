import sqlite3
import unittest
import app, treasury

class HierarchyTests(unittest.TestCase):
    def test_permissions_and_rank(self):
        c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
        c.executescript(app.SCHEMA)
        c.execute("INSERT INTO companies(id,name) VALUES(1,'Empresa')")
        c.execute("INSERT INTO users(id,username,name,password) VALUES(1,'admin','Admin','!')")
        c.execute("INSERT INTO memberships(user_id,company_id,role,role_name) VALUES(1,1,'admin','Admin')")
        data=dict(username='supervisor',name='Supervisor',password='UnaClaveSegura123',role='review',role_name='Jefe de área',hierarchy_rank=4,departments=[],projects=[])
        ident=app.mutate(c,1,1,'member',data)['id']
        self.assertEqual(c.execute('SELECT rank FROM member_hierarchy WHERE user_id=?',(ident,)).fetchone()[0],4)
        with self.assertRaises(app.Denied): app.mutate(c,ident,1,'member',data)
        with self.assertRaises(ValueError): app.mutate(c,1,1,'member',dict(data,hierarchy_rank=0))
        self.assertEqual(app.membership(c,ident,1)['role'],'review')
        c.close()

    def test_hierarchy_level_and_account_balance_conditioning(self):
        c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
        c.executescript(app.SCHEMA)
        c.execute("INSERT INTO companies(id,name) VALUES(1,'Empresa')")
        c.execute("INSERT INTO users(id,username,name,password) VALUES(1,'admin','Admin','!')")
        c.execute("INSERT INTO memberships(user_id,company_id,role,role_name) VALUES(1,1,'admin','Admin')")

        # Create Rank 2 user (Gerente financiero)
        u2=app.mutate(c,1,1,'member',dict(username='gerente',name='Gerente Finanzas',password='UnaClaveSegura123',role='review',role_name='Gerente Financiero',hierarchy_rank=2,departments=[],projects=[],collections=1))['id']
        # Create Rank 3 user (Supervisor operativo)
        u3=app.mutate(c,1,1,'member',dict(username='operativo',name='Supervisor Operativo',password='UnaClaveSegura123',role='review',role_name='Supervisor',hierarchy_rank=3,departments=[],projects=[],collections=1))['id']

        # Rank 2 can create cash account
        acc_data=dict(name='Cuenta Banco',kind='bank',bank_name='Banco BHD',account_number='1234567890',holder_name='Empresa',holder_document='130000000',account_type='checking',currency='DOP')
        acc_id=app.mutate(c,u2,1,'cash_account',acc_data)['id']
        self.assertTrue(acc_id>0)

        # Rank 3 cannot create or edit cash account
        with self.assertRaises(app.Denied):
            app.mutate(c,u3,1,'cash_account',dict(acc_data,name='Cuenta Otra'))
        with self.assertRaises(app.Denied):
            app.mutate(c,u3,1,'edit_cash_account',dict(acc_data,id=acc_id,name='Nuevo Nombre'))

        # Rank 3 cannot make deposit or transfer
        with self.assertRaises(app.Denied):
            app.mutate(c,u3,1,'cash_deposit',dict(account_id=acc_id,amount='5000',movement_date=app.today().isoformat(),reference='Dep',request_key='dep-u3'))

        # Rank 2 deposits 10,000 DOP
        app.mutate(c,u2,1,'cash_deposit',dict(account_id=acc_id,amount='10000',movement_date=app.today().isoformat(),reference='Depósito inicial',request_key='dep-u2'))
        self.assertEqual(treasury.balance(c,acc_id),1000000)

        # Create approved expense of 6,000 DOP
        dep=c.execute("INSERT INTO departments(company_id,name) VALUES(1,'Operaciones')").lastrowid
        exp_id=app.mutate(c,1,1,'expense',dict(description='Materiales',amount='6000',expense_date=app.today().isoformat(),department_id=dep))['id']
        app.mutate(c,1,1,'approve_expense',dict(id=exp_id))

        # Rank 3 cannot execute payment
        with self.assertRaises(app.Denied):
            app.mutate(c,u3,1,'expense_payment',dict(expense_id=exp_id,amount='6000',paid_date=app.today().isoformat(),reference='Recibo 01',request_key='pay-u3',account_id=acc_id))

        # Rank 2 pays 6,000 DOP successfully
        app.mutate(c,u2,1,'expense_payment',dict(expense_id=exp_id,amount='6000',paid_date=app.today().isoformat(),reference='Recibo 01',request_key='pay-u2',account_id=acc_id))
        self.assertEqual(treasury.balance(c,acc_id),400000) # Remaining: 4,000 DOP

        # Create another expense of 5,000 DOP
        exp2_id=app.mutate(c,1,1,'expense',dict(description='Herramientas',amount='5000',expense_date=app.today().isoformat(),department_id=dep))['id']
        app.mutate(c,1,1,'approve_expense',dict(id=exp2_id))

        c.commit()
        # Payment of 5,000 DOP exceeds remaining 4,000 DOP -> blocked with insufficient balance error
        with self.assertRaises(ValueError) as ctx:
            with c:
                app.mutate(c,u2,1,'expense_payment',dict(expense_id=exp2_id,amount='5000',paid_date=app.today().isoformat(),reference='Recibo 02',request_key='pay-u2-2',account_id=acc_id))
        self.assertIn('Saldo insuficiente',str(ctx.exception))

        # Partial payment of 4,000 DOP succeeds
        app.mutate(c,u2,1,'expense_payment',dict(expense_id=exp2_id,amount='4000',paid_date=app.today().isoformat(),reference='Recibo 02 parcial',request_key='pay-u2-partial',account_id=acc_id))
        self.assertEqual(treasury.balance(c,acc_id),0)

        c.close()
