import datetime, json, sqlite3, tempfile, concurrent.futures
import app, commerce, fiscal, transfer
from test_commerce import CommerceTests

class FiscalTests(CommerceTests):
 def rango(self,tipo='B01',start=1,end=20):
  return fiscal.cargar_secuencia_ncf(app,self.c,1,1,dict(tipo_ncf=tipo,numero_inicial=start,numero_final=end,fecha_vencimiento=(app.today()+datetime.timedelta(days=10)).isoformat()))
 def invoice(self,key='fiscal',tipo='B01',doc='123456789'):
  return app.mutate(self.c,1,1,'invoice',dict(customer_id=1,invoice_date=app.today().isoformat(),due_date=app.today().isoformat(),items=[dict(product_id=1,quantity='1')],request_key=key,tipo_ncf=tipo,documento_cliente=doc))
 def issuer(self):
  self.c.execute("INSERT INTO company_profiles(company_id,tax_id) VALUES(1,'123456789')")
 def test_assignment_reprint_retry_import(self):
  self.issuer();self.rango();r=self.invoice();self.assertEqual(self.invoice(),r)
  inv=app.one(self.c,'SELECT * FROM sales_invoices')
  self.assertEqual(inv['ncf_asignado'],'B0100000001');self.assertEqual(app.one(self.c,'SELECT * FROM secuencias_ncf')['contador_actual'],1)
  self.assertIn(b'B0100000001',commerce.document(app,self.c,1,1,'invoice',r['id']))
  archive=transfer.export_company(app,self.c,1,1)
  result=transfer.register(app,self.c,dict(company_name='Copia fiscal',username='copiarf',name='Admin',password='abcd',archive=archive),True)
  self.assertEqual(fiscal.sequences(app,self.c,result['company_id'])[0]['estado'],'Agotado')
 def test_invalid_documents_and_scope(self):
  self.issuer();self.rango()
  for document in ('','abc123456789','１２３４５６７８９'):
   with self.assertRaises(ValueError): self.invoice(doc=document)
  self.assertEqual(app.one(self.c,'SELECT * FROM secuencias_ncf')['contador_actual'],0)
  with self.assertRaises(app.Denied): fiscal.cargar_secuencia_ncf(app,self.c,2,1,{})
  with self.assertRaises(ValueError): fiscal.obtener_siguiente_ncf(app,self.c,2,'B01')
  self.assertTrue(fiscal.validar_rnc_cedula('001-1234567-8'))
 def test_expired_exhaustion_and_warning(self):
  self.rango();self.c.execute("UPDATE secuencias_ncf SET fecha_vencimiento='2020-01-01'")
  with self.assertRaises(ValueError): fiscal.obtener_siguiente_ncf(app,self.c,1,'B01')
  self.assertEqual(fiscal.sequences(app,self.c,1)[0]['estado'],'Vencido')
  self.rango('B02');self.c.execute("UPDATE secuencias_ncf SET contador_actual=17 WHERE tipo_ncf='B02'")
  self.assertFalse(fiscal.obtener_siguiente_ncf(app,self.c,1,'B02')['aviso'])
  self.assertTrue(fiscal.obtener_siguiente_ncf(app,self.c,1,'B02')['aviso'])
  self.assertEqual(fiscal.obtener_siguiente_ncf(app,self.c,1,'B02')['ncf_asignado'],'B0200000020')
  with self.assertRaises(ValueError): fiscal.obtener_siguiente_ncf(app,self.c,1,'B02')
 def test_overlap_rollback_migration(self):
  self.rango()
  with self.assertRaises(ValueError): self.rango(start=20,end=30)
  with self.assertRaises(ValueError): self.rango(start=2,end=2)
  self.c.commit()
  try:
   with self.c:
    self.c.execute('BEGIN IMMEDIATE');fiscal.obtener_siguiente_ncf(app,self.c,1,'B01');raise ValueError('fallo posterior')
  except ValueError: pass
  self.assertEqual(app.one(self.c,'SELECT * FROM secuencias_ncf')['contador_actual'],0)
  with sqlite3.connect(':memory:') as c:
   c.execute('CREATE TABLE sales_invoices(id INTEGER PRIMARY KEY,company_id INTEGER,snapshot TEXT)')
   c.execute("INSERT INTO sales_invoices VALUES(1,1,'{}')");fiscal.migrate(c);fiscal.migrate(c)
   self.assertEqual(c.execute('SELECT snapshot,ncf_asignado FROM sales_invoices').fetchone(),('{}',None))
 def test_concurrent_allocation(self):
  self.rango('B02');self.c.commit()
  with tempfile.TemporaryDirectory() as folder:
   path=folder+'/test.sqlite3'
   with sqlite3.connect(path) as target: self.c.backup(target)
   def allocate(_):
    with sqlite3.connect(path,timeout=10) as c:
     c.row_factory=sqlite3.Row;c.execute('BEGIN IMMEDIATE')
     return fiscal.obtener_siguiente_ncf(app,c,1,'B02')['ncf_asignado']
   with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(allocate,range(12)))
   self.assertEqual(len(set(results)),12)
