import unittest, sqlite3
import app,commerce,transfer

class CommerceTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row;self.c.executescript(app.SCHEMA)
  self.c.execute("INSERT INTO companies(id,name) VALUES(1,'Empresa')")
  self.c.execute("INSERT INTO users(id,username,name,password) VALUES(1,'admin','Admin','!')")
  self.c.execute("INSERT INTO memberships(user_id,company_id,role,role_name) VALUES(1,1,'admin','Admin')")
  self.c.execute("INSERT INTO customers(id,company_id,name,contact) VALUES(1,1,'Cliente','Contacto')")
  self.c.execute("INSERT INTO products(id,company_id,name,amount) VALUES(1,1,'Cacao',1500)")
 def tearDown(self): self.c.close()
 def test_invoice_payment_receipt_and_archive(self):
  d=dict(customer_id=1,invoice_date=app.today().isoformat(),due_date=app.today().isoformat(),items=[dict(product_id=1,quantity='2.5')],request_key='test-invoice')
  r=app.mutate(self.c,1,1,'invoice',d)
  self.assertEqual(app.mutate(self.c,1,1,'invoice',d),r)
  self.assertEqual(app.charge_list(self.c,1)[0]['balance'],3750)
  p=app.mutate(self.c,1,1,'payment',dict(charge_id=r['charge_id'],amount='37.50',paid_date=app.today().isoformat(),reference='Pago 1',request_key='payment1'))
  self.assertEqual(app.charge_list(self.c,1)[0]['balance'],0)
  self.assertIn(b'Cacao',commerce.document(app,self.c,1,1,'invoice',r['id']))
  self.assertIn(b'37.50',commerce.document(app,self.c,1,1,'receipt',p['id']))
  with self.assertRaises(app.Denied): commerce.document(app,self.c,2,1,'receipt',p['id'])
  archive=transfer.export_company(app,self.c,1,1)
  imported=transfer.register(app,self.c,dict(company_name='Copia',username='copia',name='Admin',password='abcd',archive=archive),True)
  self.assertEqual(len(app.state(self.c,imported['user_id'],imported['company_id'])['invoices']),1)
 def test_profile_logo_and_snapshot(self):
  app.mutate(self.c,1,1,'company_profile',dict(name='Nuevo nombre',phone='809',email='hola@example.com',address='Dirección',tax_id='123'))
  self.assertEqual(commerce.profile(app,self.c,1)['phone'],'809')
  with self.assertRaises(ValueError): app.mutate(self.c,1,1,'company_profile',dict(name='Empresa',logo='javascript:bad'))
 def test_edit_company_and_admin_permissions(self):
  self.c.execute("INSERT INTO companies(id,name,group_name) VALUES(2,'Empresa Dos','Grupo Monarca')")
  self.c.execute("INSERT INTO memberships(user_id,company_id,role,role_name) VALUES(1,2,'admin','Gerente General')")
  self.c.execute("INSERT INTO users(id,username,name,password) VALUES(2,'viewer','Viewer','!')")
  self.c.execute("INSERT INTO memberships(user_id,company_id,role,role_name) VALUES(2,2,'register','Auxiliar')")
  res = app.mutate(self.c, 1, 1, 'edit_company', dict(id=2, name='Empresa Dos Renovada', group_name='Grupo Monarca Holdings', phone='809-555-1234', email='info@monarca.do', address='Av. Winston Churchill', tax_id='131-12345-1', unit_singular='Sucursal', unit_plural='Sucursales', demo=False))
  self.assertTrue(res['ok'])
  co = app.one(self.c, "SELECT * FROM companies WHERE id=2")
  self.assertEqual(co['name'], 'Empresa Dos Renovada')
  self.assertEqual(co['group_name'], 'Grupo Monarca Holdings')
  prof = commerce.profile(app, self.c, 2)
  self.assertEqual(prof['phone'], '809-555-1234')
  self.assertEqual(prof['unit_singular'], 'Sucursal')
  with self.assertRaises(app.Denied):
      app.mutate(self.c, 2, 2, 'edit_company', dict(id=2, name='Intento no autorizado'))

 def test_edit_and_delete_products_and_customers(self):
  res = app.mutate(self.c, 1, 1, 'edit_product', dict(id=1, name='Cacao Orgánico Premium', amount='25.50', description='Grano seleccionado'))
  self.assertEqual(res['id'], 1)
  p = app.one(self.c, "SELECT * FROM products WHERE id=1")
  self.assertEqual(p['name'], 'Cacao Orgánico Premium')
  self.assertEqual(p['amount'], 2550)
  self.assertEqual(p['description'], 'Grano seleccionado')

  res_c = app.mutate(self.c, 1, 1, 'edit_customer', dict(id=1, name='Cliente VIP Internacional', contact='809-999-0000'))
  self.assertEqual(res_c['id'], 1)
  cust = app.one(self.c, "SELECT * FROM customers WHERE id=1")
  self.assertEqual(cust['name'], 'Cliente VIP Internacional')
  self.assertEqual(cust['contact'], '809-999-0000')

  p2 = app.mutate(self.c, 1, 1, 'product', dict(name='Café', amount='500', description='Café molido'))
  self.assertIn('id', p2)
  del_res = app.mutate(self.c, 1, 1, 'delete_product', dict(id=p2['id']))
  self.assertTrue(del_res['ok'])
  self.assertIsNone(app.one(self.c, "SELECT * FROM products WHERE id=?", (p2['id'],)))

  d=dict(customer_id=1,invoice_date=app.today().isoformat(),due_date=app.today().isoformat(),items=[dict(product_id=1,quantity='1')],request_key='test-inv-block-delete')
  app.mutate(self.c,1,1,'invoice',d)
  with self.assertRaises(ValueError):
      app.mutate(self.c, 1, 1, 'delete_product', dict(id=1))

 def test_delete_company_and_backup(self):
  # Cannot delete sole company
  with self.assertRaises(ValueError):
      app.mutate(self.c, 1, 1, 'delete_company', dict(id=1))

  # Create company 2
  self.c.execute("INSERT INTO companies(id,name) VALUES(2,'Empresa Secundaria')")
  self.c.execute("INSERT INTO memberships(user_id,company_id,role,role_name) VALUES(1,2,'admin','Admin')")
  self.c.execute("INSERT INTO customers(id,company_id,name,contact) VALUES(2,2,'Cliente 2','Contacto 2')")

  # Non-admin cannot delete
  self.c.execute("INSERT INTO users(id,username,name,password) VALUES(3,'user3','User 3','!')")
  self.c.execute("INSERT INTO memberships(user_id,company_id,role,role_name) VALUES(3,2,'register','Auxiliar')")
  with self.assertRaises(app.Denied):
      app.mutate(self.c, 3, 2, 'delete_company', dict(id=2))

  # Admin deletes company 2
  res = app.mutate(self.c, 1, 1, 'delete_company', dict(id=2))
  self.assertTrue(res['ok'])
  self.assertEqual(res['deleted_company_id'], 2)
  self.assertEqual(res['next_company_id'], 1)
  self.assertIsNone(app.one(self.c, "SELECT * FROM companies WHERE id=2"))
  self.assertIsNone(app.one(self.c, "SELECT * FROM customers WHERE id=2"))
