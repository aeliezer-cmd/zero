import sqlite3
import unittest
import app, real_estate, commerce

class RealEstateTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(':memory:')
        self.c.row_factory = sqlite3.Row
        self.c.executescript(app.SCHEMA)
        self.c.execute("INSERT INTO companies(id,name) VALUES(1,'Inmobiliaria Test')")
        self.c.execute("INSERT INTO users(id,username,name,password) VALUES(1,'admin','Admin Inmobiliaria','!')")
        self.c.execute("INSERT INTO memberships(user_id,company_id,role,role_name) VALUES(1,1,'admin','Admin')")
        self.c.execute("INSERT INTO departments(id,company_id,name) VALUES(1,1,'Ventas y Alquileres')")
        self.c.execute("INSERT INTO employees(id,company_id,name,position,basis,rate,department_id) VALUES(1,1,'Laura Agente','Asesora Senior','monthly',3000000,1)")
        self.c.commit()

    def tearDown(self):
        self.c.close()

    def save(self, action, **data):
        with self.c:
            return app.mutate(self.c, 1, 1, action, data)

    def test_property_crud_and_status(self):
        # Create property
        res = self.save('create_re_property',
            title='Apartamento 4A Piantini',
            code='PROP-001',
            property_type='apartment',
            listing_type='rent',
            status='available',
            address='Calle Fantino Falco #22',
            city='Santo Domingo',
            price_rent='35000',
            price_sale='0',
            area_sqm=85.5,
            bedrooms=2,
            bathrooms=2,
            parking_spots=1,
            owner_name='Pedro Propietario',
            owner_phone='809-555-1234',
            agent_id=1
        )
        self.assertTrue(res['ok'])
        prop_id = res['id']

        # Verify property in state
        st = app.state(self.c, 1, 1)
        self.assertEqual(len(st['re_properties']), 1)
        self.assertEqual(st['re_properties'][0]['title'], 'Apartamento 4A Piantini')
        self.assertEqual(st['re_properties'][0]['price_rent'], 3500000)

        # Edit property
        edit_res = self.save('edit_re_property',
            id=prop_id,
            title='Apartamento 4A Piantini Amueblado',
            code='PROP-001',
            property_type='apartment',
            listing_type='rent',
            status='available',
            price_rent='40000'
        )
        self.assertTrue(edit_res['ok'])
        st = app.state(self.c, 1, 1)
        self.assertEqual(st['re_properties'][0]['title'], 'Apartamento 4A Piantini Amueblado')
        self.assertEqual(st['re_properties'][0]['price_rent'], 4000000)

        # Delete property
        del_res = self.save('delete_re_property', id=prop_id)
        self.assertTrue(del_res['ok'])
        st = app.state(self.c, 1, 1)
        self.assertEqual(len(st['re_properties']), 0)

    def test_condo_crud_and_units(self):
        # 1. Create Condominium
        condo_res = self.save('create_re_condo',
            name='Torre Vista Hermosa',
            code='COND-VH',
            condo_type='residential',
            address='Av. Enriquillo #88, Los Cacicazgos',
            city='Santo Domingo D.N.',
            rnc_tax_id='4-30-55112-9',
            admin_name='Lic. Roberto Morales',
            admin_phone='809-555-9090',
            reserve_fund='100000',
            bank_account_info='Popular Cta #789012345'
        )
        self.assertTrue(condo_res['ok'])
        condo_id = condo_res['id']

        # 2. Add units to condo
        u1_res = self.save('create_re_property',
            title='Apto 2B Torre Vista Hermosa',
            code='PROP-VH01',
            property_type='apartment',
            listing_type='both',
            status='available',
            condo_id=condo_id,
            unit_number='2B',
            aliquot_pct=5.5,
            condo_fee='7500',
            condo_fee_day=5,
            owner_name='Ing. Francisco Gómez',
            owner_document='001-0981234-5',
            owner_phone='809-777-6655',
            owner_email='fgomez@test.com'
        )
        self.assertTrue(u1_res['ok'])
        u1_id = u1_res['id']

        u2_res = self.save('create_re_property',
            title='Penthouse 10A Vista Hermosa',
            code='PROP-VH02',
            property_type='penthouse',
            listing_type='sale',
            status='available',
            condo_id=condo_id,
            unit_number='PH-10A',
            aliquot_pct=11.0,
            condo_fee='15000',
            condo_fee_day=5,
            owner_name='Familia Castillo',
            owner_document='1-30-88991-2'
        )
        self.assertTrue(u2_res['ok'])

        # Verify state enrichment
        st = app.state(self.c, 1, 1)
        self.assertEqual(len(st['re_condos']), 1)
        c_state = st['re_condos'][0]
        self.assertEqual(c_state['name'], 'Torre Vista Hermosa')
        self.assertEqual(c_state['units_count'], 2)
        self.assertEqual(c_state['monthly_potential'], 2250000) # (7,500 + 15,000) * 100

        # Cannot delete condo while units are attached
        with self.assertRaises(ValueError):
            self.save('delete_re_condo', id=condo_id)

    def test_condo_month_fees_generation_and_payment(self):
        condo_id = self.save('create_re_condo',
            name='Residencial Palmeras del Este',
            code='COND-PE',
            condo_type='residential'
        )['id']

        self.save('create_re_property',
            title='Apartamento 101 Palmeras',
            condo_id=condo_id,
            unit_number='101',
            condo_fee='5000',
            condo_fee_day=5
        )
        self.save('create_re_property',
            title='Apartamento 102 Palmeras',
            condo_id=condo_id,
            unit_number='102',
            condo_fee='5500',
            condo_fee_day=5
        )

        # Generate month fees
        gen_res = self.save('generate_condo_month_fees', condo_id=condo_id, period='2026-10')
        self.assertTrue(gen_res['ok'])
        self.assertEqual(gen_res['count'], 2)

        # Generating again for same period should not duplicate
        gen2 = self.save('generate_condo_month_fees', condo_id=condo_id, period='2026-10')
        self.assertEqual(gen2['count'], 0)

        st = app.state(self.c, 1, 1)
        self.assertEqual(len(st['re_condo_charges']), 2)
        ch_101 = next(c for c in st['re_condo_charges'] if c['amount'] == 500000)
        self.assertEqual(ch_101['status'], 'pending')
        self.assertEqual(ch_101['paid_amount'], 0)

        # Pay charge
        pay_res = self.save('record_condo_charge_payment',
            id=ch_101['id'],
            amount='5000',
            payment_date=app.today().isoformat(),
            payment_reference='Depósito BHD #44192'
        )
        self.assertTrue(pay_res['ok'])

        st = app.state(self.c, 1, 1)
        paid_ch = next(c for c in st['re_condo_charges'] if c['id'] == ch_101['id'])
        self.assertEqual(paid_ch['status'], 'paid')
        self.assertEqual(paid_ch['paid_amount'], 500000)

        # Condo rollup verification
        condo_st = st['re_condos'][0]
        self.assertEqual(condo_st['total_collected'], 500000)
        self.assertEqual(condo_st['total_pending_charges'], 550000)

    def test_common_area_utility_expenses_workflow(self):
        condo_id = self.save('create_re_condo',
            name='Torre Metropolitana',
            code='COND-TM'
        )['id']

        # 1. Register electricity bill (Edesur)
        exp_res = self.save('create_re_condo_expense',
            condo_id=condo_id,
            service_type='electricity',
            provider_name='Edesur Dominicana S.A.',
            invoice_number='NIC 8899120',
            service_period='Octubre 2026',
            amount='16500',
            notes='Energía eléctrica de áreas comunes y bombas'
        )
        self.assertTrue(exp_res['ok'])
        exp_id = exp_res['id']

        # 2. Register water bill (CAASD)
        exp_res2 = self.save('create_re_condo_expense',
            condo_id=condo_id,
            service_type='water',
            provider_name='CAASD',
            invoice_number='FAC-99123',
            service_period='Octubre 2026',
            amount='3800',
            notes='Suministro de agua para cisterna'
        )
        self.assertTrue(exp_res2['ok'])

        st = app.state(self.c, 1, 1)
        self.assertEqual(len(st['re_condo_expenses']), 2)
        e1 = next(e for e in st['re_condo_expenses'] if e['id'] == exp_id)
        self.assertEqual(e1['status'], 'pending')
        self.assertEqual(e1['service_type'], 'electricity')

        # 3. Pay electricity bill
        pay_res = self.save('pay_re_condo_expense',
            id=exp_id,
            payment_date=app.today().isoformat(),
            payment_reference='Transferencia Banreservas #9901'
        )
        self.assertTrue(pay_res['ok'])

        st = app.state(self.c, 1, 1)
        e1_paid = next(e for e in st['re_condo_expenses'] if e['id'] == exp_id)
        self.assertEqual(e1_paid['status'], 'paid')
        self.assertEqual(e1_paid['paid_amount'], 1650000)

        # Rollup check on condo
        condo_st = st['re_condos'][0]
        self.assertEqual(condo_st['total_expenses'], 2030000) # (16500 + 3800) * 100
        self.assertEqual(condo_st['total_paid_expenses'], 1650000)
        self.assertEqual(condo_st['total_pending_expenses'], 380000)

    def test_lease_workflow_and_rent_charge(self):
        prop_id = self.save('create_re_property',
            title='Casa Residencial Alameda',
            price_rent='50000',
            listing_type='rent',
            status='available'
        )['id']

        # Create lease
        lease_res = self.save('create_re_lease',
            property_id=prop_id,
            tenant_name='María Inquilina',
            tenant_phone='809-444-5555',
            start_date=app.today().isoformat(),
            end_date=(app.today().replace(year=app.today().year + 1)).isoformat(),
            monthly_rent='50000',
            deposit_amount='100000',
            payment_day=5,
            agent_id=1
        )
        self.assertTrue(lease_res['ok'])
        lease_id = lease_res['id']

        # Property should automatically become rented
        st = app.state(self.c, 1, 1)
        prop = next(p for p in st['re_properties'] if p['id'] == prop_id)
        self.assertEqual(prop['status'], 'rented')

        # Cannot delete property while lease is active
        with self.assertRaises(ValueError):
            self.save('delete_re_property', id=prop_id)

        # Generate rent charge (accounts receivable integration)
        ch_res = self.save('generate_re_lease_charge', lease_id=lease_id)
        self.assertTrue(ch_res['ok'])
        ch_id = ch_res['charge_id']

        # Verify charge in system
        charges = app.charge_list(self.c, 1)
        charge_row = next(ch for ch in charges if ch['id'] == ch_id)
        self.assertEqual(charge_row['customer'], 'María Inquilina')
        self.assertEqual(charge_row['amount'], 5000000)

        # Terminate lease
        term_res = self.save('terminate_re_lease', id=lease_id)
        self.assertTrue(term_res['ok'])

        # Property should now be available again
        st = app.state(self.c, 1, 1)
        prop = next(p for p in st['re_properties'] if p['id'] == prop_id)
        self.assertEqual(prop['status'], 'available')

    def test_sale_and_visit_and_maintenance(self):
        prop_id = self.save('create_re_property',
            title='Local Bella Vista Mall',
            price_sale='10000000',
            listing_type='sale',
            status='available'
        )['id']

        # Visit
        visit_res = self.save('create_re_visit',
            property_id=prop_id,
            client_name='Dr. Roberto Gómez',
            client_phone='809-888-7777',
            visit_date=app.today().isoformat(),
            agent_id=1,
            interest_level='high',
            feedback='Le gustó la ubicación para consultorio médico'
        )
        self.assertTrue(visit_res['ok'])

        # Maintenance
        maint_res = self.save('create_re_maintenance',
            property_id=prop_id,
            title='Pintura interior general',
            cost_estimate='15000',
            reported_date=app.today().isoformat(),
            contractor_technician='Pinturas Express'
        )
        self.assertTrue(maint_res['ok'])
        m_id = maint_res['id']
        self.save('resolve_re_maintenance', id=m_id)

        # Sale
        sale_res = self.save('create_re_sale',
            property_id=prop_id,
            buyer_name='Dr. Roberto Gómez',
            buyer_phone='809-888-7777',
            sale_price='9800000',
            commission_rate=5.0,
            closing_date=app.today().isoformat(),
            status='closed',
            agent_id=1
        )
        self.assertTrue(sale_res['ok'])

        # Property is now sold
        st = app.state(self.c, 1, 1)
        prop = next(p for p in st['re_properties'] if p['id'] == prop_id)
        self.assertEqual(prop['status'], 'sold')
        self.assertEqual(len(st['re_sales']), 1)
        self.assertEqual(st['re_sales'][0]['commission_amount'], 49000000)

    def test_demo_real_estate_seeding(self):
        res = self.save('seed_demo_real_estate')
        self.assertTrue(res['ok'])

        st = app.state(self.c, 1, 1)
        self.assertGreaterEqual(len(st['re_condos']), 1)
        self.assertGreaterEqual(len(st['re_properties']), 7) # 3 condo units + 4 independent (commercial, land, lot, villa)
        self.assertGreaterEqual(len(st['re_condo_charges']), 3)
        self.assertGreaterEqual(len(st['re_condo_expenses']), 5) # Electricity, water, elevator, security, fuel
        self.assertGreaterEqual(len(st['re_leases']), 1)
        self.assertGreaterEqual(len(st['re_sales']), 1)
        self.assertGreaterEqual(len(st['re_buyers']), 3) # Demo buyers
        self.assertGreaterEqual(len(st['re_sale_installments']), 24) # 24 installments
        self.assertGreaterEqual(len(st['re_sale_payments']), 3) # Initial + 2 installments
        self.assertGreaterEqual(len(st['re_visits']), 1)
        self.assertGreaterEqual(len(st['re_maintenances']), 1)
        self.assertEqual(st['company_profile']['business_vertical'], 'real_estate')
        self.assertEqual(st['company_profile']['unit_singular'], 'Propiedad')
        self.assertEqual(st['company_profile']['unit_plural'], 'Propiedades')

        # Test force re-seeding works idempotently
        res2 = self.save('seed_demo_real_estate', force=True)
        self.assertTrue(res2['ok'])
        st2 = app.state(self.c, 1, 1)
        self.assertEqual(len(st2['re_condos']), 1)
        self.assertEqual(len(st2['re_properties']), 7)
        self.assertGreaterEqual(len(st2['re_buyers']), 3)
        self.assertGreaterEqual(len(st2['re_sale_installments']), 24)

    def test_buyer_crud(self):
        res = self.save('create_re_buyer',
            name='Ing. Roberto Gómez',
            document_id='001-2233445-6',
            phone='809-555-4321',
            email='roberto.gomez@test.do',
            address='Calle Sarasota #10',
            city='Santo Domingo',
            buyer_type='individual',
            budget=15000000,
            preferred_property_type='apartment',
            status='prospect'
        )
        self.assertTrue(res['ok'])
        b_id = res['id']

        st = app.state(self.c, 1, 1)
        b = next(x for x in st['re_buyers'] if x['id'] == b_id)
        self.assertEqual(b['name'], 'Ing. Roberto Gómez')
        self.assertEqual(b['document_id'], '001-2233445-6')
        self.assertEqual(b['status'], 'prospect')

        # Edit buyer
        edit_res = self.save('edit_re_buyer',
            id=b_id,
            name='Ing. Roberto Gómez Santana',
            status='active'
        )
        self.assertTrue(edit_res['ok'])
        st = app.state(self.c, 1, 1)
        b = next(x for x in st['re_buyers'] if x['id'] == b_id)
        self.assertEqual(b['name'], 'Ing. Roberto Gómez Santana')
        self.assertEqual(b['status'], 'active')

        # Delete buyer
        del_res = self.save('delete_re_buyer', id=b_id)
        self.assertTrue(del_res['ok'])
        st = app.state(self.c, 1, 1)
        self.assertFalse(any(x['id'] == b_id for x in st['re_buyers']))

    def test_sales_financing_installments_and_payments(self):
        # 1. Create property
        prop_res = self.save('create_re_property',
            title='Apartamento 10B Torre Horizonte',
            code='PROP-HZ10',
            property_type='apartment',
            listing_type='sale',
            status='available',
            price_sale='10000000' # 10,000,000 DOP
        )
        prop_id = prop_res['id']

        # 2. Create buyer
        buyer_res = self.save('create_re_buyer',
            name='Dra. Elena Santos',
            document_id='001-9988776-5',
            phone='809-777-6655',
            status='prospect'
        )
        buyer_id = buyer_res['id']

        # 3. Create sale with financing: 20% down payment (2,000,000 DOP), 8,000,000 financed in 12 installments at 12% annual
        sale_res = self.save('create_re_sale',
            property_id=prop_id,
            buyer_id=buyer_id,
            sale_price='10000000',
            down_payment='2000000',
            financed_amount='8000000',
            installments_count=12,
            interest_rate_annual=12.0,
            late_fee_rate_monthly=2.0,
            grace_days=5,
            installment_day=15,
            closing_date=app.today().isoformat()
        )
        self.assertTrue(sale_res['ok'])
        sale_id = sale_res['id']

        st = app.state(self.c, 1, 1)
        prop = next(p for p in st['re_properties'] if p['id'] == prop_id)
        self.assertEqual(prop['status'], 'reserved')

        sale = next(s for s in st['re_sales'] if s['id'] == sale_id)
        self.assertEqual(sale['status'], 'in_progress')
        self.assertEqual(sale['down_payment'], 200000000)
        self.assertEqual(sale['financed_amount'], 800000000)
        self.assertEqual(sale['remaining_capital'], 800000000)
        self.assertEqual(sale['total_capital_paid'], 200000000)
        self.assertEqual(sale['installments_total'], 12)

        # Down payment payment receipt should be automatically created
        dp_payment = next(p for p in st['re_sale_payments'] if p['sale_id'] == sale_id and p['receipt_number'].endswith('-001'))
        self.assertEqual(dp_payment['amount'], 200000000)
        self.assertEqual(dp_payment['capital_paid'], 200000000)

        # 12 installments generated
        sale_insts = [i for i in st['re_sale_installments'] if i['sale_id'] == sale_id]
        self.assertEqual(len(sale_insts), 12)

        # 4. Pay installment 1
        inst1 = sale_insts[0]
        pay1_res = self.save('record_re_sale_payment',
            sale_id=sale_id,
            installment_id=inst1['id'],
            amount=inst1['total_due'] / 100.0,
            payment_method='transfer',
            reference='TRF-00123'
        )
        self.assertTrue(pay1_res['ok'])
        self.assertTrue('REC-VTA-' in pay1_res['receipt_number'])

        st = app.state(self.c, 1, 1)
        inst1_updated = next(i for i in st['re_sale_installments'] if i['id'] == inst1['id'])
        self.assertEqual(inst1_updated['status'], 'paid')

        sale_updated = next(s for s in st['re_sales'] if s['id'] == sale_id)
        self.assertEqual(sale_updated['installments_paid'], 1)
        self.assertLess(sale_updated['remaining_capital'], 800000000)

        # 5. Make extraordinary capital abono of the rest to close the sale
        rem_cap = sale_updated['remaining_capital'] / 100.0
        pay2_res = self.save('record_re_sale_payment',
            sale_id=sale_id,
            amount=rem_cap,
            capital_amount=rem_cap,
            payment_method='check',
            reference='CHK-88990'
        )
        self.assertTrue(pay2_res['ok'])

        # Property should now be sold and sale status closed
        st = app.state(self.c, 1, 1)
        sale_final = next(s for s in st['re_sales'] if s['id'] == sale_id)
        self.assertEqual(sale_final['status'], 'closed')
        self.assertEqual(sale_final['remaining_capital'], 0)
        self.assertTrue(sale_final['is_paid_in_full'])

        prop_final = next(p for p in st['re_properties'] if p['id'] == prop_id)
        self.assertEqual(prop_final['status'], 'sold')

    def test_edit_re_visit_and_maintenance(self):
        prop_res = self.save('create_re_property',
            title='Apartamento Evaristo Morales',
            address='Calle Paseo de los Locutores #45',
            city='Santo Domingo',
            property_type='apartment',
            listing_type='both',
            price_sale='9500000',
            price_rent='55000',
            status='available'
        )
        prop_id = prop_res['id']

        # 1. Create and edit visit
        v_res = self.save('create_re_visit',
            property_id=prop_id,
            client_name='Carlos Santana',
            client_phone='809-555-8888',
            visit_date=app.today().isoformat(),
            interest_level='medium',
            status='scheduled'
        )
        self.assertTrue(v_res['ok'])
        visit_id = v_res['id']

        # Edit visit
        edit_v_res = self.save('edit_re_visit',
            id=visit_id,
            property_id=prop_id,
            client_name='Carlos Santana',
            client_phone='809-555-8888',
            visit_date=app.today().isoformat(),
            interest_level='high',
            feedback='Cliente encantado con la vista y distribución. Quiere presentar oferta.',
            status='completed'
        )
        self.assertTrue(edit_v_res['ok'])

        st = app.state(self.c, 1, 1)
        visit_obj = next(v for v in st['re_visits'] if v['id'] == visit_id)
        self.assertEqual(visit_obj['interest_level'], 'high')
        self.assertEqual(visit_obj['status'], 'completed')
        self.assertIn('presentar oferta', visit_obj['feedback'])

        # 2. Create and edit maintenance
        m_res = self.save('create_re_maintenance',
            property_id=prop_id,
            title='Fuga de agua en lavamanos secundario',
            cost_estimate='2500',
            reported_date=app.today().isoformat(),
            contractor_technician='Plomería González',
            status='pending'
        )
        self.assertTrue(m_res['ok'])
        m_id = m_res['id']

        # Edit maintenance
        edit_m_res = self.save('edit_re_maintenance',
            id=m_id,
            property_id=prop_id,
            title='Fuga en lavamanos y cambio de tubería de desagüe',
            cost_estimate='3800',
            reported_date=app.today().isoformat(),
            contractor_technician='Plomería González & Hnos',
            status='in_progress',
            notes='Repuesto comprado en ferretería Americana'
        )
        self.assertTrue(edit_m_res['ok'])

        st = app.state(self.c, 1, 1)
        m_obj = next(m for m in st['re_maintenances'] if m['id'] == m_id)
        self.assertEqual(m_obj['cost_estimate'], 380000)
        self.assertEqual(m_obj['status'], 'in_progress')
        self.assertEqual(m_obj['contractor_technician'], 'Plomería González & Hnos')

if __name__ == '__main__':
    unittest.main()

