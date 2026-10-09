import unittest
import sqlite3
import datetime as dt
import app
import ecf

class EcfTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(':memory:')
        self.c.row_factory = sqlite3.Row
        self.c.executescript(app.SCHEMA)
        ecf.migrate(self.c)
        self.c.execute("INSERT INTO companies(id,name) VALUES(1,'Constructora del Caribe SRL')")
        self.c.execute("INSERT INTO users(id,username,name,password) VALUES(1,'admin','Admin','!')")
        self.c.execute("INSERT INTO memberships(user_id,company_id,role,role_name) VALUES(1,1,'admin','Admin')")

    def tearDown(self):
        self.c.close()

    def test_config_and_norma_07_07_calculation(self):
        # 1. Enable e-CF module with Norma 07-07
        cfg = ecf.save_config(app, self.c, 1, 1, {
            'enabled': True,
            'environment': 'cert',
            'rnc_emisor': '131234567',
            'razon_social_emisor': 'Constructora del Caribe SRL',
            'apply_norma_07_07': True
        })
        self.assertEqual(cfg['enabled'], 1)
        self.assertEqual(cfg['environment'], 'cert')

        # 2. Test Norma 07-2007 calculation
        # Subtotal: RD$ 1,000,000.00
        # Base Gravable (10%): RD$ 100,000.00
        # Base Exenta (90%): RD$ 900,000.00
        # ITBIS (18% de 100,000): RD$ 18,000.00 (1.8% del subtotal)
        # Total: RD$ 1,018,000.00
        items = [{
            'nombre': 'Cubicación No. 4 - Estructura Torre Altagracia',
            'cantidad': 1,
            'precio_unitario': 1000000,
            'norma_07_07': True
        }]
        totals = ecf.compute_fiscal_totals(items, apply_norma_07_07=True)
        self.assertEqual(totals['subtotal'], 100000000) # centavos
        self.assertEqual(totals['exento'], 90000000)
        self.assertEqual(totals['gravado'], 10000000)
        self.assertEqual(totals['itbis'], 1800000)
        self.assertEqual(totals['total'], 101800000)

    def test_ecf_submission_and_idempotency(self):
        ecf.save_config(app, self.c, 1, 1, {
            'enabled': True,
            'rnc_emisor': '131234567',
            'razon_social_emisor': 'Constructora del Caribe SRL'
        })

        dto = {
            'idempotency_key': 'OP-OBRA-2026-001',
            'tipo_ecf': '31', # Crédito Fiscal
            'rnc_receptor': '101987654',
            'razon_social_receptor': 'Inversiones Inmobiliarias SA',
            'items': [
                {'nombre': 'Honorarios Dirección Técnica', 'cantidad': 1, 'precio_unitario': 50000, 'norma_07_07': True}
            ]
        }

        # First submission
        doc1 = ecf.process_ecf_submission(app, self.c, 1, 1, dto)
        self.assertEqual(doc1['tipo_ecf'], '31')
        self.assertTrue(doc1['e_ncf'].startswith('E31'))
        self.assertEqual(doc1['estado'], 'accepted')
        self.assertIn('ConsultaTimbre', doc1['qr_url'])

        # Duplicate submission with same idempotency key returns identical record
        doc2 = ecf.process_ecf_submission(app, self.c, 1, 1, dto)
        self.assertEqual(doc1['id'], doc2['id'])
        self.assertEqual(doc1['e_ncf'], doc2['e_ncf'])

    def test_strict_immutability_and_credit_note(self):
        ecf.save_config(app, self.c, 1, 1, {
            'enabled': True,
            'rnc_emisor': '131234567',
            'razon_social_emisor': 'Constructora del Caribe SRL'
        })

        dto = {
            'idempotency_key': 'FACT-ORIGINAL-99',
            'tipo_ecf': '31',
            'rnc_receptor': '101987654',
            'razon_social_receptor': 'Cliente Fiel',
            'items': [{'nombre': 'Comisión de corretaje', 'cantidad': 1, 'precio_unitario': 20000}]
        }
        original = ecf.process_ecf_submission(app, self.c, 1, 1, dto)
        self.assertEqual(original['estado'], 'accepted')

        # Rule: Cannot cancel or delete accepted document directly
        with self.assertRaises(ValueError) as ctx:
            ecf.cancel_or_void_ecf(app, self.c, 1, 1, original['id'], 'Error en precio')
        self.assertIn('Ley 32-23', str(ctx.exception))

        # Must issue a Credit Note (Tipo 34)
        credit_note_dto = {
            'idempotency_key': 'NC-FACT-ORIGINAL-99',
            'tipo_ecf': '34',
            'rnc_receptor': '101987654',
            'razon_social_receptor': 'Cliente Fiel',
            'e_ncf_modificado': original['e_ncf'],
            'rnc_modificado': original['rnc_receptor'],
            'codigo_modificacion': '1', # 1 = Anulación total
            'items': [{'nombre': 'Anulación completa por error en comisión', 'cantidad': 1, 'precio_unitario': 20000}]
        }
        nc_doc = ecf.process_ecf_submission(app, self.c, 1, 1, credit_note_dto)
        self.assertEqual(nc_doc['tipo_ecf'], '34')
        self.assertEqual(nc_doc['e_ncf_modificado'], original['e_ncf'])
        self.assertEqual(nc_doc['codigo_modificacion'], '1')

    def test_contingency_offline_queue_and_retry(self):
        ecf.save_config(app, self.c, 1, 1, {
            'enabled': True,
            'rnc_emisor': '131234567',
            'razon_social_emisor': 'Constructora del Caribe SRL'
        })

        dto = {
            'idempotency_key': 'OBRA-OFFLINE-01',
            'tipo_ecf': '32', # Consumo
            'rnc_receptor': '00100000000',
            'razon_social_receptor': 'Comprador Inmueble',
            'simulate_offline': True,
            'items': [{'nombre': 'Separación Solar No. 12', 'cantidad': 1, 'precio_unitario': 50000}]
        }

        # Offline submission
        doc = ecf.process_ecf_submission(app, self.c, 1, 1, dto)
        self.assertEqual(doc['estado'], 'queued_contingency')
        self.assertTrue(bool(doc['codigo_seguridad']))

        # Retry contingency worker
        res = ecf.retry_contingency_queue(app, self.c, 1, 1)
        self.assertEqual(res['processed_count'], 1)

        updated = self.c.execute('SELECT * FROM ecf_documents WHERE id=?', (doc['id'],)).fetchone()
        self.assertEqual(updated['estado'], 'accepted')
        self.assertTrue(updated['track_id'].startswith('TRK-'))

if __name__ == '__main__':
    unittest.main()
